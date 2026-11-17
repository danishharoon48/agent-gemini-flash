import contextlib
import io
import json
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

    def test_diagnostic_reports_all_model_probes_even_if_models_list_times_out(self):
        response = {
            "candidates": [{"content": {"parts": [{"text": "OK"}]}}],
        }
        with (
            patch.object(
                gemini_diagnostic,
                "_request",
                side_effect=[(None, {}), (503, {}), (404, {}), (200, response)],
            ) as request,
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            exit_code = gemini_diagnostic.run_diagnostic("test-key")

        result = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(request.call_count, 4)
        self.assertIsNone(result["models_list_http_status"])
        self.assertEqual(
            [item["http_status"] for item in result["generate_content_probes"]],
            [503, 404, 200],
        )
        self.assertTrue(result["generate_content_probes"][2]["generated_text"])


if __name__ == "__main__":
    unittest.main()
