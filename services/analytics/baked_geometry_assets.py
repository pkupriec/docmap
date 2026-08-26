from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import mapbox_vector_tile
import mercantile
from mapbox_vector_tile import encoder
from psycopg import Connection

logger = logging.getLogger(__name__)

WORLD_BOUNDS = (-180.0, -85.05112878, 180.0, 85.05112878)
ZOOM_MIN_DEFAULT = 0
ZOOM_MAX_DEFAULT = 8
ZOOM_BANDS: dict[str, tuple[int, int]] = {
    "world": (0, 2),
    "regional": (3, 5),
    "local": (6, ZOOM_MAX_DEFAULT),
}
PRECISION_MODES: dict[str, dict[str, float]] = {
    "full_precise": {"world": 0.0, "regional": 0.0, "local": 0.0},
    "balanced_precise": {"world": 0.05, "regional": 0.01, "local": 0.002},
    "simplified": {"world": 0.2, "regional": 0.05, "local": 0.01},
    "primitive": {"world": 0.8, "regional": 0.2, "local": 0.05},
}
ARTIFACT_SCHEMA_VERSION = "v1"
_PROGRESS_LOG_INTERVAL = 250

BakedProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class BakedModeStats:
    mode: str
    tile_count: int
    byte_size: int
    tolerance_by_band: dict[str, float]
    path: Path


@dataclass(frozen=True)
class BakedGeometryBuildResult:
    version: str
    root_path: Path
    manifest_path: Path
    source_feature_count: int
    modes: dict[str, BakedModeStats]

    @property
    def total_tiles(self) -> int:
        return sum(mode.tile_count for mode in self.modes.values())


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_assets_root() -> Path:
    return _project_root() / "services" / "analytics" / "assets" / "presentation_geometry"


def _mode_alias(mode: str) -> str:
    normalized = str(mode or "").strip().lower().replace(" ", "_")
    aliases = {
        "full_precise": "full_precise",
        "balanced_precise": "balanced_precise",
        "simplified": "simplified",
        "primitive": "primitive",
        "full precise": "full_precise",
        "balanced precise": "balanced_precise",
    }
    return aliases.get(normalized, normalized)


def _zoom_band(zoom: int) -> str:
    for band, (z_min, z_max) in ZOOM_BANDS.items():
        if z_min <= zoom <= z_max:
            return band
    return "local"


def _query_boundary_features(conn: Connection) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT location_id::text, location_rank, feature_json
            FROM bi_admin_boundaries
            ORDER BY location_id ASC
            """
        )
        rows = cur.fetchall()

    features: list[dict[str, Any]] = []
    for location_id, location_rank, payload in rows:
        parsed: dict[str, Any]
        if isinstance(payload, dict):
            parsed = payload
        else:
            try:
                parsed = json.loads(payload)
            except Exception:
                continue
        geometry = parsed.get("geometry")
        if not isinstance(geometry, dict):
            continue
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        properties = parsed.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        location_name = str(properties.get("location_name") or location_id)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "location_id": str(location_id),
                    "location_rank": str(location_rank or properties.get("location_rank") or "unknown"),
                    "location_name": location_name,
                },
                "geometry": geometry,
            }
        )
    return features


def _geometry_bbox(geometry: dict[str, Any]) -> tuple[float, float, float, float] | None:
    lons: list[float] = []
    lats: list[float] = []

    def walk(node: Any) -> None:
        if isinstance(node, (list, tuple)) and node and isinstance(node[0], (int, float)):
            lons.append(float(node[0]))
            lats.append(float(node[1]))
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(geometry.get("coordinates"))
    if not lons:
        return None
    return (min(lons), min(lats), max(lons), max(lats))


def _quantize(value: float, tolerance: float) -> float:
    if tolerance <= 0:
        return float(value)
    return round(float(value) / tolerance) * tolerance


def _simplify_ring(ring: list[list[float]], tolerance: float) -> list[list[float]]:
    if tolerance <= 0 or len(ring) < 4:
        return [[float(point[0]), float(point[1])] for point in ring]

    simplified: list[list[float]] = []
    for point in ring:
        quantized = [_quantize(float(point[0]), tolerance), _quantize(float(point[1]), tolerance)]
        if not simplified or simplified[-1] != quantized:
            simplified.append(quantized)

    if simplified and simplified[0] != simplified[-1]:
        simplified.append(list(simplified[0]))

    if len(simplified) < 4:
        return [[float(point[0]), float(point[1])] for point in ring]
    return simplified


def _simplify_geometry(geometry: dict[str, Any], tolerance: float) -> dict[str, Any]:
    geometry_type = str(geometry.get("type") or "")
    coordinates = geometry.get("coordinates")
    if tolerance <= 0:
        return {
            "type": geometry_type,
            "coordinates": coordinates,
        }

    if geometry_type == "Polygon" and isinstance(coordinates, list):
        rings = [_simplify_ring(ring, tolerance) for ring in coordinates if isinstance(ring, list)]
        return {"type": "Polygon", "coordinates": rings}
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        polygons: list[list[list[list[float]]]] = []
        for polygon in coordinates:
            if not isinstance(polygon, list):
                continue
            polygons.append([_simplify_ring(ring, tolerance) for ring in polygon if isinstance(ring, list)])
        return {"type": "MultiPolygon", "coordinates": polygons}
    return geometry


def _tile_windows(zoom_min: int, zoom_max: int) -> list[tuple[int, int, int]]:
    tiles: list[tuple[int, int, int]] = []
    for zoom in range(zoom_min, zoom_max + 1):
        for tile in mercantile.tiles(*WORLD_BOUNDS, [zoom]):
            tiles.append((tile.z, tile.x, tile.y))
    return tiles


def _tile_feature_index(
    indexed_features: list[tuple[tuple[float, float, float, float], dict[str, Any]]],
    *,
    zoom_min: int,
    zoom_max: int,
) -> dict[tuple[int, int, int], tuple[int, ...]]:
    tile_to_feature_ids: dict[tuple[int, int, int], set[int]] = {}
    for feature_id, (bbox, _feature) in enumerate(indexed_features):
        west, south, east, north = bbox
        south = max(south, WORLD_BOUNDS[1])
        north = min(north, WORLD_BOUNDS[3])
        if south > north:
            continue
        for zoom in range(zoom_min, zoom_max + 1):
            for tile in mercantile.tiles(west, south, east, north, [zoom]):
                tile_key = (tile.z, tile.x, tile.y)
                tile_to_feature_ids.setdefault(tile_key, set()).add(feature_id)
    return {tile_key: tuple(sorted(feature_ids)) for tile_key, feature_ids in tile_to_feature_ids.items()}


def _artifact_version(features: list[dict[str, Any]], mode_tolerances: dict[str, dict[str, float]]) -> str:
    payload = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "mode_tolerances": mode_tolerances,
        "features": [
            {
                "location_id": feature["properties"]["location_id"],
                "location_rank": feature["properties"]["location_rank"],
                "location_name": feature["properties"]["location_name"],
                "geometry": feature["geometry"],
            }
            for feature in features
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()[:16]
    return f"{ARTIFACT_SCHEMA_VERSION}-{digest}"


def build_baked_geometry_assets(
    conn: Connection,
    *,
    assets_root: Path | None = None,
    zoom_min: int = ZOOM_MIN_DEFAULT,
    zoom_max: int = ZOOM_MAX_DEFAULT,
    mode_tolerances: dict[str, dict[str, float]] | None = None,
    on_tile_progress: BakedProgressCallback | None = None,
) -> BakedGeometryBuildResult:
    root = assets_root or Path(os.getenv("DOCMAP_PRESENTATION_BAKED_GEOMETRY_ROOT", str(_default_assets_root())))
    tolerances = mode_tolerances or PRECISION_MODES

    features = _query_boundary_features(conn)
    features.sort(key=lambda item: str(item["properties"]["location_id"]))
    version = _artifact_version(features, tolerances)

    version_root = root / version
    version_root.mkdir(parents=True, exist_ok=True)
    indexed: list[tuple[tuple[float, float, float, float], dict[str, Any]]] = []
    for feature in features:
        bbox = _geometry_bbox(feature["geometry"])
        if bbox is None:
            continue
        indexed.append((bbox, feature))
    tile_index = _tile_feature_index(indexed, zoom_min=zoom_min, zoom_max=zoom_max)
    tiles = sorted(tile_index.keys(), key=lambda item: (item[0], item[1], item[2]))

    mode_results: dict[str, BakedModeStats] = {}
    total_tile_jobs = len(tiles) * len(tolerances)
    processed_tile_jobs = 0
    if on_tile_progress:
        on_tile_progress(processed_tile_jobs, total_tile_jobs)

    for mode_name, tolerance_by_band in sorted(tolerances.items()):
        canonical_mode = _mode_alias(mode_name)
        mode_root = version_root / canonical_mode
        tile_count = 0
        total_bytes = 0

        for z, x, y in tiles:
            bounds = mercantile.bounds(x, y, z)
            west, south, east, north = bounds.west, bounds.south, bounds.east, bounds.north
            selected_rows: list[dict[str, Any]] = []
            band = _zoom_band(z)
            tolerance = float(tolerance_by_band.get(band, 0.0))

            for feature_id in tile_index.get((z, x, y), ()):
                _bbox, feature = indexed[feature_id]
                simplified_geometry = _simplify_geometry(feature["geometry"], tolerance=tolerance)
                selected_rows.append(
                    {
                        "id": feature["properties"]["location_id"],
                        "geometry": simplified_geometry,
                        "properties": {
                            "location_id": feature["properties"]["location_id"],
                            "location_rank": feature["properties"]["location_rank"],
                            "location_name": feature["properties"]["location_name"],
                        },
                    }
                )

            if not selected_rows:
                processed_tile_jobs += 1
                if on_tile_progress and (
                    processed_tile_jobs == total_tile_jobs
                    or processed_tile_jobs == 1
                    or processed_tile_jobs % _PROGRESS_LOG_INTERVAL == 0
                ):
                    on_tile_progress(processed_tile_jobs, total_tile_jobs)
                continue

            payload = mapbox_vector_tile.encode(
                [{"name": "boundaries", "features": selected_rows}],
                default_options={
                    "quantize_bounds": (west, south, east, north),
                    "extents": 4096,
                    "on_invalid_geometry": encoder.on_invalid_geometry_make_valid,
                    "check_winding_order": True,
                },
            )
            destination = mode_root / str(z) / str(x) / f"{y}.mvt"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            tile_count += 1
            total_bytes += len(payload)
            processed_tile_jobs += 1
            if on_tile_progress and (
                processed_tile_jobs == total_tile_jobs
                or processed_tile_jobs == 1
                or processed_tile_jobs % _PROGRESS_LOG_INTERVAL == 0
            ):
                on_tile_progress(processed_tile_jobs, total_tile_jobs)

        mode_results[canonical_mode] = BakedModeStats(
            mode=canonical_mode,
            tile_count=tile_count,
            byte_size=total_bytes,
            tolerance_by_band={
                "world": float(tolerance_by_band.get("world", 0.0)),
                "regional": float(tolerance_by_band.get("regional", 0.0)),
                "local": float(tolerance_by_band.get("local", 0.0)),
            },
            path=mode_root,
        )

    manifest_payload = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "version": version,
        "source_feature_count": len(features),
        "source_table": "bi_admin_boundaries",
        "tile_format": "mvt_zxy_directory",
        "zoom_min": zoom_min,
        "zoom_max": zoom_max,
        "modes": {
            mode: {
                "path": str(result.path.relative_to(root)),
                "tile_count": result.tile_count,
                "byte_size": result.byte_size,
                "tolerance_by_zoom_band": result.tolerance_by_band,
            }
            for mode, result in sorted(mode_results.items())
        },
    }
    manifest_path = version_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    current_pointer = root / "current.json"
    current_pointer.write_text(
        json.dumps(
            {
                "schema_version": ARTIFACT_SCHEMA_VERSION,
                "current_version": version,
                "manifest": str(manifest_path.relative_to(root)),
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    logger.info(
        "analytics.baked_geometry_assets_built root=%s version=%s source_features=%s total_tiles=%s",
        root,
        version,
        len(features),
        sum(item.tile_count for item in mode_results.values()),
    )
    return BakedGeometryBuildResult(
        version=version,
        root_path=root,
        manifest_path=manifest_path,
        source_feature_count=len(features),
        modes=mode_results,
    )
