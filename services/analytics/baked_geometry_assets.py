from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence
from uuid import uuid4

from psycopg import Connection

logger = logging.getLogger(__name__)

ARTIFACT_SCHEMA_VERSION = "v2"
ZOOM_MIN_DEFAULT = 0
ZOOM_MAX_DEFAULT = 8
DEFAULT_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
DEFAULT_RELEASE_RETENTION = 2

# Tippecanoe owns clipping, topology repair, and zoom-aware simplification.
PRECISION_MODES: dict[str, tuple[str, ...]] = {
    "full_precise": (
        "--no-line-simplification",
        "--no-tiny-polygon-reduction",
    ),
    "balanced_precise": ("--simplification=2",),
    "simplified": ("--simplification=6",),
    "primitive": (
        "--simplification=10",
        "--tiny-polygon-size=4",
    ),
}

BakedProgressCallback = Callable[[int, int], None]
CommandRunner = Callable[[Sequence[str]], None]


@dataclass(frozen=True)
class BakedModeStats:
    mode: str
    byte_size: int
    path: Path
    options: tuple[str, ...]


@dataclass(frozen=True)
class BakedGeometryBuildResult:
    version: str
    root_path: Path
    manifest_path: Path
    source_feature_count: int
    modes: dict[str, BakedModeStats]

    @property
    def total_archives(self) -> int:
        return len(self.modes)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_assets_root() -> Path:
    configured = os.getenv("DOCMAP_PRESENTATION_ARTIFACT_ROOT")
    if configured:
        return Path(configured)
    return _project_root() / "services" / "analytics" / "assets" / "presentation_geometry"


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
        if isinstance(payload, dict):
            parsed = payload
        else:
            try:
                parsed = json.loads(payload)
            except (TypeError, json.JSONDecodeError):
                continue
        geometry = parsed.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        properties = parsed.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "location_id": str(location_id),
                    "location_rank": str(location_rank or properties.get("location_rank") or "unknown"),
                    "location_name": str(properties.get("location_name") or location_id),
                },
                "geometry": geometry,
            }
        )
    return features


def _artifact_version(
    features: list[dict[str, Any]],
    *,
    zoom_min: int,
    zoom_max: int,
    mode_options: dict[str, tuple[str, ...]],
) -> str:
    payload = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "min_zoom": zoom_min,
        "max_zoom": zoom_max,
        "mode_options": mode_options,
        "features": features,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{ARTIFACT_SCHEMA_VERSION}-{hashlib.sha256(encoded).hexdigest()[:16]}"


def _resolve_tippecanoe_binary() -> str:
    configured = os.getenv("TIPPECANOE_BIN", "tippecanoe")
    resolved = shutil.which(configured)
    if resolved:
        return resolved
    candidate = Path(configured)
    if candidate.is_file():
        return str(candidate.resolve())
    raise RuntimeError(
        "tippecanoe executable is unavailable; install the pinned runtime image or set TIPPECANOE_BIN"
    )


def _run_command(command: Sequence[str]) -> None:
    try:
        subprocess.run(list(command), check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"tippecanoe failed with exit code {exc.returncode}: {detail}") from exc


def _tippecanoe_command(
    *,
    executable: str,
    source_path: Path,
    output_path: Path,
    zoom_min: int,
    zoom_max: int,
    mode_options: Sequence[str],
) -> list[str]:
    return [
        executable,
        "--force",
        f"--output={output_path}",
        "--layer=boundaries",
        f"--minimum-zoom={zoom_min}",
        f"--maximum-zoom={zoom_max}",
        "--projection=EPSG:4326",
        "--preserve-input-order",
        "--no-feature-limit",
        "--no-tile-size-limit",
        "--no-simplification-of-shared-nodes",
        "--include=location_id",
        "--include=location_rank",
        "--include=location_name",
        *mode_options,
        str(source_path),
    ]


def _validate_archive(path: Path, *, max_bytes: int) -> int:
    if not path.is_file():
        raise RuntimeError(f"tippecanoe did not create expected archive: {path}")
    byte_size = path.stat().st_size
    if byte_size <= 8:
        raise RuntimeError(f"generated PMTiles archive is empty: {path}")
    if byte_size > max_bytes:
        raise RuntimeError(
            f"generated PMTiles archive exceeds budget: path={path} bytes={byte_size} max={max_bytes}"
        )
    with path.open("rb") as stream:
        if stream.read(7) != b"PMTiles":
            raise RuntimeError(f"generated artifact is not a PMTiles v3 archive: {path}")
    return byte_size


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _prune_old_releases(root: Path, *, current_version: str) -> None:
    retention = max(
        1,
        int(os.getenv("DOCMAP_PRESENTATION_ARTIFACT_RETENTION", str(DEFAULT_RELEASE_RETENTION))),
    )
    releases = sorted(
        (
            path
            for path in root.iterdir()
            if path.is_dir()
            and not path.name.startswith(".")
            and (path / "manifest.json").is_file()
        ),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    keep = {current_version}
    for release in releases:
        if len(keep) >= retention:
            break
        keep.add(release.name)
    for release in releases:
        if release.name not in keep:
            shutil.rmtree(release)


def _result_from_manifest(root: Path, manifest_path: Path) -> BakedGeometryBuildResult:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    modes: dict[str, BakedModeStats] = {}
    for mode, raw in payload.get("modes", {}).items():
        archive = root / str(raw["path"])
        if not archive.is_file():
            raise RuntimeError(f"published PMTiles archive is missing: {archive}")
        modes[mode] = BakedModeStats(
            mode=mode,
            byte_size=int(raw["byte_size"]),
            path=archive,
            options=tuple(str(item) for item in raw.get("options", ())),
        )
    return BakedGeometryBuildResult(
        version=str(payload["version"]),
        root_path=root,
        manifest_path=manifest_path,
        source_feature_count=int(payload["source_feature_count"]),
        modes=modes,
    )


def build_baked_geometry_assets(
    conn: Connection,
    *,
    assets_root: Path | None = None,
    zoom_min: int = ZOOM_MIN_DEFAULT,
    zoom_max: int = ZOOM_MAX_DEFAULT,
    mode_options: dict[str, tuple[str, ...]] | None = None,
    on_progress: BakedProgressCallback | None = None,
    command_runner: CommandRunner | None = None,
    tippecanoe_binary: str | None = None,
    max_archive_bytes: int | None = None,
) -> BakedGeometryBuildResult:
    if zoom_min < 0 or zoom_max < zoom_min:
        raise ValueError("invalid PMTiles zoom range")

    root = assets_root or _default_assets_root()
    root.mkdir(parents=True, exist_ok=True)
    options = mode_options or PRECISION_MODES
    features = _query_boundary_features(conn)
    features.sort(key=lambda feature: str(feature["properties"]["location_id"]))
    version = _artifact_version(features, zoom_min=zoom_min, zoom_max=zoom_max, mode_options=options)
    version_root = root / version
    manifest_path = version_root / "manifest.json"

    if manifest_path.is_file():
        result = _result_from_manifest(root, manifest_path)
        _atomic_write_json(
            root / "current.json",
            {
                "schema_version": ARTIFACT_SCHEMA_VERSION,
                "current_version": version,
                "manifest": f"{version}/manifest.json",
            },
        )
        _prune_old_releases(root, current_version=version)
        return result

    runner = command_runner or _run_command
    executable = tippecanoe_binary or _resolve_tippecanoe_binary()
    archive_budget = max_archive_bytes or int(
        os.getenv("DOCMAP_PRESENTATION_MAX_ARCHIVE_BYTES", str(DEFAULT_MAX_ARCHIVE_BYTES))
    )
    staging_root = root / f".{version}.building-{uuid4().hex}"
    staging_root.mkdir(parents=True, exist_ok=False)
    total = len(options)
    completed = 0
    if on_progress:
        on_progress(completed, total)

    try:
        source_path = staging_root / "boundaries.geojson"
        source_path.write_text(
            json.dumps(
                {"type": "FeatureCollection", "features": features},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        mode_results: dict[str, BakedModeStats] = {}
        for mode, current_options in options.items():
            archive_path = staging_root / f"{mode}.pmtiles"
            command = _tippecanoe_command(
                executable=executable,
                source_path=source_path,
                output_path=archive_path,
                zoom_min=zoom_min,
                zoom_max=zoom_max,
                mode_options=current_options,
            )
            logger.info("analytics.pmtiles_build_start mode=%s", mode)
            runner(command)
            byte_size = _validate_archive(archive_path, max_bytes=archive_budget)
            mode_results[mode] = BakedModeStats(
                mode=mode,
                byte_size=byte_size,
                path=version_root / archive_path.name,
                options=tuple(current_options),
            )
            completed += 1
            if on_progress:
                on_progress(completed, total)
            logger.info("analytics.pmtiles_build_done mode=%s bytes=%s", mode, byte_size)

        source_path.unlink()
        manifest_payload = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "version": version,
            "source_feature_count": len(features),
            "source_table": "bi_admin_boundaries",
            "tile_format": "pmtiles",
            "layer": "boundaries",
            "min_zoom": zoom_min,
            "max_zoom": zoom_max,
            "modes": {
                mode: {
                    "path": f"{version}/{mode}.pmtiles",
                    "byte_size": stats.byte_size,
                    "options": list(stats.options),
                }
                for mode, stats in mode_results.items()
            },
        }
        (staging_root / "manifest.json").write_text(
            json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(staging_root, version_root)
        _atomic_write_json(
            root / "current.json",
            {
                "schema_version": ARTIFACT_SCHEMA_VERSION,
                "current_version": version,
                "manifest": f"{version}/manifest.json",
            },
        )
        _prune_old_releases(root, current_version=version)
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise

    result = _result_from_manifest(root, manifest_path)
    logger.info(
        "analytics.pmtiles_assets_published root=%s version=%s source_features=%s total_bytes=%s",
        root,
        version,
        len(features),
        sum(item.byte_size for item in result.modes.values()),
    )
    return result
