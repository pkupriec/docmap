from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from services.common.logging import configure_logging
from services.common.migrations import run_startup_migrations
from services.presentation.backend.repository import PresentationRepository, parse_boundary_chunk, parse_viewport_bucket

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/map")

RankFilter = Literal["default", "all"]
_INSTRUMENTED_ROUTE_PATHS = {
    "/api/map/locations",
    "/api/map/boundaries",
    "/api/map/baked/manifest",
    "/api/map/baked/tile-index",
    "/api/map/baked/tiles/{version}/{mode}/{z}/{x}/{y}.mvt",
    "/api/map/location/{location_id}/documents",
    "/api/map/document/{document_id}/locations",
    "/api/search",
}
_ADMIN_LEVEL_RE = re.compile(r"^admin_level_(\d+)$")
_BAKED_VERSION_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$", re.IGNORECASE)
_BAKED_MODE_RE = re.compile(r"^[a-z][a-z0-9_]*$", re.IGNORECASE)
_SUPPORTED_BOUNDARY_RANKS = {
    "city",
    "admin_region",
    "country",
    "continent",
    "ocean",
    "national_park",
    "desert",
    "unknown",
}


@dataclass(frozen=True)
class BoundariesRequestShape:
    lite: bool
    rank_filter: RankFilter
    ranks: tuple[str, ...]
    chunk_ids: tuple[str, ...]
    viewport_bucket: str | None
    bbox: tuple[float, float, float, float] | None
    selected_location_id: str | None
    highlighted_location_ids: tuple[str, ...]


class BoundariesCache:
    def __init__(self, *, ttl_seconds: float) -> None:
        self._ttl_seconds = ttl_seconds
        self._data: dict[BoundariesRequestShape, tuple[float, dict[str, object]]] = {}
        self._lock = threading.Lock()

    def get(self, key: BoundariesRequestShape) -> dict[str, object] | None:
        now = time.monotonic()
        with self._lock:
            cached = self._data.get(key)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                self._data.pop(key, None)
                return None
            return payload

    def set(self, key: BoundariesRequestShape, payload: dict[str, object]) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + self._ttl_seconds, payload)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


BOUNDARIES_CACHE = BoundariesCache(ttl_seconds=10 * 60)
BAKED_TILE_INDEX_CACHE: dict[tuple[str, str], tuple[float, dict[str, object]]] = {}
BAKED_TILE_INDEX_CACHE_LOCK = threading.Lock()


def _presentation_geometry_root() -> Path:
    return Path(
        os.getenv(
            "DOCMAP_PRESENTATION_BAKED_GEOMETRY_ROOT",
            "/app/services/analytics/assets/presentation_geometry",
        )
    )


def _safe_baked_segment(raw: str, *, pattern: re.Pattern[str], field_name: str) -> str:
    value = str(raw or "").strip()
    if not value:
        raise _validation_error(field_name, f"{field_name} must not be empty")
    if pattern.match(value) is None:
        raise _validation_error(field_name, f"{field_name} has unsupported characters")
    return value


def _default_baked_mode(available_modes: list[str]) -> str:
    configured = str(os.getenv("DOCMAP_PRESENTATION_DEFAULT_PRECISION_MODE", "")).strip()
    if configured:
        try:
            safe_configured = _safe_baked_segment(
                configured,
                pattern=_BAKED_MODE_RE,
                field_name="mode",
            )
            if safe_configured in available_modes:
                return safe_configured
        except HTTPException:
            pass
    return available_modes[0] if available_modes else ""


def _load_baked_manifest(mode: str | None) -> tuple[Path, dict[str, object], str, str, str]:
    root = _presentation_geometry_root()
    pointer_path = root / "current.json"
    if not pointer_path.exists():
        raise HTTPException(status_code=404, detail="baked_geometry_pointer_not_found")
    try:
        pointer_payload = json.loads(pointer_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="baked_geometry_pointer_invalid") from exc

    current_version = _safe_baked_segment(
        str(pointer_payload.get("current_version") or ""),
        pattern=_BAKED_VERSION_RE,
        field_name="version",
    )
    manifest_rel = str(pointer_payload.get("manifest") or f"{current_version}/manifest.json")
    manifest_path = (root / manifest_rel).resolve()
    if not str(manifest_path).startswith(str(root.resolve())) or not manifest_path.exists():
        raise HTTPException(status_code=404, detail="baked_geometry_manifest_not_found")
    try:
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="baked_geometry_manifest_invalid") from exc

    mode_payload = manifest_payload.get("modes")
    if not isinstance(mode_payload, dict) or not mode_payload:
        raise HTTPException(status_code=404, detail="baked_geometry_modes_missing")
    available_modes = sorted(str(item) for item in mode_payload.keys())
    default_mode = _default_baked_mode(available_modes)
    selected_mode = mode or default_mode
    selected_mode = _safe_baked_segment(
        selected_mode,
        pattern=_BAKED_MODE_RE,
        field_name="mode",
    )
    if selected_mode not in mode_payload:
        raise HTTPException(status_code=404, detail="baked_geometry_mode_not_found")
    return root, manifest_payload, current_version, selected_mode, default_mode


def _load_baked_tile_index(
    *,
    root: Path,
    version: str,
    mode: str,
) -> dict[str, object]:
    cache_key = (version, mode)
    mode_root = (root / version / mode).resolve()
    if not str(mode_root).startswith(str(root.resolve())) or not mode_root.exists() or not mode_root.is_dir():
        raise HTTPException(status_code=404, detail="baked_geometry_mode_not_found")
    mtime_key = mode_root.stat().st_mtime
    with BAKED_TILE_INDEX_CACHE_LOCK:
        cached = BAKED_TILE_INDEX_CACHE.get(cache_key)
        if cached is not None and math.isclose(cached[0], mtime_key):
            return cached[1]
    tiles: list[str] = []
    for tile_path in mode_root.rglob("*.mvt"):
        relative = tile_path.relative_to(mode_root).as_posix()
        tiles.append(relative[:-4])
    tiles.sort(
        key=lambda item: tuple(int(part) for part in item.split("/")) if item.count("/") == 2 else (999, 999, 999),
    )
    payload = {
        "version": version,
        "mode": mode,
        "tile_count": len(tiles),
        "tiles": tiles,
    }
    with BAKED_TILE_INDEX_CACHE_LOCK:
        BAKED_TILE_INDEX_CACHE[cache_key] = (mtime_key, payload)
    return payload


def _validation_error(loc: str, message: str, *, error_type: str = "value_error") -> HTTPException:
    return HTTPException(
        status_code=422,
        detail=[
            {
                "type": error_type,
                "loc": ["query", loc],
                "msg": message,
                "input": None,
            }
        ],
    )


def _normalize_longitude(value: float) -> float:
    normalized = ((value + 180.0) % 360.0) - 180.0
    if math.isclose(normalized, -180.0) and value > 0:
        return 180.0
    return normalized


def _boundary_rank_sort_key(rank: str) -> tuple[int, str]:
    if rank == "ocean":
        return (0, rank)
    if rank == "continent":
        return (1, rank)
    if rank == "country":
        return (2, rank)
    if rank == "admin_region":
        return (3, rank)
    if rank == "city":
        return (4, rank)
    if rank in {"national_park", "desert"}:
        return (5, rank)
    admin_level = _ADMIN_LEVEL_RE.match(rank)
    if admin_level is not None:
        return (10 + int(admin_level.group(1)), rank)
    if rank == "unknown":
        return (90, rank)
    return (99, rank)


def _normalize_rank_value(raw_rank: str, *, field_name: str) -> str:
    rank = raw_rank.strip().lower()
    if not rank:
        raise _validation_error(field_name, "rank values must be non-empty")
    if rank == "region":
        rank = "admin_region"
    if rank in _SUPPORTED_BOUNDARY_RANKS or _ADMIN_LEVEL_RE.match(rank):
        return rank
    raise _validation_error(field_name, f"unsupported rank '{raw_rank}'")


def _parse_ranks(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    parts = [part.strip() for part in raw.split(",")]
    if any(not part for part in parts):
        raise _validation_error("ranks", "ranks must be a comma-separated list of non-empty values")
    normalized = {_normalize_rank_value(part, field_name="ranks") for part in parts}
    return tuple(sorted(normalized, key=_boundary_rank_sort_key))


def _parse_uuid_value(raw: str, *, field_name: str) -> str:
    value = raw.strip()
    if not value:
        raise _validation_error(field_name, f"{field_name} must not be empty")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise _validation_error(field_name, f"{field_name} must be a valid UUID") from exc


def _parse_optional_uuid(raw: str | None, *, field_name: str) -> str | None:
    if raw is None:
        return None
    return _parse_uuid_value(raw, field_name=field_name)


def _parse_uuid_csv(raw: str | None, *, field_name: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    parts = [part.strip() for part in raw.split(",")]
    if any(not part for part in parts):
        raise _validation_error(field_name, f"{field_name} must be a comma-separated list of UUIDs")
    return tuple(sorted({_parse_uuid_value(part, field_name=field_name) for part in parts}))


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 4 or any(not part for part in parts):
        raise _validation_error("bbox", "bbox must contain west,south,east,north")
    try:
        west, south, east, north = [float(part) for part in parts]
    except ValueError as exc:
        raise _validation_error("bbox", "bbox values must be finite numbers") from exc
    values = [west, south, east, north]
    if not all(math.isfinite(value) for value in values):
        raise _validation_error("bbox", "bbox values must be finite numbers")
    if south < -90 or north > 90 or south > north:
        raise _validation_error("bbox", "bbox latitude must satisfy -90 <= south <= north <= 90")
    return (_normalize_longitude(west), south, _normalize_longitude(east), north)


def _parse_viewport_bucket(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        return parse_viewport_bucket(raw).bucket_id
    except ValueError as exc:
        raise _validation_error("viewport_bucket", str(exc)) from exc


def _parse_chunk_ids(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    parts = [part.strip() for part in raw.split(",")]
    if any(not part for part in parts):
        raise _validation_error("chunk_ids", "chunk_ids must be a comma-separated list of non-empty values")
    try:
        normalized = {parse_boundary_chunk(part).chunk_id for part in parts}
    except ValueError as exc:
        raise _validation_error("chunk_ids", str(exc)) from exc
    return tuple(sorted(normalized))


def _build_boundaries_request_shape(
    request: Request,
    *,
    lite: bool,
    rank_filter: RankFilter,
    ranks: str | None,
    chunk_ids: str | None,
    viewport_bucket: str | None,
    bbox: str | None,
    selected_location_id: str | None,
    highlighted_location_ids: str | None,
) -> BoundariesRequestShape:
    if "geometry_detail" in request.query_params:
        raise _validation_error("geometry_detail", "geometry_detail has been removed from the presentation API")
    normalized_chunk_ids = _parse_chunk_ids(chunk_ids)
    normalized_viewport_bucket = _parse_viewport_bucket(viewport_bucket)
    normalized_bbox = _parse_bbox(bbox)
    if normalized_chunk_ids and normalized_viewport_bucket is not None:
        raise _validation_error("chunk_ids", "chunk_ids cannot be combined with viewport_bucket")
    if normalized_chunk_ids and normalized_bbox is not None:
        raise _validation_error("chunk_ids", "chunk_ids cannot be combined with bbox")
    if normalized_viewport_bucket is not None and normalized_bbox is not None:
        raise _validation_error("viewport_bucket", "viewport_bucket cannot be combined with bbox")
    return BoundariesRequestShape(
        lite=lite,
        rank_filter=rank_filter,
        ranks=_parse_ranks(ranks),
        chunk_ids=normalized_chunk_ids,
        viewport_bucket=normalized_viewport_bucket,
        bbox=normalized_bbox,
        selected_location_id=_parse_optional_uuid(selected_location_id, field_name="selected_location_id"),
        highlighted_location_ids=_parse_uuid_csv(
            highlighted_location_ids,
            field_name="highlighted_location_ids",
        ),
    )


def _as_str_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _response_payload_bytes(response: Response) -> int | None:
    raw_value = response.headers.get("content-length")
    if raw_value is None:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    return request.url.path


def _log_request_metrics(
    request: Request,
    *,
    route_path: str,
    response: Response,
    duration_ms: float,
) -> None:
    response_bytes = _response_payload_bytes(response)
    query_params = request.query_params
    path_params = request.path_params
    metric_fields: list[str] = [
        f"route={route_path}",
        f"method={request.method}",
        f"status_code={response.status_code}",
        f"duration_ms={duration_ms:.2f}",
        f"response_bytes={response_bytes if response_bytes is not None else 'unknown'}",
    ]

    if route_path == "/api/map/boundaries":
        chunk_ids = [part.strip() for part in query_params.get("chunk_ids", "").split(",") if part.strip()]
        highlighted_ids = [
            part.strip() for part in query_params.get("highlighted_location_ids", "").split(",") if part.strip()
        ]
        selector = "all"
        if chunk_ids:
            selector = "chunk_ids"
        elif query_params.get("viewport_bucket"):
            selector = "viewport_bucket"
        elif query_params.get("bbox"):
            selector = "bbox"
        elif query_params.get("selected_location_id") or highlighted_ids:
            selector = "explicit_only"
        metric_fields.extend(
            [
                f"lite={query_params.get('lite', '0')}",
                f"rank_filter={query_params.get('rank_filter', 'default')}",
                f"selector={selector}",
                f"chunk_count={len(chunk_ids)}",
                f"highlighted_count={len(highlighted_ids)}",
                f"selected_location={1 if query_params.get('selected_location_id') else 0}",
            ]
        )
    elif route_path == "/api/map/location/{location_id}/documents":
        metric_fields.extend(
            [
                f"location_id={path_params.get('location_id')}",
                f"limit={query_params.get('limit', '100')}",
                f"offset={query_params.get('offset', '0')}",
            ]
        )
    elif route_path == "/api/map/document/{document_id}/locations":
        metric_fields.append(f"document_id={path_params.get('document_id')}")
    elif route_path == "/api/search":
        metric_fields.extend(
            [
                f"query_length={len(query_params.get('q', '').strip())}",
                f"limit={query_params.get('limit', '5')}",
            ]
        )
    elif route_path == "/api/map/baked/manifest":
        metric_fields.append(f"mode={query_params.get('mode', '') or 'default'}")
    elif route_path == "/api/map/baked/tile-index":
        metric_fields.append(f"mode={query_params.get('mode', '') or 'default'}")
    elif route_path == "/api/map/baked/tiles/{version}/{mode}/{z}/{x}/{y}.mvt":
        metric_fields.extend(
            [
                f"version={path_params.get('version')}",
                f"mode={path_params.get('mode')}",
                f"z={path_params.get('z')}",
                f"x={path_params.get('x')}",
                f"y={path_params.get('y')}",
            ]
        )

    logger.info("presentation.api_request %s", " ".join(metric_fields))


def _serialize_document_card(item: dict[str, object]) -> dict[str, object]:
    return {
        "document_id": str(item["document_id"]),
        "scp_number": item["scp_number"],
        "canonical_scp_id": item["canonical_scp_id"],
        "scp_url": item["scp_url"],
        "location_display": item.get("location_display"),
        "pdf_url": item.get("pdf_url"),
    }


def _dedupe_by_id(items: list[dict[str, object]], id_field: str) -> list[dict[str, object]]:
    seen: set[str] = set()
    deduped: list[dict[str, object]] = []
    for item in items:
        value = item.get(id_field)
        if value is None:
            continue
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _build_pdf_response(payload: bytes, request: Request) -> Response:
    total_size = len(payload)
    default_headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(total_size),
    }
    range_header = request.headers.get("range")
    if not range_header:
        return Response(content=payload, media_type="application/pdf", headers=default_headers)

    if not range_header.startswith("bytes="):
        return Response(status_code=416, headers={"Content-Range": f"bytes */{total_size}"})

    range_spec = range_header[6:].strip()
    if "," in range_spec:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{total_size}"})

    start_raw, _, end_raw = range_spec.partition("-")
    if not _:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{total_size}"})

    try:
        if start_raw == "":
            suffix_size = int(end_raw)
            if suffix_size <= 0:
                return Response(status_code=416, headers={"Content-Range": f"bytes */{total_size}"})
            start = max(total_size - suffix_size, 0)
            end = total_size - 1
        else:
            start = int(start_raw)
            end = int(end_raw) if end_raw else total_size - 1
    except ValueError:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{total_size}"})

    if start < 0 or end < start or start >= total_size:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{total_size}"})

    end = min(end, total_size - 1)
    chunk = payload[start : end + 1]
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{total_size}",
        "Content-Length": str(len(chunk)),
    }
    return Response(content=chunk, status_code=206, media_type="application/pdf", headers=headers)


@router.get("/locations")
def get_locations() -> list[dict[str, object]]:
    repo = PresentationRepository()
    rows = repo.list_locations()
    return [
        {
            "location_id": str(row["location_id"]),
            "name": row["name"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "precision": row["precision"],
            "location_rank": row["location_rank"],
            "document_count": row["document_count"],
            "parent_location_id": _as_str_or_none(row["parent_location_id"]),
        }
        for row in rows
    ]


@router.get("/boundaries")
def get_boundaries(
    request: Request,
    lite: bool = Query(default=False),
    rank_filter: RankFilter = Query(default="default"),
    ranks: str | None = Query(default=None),
    chunk_ids: str | None = Query(default=None),
    viewport_bucket: str | None = Query(default=None),
    bbox: str | None = Query(default=None),
    selected_location_id: str | None = Query(default=None),
    highlighted_location_ids: str | None = Query(default=None),
) -> dict[str, object]:
    request_shape = _build_boundaries_request_shape(
        request,
        lite=lite,
        rank_filter=rank_filter,
        ranks=ranks,
        chunk_ids=chunk_ids,
        viewport_bucket=viewport_bucket,
        bbox=bbox,
        selected_location_id=selected_location_id,
        highlighted_location_ids=highlighted_location_ids,
    )

    cached_payload = BOUNDARIES_CACHE.get(request_shape)
    if cached_payload is not None:
        logger.info(
            "presentation.boundaries_cache_hit lite=%s rank_filter=%s ranks=%s chunk_ids=%s viewport_bucket=%s bbox=%s selected=%s highlighted=%s",
            request_shape.lite,
            request_shape.rank_filter,
            request_shape.ranks,
            request_shape.chunk_ids,
            request_shape.viewport_bucket,
            request_shape.bbox,
            request_shape.selected_location_id,
            len(request_shape.highlighted_location_ids),
        )
        return cached_payload

    repo = PresentationRepository()
    start = time.perf_counter()
    payload = repo.get_admin_boundaries_geojson(
        minimal=request_shape.lite,
        rank_filter=request_shape.rank_filter,
        ranks=request_shape.ranks,
        chunk_ids=request_shape.chunk_ids,
        viewport_bucket=request_shape.viewport_bucket,
        bbox=request_shape.bbox,
        selected_location_id=request_shape.selected_location_id,
        highlighted_location_ids=request_shape.highlighted_location_ids,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    BOUNDARIES_CACHE.set(request_shape, payload)
    logger.info(
        "presentation.boundaries_cache_miss lite=%s rank_filter=%s ranks=%s chunk_ids=%s viewport_bucket=%s bbox=%s selected=%s highlighted=%s duration_ms=%.2f",
        request_shape.lite,
        request_shape.rank_filter,
        request_shape.ranks,
        request_shape.chunk_ids,
        request_shape.viewport_bucket,
        request_shape.bbox,
        request_shape.selected_location_id,
        len(request_shape.highlighted_location_ids),
        elapsed_ms,
    )
    return payload


@router.get("/baked/manifest")
def get_baked_manifest(mode: str | None = Query(default=None)) -> dict[str, object]:
    root, manifest_payload, version, selected_mode, default_mode = _load_baked_manifest(mode)
    modes = manifest_payload.get("modes")
    if not isinstance(modes, dict):
        raise HTTPException(status_code=404, detail="baked_geometry_modes_missing")
    selected_mode_payload = modes.get(selected_mode)
    if not isinstance(selected_mode_payload, dict):
        raise HTTPException(status_code=404, detail="baked_geometry_mode_not_found")
    mode_path = str(selected_mode_payload.get("path") or f"{version}/{selected_mode}")
    return {
        "schema_version": manifest_payload.get("schema_version"),
        "version": version,
        "mode": selected_mode,
        "default_mode": default_mode,
        "available_modes": sorted(str(item) for item in modes.keys()),
        "zoom_min": manifest_payload.get("zoom_min"),
        "zoom_max": manifest_payload.get("zoom_max"),
        "tile_format": manifest_payload.get("tile_format"),
        "tolerance_by_zoom_band": selected_mode_payload.get("tolerance_by_zoom_band", {}),
        "tile_url_template": f"/api/map/baked/tiles/{version}/{selected_mode}" + "/{z}/{x}/{y}.mvt",
        "mode_path": mode_path,
        "manifest_path": str((root / version / "manifest.json").as_posix()),
    }


@router.get("/baked/tile-index")
def get_baked_tile_index(mode: str | None = Query(default=None)) -> dict[str, object]:
    root, _manifest_payload, version, selected_mode, _default_mode = _load_baked_manifest(mode)
    return _load_baked_tile_index(root=root, version=version, mode=selected_mode)


@router.get("/baked/tiles/{version}/{mode}/{z}/{x}/{y}.mvt")
def get_baked_tile(version: str, mode: str, z: int, x: int, y: int) -> Response:
    if z < 0 or x < 0 or y < 0:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    safe_version = _safe_baked_segment(version, pattern=_BAKED_VERSION_RE, field_name="version")
    safe_mode = _safe_baked_segment(mode, pattern=_BAKED_MODE_RE, field_name="mode")
    root, _manifest_payload, _current_version, _selected_mode, _default_mode = _load_baked_manifest(safe_mode)
    tile_path = (root / safe_version / safe_mode / str(z) / str(x) / f"{y}.mvt").resolve()
    if not str(tile_path).startswith(str(root.resolve())) or not tile_path.exists() or not tile_path.is_file():
        return JSONResponse(status_code=404, content={"error": "not_found"})
    return FileResponse(tile_path, media_type="application/vnd.mapbox-vector-tile")


@router.get("/location/{location_id}/documents")
def get_location_documents(
    location_id: UUID,
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    repo = PresentationRepository()
    resolved = repo.resolve_location_for_documents(location_id)
    if resolved is None:
        return {
            "requested_location_id": str(location_id),
            "resolved_location_id": None,
            "fallback_depth": None,
            "scope_rank": None,
            "scope_location_count": 0,
            "total_items": 0,
            "returned_items": 0,
            "limit": limit,
            "offset": offset,
            "items": [],
        }

    resolved_uuid = UUID(resolved.location_id)
    semantic_scope_location_ids = []
    if resolved.location_rank == "city" and hasattr(repo, "get_semantic_scope_location_ids"):
        semantic_scope_location_ids = list(
            getattr(repo, "get_semantic_scope_location_ids")(resolved_uuid, scope_rank=resolved.location_rank),
        )
    list_documents_kwargs: dict[str, object] = {
        "scope_rank": resolved.location_rank,
        "limit": limit,
        "offset": offset,
    }
    if semantic_scope_location_ids:
        list_documents_kwargs["semantic_scope_location_ids"] = semantic_scope_location_ids
    scoped = repo.list_location_documents(
        resolved_uuid,
        **list_documents_kwargs,
    )
    location_display = repo.get_location_name(resolved_uuid)
    serialized_items = [
        _serialize_document_card(
            {
                **item,
                "location_display": location_display,
            }
        )
        for item in scoped.items
    ]
    deduped_items = _dedupe_by_id(serialized_items, "document_id")
    return {
        "requested_location_id": str(location_id),
        "resolved_location_id": resolved.location_id,
        "fallback_depth": resolved.depth,
        "scope_rank": scoped.scope_rank,
        "scope_location_count": scoped.location_count,
        "total_items": scoped.total_items,
        "returned_items": len(deduped_items),
        "limit": limit,
        "offset": offset,
        "items": deduped_items,
    }


@router.get("/document/{document_id}")
def get_document(document_id: UUID) -> dict[str, object]:
    repo = PresentationRepository()
    item = repo.get_document_card(document_id)
    if item is None:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    return _serialize_document_card(item)


@router.get("/document/{document_id}/pdf")
def get_document_pdf(document_id: UUID, request: Request) -> Response:
    repo = PresentationRepository()
    payload = repo.get_document_pdf(document_id)
    if payload is None:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    return _build_pdf_response(payload, request)


@router.get("/document/{document_id}/locations")
def get_document_locations(document_id: UUID) -> list[dict[str, object]]:
    repo = PresentationRepository()
    rows = repo.list_document_locations(document_id)
    return [
        {
            "document_id": str(row["document_id"]),
            "location_id": str(row["location_id"]),
            "name": row["name"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "precision": row["precision"],
            "location_rank": row["location_rank"],
            "evidence_quote": row["evidence_quote"],
            "mention_count": row["mention_count"],
        }
        for row in rows
    ]


@router.get("/overlays/density")
def get_density_overlay() -> list[dict[str, object]]:
    repo = PresentationRepository()
    rows = repo.list_density_points()
    return [
        {
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "document_count": row["document_count"],
        }
        for row in rows
    ]


def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=5, ge=1, le=5),
) -> dict[str, object]:
    repo = PresentationRepository()
    payload = repo.search(query=q, limit=min(limit, 5))
    documents = _dedupe_by_id(
        [_serialize_document_card(item) for item in payload["documents"]],
        "document_id",
    )
    locations = _dedupe_by_id(
        [
            {
                "location_id": str(row["location_id"]),
                "name": row["name"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "precision": row["precision"],
                "location_rank": row["location_rank"],
                "document_count": row["document_count"],
                "parent_location_id": _as_str_or_none(row["parent_location_id"]),
            }
            for row in payload["locations"]
        ],
        "location_id",
    )
    return {
        "query": q,
        "documents": documents[:5],
        "locations": locations[:5],
    }


def create_presentation_app() -> FastAPI:
    app = FastAPI(title="DocMap Presentation API", version="1.0.0")
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.include_router(router)

    @app.middleware("http")
    async def instrument_presentation_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        route_path = _route_template(request)
        if route_path in _INSTRUMENTED_ROUTE_PATHS:
            _log_request_metrics(
                request,
                route_path=route_path,
                response=response,
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )
        return response

    @app.get("/api/search")
    def root_search(
        q: str = Query(..., min_length=1),
        limit: int = Query(default=5, ge=1, le=5),
    ) -> dict[str, object]:
        return search(q=q, limit=limit)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    static_dir = Path(os.getenv("PRESENTATION_STATIC_DIR", "/app/services/presentation/frontend/dist"))
    if static_dir.exists():
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount(
                "/assets",
                StaticFiles(directory=assets_dir),
                name="presentation-assets",
            )

        @app.get("/")
        def root() -> FileResponse:
            return FileResponse(static_dir / "index.html")

        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"error": "not_found"})
            requested = static_dir / full_path
            if requested.exists() and requested.is_file():
                return FileResponse(requested)
            # Avoid serving index.html for missing static-like resources
            # (e.g. /sw.js), which can break browser runtime behavior.
            if "." in Path(full_path).name:
                return JSONResponse(status_code=404, content={"error": "not_found"})
            return FileResponse(static_dir / "index.html")

    @app.on_event("startup")
    def _startup() -> None:
        BOUNDARIES_CACHE.clear()
        with BAKED_TILE_INDEX_CACHE_LOCK:
            BAKED_TILE_INDEX_CACHE.clear()
        configure_logging()
        run_startup_migrations()

    return app
