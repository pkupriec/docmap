from __future__ import annotations

import random
import time

import requests


class RequestThrottler:
    def __init__(self, min_interval_seconds: float = 1.0, jitter_seconds: float = 0.2) -> None:
        self.min_interval_seconds = min_interval_seconds
        self.jitter_seconds = jitter_seconds
        self._last_request_at = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_at
        target = self.min_interval_seconds + random.uniform(0.0, self.jitter_seconds)
        remaining = target - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_request_at = time.monotonic()


def download_page(
    url: str,
    *,
    timeout_seconds: int = 15,
    max_retries: int = 3,
    throttler: RequestThrottler | None = None,
) -> str:
    headers = {"User-Agent": "docmap-crawler/0.1 (+https://github.com/docmap)"}
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        if throttler is not None:
            throttler.wait()
        try:
            response = requests.get(url, headers=headers, timeout=timeout_seconds)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == max_retries:
                break
            backoff_seconds = 2 ** (attempt - 1)
            time.sleep(backoff_seconds)

    raise RuntimeError(f"Failed to download {url}") from last_error
