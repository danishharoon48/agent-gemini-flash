import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.gemini_model_discovery import discover_generation_models, has_valid_ping_response
import agent_runner


class GeminiModelDiscoveryTests(unittest.TestCase):
    def test_discovery_keeps_every_unique_generate_content_model(self):
        listing = {
            "models": [
                {"name": "models/gemini-flash-a", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-embed", "supportedGenerationMethods": ["embedContent"]},
                {"name": "models/gemini-flash-b", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-flash-a", "supportedGenerationMethods": ["generateContent"]},
            ]
        }
        self.assertEqual(
            discover_generation_models(listing),
            ["gemini-flash-a", "gemini-flash-b"],
        )

    def test_discovery_only_returns_gemini_flash_models(self):
        listing = {
            "models": [
                {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-flash-lite-latest", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemma-4-26b-a4b-it", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/text-embedding-flash", "supportedGenerationMethods": ["generateContent"]},
            ]
        }
        self.assertEqual(
            discover_generation_models(listing),
            ["gemini-2.5-flash", "gemini-flash-lite-latest"],
        )

    def test_ping_requires_structured_json_status_and_nonempty_message(self):
        valid = {"candidates": [{"content": {"parts": [{
            "text": '{"status":"ok","message":"pong"}'
        }]}}]}
        self.assertTrue(has_valid_ping_response(valid))
        self.assertFalse(has_valid_ping_response({
            "candidates": [{"content": {"parts": [{"text": "pong"}]}}],
        }))
        self.assertFalse(has_valid_ping_response({
            "candidates": [{"content": {"parts": [{
                "text": '{"status":"ok","message":"  "}'
            }]}}],
        }))
        self.assertFalse(has_valid_ping_response({
            "candidates": [{"content": {"parts": [{"text": '{"status":"error","message":"pong"}'}]}}],
        }))
        self.assertFalse(has_valid_ping_response({"candidates": []}))

    def test_discovery_ignores_malformed_model_entries(self):
        listing = {"models": [None, {}, {"name": 42, "supportedGenerationMethods": ["generateContent"]}]}
        self.assertEqual(discover_generation_models(listing), [])

    def test_runner_promotes_all_healthy_diagnostic_models_in_order(self):
        selection = {
            "selected_model": "gemini-healthy-flash",
            "discovered_models": [
                "gemini-healthy-flash",
                "gemini-flash-lite",
                "gemini-3.1-flash-lite",
                "gemma-4-26b-a4b-it",
                "gemini-unhealthy",
            ],
            "probes": [
                {"model": "gemini-healthy-flash", "http_status": 200, "valid_structured_response": True},
                {"model": "gemini-flash-lite", "http_status": 200, "valid_structured_response": True},
                {"model": "gemini-3.1-flash-lite", "http_status": 200, "valid_structured_response": True},
                {"model": "gemma-4-26b-a4b-it", "http_status": 200, "valid_structured_response": True},
                {"model": "gemini-unhealthy", "http_status": 404, "valid_structured_response": False},
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            selection_file = Path(temporary) / "gemini_model_selection.json"
            selection_file.write_text(json.dumps(selection), encoding="utf-8")
            with (
                patch.object(agent_runner, "ROOT", Path(temporary)),
                patch.dict("os.environ", {
                    "GEMINI_MODEL": "gemini-static-primary-flash",
                    "GEMINI_MODEL_FALLBACKS": "gemini-static-fallback-flash",
                }, clear=True),
            ):
                self.assertEqual(
                    agent_runner._gemini_model_chain("gemini-static-primary-flash"),
                    [
                        "gemini-healthy-flash",
                        "gemini-flash-lite",
                        "gemini-3.1-flash-lite",
                        "gemini-static-primary-flash",
                        "gemini-static-fallback-flash",
                    ],
                )

    def test_runner_ignores_invalid_diagnostic_model_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            selection_file = Path(temporary) / "gemini_model_selection.json"
            selection_file.write_text(json.dumps({"selected_model": "../unsafe"}), encoding="utf-8")
            with (
                patch.object(agent_runner, "ROOT", Path(temporary)),
                patch.dict("os.environ", {"GEMINI_MODEL_FALLBACKS": "gemini-safe-flash"}, clear=True),
            ):
                self.assertEqual(
                    agent_runner._gemini_model_chain("gemini-primary-flash"),
                    ["gemini-primary-flash", "gemini-safe-flash"],
                )


if __name__ == "__main__":
    unittest.main()
