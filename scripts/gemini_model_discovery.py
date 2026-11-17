"""Pure helpers for discovering Gemini models that can generate text."""
import json


def is_gemini_flash_model(model_id):
    """Accept Gemini model IDs explicitly marked as Flash."""
    if not isinstance(model_id, str):
        return False
    normalized = model_id.strip().lower()
    return normalized.startswith("gemini-") and "flash" in normalized


def discover_generation_models(listing):
    """Return unique Gemini Flash model IDs advertising generateContent."""
    if not isinstance(listing, dict):
        return []
    models = listing.get("models", [])
    if not isinstance(models, list):
        return []

    discovered = []
    seen = set()
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        methods = item.get("supportedGenerationMethods", [])
        if not isinstance(name, str) or not isinstance(methods, list):
            continue
        if "generateContent" not in methods:
            continue
        model_id = name.removeprefix("models/").strip()
        if is_gemini_flash_model(model_id) and model_id not in seen:
            seen.add(model_id)
            discovered.append(model_id)
    return discovered


def has_valid_ping_response(response):
    """Require a candidate text part containing the expected structured JSON."""
    if not isinstance(response, dict):
        return False
    candidates = response.get("candidates", [])
    if not isinstance(candidates, list):
        return False
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content", {})
        if not isinstance(content, dict):
            continue
        parts = content.get("parts", [])
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict) or not isinstance(part.get("text"), str):
                continue
            try:
                parsed = json.loads(part["text"].strip())
            except (TypeError, ValueError):
                continue
            if (
                isinstance(parsed, dict)
                and parsed.get("status") == "ok"
                and isinstance(parsed.get("message"), str)
                and bool(parsed["message"].strip())
            ):
                return True
    return False
