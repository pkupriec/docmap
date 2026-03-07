import json

import pytest

from services.extractor.validator import parse_extraction_json, validate_extraction_response


def test_parse_extraction_json_direct() -> None:
    payload = parse_extraction_json('{"locations": []}')
    assert payload == {"locations": []}


def test_parse_extraction_json_with_wrapping_text() -> None:
    payload = parse_extraction_json('Here you go: {"locations": []} Thank you')
    assert payload == {"locations": []}


def test_parse_extraction_json_invalid_raises() -> None:
    with pytest.raises(json.JSONDecodeError):
        parse_extraction_json("not json")


def test_validate_extraction_response_ok() -> None:
    validated = validate_extraction_response(
        {
            "locations": [
                {
                    "mention_text": "near Kyoto",
                    "normalized_location": "Kyoto, Japan",
                    "precision": "city",
                    "relation_type": "unspecified",
                    "confidence": 0.95,
                    "evidence_quote": "Recovered near Kyoto in 1993.",
                }
            ]
        }
    )
    assert len(validated.locations) == 1


def test_validate_extraction_response_invalid_confidence() -> None:
    with pytest.raises(ValueError):
        validate_extraction_response(
            {
                "locations": [
                    {
                        "mention_text": "near Kyoto",
                        "normalized_location": "Kyoto, Japan",
                        "precision": "city",
                        "relation_type": "unspecified",
                        "confidence": "high",
                        "evidence_quote": "Recovered near Kyoto in 1993.",
                    }
                ]
            }
        )
