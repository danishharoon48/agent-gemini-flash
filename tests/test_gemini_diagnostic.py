import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import gemini_diagnostic


class GeminiDiagnosticTests(unittest.TestCase):
    def test_request_converts_socket_timeout_to_unavailable_status(self):
        with patch(
            "scripts.gemini_diagnostic.urllib.request.urlopen",
            side_effect=TimeoutError("upstream timed out"),
        ):
            status, body = gemini_diagnostic._request(
                "https://generativelanguage.googleapis.com/v1beta/models",
                "test-key",
            )
        self.assertIsNone(status)
        self.assertEqual(body, {})

    def test_request_preserves_http_error_status_without_body(self):
        import urllib.error

        error = urllib.error.HTTPError(
            "https://generativelanguage.googleapis.com/v1beta/models",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(b""),
        )
        with patch(
            "scripts.gemini_diagnostic.urllib.request.urlopen",
            side_effect=error,
        ):
            status, body = gemini_diagnostic._request(
                "https://generativelanguage.googleapis.com/v1beta/models",
                "test-key",
            )
        self.assertEqual(status, 503)
        self.assertEqual(body, {})

    def test_diagnostic_handles_models_list_timeout_without_static_model_probes(self):
        with tempfile.TemporaryDirectory() as temporary:
            selection_path = Path(temporary) / "selection.json"
            with (
                patch.dict(os.environ, {"GEMINI_MODEL_SELECTION_PATH": str(selection_path)}),
                patch.object(
                    gemini_diagnostic,
                    "_request",
                    return_value=(None, {}),
                ) as request,
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                exit_code = gemini_diagnostic.run_diagnostic("test-key")
            persisted = json.loads(selection_path.read_text(encoding="utf-8"))

        result = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(request.call_count, 1)
        self.assertIsNone(result["models_list_http_status"])
        self.assertEqual(result["models_list_supported"], [])
        self.assertEqual(result["generate_content_probes"], [])
        self.assertIsNone(result["selected_model"])
        self.assertIsNone(persisted["selected_model"])

    def test_script_entrypoint_imports_discovery_module_when_run_directly(self):
        environment = os.environ.copy()
        environment.pop("GEMINI_API_KEY", None)
        environment.pop("GOOGLE_API_KEY", None)
        completed = subprocess.run(
            [sys.executable, "scripts/gemini_diagnostic.py"],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("GEMINI_API_KEY is not configured", completed.stdout)
        self.assertNotIn("ModuleNotFoundError", completed.stderr)

    def test_diagnostic_probes_every_discovered_model_and_selects_first_healthy(self):
        listing = {
            "models": [
                {"name": "models/gemini-unhealthy-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-healthy-first-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-healthy-second-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-embedding", "supportedGenerationMethods": ["embedContent"]},
                {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemma-4-26b-a4b-it", "supportedGenerationMethods": ["generateContent"]},
            ]
        }
        valid_response = {
            "candidates": [{"content": {"parts": [{
                "text": '{"status":"ok","message":"pong"}'
            }]}}],
        }
        with tempfile.TemporaryDirectory() as temporary:
            selection_path = Path(temporary) / "selection.json"
            with (
                patch.dict(os.environ, {"GEMINI_MODEL_SELECTION_PATH": str(selection_path)}),
                patch.object(
                    gemini_diagnostic,
                    "_request",
                    side_effect=[
                        (200, listing),
                        (503, {}),
                        (200, valid_response),
                        (200, valid_response),
                    ],
                ) as request,
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                exit_code = gemini_diagnostic.run_diagnostic("test-key")
            persisted = json.loads(selection_path.read_text(encoding="utf-8"))

        result = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(request.call_count, 4)
        self.assertEqual(
            result["models_list_supported"],
            ["gemini-unhealthy-flash", "gemini-healthy-first-flash", "gemini-healthy-second-flash"],
        )
        self.assertEqual(result["selected_model"], "gemini-healthy-first-flash")
        self.assertEqual(persisted["selected_model"], "gemini-healthy-first-flash")
        self.assertEqual(
            [item["http_status"] for item in result["generate_content_probes"]],
            [503, 200, 200],
        )
        self.assertTrue(all(call.args[0].startswith(gemini_diagnostic.API_ROOT + "/models/") for call in request.call_args_list[1:]))


if __name__ == "__main__":
    unittest.main()
