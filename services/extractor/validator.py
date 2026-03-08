from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from services.extractor.models import ExtractionPayload

logger = logging.getLogger(__name__)

def parse_extraction_json(raw_response: str) -> dict:
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        logger.warning("extractor.json_parse_fallback")
        # Handle model output with surrounding text.
        start = raw_response.find("{")
        end = raw_response.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise
        return json.loads(raw_response[start : end + 1])


def validate_extraction_response(payload: dict) -> ExtractionPayload:
    try:
        validated = ExtractionPayload.model_validate(payload)
        logger.info("extractor.payload_valid locations=%s", len(validated.locations))
        return validated
    except ValidationError as exc:
        logger.error("extractor.payload_invalid")
        raise ValueError("Invalid extraction payload") from exc
