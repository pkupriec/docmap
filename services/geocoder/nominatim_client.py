from __future__ import annotations

import os
from typing import Any

import requests


def geocode_location(name: str, *, timeout_seconds: int = 20) -> dict[str, Any] | None:
    base_url = os.getenv("GEOCODER_URL", "https://nominatim.openstreetmap.org").rstrip("/")
    endpoint = f"{base_url}/search"

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
        return None
    return normalize_geocoder_response(name, payload[0])


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
