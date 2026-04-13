from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from services.common.logging import configure_logging
from services.common.migrations import run_startup_migrations
from services.presentation.backend.repository import PresentationRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/map")

RankFilter = Literal["default", "all"]
GeometryDetail = Literal["low", "full"]


class BoundariesCache:
    def __init__(self, *, ttl_seconds: float) -> None:
        self._ttl_seconds = ttl_seconds
        self._data: dict[tuple[bool, RankFilter, GeometryDetail], tuple[float, dict[str, object]]] = {}
        self._lock = threading.Lock()

    def get(self, key: tuple[bool, RankFilter, GeometryDetail]) -> dict[str, object] | None:
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

    def set(self, key: tuple[bool, RankFilter, GeometryDetail], payload: dict[str, object]) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + self._ttl_seconds, payload)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


BOUNDARIES_CACHE = BoundariesCache(ttl_seconds=10 * 60)


def _as_str_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


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
    lite: bool = Query(default=False),
    rank_filter: RankFilter = Query(default="default"),
    geometry_detail: GeometryDetail = Query(default="full"),
) -> dict[str, object]:
    cache_key = (lite, rank_filter, geometry_detail)
    cached_payload = BOUNDARIES_CACHE.get(cache_key)
    if cached_payload is not None:
        logger.info(
            "presentation.boundaries_cache_hit lite=%s rank_filter=%s geometry_detail=%s",
            lite,
            rank_filter,
            geometry_detail,
        )
        return cached_payload

    repo = PresentationRepository()
    start = time.perf_counter()
    payload = repo.get_admin_boundaries_geojson(
        minimal=lite,
        rank_filter=rank_filter,
        geometry_detail=geometry_detail,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    BOUNDARIES_CACHE.set(cache_key, payload)
    logger.info(
        "presentation.boundaries_cache_miss lite=%s rank_filter=%s geometry_detail=%s duration_ms=%.2f",
        lite,
        rank_filter,
        geometry_detail,
        elapsed_ms,
    )
    return payload


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
    scoped = repo.list_location_documents(
        resolved_uuid,
        scope_rank=resolved.location_rank,
        limit=limit,
        offset=offset,
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
        configure_logging()
        run_startup_migrations()

    return app
