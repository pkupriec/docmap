from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from services.common.db import create_connection_pool
from services.common.logging import configure_logging
from services.presentation.backend.byte_ranges import RangeNotSatisfiable, parse_byte_range
from services.presentation.backend.geometry_artifacts import GeometryArtifactError, GeometryArtifactStore
from services.presentation.backend.repository import PresentationRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/map")
_INSTRUMENTED_ROUTE_PATHS = {
    "/api/map/locations",
    "/api/map/boundaries",
    "/api/map/baked/manifest",
    "/api/map/baked/archives/{version}/{mode}.pmtiles",
    "/api/map/location/{location_id}/documents",
    "/api/map/document/{document_id}/locations",
    "/api/search",
}


@dataclass(frozen=True)
class BoundariesRequestShape:
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


def _validation_error(field: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail=[{"type": "value_error", "loc": ["query", field], "msg": message, "input": None}],
    )


def _parse_optional_uuid(raw: str | None, *, field: str) -> str | None:
    if raw is None:
        return None
    try:
        return str(UUID(raw.strip()))
    except (AttributeError, ValueError) as exc:
        raise _validation_error(field, f"{field} must be a valid UUID") from exc


def _parse_uuid_csv(raw: str | None, *, field: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    parts = [part.strip() for part in raw.split(",")]
    if any(not part for part in parts):
        raise _validation_error(field, f"{field} must be a comma-separated list of UUIDs")
    normalized = [_parse_optional_uuid(part, field=field) for part in parts]
    return tuple(sorted(value for value in normalized if value is not None))


def _repository(request: Request) -> PresentationRepository:
    factory: Callable[[], PresentationRepository] = request.app.state.presentation_repository_factory
    return factory()


def _artifact_store(request: Request) -> GeometryArtifactStore:
    return request.app.state.geometry_artifact_store


def _artifact_error(exc: GeometryArtifactError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.code)


def _as_str_or_none(value: object | None) -> str | None:
    return None if value is None else str(value)


def _serialize_document_card(item: dict[str, object]) -> dict[str, object]:
    return {
        "document_id": str(item["document_id"]),
        "scp_number": item["scp_number"],
        "canonical_scp_id": item["canonical_scp_id"],
        "scp_url": item["scp_url"],
        "location_display": item.get("location_display"),
        "pdf_url": item.get("pdf_url"),
        "thumbnail_url": item.get("thumbnail_url"),
    }


def _dedupe_by_id(items: list[dict[str, object]], id_field: str) -> list[dict[str, object]]:
    seen: set[str] = set()
    result: list[dict[str, object]] = []
    for item in items:
        value = item.get(id_field)
        if value is None or str(value) in seen:
            continue
        seen.add(str(value))
        result.append(item)
    return result


def _range_error(total_size: int) -> Response:
    return Response(
        status_code=416,
        headers={"Accept-Ranges": "bytes", "Content-Range": f"bytes */{total_size}"},
    )


def _partial_response(content: bytes, *, start: int, end: int, total_size: int, media_type: str) -> Response:
    return Response(
        content=content,
        status_code=206,
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{total_size}",
            "Content-Length": str(len(content)),
            "Content-Encoding": "identity",
        },
    )


@router.get("/locations")
def get_locations(request: Request) -> list[dict[str, object]]:
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
        for row in _repository(request).list_locations()
    ]


@router.get("/boundaries")
def get_boundaries(
    request: Request,
    selected_location_id: str | None = Query(default=None),
    highlighted_location_ids: str | None = Query(default=None),
) -> dict[str, object]:
    unsupported = sorted(set(request.query_params) - {"selected_location_id", "highlighted_location_ids"})
    if unsupported:
        raise _validation_error(unsupported[0], "only explicit selected/highlighted location IDs are supported")
    shape = BoundariesRequestShape(
        selected_location_id=_parse_optional_uuid(selected_location_id, field="selected_location_id"),
        highlighted_location_ids=_parse_uuid_csv(highlighted_location_ids, field="highlighted_location_ids"),
    )
    cached = BOUNDARIES_CACHE.get(shape)
    if cached is not None:
        return cached
    payload = _repository(request).get_admin_boundaries_geojson(
        selected_location_id=shape.selected_location_id,
        highlighted_location_ids=shape.highlighted_location_ids,
    )
    BOUNDARIES_CACHE.set(shape, payload)
    return payload


@router.get("/baked/manifest")
def get_baked_manifest(
    request: Request,
    response: Response,
    mode: str | None = Query(default=None),
) -> dict[str, object]:
    try:
        response.headers["Cache-Control"] = "no-store"
        return _artifact_store(request).manifest_response(mode)
    except GeometryArtifactError as exc:
        raise _artifact_error(exc) from exc


@router.get("/baked/archives/{version}/{mode}.pmtiles")
def get_baked_archive(version: str, mode: str, request: Request) -> Response:
    try:
        archive = _artifact_store(request).archive(version=version, mode=mode)
    except GeometryArtifactError as exc:
        if exc.status_code == 404:
            return JSONResponse(status_code=404, content={"error": "not_found"})
        raise _artifact_error(exc) from exc

    try:
        byte_range = parse_byte_range(request.headers.get("range"), total_size=archive.byte_size)
    except RangeNotSatisfiable:
        return _range_error(archive.byte_size)
    if byte_range is None:
        return FileResponse(
            archive.path,
            media_type="application/vnd.pmtiles",
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=31536000, immutable",
                "Content-Encoding": "identity",
            },
        )
    with archive.path.open("rb") as handle:
        handle.seek(byte_range.start)
        content = handle.read(byte_range.length)
    response = _partial_response(
        content,
        start=byte_range.start,
        end=byte_range.end,
        total_size=archive.byte_size,
        media_type="application/vnd.pmtiles",
    )
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


@router.get("/location/{location_id}/documents")
def get_location_documents(
    location_id: UUID,
    request: Request,
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    result = _repository(request).get_location_documents(location_id, limit=limit, offset=offset)
    if result.resolved is None or result.scoped is None:
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
    items = _dedupe_by_id(
        [_serialize_document_card({**item, "location_display": result.location_display}) for item in result.scoped.items],
        "document_id",
    )
    return {
        "requested_location_id": str(location_id),
        "resolved_location_id": result.resolved.location_id,
        "fallback_depth": result.resolved.depth,
        "scope_rank": result.scoped.scope_rank,
        "scope_location_count": result.scoped.location_count,
        "total_items": result.scoped.total_items,
        "returned_items": len(items),
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/document/{document_id}")
def get_document(document_id: UUID, request: Request) -> dict[str, object]:
    item = _repository(request).get_document_card(document_id)
    if item is None:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    return _serialize_document_card(item)


@router.get("/document/{document_id}/pdf")
def get_document_pdf(document_id: UUID, request: Request) -> Response:
    repo = _repository(request)
    total_size = repo.get_document_pdf_size(document_id)
    if total_size is None:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    try:
        byte_range = parse_byte_range(request.headers.get("range"), total_size=total_size)
    except RangeNotSatisfiable:
        return _range_error(total_size)
    if byte_range is None:
        payload = repo.get_document_pdf(document_id)
        if payload is None:
            return JSONResponse(status_code=404, content={"error": "not_found"})
        return Response(
            content=payload,
            media_type="application/pdf",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(total_size),
                "Content-Encoding": "identity",
            },
        )
    payload = repo.get_document_pdf_range(document_id, start=byte_range.start, length=byte_range.length)
    if payload is None:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    return _partial_response(
        payload,
        start=byte_range.start,
        end=byte_range.end,
        total_size=total_size,
        media_type="application/pdf",
    )


@router.get("/document/{document_id}/thumbnail")
def get_document_thumbnail(document_id: UUID, request: Request) -> Response:
    payload = _repository(request).get_document_thumbnail(document_id)
    if payload is None:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    return Response(
        content=payload,
        media_type="image/webp",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/document/{document_id}/locations")
def get_document_locations(document_id: UUID, request: Request) -> list[dict[str, object]]:
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
        for row in _repository(request).list_document_locations(document_id)
    ]


@router.get("/overlays/density")
def get_density_overlay(request: Request) -> list[dict[str, object]]:
    return [
        {"latitude": row["latitude"], "longitude": row["longitude"], "document_count": row["document_count"]}
        for row in _repository(request).list_density_points()
    ]


def search(request: Request, q: str, limit: int) -> dict[str, object]:
    payload = _repository(request).search(query=q, limit=min(limit, 5))
    documents = _dedupe_by_id([_serialize_document_card(item) for item in payload["documents"]], "document_id")
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
    return {"query": q, "documents": documents[:5], "locations": locations[:5]}


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


def _log_request_metrics(request: Request, response: Response, *, duration_ms: float) -> None:
    route_path = _route_template(request)
    if route_path not in _INSTRUMENTED_ROUTE_PATHS:
        return
    logger.info(
        "presentation.api_request route=%s method=%s status_code=%s duration_ms=%.2f response_bytes=%s",
        route_path,
        request.method,
        response.status_code,
        duration_ms,
        response.headers.get("content-length", "unknown"),
    )


def create_presentation_app(
    *,
    repository_factory: Callable[[], PresentationRepository] | None = None,
    artifact_store: GeometryArtifactStore | None = None,
) -> FastAPI:
    BOUNDARIES_CACHE.clear()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        BOUNDARIES_CACHE.clear()
        pool = None
        if repository_factory is None:
            pool = create_connection_pool(read_only=True)
            pool.open()
            pool.wait()
            app.state.presentation_repository_factory = lambda: PresentationRepository(pool.connection)
        try:
            yield
        finally:
            if pool is not None:
                pool.close()

    app = FastAPI(title="DocMap Presentation API", version="2.0.0", lifespan=lifespan)
    app.state.presentation_repository_factory = repository_factory or PresentationRepository
    app.state.geometry_artifact_store = artifact_store or GeometryArtifactStore()
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.include_router(router)

    @app.middleware("http")
    async def instrument_presentation_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        _log_request_metrics(request, response, duration_ms=(time.perf_counter() - start) * 1000.0)
        return response

    @app.get("/api/search")
    def root_search(
        request: Request,
        q: str = Query(..., min_length=1),
        limit: int = Query(default=5, ge=1, le=5),
    ) -> dict[str, object]:
        return search(request=request, q=q, limit=limit)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    static_dir = Path(os.getenv("PRESENTATION_STATIC_DIR", "/app/services/presentation/frontend/dist"))
    if static_dir.exists():
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="presentation-assets")

        @app.get("/")
        def root() -> FileResponse:
            return FileResponse(static_dir / "index.html")

        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"error": "not_found"})
            requested = static_dir / full_path
            if requested.is_file():
                return FileResponse(requested)
            if "." in Path(full_path).name:
                return JSONResponse(status_code=404, content={"error": "not_found"})
            return FileResponse(static_dir / "index.html")

    return app
