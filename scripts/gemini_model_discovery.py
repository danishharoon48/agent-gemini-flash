"""Pure helpers for discovering Gemini models that can generate text."""


def discover_generation_models(listing):
    """Return unique model IDs advertising generateContent, preserving API order."""
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
        if model_id and model_id not in seen:
            seen.add(model_id)
            discovered.append(model_id)
    return discovered


def has_generated_text(response):
    """True only when a Gemini response contains at least one nonempty text part."""
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
            if isinstance(part, dict) and isinstance(part.get("text"), str) and part["text"].strip():
                return True
    return False
