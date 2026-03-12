from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from psycopg import Connection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeometryTargetCountry:
    key: str
    label: str


@dataclass(frozen=True)
class GeometryTargetRegion:
    country_key: str
    country_label: str
    region_key: str
    region_label: str


@dataclass(frozen=True)
class GeometryBuildResult:
    features_written: int
    matched_countries: int
    matched_regions: int
    total_countries: int
    total_regions: int
    output_path: Path
    coverage_path: Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_source_path() -> Path:
    return _project_root() / "services" / "analytics" / "assets" / "admin_boundaries_source.geojson"


def _default_output_path() -> Path:
    return _project_root() / "services" / "presentation" / "frontend" / "src" / "assets" / "admin_boundaries.geojson"


def _default_coverage_path() -> Path:
    return _project_root() / "services" / "presentation" / "frontend" / "src" / "assets" / "admin_boundaries.coverage.json"


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _feature_geometry_supported(feature: dict[str, Any]) -> bool:
    geometry = feature.get("geometry") or {}
    geometry_type = str(geometry.get("type") or "")
    return geometry_type in {"Polygon", "MultiPolygon"}


def _query_targets(conn: Connection) -> tuple[list[GeometryTargetCountry], list[GeometryTargetRegion]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                LOWER(TRIM(bl.country)) AS country_key,
                MIN(bl.country) AS country_label
            FROM bi_locations bl
            WHERE bl.country IS NOT NULL
              AND TRIM(bl.country) <> ''
            GROUP BY LOWER(TRIM(bl.country))
            ORDER BY LOWER(TRIM(bl.country)) ASC
            """
        )
        countries = [
            GeometryTargetCountry(key=str(row[0]), label=str(row[1]))
            for row in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT
                LOWER(TRIM(bl.country)) AS country_key,
                MIN(bl.country) AS country_label,
                LOWER(TRIM(bl.region)) AS region_key,
                MIN(bl.region) AS region_label
            FROM bi_locations bl
            WHERE bl.country IS NOT NULL
              AND TRIM(bl.country) <> ''
              AND bl.region IS NOT NULL
              AND TRIM(bl.region) <> ''
            GROUP BY LOWER(TRIM(bl.country)), LOWER(TRIM(bl.region))
            ORDER BY LOWER(TRIM(bl.country)) ASC, LOWER(TRIM(bl.region)) ASC
            """
        )
        regions = [
            GeometryTargetRegion(
                country_key=str(row[0]),
                country_label=str(row[1]),
                region_key=str(row[2]),
                region_label=str(row[3]),
            )
            for row in cur.fetchall()
        ]
    return countries, regions


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

    countries, regions = _query_targets(conn)
    if not source.exists():
        raise FileNotFoundError(f"Admin boundaries source dataset not found: {source}")

    raw = json.loads(source.read_text(encoding="utf-8"))
    source_features = list(raw.get("features") or [])

    country_by_key: dict[str, dict[str, Any]] = {}
    region_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    region_by_name_candidates: dict[str, list[dict[str, Any]]] = {}

    for feature in source_features:
        if not _feature_geometry_supported(feature):
            continue
        properties = feature.get("properties") or {}
        rank = _normalize(str(properties.get("location_rank") or ""))
        location_name = str(properties.get("location_name") or "")
        country_name = str(properties.get("country_name") or "")
        region_name = str(properties.get("region_name") or "")

        if rank == "country":
            country_key = _normalize(country_name or location_name)
            if country_key:
                country_by_key[country_key] = feature
            continue

        if rank != "region":
            continue

        normalized_country = _normalize(country_name)
        normalized_region = _normalize(region_name or location_name)
        if normalized_country and normalized_region:
            region_by_pair[(normalized_country, normalized_region)] = feature
        if normalized_region:
            region_by_name_candidates.setdefault(normalized_region, []).append(feature)

    selected_features: list[dict[str, Any]] = []
    used_feature_keys: set[str] = set()
    unmatched_countries: list[str] = []
    unmatched_regions: list[str] = []
    matched_countries = 0
    matched_regions = 0

    for country in countries:
        feature = country_by_key.get(country.key)
        if feature is None:
            unmatched_countries.append(country.label)
            continue
        unique_key = f"country:{country.key}"
        if unique_key in used_feature_keys:
            continue
        used_feature_keys.add(unique_key)
        selected_features.append(
            {
                "type": "Feature",
                "properties": {
                    "location_rank": "country",
                    "location_name": country.label,
                    "country_name": country.label,
                },
                "geometry": feature["geometry"],
            }
        )
        matched_countries += 1

    for region in regions:
        feature = region_by_pair.get((region.country_key, region.region_key))
        if feature is None:
            candidates = region_by_name_candidates.get(region.region_key, [])
            if len(candidates) == 1:
                feature = candidates[0]
        if feature is None:
            unmatched_regions.append(f"{region.region_label}, {region.country_label}")
            continue
        unique_key = f"region:{region.country_key}:{region.region_key}"
        if unique_key in used_feature_keys:
            continue
        used_feature_keys.add(unique_key)
        selected_features.append(
            {
                "type": "Feature",
                "properties": {
                    "location_rank": "region",
                    "location_name": region.region_label,
                    "country_name": region.country_label,
                    "region_name": region.region_label,
                },
                "geometry": feature["geometry"],
            }
        )
        matched_regions += 1

    selected_features.sort(
        key=lambda item: (
            0 if item["properties"]["location_rank"] == "country" else 1,
            _normalize(str(item["properties"].get("country_name") or "")),
            _normalize(str(item["properties"].get("location_name") or "")),
        )
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output_payload = {"type": "FeatureCollection", "features": selected_features}
    output.write_text(json.dumps(output_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    coverage.parent.mkdir(parents=True, exist_ok=True)
    coverage_payload = {
        "source_path": str(source),
        "output_path": str(output),
        "totals": {
            "countries": len(countries),
            "regions": len(regions),
            "matched_countries": matched_countries,
            "matched_regions": matched_regions,
            "features_written": len(selected_features),
        },
        "unmatched": {
            "countries": unmatched_countries,
            "regions": unmatched_regions,
        },
    }
    coverage.write_text(json.dumps(coverage_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    logger.info(
        "analytics.admin_boundaries_built source=%s output=%s features=%s matched_countries=%s/%s matched_regions=%s/%s",
        source,
        output,
        len(selected_features),
        matched_countries,
        len(countries),
        matched_regions,
        len(regions),
    )
    return GeometryBuildResult(
        features_written=len(selected_features),
        matched_countries=matched_countries,
        matched_regions=matched_regions,
        total_countries=len(countries),
        total_regions=len(regions),
        output_path=output,
        coverage_path=coverage,
    )
