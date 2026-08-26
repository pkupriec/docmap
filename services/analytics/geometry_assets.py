from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import requests
from psycopg import Connection

logger = logging.getLogger(__name__)

BASE_POLYGON_RANKS = ("admin_region", "country", "continent", "ocean", "national_park", "desert")
_ADMIN_LEVEL_PATTERN = re.compile(r"^admin_level_(\d+)$")
RANK_ALIAS = {
    "region": "admin_region",
    "admin_region": "admin_region",
    "country": "country",
    "continent": "continent",
    "ocean": "ocean",
    "national_park": "national_park",
    "desert": "desert",
    "city": "city",
    "unknown": "unknown",
}
RANK_ORDER = {
    "country": 0,
    "admin_region": 1,
    "continent": 2,
    "ocean": 3,
    "national_park": 4,
    "desert": 5,
    "unknown": 99,
}
NAME_SPLIT_RE = re.compile(r"[|/;]+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
BoundaryProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class GeometryTarget:
    location_id: str
    canonical_id: str | None
    location_name: str
    location_rank: str
    country_name: str | None
    region_name: str | None
    document_count: int
    osm_type: str | None
    osm_id: int | None
    osm_admin_level: int | None
    boundary_intent: bool
    geocode_candidates: list[dict[str, Any]]
    osm_category: str | None
    osm_place_type: str | None
    canonical_resolution_method: str | None
    canonical_confidence: int | None


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
    if _ADMIN_LEVEL_PATTERN.match(normalized):
        return normalized
    return RANK_ALIAS.get(normalized, normalized or "unknown")


def _is_polygon_rank(rank: str) -> bool:
    normalized = _normalize_rank(rank)
    return normalized in BASE_POLYGON_RANKS or _ADMIN_LEVEL_PATTERN.match(normalized) is not None


def _feature_geometry_supported(feature: dict[str, Any]) -> bool:
    geometry = feature.get("geometry") or {}
    geometry_type = str(geometry.get("type") or "")
    return geometry_type in {"Polygon", "MultiPolygon"}


def _parse_feature_payload(payload: object) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        parsed = payload
    elif isinstance(payload, (str, bytes, bytearray)):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
    else:
        return None
    if not _feature_geometry_supported(parsed):
        return None
    return parsed


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
    precision_value = _normalize(precision)
    if precision_value in {"city", "admin_region", "country", "continent", "ocean"}:
        return precision_value
    if normalized_rank == "admin_level_2":
        return "country"
    if _ADMIN_LEVEL_PATTERN.match(normalized_rank):
        return "admin_region"
    if normalized_rank and normalized_rank != "unknown":
        return normalized_rank
    if city:
        return "city"
    if region:
        return "admin_region"
    if country:
        return "country"
    return "unknown"


def _entity_class_for_rank(rank: str) -> str:
    normalized = _normalize_rank(rank)
    if normalized in {"country", "admin_region", "continent"} or _ADMIN_LEVEL_PATTERN.match(normalized):
        return "admin"
    if normalized == "national_park":
        return "park"
    if normalized == "desert":
        return "desert"
    if normalized == "ocean":
        return "ocean"
    return "other"


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
                bl.document_count,
                bl.precision,
                bl.location_rank,
                gl.osm_type,
                gl.osm_id,
                gl.osm_admin_level,
                gl.boundary_intent,
                gl.geocode_candidates,
                gl.osm_category,
                gl.osm_place_type,
                gl.canonical_id,
                gl.canonical_resolution_method,
                gl.canonical_confidence
            FROM bi_locations bl
            LEFT JOIN geo_locations gl ON gl.id = bl.location_id
            ORDER BY bl.location_id ASC
            """
        )
        rows = cur.fetchall()

    targets: list[GeometryTarget] = []
    for row in rows:
        location_rank = _infer_rank_from_row(
            location_rank=_coerce_text(row[7]),
            precision=_coerce_text(row[6]),
            city=_coerce_text(row[4]),
            region=_coerce_text(row[3]),
            country=_coerce_text(row[2]),
        )
        document_count_raw = row[5]
        if isinstance(document_count_raw, int):
            document_count = document_count_raw
        else:
            document_count = int(document_count_raw or 0)
        targets.append(
            GeometryTarget(
                location_id=str(row[0]),
                location_name=str(row[1]),
                location_rank=location_rank,
                country_name=_coerce_text(row[2]),
                region_name=_coerce_text(row[3]),
                document_count=document_count,
                osm_type=_coerce_text(row[8]),
                osm_id=_coerce_int(row[9]),
                osm_admin_level=_coerce_int(row[10]),
                boundary_intent=bool(row[11]) if row[11] is not None else False,
                geocode_candidates=list(row[12]) if isinstance(row[12], list) else [],
                osm_category=_coerce_text(row[13]),
                osm_place_type=_coerce_text(row[14]),
                canonical_id=_coerce_text(row[15]),
                canonical_resolution_method=_coerce_text(row[16]),
                canonical_confidence=_coerce_int(row[17]),
            )
        )
    targets.sort(key=lambda item: item.location_id)
    return targets


def _target_alias_key(target: GeometryTarget) -> tuple[str, str, str] | None:
    if target.location_rank == "country":
        # Country dedupe must be keyed by the target display identity first.
        # `country_name` can legitimately collide for distinct normalized country targets
        # (for example "Democratic Republic of the Congo" vs "Congo"), and collapsing
        # those targets drops valid per-location boundaries in presentation.
        country_key = _normalize(target.location_name) or _normalize(target.country_name)
        if country_key:
            return ("country", country_key, "")
    if target.location_rank == "admin_region":
        country_key = _normalize(target.country_name)
        region_key = _normalize(target.region_name or target.location_name)
        if country_key and region_key:
            return ("admin_region", country_key, region_key)
    return None


def _target_priority(target: GeometryTarget) -> tuple[int, int, int, int, str]:
    has_canonical = int(bool(target.canonical_id))
    has_osm_identity = int(_osm_key(target.osm_type, target.osm_id) is not None)
    canonical_confidence = int(target.canonical_confidence or 0)
    return (
        has_canonical,
        canonical_confidence,
        has_osm_identity,
        int(target.document_count),
        target.location_id,
    )


def _dedupe_alias_targets(targets: list[GeometryTarget]) -> list[GeometryTarget]:
    # Phase 19 direct cutover removes lossy alias dedupe: distinct geocoded targets
    # remain distinct geometry targets even if aliases collide.
    return sorted(targets, key=lambda item: item.location_id)


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


def _merge_feature_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    unique = _dedupe_features(features)
    if not unique:
        return None
    if len(unique) == 1:
        return unique[0]

    merged_coordinates: list[list[list[list[float]]]] = []
    template_feature: dict[str, Any] | None = None
    for feature in unique:
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            return None
        geometry_type = str(geometry.get("type") or "")
        coordinates = geometry.get("coordinates")
        if geometry_type == "Polygon":
            if not isinstance(coordinates, list):
                return None
            merged_coordinates.append(coordinates)
        elif geometry_type == "MultiPolygon":
            if not isinstance(coordinates, list):
                return None
            merged_coordinates.extend(coordinates)
        else:
            return None
        if template_feature is None:
            template_feature = feature

    if template_feature is None:
        return None
    return {
        "type": "Feature",
        "properties": dict(template_feature.get("properties") or {}),
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": merged_coordinates,
        },
    }


def _candidate_osm_keys(target: GeometryTarget) -> list[tuple[str, int]]:
    keys: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    if target.geocode_candidates:
        ordered = sorted(
            target.geocode_candidates,
            key=lambda item: (
                0 if _normalize(_coerce_text(item.get("role"))) == "boundary" else 1,
                _normalize(_coerce_text(item.get("osm_type"))),
                int(_coerce_int(item.get("osm_id")) or 0),
            ),
        )
        for candidate in ordered:
            key = _osm_key(_coerce_text(candidate.get("osm_type")), _coerce_int(candidate.get("osm_id")))
            if key is None or key in seen:
                continue
            seen.add(key)
            keys.append(key)
    fallback = _osm_key(target.osm_type, target.osm_id)
    if fallback is not None and fallback not in seen:
        keys.append(fallback)
    return keys


def _osm_lookup_url(osm_type: str, osm_id: int) -> str:
    prefix = {"relation": "R", "way": "W", "node": "N"}.get(osm_type.lower())
    if prefix is None:
        raise ValueError(f"unsupported osm_type: {osm_type}")
    return (
        "https://nominatim.openstreetmap.org/lookup"
        f"?osm_ids={prefix}{osm_id}&format=jsonv2&polygon_geojson=1"
    )


def _fetch_osm_feature(osm_type: str, osm_id: int) -> dict[str, Any] | None:
    response = requests.get(
        _osm_lookup_url(osm_type, osm_id),
        headers={"User-Agent": "docmap-analytics/0.1"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload:
        return None
    row = payload[0]
    if not isinstance(row, dict):
        return None
    geometry = row.get("geojson")
    if not isinstance(geometry, dict):
        return None
    if str(geometry.get("type") or "") not in {"Polygon", "MultiPolygon"}:
        return None
    return {
        "type": "Feature",
        "properties": {
            "osm_type": osm_type,
            "osm_id": osm_id,
            "location_rank": _normalize_rank(_coerce_text(row.get("addresstype"))),
            "location_name": _coerce_text(row.get("name")) or _coerce_text(row.get("display_name")) or "",
        },
        "geometry": geometry,
    }


def _allow_live_osm_lookup() -> bool:
    value = str(os.getenv("DOCMAP_ADMIN_BOUNDARIES_ALLOW_LIVE_LOOKUP", "0")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _index_source_features(
    source_features: list[dict[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, str], list[dict[str, Any]]],
    dict[tuple[str, str, str], list[dict[str, Any]]],
]:
    by_location_id: dict[str, dict[str, Any]] = {}
    by_canonical_id: dict[str, dict[str, Any]] = {}
    by_osm: dict[tuple[str, int], dict[str, Any]] = {}
    by_rank_alias: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_region_pair: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    for feature in source_features:
        if not _feature_geometry_supported(feature):
            continue
        properties = feature.get("properties") or {}
        rank = _normalize_rank(_coerce_text(properties.get("location_rank")))
        if not _is_polygon_rank(rank):
            continue

        location_id = _coerce_text(properties.get("location_id"))
        if location_id:
            by_location_id[location_id] = feature

        canonical_id = _coerce_text(properties.get("canonical_id"))
        if canonical_id:
            by_canonical_id[canonical_id] = feature

        osm_key = _osm_key(
            _coerce_text(properties.get("osm_type")),
            _coerce_int(properties.get("osm_id")),
        )
        if osm_key is not None:
            by_osm[osm_key] = feature

        location_name = _coerce_text(properties.get("location_name")) or ""
        alias_field = "safe_aliases" if rank in {"country", "admin_region"} else "aliases"
        for alias in _feature_aliases(properties, alias_field, fallback=location_name):
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

    return by_location_id, by_canonical_id, by_osm, by_rank_alias, by_region_pair


def _target_aliases(values: list[str | None]) -> set[str]:
    return _name_variants([value for value in values if value])


def _select_feature_for_target(
    target: GeometryTarget,
    *,
    by_location_id: dict[str, dict[str, Any]],
    by_canonical_id: dict[str, dict[str, Any]],
    by_osm: dict[tuple[str, int], dict[str, Any]],
    by_rank_alias: dict[tuple[str, str], list[dict[str, Any]]],
    by_region_pair: dict[tuple[str, str, str], list[dict[str, Any]]],
    allow_live_lookup: bool = False,
) -> tuple[dict[str, Any] | None, str]:
    exact = by_location_id.get(target.location_id)
    if exact is not None:
        return exact, "location_id"

    if target.canonical_id:
        canonical_match = by_canonical_id.get(target.canonical_id)
        if canonical_match is not None:
            return canonical_match, "canonical_id"

    candidate_osm_keys = _candidate_osm_keys(target)
    for candidate_key in candidate_osm_keys:
        osm_match = by_osm.get(candidate_key)
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
    if target.location_rank == "ocean":
        merged_ocean_match = _merge_feature_geometries(ranked_candidates)
        if merged_ocean_match is not None:
            return merged_ocean_match, "rank_alias_merged"
    ranked_match = _pick_unique_feature(ranked_candidates)
    if ranked_match is not None:
        return ranked_match, "rank_alias"

    if target.location_rank == "country":
        country_aliases = _target_aliases([target.country_name])
        country_candidates: list[dict[str, Any]] = []
        for alias in country_aliases:
            country_candidates.extend(by_rank_alias.get(("country", alias), []))
        country_match = _pick_unique_feature(country_candidates)
        if country_match is not None:
            return country_match, "country_alias"
    if allow_live_lookup:
        for candidate_key in candidate_osm_keys:
            try:
                osm_feature = _fetch_osm_feature(candidate_key[0], candidate_key[1])
            except requests.RequestException:
                logger.warning(
                    "analytics.osm_lookup_failed osm_type=%s osm_id=%s location_id=%s",
                    candidate_key[0],
                    candidate_key[1],
                    target.location_id,
                )
                continue
            if osm_feature is not None:
                return osm_feature, "osm_live_identity"

    if not target.canonical_id and not candidate_osm_keys:
        return None, "impossible_missing_upstream_data"
    return None, "possible_but_unmatched"


def _target_label(target: GeometryTarget) -> str:
    if target.location_rank == "admin_region":
        if target.country_name:
            return f"{target.region_name or target.location_name}, {target.country_name}"
        return target.region_name or target.location_name
    return target.location_name


def _rank_sort_value(rank: str) -> int:
    normalized = _normalize_rank(rank)
    admin_match = _ADMIN_LEVEL_PATTERN.match(normalized)
    if admin_match is not None:
        return 10 + int(admin_match.group(1))
    return RANK_ORDER.get(normalized, 99)


def _iter_geometry_positions(geometry: object):
    if not isinstance(geometry, dict):
        return
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        for ring in coordinates:
            if not isinstance(ring, list):
                continue
            for point in ring:
                if (
                    isinstance(point, list)
                    and len(point) >= 2
                    and isinstance(point[0], (int, float))
                    and isinstance(point[1], (int, float))
                ):
                    yield float(point[0]), float(point[1])
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        for polygon in coordinates:
            if not isinstance(polygon, list):
                continue
            for ring in polygon:
                if not isinstance(ring, list):
                    continue
                for point in ring:
                    if (
                        isinstance(point, list)
                        and len(point) >= 2
                        and isinstance(point[0], (int, float))
                        and isinstance(point[1], (int, float))
                    ):
                        yield float(point[0]), float(point[1])


def _feature_envelope(feature: dict[str, Any]) -> tuple[float, float, float, float] | None:
    positions = list(_iter_geometry_positions(feature.get("geometry")))
    if not positions:
        return None
    longitudes = [lon for lon, _ in positions]
    latitudes = [lat for _, lat in positions]
    return (min(longitudes), min(latitudes), max(longitudes), max(latitudes))


def _store_boundaries_in_db(conn: Connection, features: list[dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE bi_admin_boundaries")
        if not features:
            return
        rows: list[tuple[str, str, str, float, float, float, float]] = []
        for feature in features:
            properties = feature.get("properties") or {}
            location_id = _coerce_text(properties.get("location_id"))
            if not location_id:
                continue
            location_rank = _normalize_rank(_coerce_text(properties.get("location_rank")))
            envelope = _feature_envelope(feature)
            if envelope is None:
                continue
            payload = json.dumps(feature, ensure_ascii=False, separators=(",", ":"))
            rows.append((location_id, location_rank, payload, *envelope))
        if not rows:
            return
        cur.executemany(
            """
            INSERT INTO bi_admin_boundaries (
                location_id,
                location_rank,
                feature_json,
                min_lon,
                min_lat,
                max_lon,
                max_lat
            )
            VALUES (%s::uuid, %s, %s::jsonb, %s, %s, %s, %s)
            """,
            rows,
        )


def build_admin_boundaries_asset(
    conn: Connection,
    *,
    source_path: Path | None = None,
    output_path: Path | None = None,
    coverage_path: Path | None = None,
    on_target_progress: BoundaryProgressCallback | None = None,
) -> GeometryBuildResult:
    source = source_path or Path(os.getenv("DOCMAP_ADMIN_BOUNDARIES_SOURCE", str(_default_source_path())))
    output = output_path or Path(os.getenv("DOCMAP_ADMIN_BOUNDARIES_OUTPUT", str(_default_output_path())))
    coverage = coverage_path or Path(os.getenv("DOCMAP_ADMIN_BOUNDARIES_COVERAGE", str(_default_coverage_path())))

    targets = _query_targets(conn)
    if not source.exists():
        raise FileNotFoundError(f"Admin boundaries source dataset not found: {source}")

    raw = json.loads(source.read_text(encoding="utf-8"))
    source_features = list(raw.get("features") or [])
    by_location_id, by_canonical_id, by_osm, by_rank_alias, by_region_pair = _index_source_features(source_features)
    allow_live_lookup = _allow_live_osm_lookup()

    selected_features: list[dict[str, Any]] = []
    unmatched_by_rank: dict[str, list[str]] = {}
    matched_by_rank: dict[str, int] = {}
    total_by_rank: dict[str, int] = {}
    unmatched_by_reason: dict[str, int] = {}
    unmatched_by_class: dict[str, int] = {}
    match_strategy_counts: dict[str, int] = {}

    total_targets = len(targets)
    if on_target_progress:
        on_target_progress(0, total_targets)

    for index, target in enumerate(targets, start=1):
        total_by_rank[target.location_rank] = total_by_rank.get(target.location_rank, 0) + 1
        matched_feature, match_strategy = _select_feature_for_target(
            target,
            by_location_id=by_location_id,
            by_canonical_id=by_canonical_id,
            by_osm=by_osm,
            by_rank_alias=by_rank_alias,
            by_region_pair=by_region_pair,
            allow_live_lookup=allow_live_lookup,
        )
        if matched_feature is None:
            unmatched_by_rank.setdefault(target.location_rank, []).append(_target_label(target))
            unmatched_by_reason[match_strategy] = unmatched_by_reason.get(match_strategy, 0) + 1
            entity_class = _entity_class_for_rank(target.location_rank)
            unmatched_by_class[entity_class] = unmatched_by_class.get(entity_class, 0) + 1
            if on_target_progress and (index == 1 or index % 100 == 0 or index == total_targets):
                on_target_progress(index, total_targets)
            continue

        geometry = matched_feature.get("geometry")
        if not isinstance(geometry, dict):
            unmatched_by_rank.setdefault(target.location_rank, []).append(_target_label(target))
            unmatched_by_reason["invalid_geometry"] = unmatched_by_reason.get("invalid_geometry", 0) + 1
            if on_target_progress and (index == 1 or index % 100 == 0 or index == total_targets):
                on_target_progress(index, total_targets)
            continue

        match_strategy_counts[match_strategy] = match_strategy_counts.get(match_strategy, 0) + 1
        selected_features.append(
            {
                "type": "Feature",
                "properties": {
                    "location_id": target.location_id,
                    "canonical_id": target.canonical_id,
                    "location_rank": target.location_rank,
                    "location_name": target.location_name,
                    "country_name": target.country_name,
                    "region_name": target.region_name,
                    "match_strategy": match_strategy,
                    "entity_class": _entity_class_for_rank(target.location_rank),
                },
                "geometry": geometry,
            }
        )
        matched_by_rank[target.location_rank] = matched_by_rank.get(target.location_rank, 0) + 1
        if on_target_progress and (index == 1 or index % 100 == 0 or index == total_targets):
            on_target_progress(index, total_targets)

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
    all_ranks = sorted(set(total_by_rank.keys()) | set(matched_by_rank.keys()) | set(unmatched_by_rank.keys()))
    for rank in all_ranks:
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
        "match_strategy_counts": match_strategy_counts,
        "unmatched_by_reason": unmatched_by_reason,
        "unmatched_by_class": unmatched_by_class,
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


def backfill_merged_generic_ocean_boundaries(
    conn: Connection,
    *,
    source_path: Path | None = None,
) -> int:
    source = source_path or Path(os.getenv("DOCMAP_ADMIN_BOUNDARIES_SOURCE", str(_default_source_path())))
    if not source.exists():
        raise FileNotFoundError(f"Admin boundaries source dataset not found: {source}")

    raw = json.loads(source.read_text(encoding="utf-8"))
    source_features = [
        feature
        for feature in list(raw.get("features") or [])
        if _normalize_rank(_coerce_text((feature.get("properties") or {}).get("location_rank"))) == "ocean"
        and _feature_geometry_supported(feature)
    ]

    ocean_sources_by_name: dict[str, list[dict[str, Any]]] = {}
    for feature in source_features:
        props = feature.get("properties") or {}
        location_name = _coerce_text(props.get("location_name")) or ""
        for alias in _feature_aliases(props, "aliases", fallback=location_name):
            ocean_sources_by_name.setdefault(alias, []).append(feature)

    updated_rows = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT location_id::text, feature_json
            FROM bi_admin_boundaries
            WHERE location_rank = 'ocean'
            ORDER BY location_id ASC
            """
        )
        rows = cur.fetchall()

        for location_id, payload in rows:
            parsed = _parse_feature_payload(payload)
            if parsed is None:
                continue
            properties = parsed.get("properties")
            if not isinstance(properties, dict):
                continue
            location_name = _normalize(_coerce_text(properties.get("location_name")))
            if not location_name:
                continue
            matched_sources = _dedupe_features(ocean_sources_by_name.get(location_name, []))
            if len(matched_sources) <= 1:
                continue
            merged_feature = _merge_feature_geometries(matched_sources)
            if merged_feature is None:
                continue
            parsed["geometry"] = merged_feature["geometry"]
            properties["match_strategy"] = "rank_alias_merged_backfill"
            envelope = _feature_envelope(parsed)
            if envelope is None:
                continue
            cur.execute(
                """
                UPDATE bi_admin_boundaries
                SET
                    feature_json = %s::jsonb,
                    min_lon = %s,
                    min_lat = %s,
                    max_lon = %s,
                    max_lat = %s
                WHERE location_id = %s::uuid
                """,
                (json.dumps(parsed, ensure_ascii=False, separators=(",", ":")), *envelope, location_id),
            )
            updated_rows += 1

    return updated_rows
