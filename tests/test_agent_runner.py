import json
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import agent_runner


class AgentRunnerTests(unittest.TestCase):
    def test_extract_code_strips_python_fence(self):
        fence = chr(96) * 3
        self.assertEqual(
            agent_runner.extract_code(f"  {fence}python\nprint('ok')\n{fence}  "),
            "print('ok')",
        )

    def test_extract_code_strips_json_wrapped_fence(self):
        fence = chr(96) * 3
        payload = json.dumps({"code": f"{fence}py\nprint(1 + 1)\n{fence}"})
        self.assertEqual(agent_runner.extract_code(payload), "print(1 + 1)")

    def test_extract_code_preserves_unfenced_source(self):
        self.assertEqual(agent_runner.extract_code("print('plain')"), "print('plain')")

    def test_repair_prompt_uses_real_newlines(self):
        prompt = agent_runner.build_prompt(
            "search for a result", "https://example.com", "print('old')", "timeout"
        )
        self.assertIn("\nPREVIOUS SCRIPT:\n", prompt)
        self.assertNotIn("\\nPREVIOUS SCRIPT:\\n", prompt)

    def test_gemini_uses_current_default_model_for_new_api_keys(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            kind, model, key = agent_runner.provider_config("gemini")
        self.assertEqual(kind, "gemini")
        self.assertEqual(model, "gemini-3.8-flash")
        self.assertEqual(key, "test-key")

    def test_sandbox_command_does_not_forward_provider_secrets(self):
        with patch.dict(os.environ, {
            "GEMINI_API_KEY": "gemini-secret-test",
            "GROQ_API_KEY": "groq-secret-test",
            "OPENROUTER_API_KEY": "openrouter-secret-test",
        }):
            command = agent_runner.build_sandbox_command("/tmp/agent-work")
        self.assertEqual(command[:2], ["docker", "run"])
        self.assertIn("--cap-drop=ALL", command)
        self.assertIn("--security-opt=no-new-privileges", command)
        self.assertIn("--read-only", command)
        self.assertIn("--network=bridge", command)
        self.assertNotIn("gemini-secret-test", command)
        self.assertNotIn("groq-secret-test", command)
        self.assertNotIn("openrouter-secret-test", command)

    def test_execute_script_runs_in_container_and_copies_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(agent_runner, "ROOT", root),
                patch.object(agent_runner, "OUTPUT", root / "output.json"),
                patch.object(agent_runner, "ARTIFACTS", root / "artifacts"),
                patch.dict(os.environ, {"GEMINI_API_KEY": "never-forward-this"}),
                patch.object(agent_runner.os, "getuid", return_value=1001, create=True),
                patch.object(agent_runner.os, "getgid", return_value=1002, create=True),
            ):
                sandbox_paths = []
                def fake_run(command, **kwargs):
                    mount = next(item for item in command if item.startswith("type=bind,src="))
                    sandbox_path = Path(mount.split("src=", 1)[1].split(",dst=", 1)[0])
                    sandbox_paths.append(sandbox_path)
                    (sandbox_path / "output.json").write_text('{"success": true}', encoding="utf-8")
                    return subprocess.CompletedProcess(command, 0, "sandbox ok", "")

                with patch.object(agent_runner.subprocess, "run", side_effect=fake_run) as run:
                    success, logs = agent_runner.execute_script("print('safe')", 30)

                self.assertTrue(success)
                self.assertIn("sandbox ok", logs)
                self.assertTrue((root / "generated_task.py").exists())
                self.assertEqual(json.loads((root / "output.json").read_text()), {"success": True})
                command = run.call_args.args[0]
                self.assertIn("--read-only", command)
                self.assertIn("--user", command)
                self.assertEqual(command[command.index("--user") + 1], "1001:1002")
                self.assertNotIn("never-forward-this", command)


    def test_gemini_retry_schedule_uses_exponential_backoff_with_jitter(self):
        with patch.object(agent_runner.random, "uniform", return_value=1.0):
            delays = [
                agent_runner._retry_delay({}, attempt)
                for attempt in range(3)
            ]
        self.assertEqual(delays, [2.0, 5.0, 12.0])

    def test_gemini_model_chain_uses_ordered_fallbacks_without_duplicates(self):
        with patch.dict(os.environ, {
            "GEMINI_API_KEY": "test-key",
            "GEMINI_MODEL": "gemini-primary",
            "GEMINI_MODEL_FALLBACKS": "gemini-fallback-a, gemini-fallback-b,gemini-primary",
        }, clear=True):
            self.assertEqual(
                agent_runner._gemini_model_chain("gemini-primary"),
                ["gemini-primary", "gemini-fallback-a", "gemini-fallback-b"],
            )

    def test_gemini_falls_back_to_next_diagnostic_healthy_model_after_empty_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            selection = {
                "selected_model": "gemma-healthy",
                "discovered_models": ["gemma-healthy", "gemini-flash-lite"],
                "probes": [
                    {"model": "gemma-healthy", "http_status": 200, "generated_text": True},
                    {"model": "gemini-flash-lite", "http_status": 200, "generated_text": True},
                ],
            }
            (Path(temporary) / "gemini_model_selection.json").write_text(
                json.dumps(selection), encoding="utf-8"
            )
            empty = io.BytesIO(json.dumps({
                "candidates": [{"content": {"parts": []}}],
            }).encode("utf-8"))
            generated = io.BytesIO(json.dumps({
                "candidates": [{
                    "content": {"parts": [{"text": "print('fallback model worked')"}]}
                }],
            }).encode("utf-8"))

            with (
                patch.object(agent_runner, "ROOT", Path(temporary)),
                patch.dict(os.environ, {
                    "GEMINI_API_KEY": "test-key",
                    "GEMINI_MODEL": "gemini-static-primary",
                    "GEMINI_MODEL_FALLBACKS": "gemini-static-fallback",
                }, clear=True),
                patch.object(agent_runner, "urlopen", side_effect=[empty, generated]) as request,
            ):
                result = agent_runner.ask_model("gemini", "Generate a harmless test script")

        self.assertEqual(result, "print('fallback model worked')")
        self.assertEqual(request.call_count, 2)
        self.assertIn("gemma-healthy:generateContent", request.call_args_list[0].args[0].full_url)
        self.assertIn("gemini-flash-lite:generateContent", request.call_args_list[1].args[0].full_url)

    def test_gemini_falls_back_after_all_primary_503_retries(self):
        import io
        import urllib.error

        unavailable = urllib.error.HTTPError(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-primary:generateContent",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(b""),
        )
        generated = io.BytesIO(json.dumps({
            "candidates": [{
                "content": {"parts": [{"text": "print('fallback model worked')"}]}
            }]
        }).encode("utf-8"))

        with (
            patch.dict(os.environ, {
                "GEMINI_API_KEY": "test-key",
                "GEMINI_MODEL": "gemini-primary",
                "GEMINI_MODEL_FALLBACKS": "gemini-fallback",
            }, clear=True),
            patch.object(agent_runner, "urlopen", side_effect=[unavailable] * 4 + [generated]) as request,
            patch.object(agent_runner.time, "sleep") as sleep,
            patch.object(agent_runner.random, "uniform", return_value=1.0),
        ):
            result = agent_runner.ask_model("gemini", "Generate a harmless test script")

        self.assertEqual(result, "print('fallback model worked')")
        self.assertEqual(request.call_count, 5)
        requested_models = [call.args[0].full_url for call in request.call_args_list]
        self.assertTrue(all("gemini-primary:generateContent" in url for url in requested_models[:4]))
        self.assertIn("gemini-fallback:generateContent", requested_models[4])
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2.0, 5.0, 12.0])


if __name__ == "__main__":
    unittest.main()
