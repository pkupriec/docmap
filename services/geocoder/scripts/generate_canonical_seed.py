from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")


def _normalize_text(value: str | None) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    text = text.replace("&", " and ")
    text = NON_ALNUM_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_place_type(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw == "region":
        return "admin_region"
    if raw.startswith("admin_level_"):
        return raw
    if raw in {"national_park", "desert"}:
        return raw
    if raw in {"city", "admin_region", "country", "continent", "ocean"}:
        return raw
    return "unknown"


def _canonical_id(properties: dict[str, Any], place_type: str, canonical_name: str) -> str:
    existing = str(properties.get("canonical_id") or "").strip()
    if existing:
        return existing
    seed_key = _normalize_text(canonical_name).replace(" ", "_")
    return f"seed:{place_type}:{seed_key}"


def _concordances(properties: dict[str, Any]) -> list[dict[str, str]]:
    osm_type = str(properties.get("osm_type") or "").strip().lower()
    osm_id = properties.get("osm_id")
    if not osm_type or osm_id is None:
        return []
    try:
        osm_id_int = int(str(osm_id).strip())
    except ValueError:
        return []
    return [{"external_source": "osm", "external_id": f"{osm_type}:{osm_id_int}"}]


def _build_country_alias_index(country_records: list[dict[str, Any]]) -> dict[str, str]:
    by_alias: dict[str, set[str]] = {}
    for record in country_records:
        cid = str(record["canonical_id"])
        for alias in record["safe_aliases"]:
            key = _normalize_text(alias)
            if not key:
                continue
            by_alias.setdefault(key, set()).add(cid)
    resolved: dict[str, str] = {}
    for alias, ids in by_alias.items():
        if len(ids) == 1:
            resolved[alias] = next(iter(ids))
    return resolved


def build_seed_dictionary(*, source_path: Path, output_path: Path, source: str = "seed") -> dict[str, int]:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        raise ValueError("Seed source must be a FeatureCollection with a 'features' list")

    records_raw: list[dict[str, Any]] = []
    country_candidates: list[dict[str, Any]] = []

    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            continue

        place_type = _normalize_place_type(str(properties.get("location_rank") or ""))
        canonical_name = str(properties.get("location_name") or "").strip()
        if not canonical_name or place_type == "unknown":
            continue

        safe_aliases = _to_list(properties.get("safe_aliases"))
        aliases = _to_list(properties.get("aliases"))
        unsafe_aliases = _to_list(properties.get("unsafe_aliases"))
        combined_safe = [canonical_name, *safe_aliases, *aliases]

        canonical_id = _canonical_id(properties, place_type, canonical_name)
        row = {
            "canonical_id": canonical_id,
            "source": source,
            "source_id": canonical_id.split(":", 1)[-1],
            "place_type": place_type,
            "canonical_name": canonical_name,
            "safe_aliases": combined_safe,
            "unsafe_aliases": unsafe_aliases,
            "country_name": str(properties.get("country_name") or "").strip() or None,
            "concordances": _concordances(properties),
        }
        records_raw.append(row)
        if place_type == "country":
            country_candidates.append(row)

    country_alias_index = _build_country_alias_index(country_candidates)

    places: list[dict[str, Any]] = []
    alias_count = 0
    concordance_count = 0
    for row in sorted(records_raw, key=lambda item: str(item["canonical_id"])):
        aliases: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        canonical_alias = str(row["canonical_name"])
        aliases.append({"alias": canonical_alias, "alias_type": "exact_name"})
        seen.add((_normalize_text(canonical_alias), "exact_name"))

        for alias in row["safe_aliases"]:
            normalized = _normalize_text(alias)
            key = (normalized, "language_variant")
            if not normalized or key in seen or normalized == _normalize_text(canonical_alias):
                continue
            aliases.append({"alias": alias, "alias_type": "language_variant"})
            seen.add(key)

        for alias in row["unsafe_aliases"]:
            normalized = _normalize_text(alias)
            key = (normalized, "unsafe_parent_ref")
            if not normalized or key in seen:
                continue
            aliases.append({"alias": alias, "alias_type": "unsafe_parent_ref"})
            seen.add(key)

        country_canonical_id = None
        if (
            row["place_type"] == "admin_region"
            or row["place_type"].startswith("admin_level_")
            or row["place_type"] in {"national_park", "desert"}
        ) and row["country_name"]:
            country_canonical_id = country_alias_index.get(_normalize_text(row["country_name"]))

        concordances = list(row["concordances"])
        alias_count += len(aliases)
        concordance_count += len(concordances)
        places.append(
            {
                "canonical_id": row["canonical_id"],
                "source": row["source"],
                "source_id": row["source_id"],
                "place_type": row["place_type"],
                "canonical_name": row["canonical_name"],
                "country_canonical_id": country_canonical_id,
                "aliases": aliases,
                "concordances": concordances,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"places": places}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "places": len(places),
        "aliases": alias_count,
        "concordances": concordance_count,
    }
