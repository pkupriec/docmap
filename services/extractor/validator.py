from __future__ import annotations

import json

from pydantic import ValidationError

from services.extractor.models import ExtractionPayload


def parse_extraction_json(raw_response: str) -> dict:
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        # Handle model output with surrounding text.
        start = raw_response.find("{")
        end = raw_response.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise
        return json.loads(raw_response[start : end + 1])


def validate_extraction_response(payload: dict) -> ExtractionPayload:
    try:
        return ExtractionPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("Invalid extraction payload") from exc
