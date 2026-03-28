from __future__ import annotations

import argparse
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from services.common.db import get_connection

logger = logging.getLogger(__name__)

ALIAS_TYPES = {"exact_name", "language_variant", "historic_name", "unsafe_parent_ref"}
SAFE_ALIAS_TYPES = {"exact_name", "language_variant"}
PLACE_TYPES = {"city", "admin_region", "country", "continent", "ocean", "unknown"}
NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")


@dataclass(frozen=True)
class CanonicalPlaceRecord:
    canonical_id: str
    source: str
    source_id: str
    place_type: str
    canonical_name: str
    parent_canonical_id: str | None
    country_canonical_id: str | None
    centroid_lat: float | None
    centroid_lon: float | None
    valid_from: str | None
    valid_to: str | None
    aliases: list[dict[str, str]]
    concordances: list[dict[str, str]]


def _normalize_alias(value: str | None) -> str:
    lowered = (value or "").strip().lower()
    if not lowered:
        return ""
    ascii_value = unicodedata.normalize("NFKD", lowered).encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.replace("&", " and ")
    ascii_value = NON_ALNUM_RE.sub(" ", ascii_value)
    return re.sub(r"\s+", " ", ascii_value).strip()


def _normalize_place_type(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "region":
        normalized = "admin_region"
    if normalized not in PLACE_TYPES:
        return "unknown"
    return normalized


def _read_input(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        places = payload.get("places")
        if isinstance(places, list):
            return places
    raise ValueError("Canonical dictionary input must be a list or an object with a 'places' list")


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (float, int)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    return float(text)


def _normalize_aliases(place: dict[str, Any], canonical_id: str) -> list[dict[str, str]]:
    aliases_raw = place.get("aliases") or []
    aliases: list[dict[str, str]] = []
    for item in aliases_raw:
        if not isinstance(item, dict):
            continue
        alias = _coerce_str(item.get("alias"))
        alias_type = _coerce_str(item.get("alias_type"))
        if not alias or not alias_type:
            continue
        alias_type = alias_type.lower()
        if alias_type not in ALIAS_TYPES:
            raise ValueError(f"{canonical_id}: invalid alias_type '{alias_type}'")
        normalized_alias = _normalize_alias(alias)
        if not normalized_alias:
            continue
        aliases.append(
            {
                "canonical_id": canonical_id,
                "alias": alias,
                "alias_type": alias_type,
                "normalized_alias": normalized_alias,
            }
        )
    return aliases


def _normalize_concordances(place: dict[str, Any], canonical_id: str) -> list[dict[str, str]]:
    concordances_raw = place.get("concordances") or []
    concordances: list[dict[str, str]] = []
    for item in concordances_raw:
        if not isinstance(item, dict):
            continue
        external_source = _coerce_str(item.get("external_source"))
        external_id = _coerce_str(item.get("external_id"))
        if not external_source or not external_id:
            continue
        concordances.append(
            {
                "canonical_id": canonical_id,
                "external_source": external_source.lower(),
                "external_id": external_id,
            }
        )
    return concordances


def parse_records(places: list[dict[str, Any]], *, default_source: str) -> tuple[list[CanonicalPlaceRecord], dict[str, Any]]:
    records: list[CanonicalPlaceRecord] = []
    safe_alias_index: dict[tuple[str, str, str], list[str]] = {}
    for place in places:
        if not isinstance(place, dict):
            continue
        canonical_id = _coerce_str(place.get("canonical_id"))
        source = _coerce_str(place.get("source")) or default_source
        source_id = _coerce_str(place.get("source_id"))
        canonical_name = _coerce_str(place.get("canonical_name"))
        if not canonical_id or not source_id or not canonical_name:
            raise ValueError("place record requires canonical_id, source_id, canonical_name")
        place_type = _normalize_place_type(_coerce_str(place.get("place_type")))
        aliases = _normalize_aliases(place, canonical_id)
        concordances = _normalize_concordances(place, canonical_id)
        for alias in aliases:
            if alias["alias_type"] not in SAFE_ALIAS_TYPES:
                continue
            key = (place_type, alias["alias_type"], alias["normalized_alias"])
            safe_alias_index.setdefault(key, []).append(canonical_id)
        records.append(
            CanonicalPlaceRecord(
                canonical_id=canonical_id,
                source=source,
                source_id=source_id,
                place_type=place_type,
                canonical_name=canonical_name,
                parent_canonical_id=_coerce_str(place.get("parent_canonical_id")),
                country_canonical_id=_coerce_str(place.get("country_canonical_id")),
                centroid_lat=_coerce_float(place.get("centroid_lat")),
                centroid_lon=_coerce_float(place.get("centroid_lon")),
                valid_from=_coerce_str(place.get("valid_from")),
                valid_to=_coerce_str(place.get("valid_to")),
                aliases=aliases,
                concordances=concordances,
            )
        )
    collisions = {
        f"{place_type}:{alias_type}:{normalized_alias}": sorted(set(ids))
        for (place_type, alias_type, normalized_alias), ids in safe_alias_index.items()
        if len(set(ids)) > 1
    }
    diagnostics = {
        "safe_alias_collision_count": len(collisions),
        "safe_alias_collisions": collisions,
    }
    return records, diagnostics


def refresh_dictionary(
    *,
    input_path: Path,
    source: str,
    report_path: Path | None,
    replace_source: bool,
) -> dict[str, Any]:
    places = _read_input(input_path)
    records, diagnostics = parse_records(places, default_source=source)
    if replace_source and not records:
        raise ValueError(
            "Refusing to replace canonical source with empty dataset. "
            "Provide non-empty input or run without --replace-source."
        )
    aliases = [alias for record in records for alias in record.aliases]
    concordances = [concordance for record in records for concordance in record.concordances]

    with get_connection() as conn:
        with conn.cursor() as cur:
            if replace_source:
                cur.execute(
                    """
                    DELETE FROM geo_canonical_aliases a
                    USING geo_canonical_places p
                    WHERE p.canonical_id = a.canonical_id
                      AND p.source = %s
                    """,
                    (source,),
                )
                cur.execute(
                    """
                    DELETE FROM geo_canonical_concordances c
                    USING geo_canonical_places p
                    WHERE p.canonical_id = c.canonical_id
                      AND p.source = %s
                    """,
                    (source,),
                )
                cur.execute("DELETE FROM geo_canonical_places WHERE source = %s", (source,))

            # Phase 1: upsert place rows without self-referential links.
            # This avoids FK ordering failures when child rows appear before parents.
            cur.executemany(
                """
                INSERT INTO geo_canonical_places (
                    canonical_id,
                    source,
                    source_id,
                    place_type,
                    canonical_name,
                    parent_canonical_id,
                    country_canonical_id,
                    centroid_lat,
                    centroid_lon,
                    valid_from,
                    valid_to
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (canonical_id) DO UPDATE
                SET source = EXCLUDED.source,
                    source_id = EXCLUDED.source_id,
                    place_type = EXCLUDED.place_type,
                    canonical_name = EXCLUDED.canonical_name,
                    parent_canonical_id = EXCLUDED.parent_canonical_id,
                    country_canonical_id = EXCLUDED.country_canonical_id,
                    centroid_lat = EXCLUDED.centroid_lat,
                    centroid_lon = EXCLUDED.centroid_lon,
                    valid_from = EXCLUDED.valid_from,
                    valid_to = EXCLUDED.valid_to,
                    updated_at = now()
                """,
                [
                    (
                        record.canonical_id,
                        record.source,
                        record.source_id,
                        record.place_type,
                        record.canonical_name,
                        None,
                        None,
                        record.centroid_lat,
                        record.centroid_lon,
                        record.valid_from,
                        record.valid_to,
                    )
                    for record in records
                ],
            )

            # Validate link targets now that all places are present.
            cur.execute("SELECT canonical_id FROM geo_canonical_places")
            known_ids = {str(row[0]) for row in cur.fetchall() if row and row[0]}
            for record in records:
                if record.parent_canonical_id and record.parent_canonical_id not in known_ids:
                    raise ValueError(
                        f"{record.canonical_id}: parent_canonical_id '{record.parent_canonical_id}' is missing"
                    )
                if record.country_canonical_id and record.country_canonical_id not in known_ids:
                    raise ValueError(
                        f"{record.canonical_id}: country_canonical_id '{record.country_canonical_id}' is missing"
                    )

            # Phase 2: apply self-referential links after base rows exist.
            cur.executemany(
                """
                UPDATE geo_canonical_places
                SET
                    parent_canonical_id = %s,
                    country_canonical_id = %s,
                    updated_at = now()
                WHERE canonical_id = %s
                """,
                [
                    (
                        record.parent_canonical_id,
                        record.country_canonical_id,
                        record.canonical_id,
                    )
                    for record in records
                ],
            )

            if aliases:
                cur.executemany(
                    """
                    INSERT INTO geo_canonical_aliases (
                        canonical_id,
                        alias,
                        normalized_alias,
                        alias_type
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (canonical_id, normalized_alias, alias_type) DO UPDATE
                    SET alias = EXCLUDED.alias,
                        updated_at = now()
                    """,
                    [
                        (
                            item["canonical_id"],
                            item["alias"],
                            item["normalized_alias"],
                            item["alias_type"],
                        )
                        for item in aliases
                    ],
                )
            if concordances:
                cur.executemany(
                    """
                    INSERT INTO geo_canonical_concordances (
                        canonical_id,
                        external_source,
                        external_id
                    ) VALUES (%s, %s, %s)
                    ON CONFLICT (external_source, external_id) DO UPDATE
                    SET canonical_id = EXCLUDED.canonical_id,
                        updated_at = now()
                    """,
                    [
                        (
                            item["canonical_id"],
                            item["external_source"],
                            item["external_id"],
                        )
                        for item in concordances
                    ],
                )
        conn.commit()

    report = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "input_path": str(input_path),
        "source": source,
        "replace_source": replace_source,
        "counts": {
            "places": len(records),
            "aliases": len(aliases),
            "concordances": len(concordances),
        },
        "diagnostics": diagnostics,
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    logger.info(
        "geocoder.canonical_dictionary_refreshed source=%s places=%s aliases=%s concordances=%s collisions=%s",
        source,
        len(records),
        len(aliases),
        len(concordances),
        diagnostics.get("safe_alias_collision_count", 0),
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh canonical geo dictionary tables")
    parser.add_argument("--input", required=True, dest="input_path", help="Path to canonical dictionary JSON")
    parser.add_argument("--source", default="wof", help="Canonical source tag for this import (default: wof)")
    parser.add_argument("--report", dest="report_path", default=None, help="Optional output JSON report path")
    parser.add_argument(
        "--replace-source",
        action="store_true",
        help="Delete existing rows for --source before import",
    )
    args = parser.parse_args()

    report = refresh_dictionary(
        input_path=Path(args.input_path).resolve(),
        source=str(args.source).strip().lower(),
        report_path=Path(args.report_path).resolve() if args.report_path else None,
        replace_source=bool(args.replace_source),
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
