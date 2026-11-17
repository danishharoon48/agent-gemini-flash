import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.gemini_model_discovery import discover_generation_models, has_generated_text
import agent_runner


class GeminiModelDiscoveryTests(unittest.TestCase):
    def test_discovery_keeps_every_unique_generate_content_model(self):
        listing = {
            "models": [
                {"name": "models/gemini-fast-a", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-embed", "supportedGenerationMethods": ["embedContent"]},
                {"name": "models/gemini-fast-b", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-fast-a", "supportedGenerationMethods": ["generateContent"]},
            ]
        }
        self.assertEqual(
            discover_generation_models(listing),
            ["gemini-fast-a", "gemini-fast-b"],
        )

    def test_discovery_ignores_malformed_model_entries(self):
        listing = {"models": [None, {}, {"name": 42, "supportedGenerationMethods": ["generateContent"]}]}
        self.assertEqual(discover_generation_models(listing), [])

    def test_ping_requires_nonempty_candidate_text(self):
        self.assertTrue(has_generated_text({
            "candidates": [{"content": {"parts": [{"text": " OK "}]}}],
        }))
        self.assertFalse(has_generated_text({
            "candidates": [{"content": {"parts": [{"text": "  "}]}}],
        }))
        self.assertFalse(has_generated_text({"candidates": []}))

    def test_runner_promotes_all_healthy_diagnostic_models_in_order(self):
        selection = {
            "selected_model": "gemma-healthy",
            "discovered_models": [
                "gemma-healthy",
                "gemini-flash-lite",
                "gemini-3.1-flash-lite",
                "gemini-unhealthy",
            ],
            "probes": [
                {"model": "gemma-healthy", "http_status": 200, "generated_text": True},
                {"model": "gemini-flash-lite", "http_status": 200, "generated_text": True},
                {"model": "gemini-3.1-flash-lite", "http_status": 200, "generated_text": True},
                {"model": "gemini-unhealthy", "http_status": 404, "generated_text": False},
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            selection_file = Path(temporary) / "gemini_model_selection.json"
            selection_file.write_text(json.dumps(selection), encoding="utf-8")
            with (
                patch.object(agent_runner, "ROOT", Path(temporary)),
                patch.dict("os.environ", {
                    "GEMINI_MODEL": "gemini-static-primary",
                    "GEMINI_MODEL_FALLBACKS": "gemini-static-fallback",
                }, clear=True),
            ):
                self.assertEqual(
                    agent_runner._gemini_model_chain("gemini-static-primary"),
                    [
                        "gemma-healthy",
                        "gemini-flash-lite",
                        "gemini-3.1-flash-lite",
                        "gemini-static-primary",
                        "gemini-static-fallback",
                    ],
                )

    def test_runner_ignores_invalid_diagnostic_model_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            selection_file = Path(temporary) / "gemini_model_selection.json"
            selection_file.write_text(json.dumps({"selected_model": "../unsafe"}), encoding="utf-8")
            with (
                patch.object(agent_runner, "ROOT", Path(temporary)),
                patch.dict("os.environ", {"GEMINI_MODEL_FALLBACKS": "gemini-safe"}, clear=True),
            ):
                self.assertEqual(
                    agent_runner._gemini_model_chain("gemini-primary"),
                    ["gemini-primary", "gemini-safe"],
                )


if __name__ == "__main__":
    unittest.main()
