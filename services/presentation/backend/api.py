from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from services.common.logging import configure_logging
from services.common.migrations import run_startup_migrations
from services.presentation.backend.repository import PresentationRepository


router = APIRouter(prefix="/api/map")


def _as_str_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


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
    items = repo.list_location_documents(UUID(resolved.location_id))
    return {
        "requested_location_id": str(location_id),
        "resolved_location_id": resolved.location_id,
        "fallback_depth": resolved.depth,
        "items": [
            {
                "document_id": str(item["document_id"]),
                "scp_object_id": _as_str_or_none(item["scp_object_id"]),
                "title": item["title"],
                "url": item["url"],
                "preview_text": item["preview_text"],
                "evidence_quote": item["evidence_quote"],
                "mention_count": item["mention_count"],
            }
            for item in items
        ],
    }


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


def create_presentation_app() -> FastAPI:
    app = FastAPI(title="DocMap Presentation API", version="1.0.0")
    app.include_router(router)

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
            return FileResponse(static_dir / "index.html")

    @app.on_event("startup")
    def _startup() -> None:
        configure_logging()
        run_startup_migrations()

    return app
