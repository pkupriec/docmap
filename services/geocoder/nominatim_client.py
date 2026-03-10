from __future__ import annotations

import os
import logging
import time
import threading
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)
_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


def _get_min_interval_seconds() -> float:
    value = os.getenv("GEOCODER_MIN_INTERVAL_SECONDS", "1.1").strip()
    try:
        parsed = float(value)
    except ValueError:
        logger.warning("geocoder.nominatim_invalid_min_interval value=%r fallback=1.1", value)
        return 1.1
    if parsed <= 0:
        return 1.1
    return parsed


def _throttle_requests() -> None:
    global _LAST_REQUEST_AT
    min_interval = _get_min_interval_seconds()
    with _REQUEST_LOCK:
        now = time.monotonic()
        elapsed = now - _LAST_REQUEST_AT
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _LAST_REQUEST_AT = time.monotonic()


def _retry_after_seconds(raw_value: str | None) -> float | None:
    if not raw_value:
        return None
    try:
        parsed = float(raw_value)
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed


def _build_query_variants(name: str) -> list[str]:
    parts = [segment.strip() for segment in name.split(",") if segment.strip()]
    variants: list[str] = [name.strip()]

    # For landmark-heavy strings like "X, City, Country", fallback to "City, Country".
    if len(parts) >= 3:
        variants.append(", ".join(parts[-2:]))
    if len(parts) >= 2:
        variants.append(", ".join(parts[-2:]))

    # Remove some common non-geocodable venue/entity suffixes from the first segment.
    head_stripped = re.sub(
        r"\b(exchange|stock exchange|headquarters|hq|museum|building|tower|station|airport|university)\b",
        "",
        parts[0] if parts else name,
        flags=re.IGNORECASE,
    ).strip(" ,.-")
    if head_stripped and parts:
        variants.append(", ".join([head_stripped, *parts[1:]]))

    deduped: list[str] = []
    seen: set[str] = set()
    for item in variants:
        normalized = re.sub(r"\s+", " ", item).strip(" ,")
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def geocode_location(
    name: str,
    *,
    timeout_seconds: int = 20,
    max_retries: int = 3,
) -> dict[str, Any] | None:
    base_url = os.getenv("GEOCODER_URL", "https://nominatim.openstreetmap.org").rstrip("/")
    endpoint = f"{base_url}/search"
    user_agent = os.getenv("GEOCODER_USER_AGENT", "docmap-geocoder/0.1 (+https://github.com/docmap)")
    query_variants = _build_query_variants(name)
    logger.info(
        "geocoder.nominatim_request_start name=%s endpoint=%s variants=%s",
        name,
        endpoint,
        len(query_variants),
    )

    last_error: Exception | None = None
    for query in query_variants:
        for attempt in range(1, max_retries + 1):
            try:
                _throttle_requests()
                response = requests.get(
                    endpoint,
                    params={
                        "q": query,
                        "format": "jsonv2",
                        "addressdetails": 1,
                        "limit": 1,
                    },
                    headers={"User-Agent": user_agent},
                    timeout=timeout_seconds,
                )
                if response.status_code == 429:
                    retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
                    backoff_seconds = retry_after if retry_after is not None else 2 ** (attempt - 1)
                    logger.warning(
                        "geocoder.nominatim_rate_limited name=%s query=%s attempt=%s backoff_seconds=%s",
                        name,
                        query,
                        attempt,
                        round(backoff_seconds, 2),
                    )
                    if attempt < max_retries:
                        time.sleep(backoff_seconds)
                        continue
                response.raise_for_status()
                payload = response.json()
                if not payload:
                    logger.info("geocoder.nominatim_not_found name=%s query=%s", name, query)
                    break
                normalized = normalize_geocoder_response(name, payload[0])
                logger.info(
                    "geocoder.nominatim_request_success name=%s query=%s precision=%s",
                    name,
                    query,
                    normalized["precision"],
                )
                return normalized
            except (requests.RequestException, KeyError, ValueError) as exc:
                last_error = exc
                if attempt == max_retries:
                    break
                backoff_seconds = 2 ** (attempt - 1)
                logger.warning(
                    "geocoder.nominatim_retry name=%s query=%s attempt=%s backoff_seconds=%s reason=%s",
                    name,
                    query,
                    attempt,
                    backoff_seconds,
                    type(exc).__name__,
                )
                time.sleep(backoff_seconds)

    logger.error(
        "geocoder.nominatim_failed name=%s variants=%s max_retries=%s reason=%s",
        name,
        len(query_variants),
        max_retries,
        type(last_error).__name__ if last_error else "not_found",
    )
    return None


def normalize_geocoder_response(normalized_location: str, payload: dict[str, Any]) -> dict[str, Any]:
    address = payload.get("address", {}) or {}
    city = address.get("city") or address.get("town") or address.get("village")
    region = (
        address.get("state")
        or address.get("region")
        or address.get("county")
        or address.get("state_district")
    )
    country = address.get("country")

    latitude = float(payload["lat"])
    longitude = float(payload["lon"])

    return {
        "normalized_location": normalized_location,
        "country": country,
        "region": region,
        "city": city,
        "latitude": latitude,
        "longitude": longitude,
        "precision": infer_precision(city=city, region=region, country=country),
    }


def infer_precision(*, city: str | None, region: str | None, country: str | None) -> str:
    if city:
        return "city"
    if region:
        return "admin_region"
    if country:
        return "country"
    return "unknown"
