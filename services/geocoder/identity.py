from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from typing import Any


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_identity_text(value: object | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    return _NON_ALNUM_RE.sub(" ", ascii_text).strip()


def _coordinate(value: Any) -> str | None:
    try:
        coordinate = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(coordinate):
        return None
    return f"{coordinate:.5f}"


def _city_name(payload: dict[str, Any]) -> str:
    parts = [normalize_identity_text(part) for part in str(payload.get("normalized_location") or "").split(",")]
    parts = [part for part in parts if part]
    removable = {
        normalize_identity_text(payload.get("region")),
        normalize_identity_text(payload.get("country")),
    }
    removable.discard("")
    while parts and parts[-1] in removable:
        parts.pop()
    return " ".join(parts)


def location_identity_key(payload: dict[str, Any]) -> str | None:
    """Return a stable entity key while keeping mention spellings as aliases."""
    rank = normalize_identity_text(payload.get("location_rank")).replace(" ", "_")
    precision = normalize_identity_text(payload.get("precision"))
    latitude = _coordinate(payload.get("latitude"))
    longitude = _coordinate(payload.get("longitude"))

    if (rank == "city" or precision == "city") and latitude is not None and longitude is not None:
        city_name = _city_name(payload)
        if city_name:
            components = (
                city_name,
                normalize_identity_text(payload.get("region")),
                normalize_identity_text(payload.get("country")),
                latitude,
                longitude,
            )
            digest = hashlib.sha256("\x1f".join(components).encode("utf-8")).hexdigest()[:32]
            return f"city:{digest}"

    canonical_id = str(payload.get("canonical_id") or "").strip()
    if canonical_id:
        return f"canonical:{canonical_id.lower()}"

    osm_type = normalize_identity_text(payload.get("osm_type"))
    osm_id = payload.get("osm_id")
    if osm_type and osm_id is not None:
        try:
            return f"osm:{osm_type}:{int(osm_id)}"
        except (TypeError, ValueError):
            pass
    return None
