from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from services.common.logging import configure_logging
from services.common.migrations import run_startup_migrations
from services.presentation.backend.repository import PresentationRepository


router = APIRouter(prefix="/api/map")


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
            "document_count": row["document_count"],
            "parent_location_id": _as_str_or_none(row["parent_location_id"]),
        }
        for row in rows
    ]


@router.get("/location/{location_id}/documents")
def get_location_documents(location_id: UUID) -> dict[str, object]:
    repo = PresentationRepository()
    resolved = repo.resolve_location_for_documents(location_id)
    if resolved is None:
        return {
            "requested_location_id": str(location_id),
            "resolved_location_id": None,
            "fallback_depth": None,
            "items": [],
        }

    resolved_uuid = UUID(resolved.location_id)
    items = repo.list_location_documents(resolved_uuid)
    location_display = repo.get_location_name(resolved_uuid)
    serialized_items = [
        _serialize_document_card(
            {
                **item,
                "location_display": location_display,
            }
        )
        for item in items
    ]
    return {
        "requested_location_id": str(location_id),
        "resolved_location_id": resolved.location_id,
        "fallback_depth": resolved.depth,
        "items": _dedupe_by_id(serialized_items, "document_id"),
    }


@router.get("/document/{document_id}")
def get_document(document_id: UUID) -> dict[str, object]:
    repo = PresentationRepository()
    item = repo.get_document_card(document_id)
    if item is None:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    return _serialize_document_card(item)


@router.get("/document/{document_id}/pdf")
def get_document_pdf(document_id: UUID) -> Response:
    repo = PresentationRepository()
    payload = repo.get_document_pdf(document_id)
    if payload is None:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    return Response(content=payload, media_type="application/pdf")


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
        configure_logging()
        run_startup_migrations()

    return app
