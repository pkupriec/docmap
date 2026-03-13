from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from psycopg import Connection

logger = logging.getLogger(__name__)

POLYGON_RANKS = ("admin_region", "country", "continent", "ocean")
RANK_ALIAS = {
    "region": "admin_region",
    "admin_region": "admin_region",
    "country": "country",
    "continent": "continent",
    "ocean": "ocean",
    "city": "city",
    "unknown": "unknown",
}
RANK_ORDER = {
    "country": 0,
    "admin_region": 1,
    "continent": 2,
    "ocean": 3,
    "unknown": 4,
}
NAME_SPLIT_RE = re.compile(r"[|/;]+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")


@dataclass(frozen=True)
class GeometryTarget:
    location_id: str
    location_name: str
    location_rank: str
    country_name: str | None
    region_name: str | None
    osm_type: str | None
    osm_id: int | None


@dataclass(frozen=True)
class GeometryBuildResult:
    features_written: int
    matched_by_rank: dict[str, int]
    total_by_rank: dict[str, int]
    output_path: Path
    coverage_path: Path

    @property
    def matched_countries(self) -> int:
        return int(self.matched_by_rank.get("country", 0))

    @property
    def matched_regions(self) -> int:
        return int(self.matched_by_rank.get("admin_region", 0))

    @property
    def total_countries(self) -> int:
        return int(self.total_by_rank.get("country", 0))

    @property
    def total_regions(self) -> int:
        return int(self.total_by_rank.get("admin_region", 0))


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_source_path() -> Path:
    return _project_root() / "services" / "analytics" / "assets" / "admin_boundaries_source.geojson"


def _default_output_path() -> Path:
    return _project_root() / "services" / "analytics" / "assets" / "admin_boundaries.geojson"


def _default_coverage_path() -> Path:
    return _project_root() / "services" / "analytics" / "assets" / "admin_boundaries.coverage.json"


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _normalize_rank(value: str | None) -> str:
    normalized = _normalize(value)
    return RANK_ALIAS.get(normalized, normalized or "unknown")


def _feature_geometry_supported(feature: dict[str, Any]) -> bool:
    geometry = feature.get("geometry") or {}
    geometry_type = str(geometry.get("type") or "")
    return geometry_type in {"Polygon", "MultiPolygon"}


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _canonical_name(value: str) -> str:
    lowered = value.strip().lower()
    if not lowered:
        return ""
    ascii_value = unicodedata.normalize("NFKD", lowered)
    ascii_value = ascii_value.encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.replace("&", " and ")
    ascii_value = NON_ALNUM_RE.sub(" ", ascii_value)
    ascii_value = re.sub(r"\s+", " ", ascii_value).strip()
    return ascii_value


def _name_variants(values: list[str]) -> set[str]:
    variants: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            continue
        lowered = _normalize(value)
        if lowered:
            variants.add(lowered)
        canonical = _canonical_name(value)
        if canonical:
            variants.add(canonical)

        parts = [part.strip() for part in NAME_SPLIT_RE.split(value) if part.strip()]
        for part in parts:
            lowered_part = _normalize(part)
            if lowered_part:
                variants.add(lowered_part)
            canonical_part = _canonical_name(part)
            if canonical_part:
                variants.add(canonical_part)
    return variants


def _osm_key(osm_type: str | None, osm_id: int | None) -> tuple[str, int] | None:
    normalized_type = _normalize(osm_type)
    if not normalized_type or osm_id is None:
        return None
    return (normalized_type, osm_id)


def _infer_rank_from_row(
    *,
    location_rank: str | None,
    precision: str | None,
    city: str | None,
    region: str | None,
    country: str | None,
) -> str:
    normalized_rank = _normalize_rank(location_rank)
    if normalized_rank and normalized_rank != "unknown":
        return normalized_rank
    precision_value = _normalize(precision)
    if precision_value in {"city", "admin_region", "country", "continent", "ocean"}:
        return precision_value
    if city:
        return "city"
    if region:
        return "admin_region"
    if country:
        return "country"
    return "unknown"


def _query_targets(conn: Connection) -> list[GeometryTarget]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                bl.location_id,
                bl.normalized_location,
                bl.country,
                bl.region,
                bl.city,
                bl.precision,
                bl.location_rank,
                gl.osm_type,
                gl.osm_id
            FROM bi_locations bl
            LEFT JOIN geo_locations gl ON gl.id = bl.location_id
            ORDER BY bl.location_id ASC
            """
        )
        rows = cur.fetchall()

    targets: list[GeometryTarget] = []
    for row in rows:
        location_rank = _infer_rank_from_row(
            location_rank=_coerce_text(row[6]),
            precision=_coerce_text(row[5]),
            city=_coerce_text(row[4]),
            region=_coerce_text(row[3]),
            country=_coerce_text(row[2]),
        )
        if location_rank not in POLYGON_RANKS:
            continue
        targets.append(
            GeometryTarget(
                location_id=str(row[0]),
                location_name=str(row[1]),
                location_rank=location_rank,
                country_name=_coerce_text(row[2]),
                region_name=_coerce_text(row[3]),
                osm_type=_coerce_text(row[7]),
                osm_id=_coerce_int(row[8]),
            )
        )
    return targets


def _extract_alias_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _feature_aliases(properties: dict[str, Any], field_name: str, fallback: str | None = None) -> set[str]:
    values = _extract_alias_values(properties.get(field_name))
    if not values and fallback:
        values.append(fallback)
    return _name_variants(values)


def _dedupe_features(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[int] = set()
    for feature in features:
        key = id(feature)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(feature)
    return deduped


def _pick_unique_feature(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    unique = _dedupe_features(features)
    if len(unique) == 1:
        return unique[0]
    return None


def _index_source_features(
    source_features: list[dict[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, str], list[dict[str, Any]]],
    dict[tuple[str, str, str], list[dict[str, Any]]],
]:
    by_location_id: dict[str, dict[str, Any]] = {}
    by_osm: dict[tuple[str, int], dict[str, Any]] = {}
    by_rank_alias: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_region_pair: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    for feature in source_features:
        if not _feature_geometry_supported(feature):
            continue
        properties = feature.get("properties") or {}
        rank = _normalize_rank(_coerce_text(properties.get("location_rank")))
        if rank not in POLYGON_RANKS:
            continue

        location_id = _coerce_text(properties.get("location_id"))
        if location_id:
            by_location_id[location_id] = feature

        osm_key = _osm_key(
            _coerce_text(properties.get("osm_type")),
            _coerce_int(properties.get("osm_id")),
        )
        if osm_key is not None:
            by_osm[osm_key] = feature

        location_name = _coerce_text(properties.get("location_name")) or ""
        for alias in _feature_aliases(properties, "aliases", fallback=location_name):
            by_rank_alias.setdefault((rank, alias), []).append(feature)

        if rank == "admin_region":
            region_name = (
                _coerce_text(properties.get("region_name"))
                or _coerce_text(properties.get("location_name"))
                or ""
            )
            country_name = _coerce_text(properties.get("country_name")) or ""
            country_aliases = _feature_aliases(properties, "country_aliases", fallback=country_name)
            region_aliases = _feature_aliases(properties, "region_aliases", fallback=region_name)
            for country_alias in country_aliases:
                for region_alias in region_aliases:
                    by_region_pair.setdefault(("admin_region", country_alias, region_alias), []).append(feature)

    return by_location_id, by_osm, by_rank_alias, by_region_pair


def _target_aliases(values: list[str | None]) -> set[str]:
    return _name_variants([value for value in values if value])


def _select_feature_for_target(
    target: GeometryTarget,
    *,
    by_location_id: dict[str, dict[str, Any]],
    by_osm: dict[tuple[str, int], dict[str, Any]],
    by_rank_alias: dict[tuple[str, str], list[dict[str, Any]]],
    by_region_pair: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str]:
    exact = by_location_id.get(target.location_id)
    if exact is not None:
        return exact, "location_id"

    osm_key = _osm_key(target.osm_type, target.osm_id)
    if osm_key is not None:
        osm_match = by_osm.get(osm_key)
        if osm_match is not None:
            return osm_match, "osm_identity"

    if target.location_rank == "admin_region":
        country_aliases = _target_aliases([target.country_name])
        region_aliases = _target_aliases([target.region_name, target.location_name])
        pair_candidates: list[dict[str, Any]] = []
        for country_alias in country_aliases:
            for region_alias in region_aliases:
                pair_candidates.extend(by_region_pair.get(("admin_region", country_alias, region_alias), []))
        pair_match = _pick_unique_feature(pair_candidates)
        if pair_match is not None:
            return pair_match, "region_country_alias"

    ranked_aliases = _target_aliases([target.location_name])
    ranked_candidates: list[dict[str, Any]] = []
    for alias in ranked_aliases:
        ranked_candidates.extend(by_rank_alias.get((target.location_rank, alias), []))
    ranked_match = _pick_unique_feature(ranked_candidates)
    if ranked_match is not None:
        return ranked_match, "rank_alias"
    return None, "unmatched"


def _target_label(target: GeometryTarget) -> str:
    if target.location_rank == "admin_region":
        if target.country_name:
            return f"{target.region_name or target.location_name}, {target.country_name}"
        return target.region_name or target.location_name
    return target.location_name


def _rank_sort_value(rank: str) -> int:
    return RANK_ORDER.get(rank, 99)


def _store_boundaries_in_db(conn: Connection, features: list[dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bi_admin_boundaries")
        if not features:
            return
        rows: list[tuple[str, str, str]] = []
        for feature in features:
            properties = feature.get("properties") or {}
            location_id = _coerce_text(properties.get("location_id"))
            if not location_id:
                continue
            location_rank = _normalize_rank(_coerce_text(properties.get("location_rank")))
            payload = json.dumps(feature, ensure_ascii=False, separators=(",", ":"))
            rows.append((location_id, location_rank, payload))
        if not rows:
            return
        cur.executemany(
            """
            INSERT INTO bi_admin_boundaries (location_id, location_rank, feature_json)
            VALUES (%s::uuid, %s, %s::jsonb)
            """,
            rows,
        )


def build_admin_boundaries_asset(
    conn: Connection,
    *,
    source_path: Path | None = None,
    output_path: Path | None = None,
    coverage_path: Path | None = None,
) -> GeometryBuildResult:
    source = source_path or Path(os.getenv("DOCMAP_ADMIN_BOUNDARIES_SOURCE", str(_default_source_path())))
    output = output_path or Path(os.getenv("DOCMAP_ADMIN_BOUNDARIES_OUTPUT", str(_default_output_path())))
    coverage = coverage_path or Path(os.getenv("DOCMAP_ADMIN_BOUNDARIES_COVERAGE", str(_default_coverage_path())))

    targets = _query_targets(conn)
    if not source.exists():
        raise FileNotFoundError(f"Admin boundaries source dataset not found: {source}")

    raw = json.loads(source.read_text(encoding="utf-8"))
    source_features = list(raw.get("features") or [])
    by_location_id, by_osm, by_rank_alias, by_region_pair = _index_source_features(source_features)

    selected_features: list[dict[str, Any]] = []
    unmatched_by_rank: dict[str, list[str]] = {rank: [] for rank in POLYGON_RANKS}
    matched_by_rank: dict[str, int] = {rank: 0 for rank in POLYGON_RANKS}
    total_by_rank: dict[str, int] = {rank: 0 for rank in POLYGON_RANKS}

    for target in targets:
        total_by_rank[target.location_rank] = total_by_rank.get(target.location_rank, 0) + 1
        matched_feature, match_strategy = _select_feature_for_target(
            target,
            by_location_id=by_location_id,
            by_osm=by_osm,
            by_rank_alias=by_rank_alias,
            by_region_pair=by_region_pair,
        )
        if matched_feature is None:
            unmatched_by_rank.setdefault(target.location_rank, []).append(_target_label(target))
            continue

        geometry = matched_feature.get("geometry")
        if not isinstance(geometry, dict):
            unmatched_by_rank.setdefault(target.location_rank, []).append(_target_label(target))
            continue

        selected_features.append(
            {
                "type": "Feature",
                "properties": {
                    "location_id": target.location_id,
                    "location_rank": target.location_rank,
                    "location_name": target.location_name,
                    "country_name": target.country_name,
                    "region_name": target.region_name,
                    "match_strategy": match_strategy,
                },
                "geometry": geometry,
            }
        )
        matched_by_rank[target.location_rank] = matched_by_rank.get(target.location_rank, 0) + 1

    selected_features.sort(
        key=lambda item: (
            _rank_sort_value(_normalize_rank(_coerce_text(item["properties"].get("location_rank")))),
            _normalize(_coerce_text(item["properties"].get("country_name"))),
            _normalize(_coerce_text(item["properties"].get("region_name"))),
            _normalize(_coerce_text(item["properties"].get("location_name"))),
            _normalize(_coerce_text(item["properties"].get("location_id"))),
        )
    )

    _store_boundaries_in_db(conn, selected_features)

    output.parent.mkdir(parents=True, exist_ok=True)
    output_payload = {"type": "FeatureCollection", "features": selected_features}
    output.write_text(
        json.dumps(output_payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    rank_coverage: dict[str, dict[str, Any]] = {}
    for rank in POLYGON_RANKS:
        rank_coverage[rank] = {
            "targets": total_by_rank.get(rank, 0),
            "matched": matched_by_rank.get(rank, 0),
            "unmatched": len(unmatched_by_rank.get(rank, [])),
        }

    coverage.parent.mkdir(parents=True, exist_ok=True)
    coverage_payload = {
        "source_path": str(source),
        "output_path": str(output),
        "totals": {
            "targets": len(targets),
            "features_written": len(selected_features),
            "matched_targets": sum(matched_by_rank.values()),
            "matched_countries": matched_by_rank.get("country", 0),
            "matched_regions": matched_by_rank.get("admin_region", 0),
            "countries": total_by_rank.get("country", 0),
            "regions": total_by_rank.get("admin_region", 0),
        },
        "coverage_by_rank": rank_coverage,
        "unmatched": unmatched_by_rank,
    }
    coverage.write_text(json.dumps(coverage_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    logger.info(
        "analytics.admin_boundaries_built source=%s output=%s features=%s matched=%s total=%s",
        source,
        output,
        len(selected_features),
        sum(matched_by_rank.values()),
        len(targets),
    )
    return GeometryBuildResult(
        features_written=len(selected_features),
        matched_by_rank=matched_by_rank,
        total_by_rank=total_by_rank,
        output_path=output,
        coverage_path=coverage,
    )
