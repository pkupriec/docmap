from __future__ import annotations

import os

import requests


def run_extraction(
    *,
    model: str,
    prompt: str,
    timeout_seconds: int = 120,
) -> str:
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    endpoint = f"{ollama_host}/api/generate"

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
        raise RuntimeError("Invalid Ollama response: missing string 'response'")
    return output
