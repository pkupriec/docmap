from __future__ import annotations

import os
import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


def geocode_location(
    name: str,
    *,
    timeout_seconds: int = 20,
    max_retries: int = 3,
) -> dict[str, Any] | None:
    base_url = os.getenv("GEOCODER_URL", "https://nominatim.openstreetmap.org").rstrip("/")
    endpoint = f"{base_url}/search"
    logger.info("geocoder.nominatim_request_start name=%s endpoint=%s", name, endpoint)

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                endpoint,
                params={
                    "q": name,
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "limit": 1,
                },
                headers={"User-Agent": "docmap-geocoder/0.1 (+https://github.com/docmap)"},
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            if not payload:
                logger.info("geocoder.nominatim_not_found name=%s", name)
                return None
            normalized = normalize_geocoder_response(name, payload[0])
            logger.info(
                "geocoder.nominatim_request_success name=%s precision=%s",
                name,
                normalized["precision"],
            )
            return normalized
        except (requests.RequestException, KeyError, ValueError) as exc:
            last_error = exc
            if attempt == max_retries:
                break
            backoff_seconds = 2 ** (attempt - 1)
            logger.warning(
                "geocoder.nominatim_retry name=%s attempt=%s backoff_seconds=%s reason=%s",
                name,
                attempt,
                backoff_seconds,
                type(exc).__name__,
            )
            time.sleep(backoff_seconds)

    logger.error("geocoder.nominatim_failed name=%s max_retries=%s", name, max_retries)
    raise RuntimeError(f"Nominatim geocoding failed for: {name}") from last_error


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
