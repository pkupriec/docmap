from __future__ import annotations

import os
import logging

import requests

logger = logging.getLogger(__name__)
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 300


def _get_ollama_timeout_seconds() -> int:
    value = os.getenv("OLLAMA_TIMEOUT_SECONDS")
    if value is None:
        return DEFAULT_OLLAMA_TIMEOUT_SECONDS
    try:
        parsed = int(value)
    except ValueError:
        logger.warning(
            "extractor.ollama_timeout_invalid value=%r fallback=%s",
            value,
            DEFAULT_OLLAMA_TIMEOUT_SECONDS,
        )
        return DEFAULT_OLLAMA_TIMEOUT_SECONDS
    if parsed <= 0:
        logger.warning(
            "extractor.ollama_timeout_non_positive value=%s fallback=%s",
            parsed,
            DEFAULT_OLLAMA_TIMEOUT_SECONDS,
        )
        return DEFAULT_OLLAMA_TIMEOUT_SECONDS
    return parsed


def run_extraction(
    *,
    model: str,
    prompt: str,
    timeout_seconds: int | None = None,
) -> str:
    effective_timeout = timeout_seconds or _get_ollama_timeout_seconds()
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    endpoint = f"{ollama_host}/api/generate"
    logger.info(
        "extractor.ollama_request_start model=%s endpoint=%s timeout_seconds=%s",
        model,
        endpoint,
        effective_timeout,
    )

    response = requests.post(
        endpoint,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=effective_timeout,
    )
    response.raise_for_status()
    payload = response.json()
    output = payload.get("response")
    if not isinstance(output, str):
        logger.error("extractor.ollama_invalid_response model=%s", model)
        raise RuntimeError("Invalid Ollama response: missing string 'response'")
    logger.info("extractor.ollama_request_success model=%s chars=%s", model, len(output))
    return output
