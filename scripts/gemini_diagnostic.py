#!/usr/bin/env python3
"""Safe, minimal Gemini API availability diagnostic for GitHub Actions."""
import json
import os
import socket
import sys
import urllib.error
import urllib.request

try:
    from scripts.gemini_model_discovery import discover_generation_models, has_valid_ping_response
except ModuleNotFoundError:
    # Direct execution sets sys.path[0] to scripts/, not the repository root.
    from gemini_model_discovery import discover_generation_models, has_valid_ping_response

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT_SECONDS = 10

def _request(url, api_key, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read()
            try:
                parsed = json.loads(body.decode("utf-8")) if body else {}
            except (UnicodeDecodeError, ValueError):
                parsed = {}
            return response.status, parsed
    except urllib.error.HTTPError as error:
        return error.code, {}
    except (TimeoutError, socket.timeout, urllib.error.URLError):
        return None, {}


def run_diagnostic(api_key):
    list_status, listing = _request(API_ROOT + "/models", api_key)
    discovered = discover_generation_models(listing)

    probes = []
    selected_model = None
    for model in discovered:
        status, response = _request(
            API_ROOT + "/models/" + model + ":generateContent",
            api_key,
            {
                "contents": [{"role": "user", "parts": [{"text": 'Return exactly this JSON object and no other text: {"status":"ok","message":"pong"}'}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 64, "responseMimeType": "application/json"},
            },
        )
        generated_text = has_valid_ping_response(response)
        probe = {
            "model": model,
            "http_status": status,
            "valid_structured_response": generated_text,
        }
        probes.append(probe)
        if selected_model is None and status == 200 and generated_text:
            selected_model = model

    result = {
        "models_list_http_status": list_status,
        "models_list_supported": discovered,
        "generate_content_probes": probes,
        "selected_model": selected_model,
    }
    selection = {
        "selected_model": selected_model,
        "discovered_models": discovered,
        "probes": probes,
    }
    selection_path = os.getenv("GEMINI_MODEL_SELECTION_PATH", "gemini_model_selection.json")
    with open(selection_path, "w", encoding="utf-8") as output:
        json.dump(selection, output, sort_keys=True)
    print(json.dumps(result, sort_keys=True))
    return 0 if selected_model else 1


if __name__ == "__main__":
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        print(json.dumps({"error": "GEMINI_API_KEY is not configured"}))
        sys.exit(2)
    sys.exit(run_diagnostic(key))
