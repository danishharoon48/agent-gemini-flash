#!/usr/bin/env python3
"""Safe, minimal Gemini API availability diagnostic for GitHub Actions."""
import json
import os
import socket
import sys
import urllib.error
import urllib.request

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT_SECONDS = 10
MODELS_TO_PROBE = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.8-flash",
)


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
    available = []
    for item in listing.get("models", []) if isinstance(listing, dict) else []:
        name = str(item.get("name", "")).removeprefix("models/")
        methods = item.get("supportedGenerationMethods", [])
        if name in MODELS_TO_PROBE and "generateContent" in methods:
            available.append(name)

    probes = []
    for model in MODELS_TO_PROBE:
        status, response = _request(
            API_ROOT + "/models/" + model + ":generateContent",
            api_key,
            {
                "contents": [{"role": "user", "parts": [{"text": "Reply with exactly OK."}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 8},
            },
        )
        candidates = response.get("candidates", []) if isinstance(response, dict) else []
        text_generated = any(
            isinstance(part.get("text"), str) and part["text"].strip()
            for candidate in candidates
            for part in candidate.get("content", {}).get("parts", [])
        )
        probes.append({
            "model": model,
            "http_status": status,
            "generated_text": bool(text_generated),
        })

    result = {
        "models_list_http_status": list_status,
        "models_list_supported": available,
        "generate_content_probes": probes,
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        print(json.dumps({"error": "GEMINI_API_KEY is not configured"}))
        sys.exit(2)
    sys.exit(run_diagnostic(key))
