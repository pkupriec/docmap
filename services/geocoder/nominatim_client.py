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
_OCEAN_TOKENS = (
    "ocean",
    "sea",
    "gulf",
    "bay",
    "strait",
    "channel",
    "fjord",
)
_BOUNDARY_INTENT_TOKENS = (
    "boundary",
    "borders",
    "country",
    "state",
    "province",
    "region",
    "district",
    "county",
    "prefecture",
    "oblast",
    "territory",
    "municipality",
    "park",
    "desert",
)
_POINT_LIKE_TYPES = {
    "city",
    "town",
    "village",
    "hamlet",
    "locality",
    "neighbourhood",
    "suburb",
    "quarter",
    "borough",
}
_BOUNDARY_LIKE_TYPES = {
    "administrative",
    "boundary",
    "country",
    "state",
    "province",
    "region",
    "county",
    "district",
    "municipality",
    "national_park",
    "protected_area",
    "desert",
}
_OCEAN_TOKEN_PATTERN = re.compile(
    r"(?<![a-z0-9])(?:%s)(?![a-z0-9])" % "|".join(re.escape(token) for token in _OCEAN_TOKENS),
    flags=re.IGNORECASE,
)


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


def _as_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _as_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _normalize_boundingbox(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    result: list[float] = []
    for item in value:
        try:
            result.append(float(item))
        except (TypeError, ValueError):
            return None
    return result


def _extract_admin_level(payload: dict[str, Any]) -> int | None:
    extratags = payload.get("extratags")
    if isinstance(extratags, dict):
        level = _as_int_or_none(extratags.get("admin_level"))
        if level is not None:
            return level
    return _as_int_or_none(payload.get("admin_level"))


def _search_nominatim(
    *,
    endpoint: str,
    user_agent: str,
    query: str,
    limit: int,
    timeout_seconds: int,
    max_retries: int,
) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            _throttle_requests()
            response = requests.get(
                endpoint,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "namedetails": 1,
                    "extratags": 1,
                    "limit": limit,
                },
                headers={"User-Agent": user_agent},
                timeout=timeout_seconds,
            )
            if response.status_code == 429:
                retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
                backoff_seconds = retry_after if retry_after is not None else 2 ** (attempt - 1)
                logger.warning(
                    "geocoder.nominatim_rate_limited query=%s attempt=%s backoff_seconds=%s",
                    query,
                    attempt,
                    round(backoff_seconds, 2),
                )
                if attempt < max_retries:
                    time.sleep(backoff_seconds)
                    continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                return []
            return [row for row in payload if isinstance(row, dict)]
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt == max_retries:
                break
            backoff_seconds = 2 ** (attempt - 1)
            logger.warning(
                "geocoder.nominatim_retry query=%s attempt=%s backoff_seconds=%s reason=%s",
                query,
                attempt,
                backoff_seconds,
                type(exc).__name__,
            )
            time.sleep(backoff_seconds)

    if last_error is not None:
        logger.warning(
            "geocoder.nominatim_query_failed query=%s max_retries=%s reason=%s",
            query,
            max_retries,
            type(last_error).__name__,
        )
    return []


def _detect_boundary_intent(name: str) -> bool:
    normalized = _normalize_text(name)
    if not normalized:
        return False
    tokens = set(normalized.split())
    return any(token in tokens for token in _BOUNDARY_INTENT_TOKENS)


def _is_boundary_like(payload: dict[str, Any]) -> bool:
    normalized_type = _normalize_text(payload.get("type"))
    normalized_addresstype = _normalize_text(payload.get("addresstype"))
    normalized_category = _normalize_text(payload.get("category") or payload.get("class"))
    admin_level = _extract_admin_level(payload)
    if admin_level is not None:
        return True
    if normalized_type in _BOUNDARY_LIKE_TYPES or normalized_addresstype in _BOUNDARY_LIKE_TYPES:
        return True
    return normalized_category == "boundary"


def _is_point_like(payload: dict[str, Any]) -> bool:
    normalized_type = _normalize_text(payload.get("type"))
    normalized_addresstype = _normalize_text(payload.get("addresstype"))
    if normalized_type in _POINT_LIKE_TYPES:
        return True
    if normalized_addresstype in _POINT_LIKE_TYPES:
        return True
    return not _is_boundary_like(payload)


def _candidate_payload(payload: dict[str, Any], *, role: str, source_query: str) -> dict[str, Any] | None:
    osm_type = _normalize_text(payload.get("osm_type"))
    osm_id = _as_int_or_none(payload.get("osm_id"))
    latitude = _as_float_or_none(payload.get("lat"))
    longitude = _as_float_or_none(payload.get("lon"))
    if latitude is None or longitude is None:
        return None
    return {
        "role": role,
        "source_query": source_query,
        "display_name": str(payload.get("display_name") or "").strip() or None,
        "osm_type": osm_type or None,
        "osm_id": osm_id,
        "osm_class": _normalize_text(payload.get("class") or payload.get("category")) or None,
        "osm_place_type": _normalize_text(payload.get("type")) or None,
        "osm_addresstype": _normalize_text(payload.get("addresstype")) or None,
        "osm_admin_level": _extract_admin_level(payload),
        "osm_place_rank": _as_int_or_none(payload.get("place_rank")),
        "latitude": latitude,
        "longitude": longitude,
        "boundingbox": _normalize_boundingbox(payload.get("boundingbox")),
    }


def _build_candidate_set(*, primary_query: str, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str | None, int | None, str]] = set()
    for index, payload in enumerate(payloads):
        role = "boundary" if _is_boundary_like(payload) else "point"
        if index == 0 and role != "boundary":
            role = "point"
        candidate = _candidate_payload(payload, role=role, source_query=primary_query)
        if candidate is None:
            continue
        key = (candidate.get("osm_type"), candidate.get("osm_id"), role)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    return candidates


def infer_location_rank(
    *,
    normalized_location: str | None = None,
    city: str | None,
    region: str | None,
    country: str | None,
    category: str | None,
    place_type: str | None,
    addresstype: str | None,
    admin_level: int | None = None,
) -> str:
    normalized_category = _normalize_text(category)
    normalized_type = _normalize_text(place_type)
    normalized_addresstype = _normalize_text(addresstype)
    normalized_name = _normalize_text(normalized_location)
    continent_names = {
        "africa",
        "antarctica",
        "asia",
        "europe",
        "north america",
        "south america",
        "oceania",
        "australia",
    }

    if admin_level is not None and admin_level > 0:
        return f"admin_level_{admin_level}"

    if (
        normalized_type in {"national_park", "protected_area"}
        or normalized_addresstype in {"national_park", "protected_area"}
    ):
        return "national_park"
    if normalized_type in {"desert", "dune"} or normalized_addresstype in {"desert", "dune"}:
        return "desert"

    if (
        normalized_type in _OCEAN_TOKENS
        or normalized_addresstype in _OCEAN_TOKENS
        or (normalized_category == "natural" and normalized_type in _OCEAN_TOKENS)
        or _matches_ocean_token(normalized_name)
    ):
        return "ocean"

    if (
        normalized_type == "continent"
        or normalized_addresstype == "continent"
        or normalized_name in continent_names
    ):
        return "continent"

    if city:
        return "city"
    if region:
        return "admin_region"
    if country:
        return "country"
    return "unknown"


def _matches_ocean_token(normalized_name: str) -> bool:
    if not normalized_name:
        return False
    return _OCEAN_TOKEN_PATTERN.search(normalized_name) is not None


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

    for query in query_variants:
        payloads = _search_nominatim(
            endpoint=endpoint,
            user_agent=user_agent,
            query=query,
            limit=8,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        if not payloads:
            logger.info("geocoder.nominatim_not_found name=%s query=%s", name, query)
            continue
        top_payload = payloads[0]
        boundary_intent = _detect_boundary_intent(name)
        candidates = _build_candidate_set(primary_query=query, payloads=payloads)
        if boundary_intent and _is_point_like(top_payload):
            follow_up_payloads = _search_nominatim(
                endpoint=endpoint,
                user_agent=user_agent,
                query=f"{query} boundary",
                limit=8,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
            boundary_candidates = _build_candidate_set(
                primary_query=f"{query} boundary",
                payloads=[row for row in follow_up_payloads if _is_boundary_like(row)],
            )
            existing = {
                (candidate.get("osm_type"), candidate.get("osm_id"), candidate.get("role"))
                for candidate in candidates
            }
            for candidate in boundary_candidates:
                key = (candidate.get("osm_type"), candidate.get("osm_id"), candidate.get("role"))
                if key in existing:
                    continue
                existing.add(key)
                candidates.append(candidate)
        normalized = normalize_geocoder_response(
            name,
            top_payload,
            boundary_intent=boundary_intent,
            geocode_candidates=candidates,
        )
        logger.info(
            "geocoder.nominatim_request_success name=%s query=%s precision=%s boundary_intent=%s candidates=%s",
            name,
            query,
            normalized["precision"],
            normalized["boundary_intent"],
            len(normalized["geocode_candidates"]),
        )
        return normalized

    logger.error(
        "geocoder.nominatim_failed name=%s variants=%s max_retries=%s reason=%s",
        name,
        len(query_variants),
        max_retries,
        "not_found",
    )
    return None


def normalize_geocoder_response(
    normalized_location: str,
    payload: dict[str, Any],
    *,
    boundary_intent: bool = False,
    geocode_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    address = payload.get("address", {}) or {}
    city = address.get("city") or address.get("town") or address.get("village")
    region = (
        address.get("state")
        or address.get("region")
        or address.get("county")
        or address.get("state_district")
    )
    country = address.get("country")
    osm_type = payload.get("osm_type")
    osm_id = _as_int_or_none(payload.get("osm_id"))
    category = payload.get("category") or payload.get("class")
    place_type = payload.get("type")
    addresstype = payload.get("addresstype")
    admin_level = _extract_admin_level(payload)
    place_rank = _as_int_or_none(payload.get("place_rank"))
    boundingbox = _normalize_boundingbox(payload.get("boundingbox"))

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
        "location_rank": infer_location_rank(
            normalized_location=normalized_location,
            city=city,
            region=region,
            country=country,
            category=str(category) if category is not None else None,
            place_type=str(place_type) if place_type is not None else None,
            addresstype=str(addresstype) if addresstype is not None else None,
            admin_level=admin_level,
        ),
        "osm_type": str(osm_type) if osm_type is not None else None,
        "osm_id": osm_id,
        "osm_category": str(category) if category is not None else None,
        "osm_place_type": str(place_type) if place_type is not None else None,
        "osm_addresstype": str(addresstype) if addresstype is not None else None,
        "osm_admin_level": admin_level,
        "osm_place_rank": place_rank,
        "osm_boundingbox": boundingbox,
        "boundary_intent": bool(boundary_intent),
        "geocode_candidates": list(geocode_candidates or []),
    }


def infer_precision(*, city: str | None, region: str | None, country: str | None) -> str:
    if city:
        return "city"
    if region:
        return "admin_region"
    if country:
        return "country"
    return "unknown"
    if admin_level is not None and admin_level > 0:
        return f"admin_level_{admin_level}"

    if (
        normalized_type in {"national_park", "protected_area"}
        or normalized_addresstype in {"national_park", "protected_area"}
    ):
        return "national_park"
    if normalized_type in {"desert", "dune"} or normalized_addresstype in {"desert", "dune"}:
        return "desert"
