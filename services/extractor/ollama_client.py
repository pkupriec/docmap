from __future__ import annotations

import os
import logging

import requests

logger = logging.getLogger(__name__)
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 300
DEFAULT_OLLAMA_THINK_LEVEL = "low"


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


def _get_ollama_think_level() -> str:
    value = (os.getenv("OLLAMA_THINK_LEVEL") or DEFAULT_OLLAMA_THINK_LEVEL).strip().lower()
    if value in {"low", "medium", "high"}:
        return value
    logger.warning(
        "extractor.ollama_think_level_invalid value=%r fallback=%s",
        value,
        DEFAULT_OLLAMA_THINK_LEVEL,
    )
    return DEFAULT_OLLAMA_THINK_LEVEL


def _get_positive_int_env(name: str) -> int | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    try:
        parsed = int(value)
    except ValueError:
        logger.warning("extractor.ollama_env_invalid_int name=%s value=%r", name, value)
        return None
    if parsed <= 0:
        return None
    return parsed


def _ns_to_seconds(value: object) -> float | None:
    if not isinstance(value, int):
        return None
    return round(value / 1_000_000_000, 2)


def run_extraction(
    *,
    model: str,
    prompt: str,
    timeout_seconds: int | None = None,
) -> str:
    effective_timeout = timeout_seconds or _get_ollama_timeout_seconds()
    think_level = _get_ollama_think_level()
    num_predict = _get_positive_int_env("OLLAMA_NUM_PREDICT")
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    endpoint = f"{ollama_host}/api/generate"
    logger.info(
        (
            "extractor.ollama_request_start model=%s endpoint=%s timeout_seconds=%s "
            "think=%s num_predict=%s"
        ),
        model,
        endpoint,
        effective_timeout,
        think_level,
        num_predict,
    )
    request_payload: dict[str, object] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": think_level,
    }
    if num_predict is not None:
        request_payload["options"] = {"num_predict": num_predict}

    response = requests.post(
        endpoint,
        json=request_payload,
        timeout=effective_timeout,
    )
    response.raise_for_status()
    payload = response.json()
    output = payload.get("response")
    if not isinstance(output, str):
        logger.error("extractor.ollama_invalid_response model=%s", model)
        raise RuntimeError("Invalid Ollama response: missing string 'response'")
    logger.info(
        (
            "extractor.ollama_request_success model=%s chars=%s thinking_chars=%s "
            "done_reason=%s prompt_eval_tokens=%s eval_tokens=%s "
            "load_duration_s=%s prompt_eval_duration_s=%s eval_duration_s=%s total_duration_s=%s"
        ),
        model,
        len(output),
        len(payload.get("thinking") or ""),
        payload.get("done_reason"),
        payload.get("prompt_eval_count"),
        payload.get("eval_count"),
        _ns_to_seconds(payload.get("load_duration")),
        _ns_to_seconds(payload.get("prompt_eval_duration")),
        _ns_to_seconds(payload.get("eval_duration")),
        _ns_to_seconds(payload.get("total_duration")),
    )
    return output
