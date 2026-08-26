from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

import mapbox_vector_tile
import mercantile
from mapbox_vector_tile import encoder
from pmtiles.reader import MmapSource, Reader
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer


SCENARIO_TILE_WINDOWS: dict[str, dict[str, Any]] = {
    "low_zoom_world": {"bbox": (-180.0, -30.0, 180.0, 60.0), "zoom": 2},
    "regional_europe": {"bbox": (0.0, 24.0, 60.0, 48.0), "zoom": 4},
    "regional_europe_pan": {"bbox": (20.0, 24.0, 60.0, 48.0), "zoom": 4},
    "local_focus": {"bbox": (8.0, 42.0, 32.0, 60.0), "zoom": 6},
}


def _geometry_bbox(geometry: dict[str, Any]) -> tuple[float, float, float, float] | None:
    longitudes: list[float] = []
    latitudes: list[float] = []

    def walk(value: Any) -> None:
        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (int, float)):
            longitudes.append(float(value[0]))
            latitudes.append(float(value[1]))
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(geometry.get("coordinates"))
    if not longitudes:
        return None
    return (min(longitudes), min(latitudes), max(longitudes), max(latitudes))


def _decode_tile(blob: bytes) -> dict[str, Any]:
    return mapbox_vector_tile.decode(
        blob,
        default_options={"transformer": lambda x, y: (x, y)},
    )


def _collect_tiles() -> list[tuple[int, int, int]]:
    tiles: set[tuple[int, int, int]] = set()
    for window in SCENARIO_TILE_WINDOWS.values():
        for tile in mercantile.tiles(*window["bbox"], [window["zoom"]]):
            tiles.add((tile.z, tile.x, tile.y))
    return sorted(tiles)


class CountingSource:
    def __init__(self, path: Path) -> None:
        self._handle = path.open("rb")
        self._reader = MmapSource(self._handle)
        self.bytes_read = 0
        self.read_calls = 0

    def get_bytes(self, offset: int, length: int) -> bytes:
        self.read_calls += 1
        self.bytes_read += length
        return self._reader(offset, length)

    def close(self) -> None:
        self._handle.close()


def compare_formats(
    *,
    source_geojson_path: Path,
    workspace_path: Path,
    runs: int,
) -> dict[str, Any]:
    source_payload = json.loads(source_geojson_path.read_text(encoding="utf-8"))
    indexed_features: list[tuple[tuple[float, float, float, float], dict[str, Any]]] = []
    for feature in source_payload.get("features", []):
        geometry = feature.get("geometry") or {}
        bbox = _geometry_bbox(geometry)
        if bbox is None:
            continue
        indexed_features.append((bbox, feature))

    tiles = _collect_tiles()
    zxy_dir = workspace_path / "zxy"
    zxy_dir.mkdir(parents=True, exist_ok=True)
    pmtiles_path = workspace_path / "boundaries.pmtiles"

    for old_file in zxy_dir.rglob("*.mvt"):
        old_file.unlink()
    if pmtiles_path.exists():
        pmtiles_path.unlink()

    tile_payloads: dict[tuple[int, int, int], bytes] = {}
    for z, x, y in tiles:
        bounds = mercantile.bounds(x, y, z)
        west, south, east, north = bounds.west, bounds.south, bounds.east, bounds.north
        feature_rows: list[dict[str, Any]] = []
        for (min_lon, min_lat, max_lon, max_lat), feature in indexed_features:
            if max_lon < west or min_lon > east or max_lat < south or min_lat > north:
                continue
            feature_rows.append(
                {
                    "geometry": feature.get("geometry"),
                    "properties": feature.get("properties"),
                    "id": (feature.get("properties") or {}).get("location_id"),
                }
            )
        tile_payloads[(z, x, y)] = mapbox_vector_tile.encode(
            [{"name": "boundaries", "features": feature_rows}],
            default_options={
                "quantize_bounds": (west, south, east, north),
                "extents": 4096,
                "on_invalid_geometry": encoder.on_invalid_geometry_make_valid,
                "check_winding_order": True,
            },
        )

    for (z, x, y), payload in tile_payloads.items():
        tile_dir = zxy_dir / str(z) / str(x)
        tile_dir.mkdir(parents=True, exist_ok=True)
        (tile_dir / f"{y}.mvt").write_bytes(payload)

    with pmtiles_path.open("wb") as handle:
        writer = Writer(handle)
        for (z, x, y), payload in sorted(tile_payloads.items()):
            writer.write_tile(zxy_to_tileid(z, x, y), payload)
        writer.finalize(
            {
                "root_offset": 0,
                "root_length": 0,
                "metadata_offset": 0,
                "metadata_length": 0,
                "tile_data_offset": 0,
                "tile_data_length": 0,
                "clustered": True,
                "internal_compression": Compression.GZIP,
                "tile_compression": Compression.NONE,
                "tile_type": TileType.MVT,
                "min_zoom": 0,
                "max_zoom": 0,
                "center_zoom": 0,
                "center_lon_e7": 0,
                "center_lat_e7": 0,
                "min_lon_e7": int(-180 * 1e7),
                "min_lat_e7": int(-90 * 1e7),
                "max_lon_e7": int(180 * 1e7),
                "max_lat_e7": int(90 * 1e7),
            },
            {"name": "docmap-phase-a-boundaries", "format": "pbf"},
        )

    vector_times: list[float] = []
    vector_bytes: list[int] = []
    for _ in range(runs):
        started = time.perf_counter()
        bytes_read = 0
        for z, x, y in tiles:
            payload = (zxy_dir / str(z) / str(x) / f"{y}.mvt").read_bytes()
            bytes_read += len(payload)
            _decode_tile(payload)
        vector_times.append((time.perf_counter() - started) * 1000.0)
        vector_bytes.append(bytes_read)

    pmtiles_times: list[float] = []
    pmtiles_bytes: list[int] = []
    pmtiles_calls: list[int] = []
    for _ in range(runs):
        source = CountingSource(pmtiles_path)
        reader = Reader(source.get_bytes)
        started = time.perf_counter()
        for z, x, y in tiles:
            payload = reader.get(z, x, y)
            if payload is None:
                continue
            _decode_tile(payload)
        pmtiles_times.append((time.perf_counter() - started) * 1000.0)
        pmtiles_bytes.append(source.bytes_read)
        pmtiles_calls.append(source.read_calls)
        source.close()

    vector_dir_total_bytes = sum(path.stat().st_size for path in zxy_dir.rglob("*.mvt"))
    pmtiles_total_bytes = pmtiles_path.stat().st_size
    return {
        "tile_count": len(tiles),
        "scenarios": SCENARIO_TILE_WINDOWS,
        "artifacts": {
            "vector_dir_total_bytes": vector_dir_total_bytes,
            "pmtiles_total_bytes": pmtiles_total_bytes,
            "size_ratio_pmtiles_to_vector_dir": round(pmtiles_total_bytes / max(vector_dir_total_bytes, 1), 3),
        },
        "benchmarks": {
            "vector_dir": {
                "median_ms": round(statistics.median(vector_times), 2),
                "min_ms": round(min(vector_times), 2),
                "max_ms": round(max(vector_times), 2),
                "bytes_read_per_run": int(statistics.median(vector_bytes)),
                "read_calls_per_run": len(tiles),
            },
            "pmtiles": {
                "median_ms": round(statistics.median(pmtiles_times), 2),
                "min_ms": round(min(pmtiles_times), 2),
                "max_ms": round(max(pmtiles_times), 2),
                "bytes_read_per_run": int(statistics.median(pmtiles_bytes)),
                "read_calls_per_run": int(statistics.median(pmtiles_calls)),
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Phase A baked artifact format candidates.")
    parser.add_argument(
        "--source",
        default="services/analytics/assets/admin_boundaries.geojson",
        help="Source GeoJSON path for prototype tile generation.",
    )
    parser.add_argument(
        "--workspace",
        default=".tmp/phase_a_artifacts",
        help="Workspace directory for temporary generated artifacts.",
    )
    parser.add_argument("--runs", type=int, default=5, help="Number of benchmark runs per format.")
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    args = parser.parse_args()

    payload = compare_formats(
        source_geojson_path=Path(args.source),
        workspace_path=Path(args.workspace),
        runs=max(1, int(args.runs)),
    )
    encoded = json.dumps(payload, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
