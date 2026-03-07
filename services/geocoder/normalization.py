from __future__ import annotations

import re


LEADING_PHRASES = (
    "near ",
    "in ",
    "at ",
    "outside ",
    "inside ",
    "around ",
    "within ",
    "a village near ",
    "rural ",
)

DIRECTIONAL_WORDS = {
    "western",
    "eastern",
    "northern",
    "southern",
    "central",
}


def normalize_location_name(value: str, precision: str) -> str:
    text = _normalize_whitespace(value).strip(" ,.")
    text = _strip_leading_phrases(text)

    if precision == "country":
        text = _remove_directional_prefix(text)
    elif precision == "city":
        text = _strip_city_context(text)
    elif precision == "admin_region":
        text = _remove_directional_prefix(text)

    return text.strip(" ,.")


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _strip_leading_phrases(value: str) -> str:
    lowered = value.lower()
    for phrase in LEADING_PHRASES:
        if lowered.startswith(phrase):
            return value[len(phrase) :]
    return value


def _remove_directional_prefix(value: str) -> str:
    tokens = value.split()
    if tokens and tokens[0].lower() in DIRECTIONAL_WORDS:
        return " ".join(tokens[1:])
    return value


def _strip_city_context(value: str) -> str:
    candidates = [
        r"^city of\s+",
        r"^town of\s+",
        r"^village of\s+",
        r"^district of\s+",
    ]
    result = value
    for pattern in candidates:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    return result
