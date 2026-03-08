from __future__ import annotations

import os
import logging

import requests

logger = logging.getLogger(__name__)


def run_extraction(
    *,
    model: str,
    prompt: str,
    timeout_seconds: int = 120,
) -> str:
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    endpoint = f"{ollama_host}/api/generate"
    logger.info("extractor.ollama_request_start model=%s endpoint=%s", model, endpoint)

    response = requests.post(
        endpoint,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    output = payload.get("response")
    if not isinstance(output, str):
        logger.error("extractor.ollama_invalid_response model=%s", model)
        raise RuntimeError("Invalid Ollama response: missing string 'response'")
    logger.info("extractor.ollama_request_success model=%s chars=%s", model, len(output))
    return output
