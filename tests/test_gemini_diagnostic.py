import contextlib
import io
import json
import os
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
        with (
            patch.object(
                gemini_diagnostic,
                "_request",
                return_value=(None, {}),
            ) as request,
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            exit_code = gemini_diagnostic.run_diagnostic("test-key")

        result = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(request.call_count, 1)
        self.assertIsNone(result["models_list_http_status"])
        self.assertEqual(result["models_list_supported"], [])
        self.assertEqual(result["generate_content_probes"], [])
        self.assertIsNone(result["selected_model"])

    def test_diagnostic_probes_every_discovered_model_and_selects_first_healthy(self):
        listing = {
            "models": [
                {"name": "models/gemini-unhealthy", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-healthy-first", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-healthy-second", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-embedding", "supportedGenerationMethods": ["embedContent"]},
            ]
        }
        valid_response = {
            "candidates": [{"content": {"parts": [{"text": "pong"}]}}],
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
            ["gemini-unhealthy", "gemini-healthy-first", "gemini-healthy-second"],
        )
        self.assertEqual(result["selected_model"], "gemini-healthy-first")
        self.assertEqual(persisted["selected_model"], "gemini-healthy-first")
        self.assertEqual(
            [item["http_status"] for item in result["generate_content_probes"]],
            [503, 200, 200],
        )
        self.assertTrue(all(call.args[0].startswith(gemini_diagnostic.API_ROOT + "/models/") for call in request.call_args_list[1:]))


if __name__ == "__main__":
    unittest.main()
