from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from services.presentation.backend import api
from services.presentation.backend.api import create_presentation_app
from services.presentation.backend.repository import ResolvedLocation


def _seed_baked_geometry(root: Path) -> tuple[str, str]:
    version = "2026-04-17-phase-a"
    mode = "balanced_precise"
    (root / version / mode / "0" / "0").mkdir(parents=True, exist_ok=True)
    (root / version / mode / "0" / "0" / "0.mvt").write_bytes(b"\x1f\x8b")
    (root / "current.json").write_text(
        json.dumps(
            {
                "current_version": version,
                "manifest": f"{version}/manifest.json",
            }
        ),
        encoding="utf-8",
    )
    (root / version / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tile_format": "mvt",
                "zoom_min": 0,
                "zoom_max": 8,
                "modes": {
                    "balanced_precise": {
                        "path": f"{version}/balanced_precise",
                        "tolerance_by_zoom_band": {"world": 8, "regional": 4, "local": 2},
                    },
                    "full_precise": {
                        "path": f"{version}/full_precise",
                        "tolerance_by_zoom_band": {"world": 0, "regional": 0, "local": 0},
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return version, mode


class PresentationRepo:
    last_boundaries_minimal: bool | None = None
    last_boundaries_rank_filter: str | None = None
    last_boundaries_ranks: tuple[str, ...] | None = None
    last_boundaries_chunk_ids: tuple[str, ...] | None = None
    last_boundaries_viewport_bucket: str | None = None
    last_boundaries_bbox: tuple[float, float, float, float] | None = None
    last_boundaries_selected_location_id: str | None = None
    last_boundaries_highlighted_location_ids: tuple[str, ...] | None = None
    boundaries_calls: int = 0

    def get_admin_boundaries_geojson(
        self,
        *,
        minimal: bool = False,
        rank_filter: str = "default",
        ranks: tuple[str, ...] | list[str] | None = None,
        chunk_ids: tuple[str, ...] | list[str] | None = None,
        viewport_bucket: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        selected_location_id: str | None = None,
        highlighted_location_ids: tuple[str, ...] | list[str] | None = None,
    ):
        PresentationRepo.last_boundaries_minimal = minimal
        PresentationRepo.last_boundaries_rank_filter = rank_filter
        PresentationRepo.last_boundaries_ranks = tuple(ranks or ())
        PresentationRepo.last_boundaries_chunk_ids = tuple(chunk_ids or ())
        PresentationRepo.last_boundaries_viewport_bucket = viewport_bucket
        PresentationRepo.last_boundaries_bbox = bbox
        PresentationRepo.last_boundaries_selected_location_id = selected_location_id
        PresentationRepo.last_boundaries_highlighted_location_ids = tuple(highlighted_location_ids or ())
        PresentationRepo.boundaries_calls += 1
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "location_id": "00000000-0000-0000-0000-000000000001",
                        "location_rank": "country",
                        "location_name": "France",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[2.0, 46.0], [3.0, 46.0], [3.0, 47.0], [2.0, 46.0]]],
                    },
                }
            ],
        }

    def list_locations(self):
        return [
            {
                "location_id": UUID("00000000-0000-0000-0000-000000000001"),
                "name": "Paris, France",
                "latitude": 48.8566,
                "longitude": 2.3522,
                "precision": "city",
                "location_rank": "city",
                "document_count": 3,
                "parent_location_id": UUID("00000000-0000-0000-0000-000000000011"),
            }
        ]

    def resolve_location_for_documents(self, location_id):
        return ResolvedLocation(location_id=str(location_id), depth=0, location_rank="city")

    def get_location_name(self, location_id):
        return "Paris, France"

    def list_location_documents(self, location_id, *, scope_rank: str, limit: int, offset: int):
        assert scope_rank == "city"
        assert limit >= 1
        assert offset >= 0
        from services.presentation.backend.repository import ScopedLocationDocuments

        return ScopedLocationDocuments(
            scope_rank="city",
            location_count=1,
            total_items=1,
            items=[
                {
                    "document_id": UUID("00000000-0000-0000-0000-000000000101"),
                    "scp_number": "SCP-101",
                    "canonical_scp_id": "scp-101",
                    "scp_url": "https://scp-wiki.wikidot.com/scp-101",
                    "pdf_url": "/api/map/document/00000000-0000-0000-0000-000000000101/pdf",
                },
                {
                    "document_id": UUID("00000000-0000-0000-0000-000000000101"),
                    "scp_number": "SCP-101",
                    "canonical_scp_id": "scp-101",
                    "scp_url": "https://scp-wiki.wikidot.com/scp-101",
                    "pdf_url": "/api/map/document/00000000-0000-0000-0000-000000000101/pdf",
                },
            ],
        )

    def get_document_card(self, document_id):
        return {
            "document_id": document_id,
            "scp_number": "SCP-101",
            "canonical_scp_id": "scp-101",
            "scp_url": "https://scp-wiki.wikidot.com/scp-101",
            "location_display": "Paris, France",
            "pdf_url": f"/api/map/document/{document_id}/pdf",
        }

    def get_document_pdf(self, document_id):
        return b"%PDF-1.7\n"

    def list_document_locations(self, document_id):
        return [
            {
                "document_id": document_id,
                "location_id": UUID("00000000-0000-0000-0000-000000000001"),
                "name": "Paris, France",
                "latitude": 48.8566,
                "longitude": 2.3522,
                "precision": "city",
                "location_rank": "city",
                "evidence_quote": "near Paris",
                "mention_count": 2,
            }
        ]

    def list_density_points(self):
        return [
            {
                "latitude": 48.8566,
                "longitude": 2.3522,
                "document_count": 3,
            }
        ]

    def search(self, query: str, limit: int):
        return {
            "documents": [
                {
                    "document_id": UUID("00000000-0000-0000-0000-000000000101"),
                    "scp_number": "SCP-101",
                    "canonical_scp_id": "scp-101",
                    "scp_url": "https://scp-wiki.wikidot.com/scp-101",
                    "location_display": "Paris, France",
                    "pdf_url": "/api/map/document/00000000-0000-0000-0000-000000000101/pdf",
                },
                {
                    "document_id": UUID("00000000-0000-0000-0000-000000000101"),
                    "scp_number": "SCP-101",
                    "canonical_scp_id": "scp-101",
                    "scp_url": "https://scp-wiki.wikidot.com/scp-101",
                    "location_display": "Paris, France",
                    "pdf_url": "/api/map/document/00000000-0000-0000-0000-000000000101/pdf",
                },
            ][:limit],
            "locations": [
                {
                    "location_id": UUID("00000000-0000-0000-0000-000000000001"),
                    "name": "Paris, France",
                    "latitude": 48.8566,
                    "longitude": 2.3522,
                    "precision": "city",
                    "location_rank": "city",
                    "document_count": 3,
                    "parent_location_id": UUID("00000000-0000-0000-0000-000000000011"),
                },
                {
                    "location_id": UUID("00000000-0000-0000-0000-000000000001"),
                    "name": "Paris, France",
                    "latitude": 48.8566,
                    "longitude": 2.3522,
                    "precision": "city",
                    "location_rank": "city",
                    "document_count": 3,
                    "parent_location_id": UUID("00000000-0000-0000-0000-000000000011"),
                },
            ][:limit],
        }


def _client(monkeypatch) -> TestClient:
    baked_root = Path(tempfile.mkdtemp(prefix="docmap-baked-test-"))
    _seed_baked_geometry(baked_root)
    monkeypatch.setattr(api, "PresentationRepository", PresentationRepo)
    monkeypatch.setattr(api, "run_startup_migrations", lambda: None)
    monkeypatch.setenv("DOCMAP_PRESENTATION_BAKED_GEOMETRY_ROOT", str(baked_root))
    api.BOUNDARIES_CACHE.clear()
    PresentationRepo.boundaries_calls = 0
    PresentationRepo.last_boundaries_minimal = None
    PresentationRepo.last_boundaries_rank_filter = None
    PresentationRepo.last_boundaries_ranks = None
    PresentationRepo.last_boundaries_chunk_ids = None
    PresentationRepo.last_boundaries_viewport_bucket = None
    PresentationRepo.last_boundaries_bbox = None
    PresentationRepo.last_boundaries_selected_location_id = None
    PresentationRepo.last_boundaries_highlighted_location_ids = None
    app = create_presentation_app()
    return TestClient(app)


def test_locations_endpoint(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/locations")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "Paris, France"
    assert payload[0]["location_id"] == "00000000-0000-0000-0000-000000000001"
    assert payload[0]["location_rank"] == "city"


def test_boundaries_endpoint(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/boundaries")

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 1
    assert payload["features"][0]["properties"]["location_rank"] == "country"
    assert PresentationRepo.last_boundaries_minimal is False
    assert PresentationRepo.last_boundaries_rank_filter == "default"
    assert PresentationRepo.last_boundaries_ranks == ()
    assert PresentationRepo.last_boundaries_chunk_ids == ()
    assert PresentationRepo.last_boundaries_viewport_bucket is None
    assert PresentationRepo.last_boundaries_bbox is None
    assert PresentationRepo.last_boundaries_selected_location_id is None
    assert PresentationRepo.last_boundaries_highlighted_location_ids == ()


def test_baked_manifest_endpoint(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/baked/manifest?mode=balanced_precise")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "2026-04-17-phase-a"
    assert payload["mode"] == "balanced_precise"
    assert payload["default_mode"] == "balanced_precise"
    assert payload["tile_url_template"].endswith("/api/map/baked/tiles/2026-04-17-phase-a/balanced_precise/{z}/{x}/{y}.mvt")
    assert "balanced_precise" in payload["available_modes"]


def test_baked_manifest_uses_configured_default_mode(monkeypatch) -> None:
    monkeypatch.setenv("DOCMAP_PRESENTATION_DEFAULT_PRECISION_MODE", "full_precise")
    client = _client(monkeypatch)

    response = client.get("/api/map/baked/manifest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["default_mode"] == "full_precise"
    assert payload["mode"] == "full_precise"


def test_baked_tile_endpoint(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/baked/tiles/2026-04-17-phase-a/balanced_precise/0/0/0.mvt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.mapbox-vector-tile")
    assert response.content == b"\x1f\x8b"


def test_baked_tile_index_endpoint(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/baked/tile-index?mode=balanced_precise")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "2026-04-17-phase-a"
    assert payload["mode"] == "balanced_precise"
    assert payload["tile_count"] == 1
    assert payload["tiles"] == ["0/0/0"]


def test_baked_tile_endpoint_not_found(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/baked/tiles/2026-04-17-phase-a/balanced_precise/0/0/9.mvt")

    assert response.status_code == 404


def test_boundaries_scoped_endpoint_normalizes_shape(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get(
        "/api/map/boundaries"
        "?lite=1"
        "&rank_filter=all"
        "&ranks=country,region,city"
        "&bbox=170,-12,-170,18"
        "&selected_location_id=00000000-0000-0000-0000-000000000011"
        "&highlighted_location_ids=00000000-0000-0000-0000-000000000012,00000000-0000-0000-0000-000000000010",
    )

    assert response.status_code == 200
    assert PresentationRepo.last_boundaries_minimal is True
    assert PresentationRepo.last_boundaries_rank_filter == "all"
    assert PresentationRepo.last_boundaries_ranks == ("country", "admin_region", "city")
    assert PresentationRepo.last_boundaries_bbox == (170.0, -12.0, -170.0, 18.0)
    assert PresentationRepo.last_boundaries_selected_location_id == "00000000-0000-0000-0000-000000000011"
    assert PresentationRepo.last_boundaries_highlighted_location_ids == (
        "00000000-0000-0000-0000-000000000010",
        "00000000-0000-0000-0000-000000000012",
    )


def test_boundaries_bucket_endpoint_normalizes_shape(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get(
        "/api/map/boundaries"
        "?lite=1"
        "&ranks=country,region,city"
        "&viewport_bucket=regional:-20:-24:40:36"
        "&selected_location_id=00000000-0000-0000-0000-000000000011"
        "&highlighted_location_ids=00000000-0000-0000-0000-000000000012,00000000-0000-0000-0000-000000000010",
    )

    assert response.status_code == 200
    assert PresentationRepo.last_boundaries_minimal is True
    assert PresentationRepo.last_boundaries_rank_filter == "default"
    assert PresentationRepo.last_boundaries_ranks == ("country", "admin_region", "city")
    assert PresentationRepo.last_boundaries_viewport_bucket == "regional:-20:-24:40:36"
    assert PresentationRepo.last_boundaries_bbox is None
    assert PresentationRepo.last_boundaries_selected_location_id == "00000000-0000-0000-0000-000000000011"
    assert PresentationRepo.last_boundaries_highlighted_location_ids == (
        "00000000-0000-0000-0000-000000000010",
        "00000000-0000-0000-0000-000000000012",
    )


def test_boundaries_chunk_endpoint_normalizes_shape(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get(
        "/api/map/boundaries"
        "?lite=1"
        "&ranks=country,region,city"
        "&chunk_ids=regional:3:4,regional:2:4,regional:2:4"
        "&selected_location_id=00000000-0000-0000-0000-000000000011"
        "&highlighted_location_ids=00000000-0000-0000-0000-000000000012,00000000-0000-0000-0000-000000000010",
    )

    assert response.status_code == 200
    assert PresentationRepo.last_boundaries_minimal is True
    assert PresentationRepo.last_boundaries_rank_filter == "default"
    assert PresentationRepo.last_boundaries_ranks == ("country", "admin_region", "city")
    assert PresentationRepo.last_boundaries_chunk_ids == ("regional:2:4", "regional:3:4")
    assert PresentationRepo.last_boundaries_viewport_bucket is None
    assert PresentationRepo.last_boundaries_bbox is None


def test_boundaries_bucket_endpoint_uses_in_process_cache_for_identical_request_shape(monkeypatch) -> None:
    client = _client(monkeypatch)

    response1 = client.get(
        "/api/map/boundaries"
        "?lite=1"
        "&ranks=city,region"
        "&viewport_bucket=regional:-20:-12:20:12"
        "&highlighted_location_ids=00000000-0000-0000-0000-000000000002,00000000-0000-0000-0000-000000000001",
    )
    response2 = client.get(
        "/api/map/boundaries"
        "?lite=1"
        "&ranks=region,city"
        "&viewport_bucket=regional:-20:-12:20:12"
        "&highlighted_location_ids=00000000-0000-0000-0000-000000000001,00000000-0000-0000-0000-000000000002",
    )

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert PresentationRepo.boundaries_calls == 1


def test_boundaries_chunk_endpoint_uses_in_process_cache_for_identical_request_shape(monkeypatch) -> None:
    client = _client(monkeypatch)

    response1 = client.get(
        "/api/map/boundaries"
        "?lite=1"
        "&ranks=city,region"
        "&chunk_ids=regional:3:4,regional:2:4"
        "&highlighted_location_ids=00000000-0000-0000-0000-000000000002,00000000-0000-0000-0000-000000000001",
    )
    response2 = client.get(
        "/api/map/boundaries"
        "?lite=1"
        "&ranks=region,city"
        "&chunk_ids=regional:2:4,regional:3:4"
        "&highlighted_location_ids=00000000-0000-0000-0000-000000000001,00000000-0000-0000-0000-000000000002",
    )

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert PresentationRepo.boundaries_calls == 1


def test_boundaries_bucket_and_bbox_are_mutually_exclusive(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/boundaries?viewport_bucket=world:-180:-30:180:60&bbox=-10,-5,10,5")

    assert response.status_code == 422
    assert "viewport_bucket" in response.text


def test_boundaries_chunk_ids_and_bbox_are_mutually_exclusive(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/boundaries?chunk_ids=world:0:0&bbox=-10,-5,10,5")

    assert response.status_code == 422
    assert "chunk_ids" in response.text


def test_boundaries_chunk_ids_and_viewport_bucket_are_mutually_exclusive(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/boundaries?chunk_ids=world:0:0&viewport_bucket=world:-180:-30:180:60")

    assert response.status_code == 422
    assert "chunk_ids" in response.text


def test_boundaries_rejects_invalid_viewport_bucket(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/boundaries?viewport_bucket=regional:-10:-5:10:5")

    assert response.status_code == 422
    assert "viewport_bucket" in response.text


def test_boundaries_rejects_invalid_chunk_ids(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/boundaries?chunk_ids=regional:99:0")

    assert response.status_code == 422
    assert "chunk_ids" in response.text


def test_boundaries_rejects_removed_geometry_detail(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/boundaries?geometry_detail=low")

    assert response.status_code == 422
    assert "geometry_detail" in response.text


def test_boundaries_rejects_invalid_bbox(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/boundaries?bbox=10,20,30")

    assert response.status_code == 422
    assert "bbox" in response.text


def test_boundaries_rejects_invalid_highlighted_ids(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/boundaries?highlighted_location_ids=not-a-uuid")

    assert response.status_code == 422
    assert "highlighted_location_ids" in response.text


def test_location_documents_endpoint(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/location/00000000-0000-0000-0000-000000000001/documents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback_depth"] == 0
    assert payload["scope_rank"] == "city"
    assert payload["scope_location_count"] == 1
    assert payload["total_items"] == 1
    assert payload["returned_items"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["scp_number"] == "SCP-101"
    assert payload["items"][0]["location_display"] == "Paris, France"


def test_document_endpoint(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/document/00000000-0000-0000-0000-000000000101")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scp_number"] == "SCP-101"
    assert payload["canonical_scp_id"] == "scp-101"


def test_document_pdf_endpoint(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/document/00000000-0000-0000-0000-000000000101/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == str(len(b"%PDF-1.7\n"))


def test_document_pdf_range_endpoint(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get(
        "/api/map/document/00000000-0000-0000-0000-000000000101/pdf",
        headers={"Range": "bytes=0-3"},
    )

    assert response.status_code == 206
    assert response.content == b"%PDF"
    assert response.headers["content-range"] == "bytes 0-3/9"


def test_document_locations_endpoint(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/document/00000000-0000-0000-0000-000000000101/locations")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["name"] == "Paris, France"
    assert payload[0]["location_rank"] == "city"


def test_density_endpoint(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/overlays/density")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["document_count"] == 3


def test_search_endpoint(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/search?q=scp-101&limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "scp-101"
    assert len(payload["documents"]) == 1
    assert len(payload["locations"]) == 1
    assert payload["documents"][0]["scp_number"] == "SCP-101"
    assert payload["locations"][0]["name"] == "Paris, France"
    assert payload["locations"][0]["location_rank"] == "city"


def test_search_limit_validation(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/search?q=paris&limit=6")

    assert response.status_code == 422


def test_locations_endpoint_logs_request_metrics(monkeypatch, caplog) -> None:
    client = _client(monkeypatch)

    with caplog.at_level(logging.INFO, logger="services.presentation.backend.api"):
        response = client.get("/api/map/locations")

    assert response.status_code == 200
    assert any(
        "presentation.api_request route=/api/map/locations" in record.message
        and "status_code=200" in record.message
        and "response_bytes=" in record.message
        for record in caplog.records
    )


def test_boundaries_endpoint_logs_request_metrics(monkeypatch, caplog) -> None:
    client = _client(monkeypatch)

    with caplog.at_level(logging.INFO, logger="services.presentation.backend.api"):
        response = client.get("/api/map/boundaries?lite=1&chunk_ids=regional:2:4,regional:3:4")

    assert response.status_code == 200
    assert any(
        "presentation.api_request route=/api/map/boundaries" in record.message
        and "selector=chunk_ids" in record.message
        and "chunk_count=2" in record.message
        for record in caplog.records
    )


def test_baked_manifest_endpoint_logs_request_metrics(monkeypatch, caplog) -> None:
    client = _client(monkeypatch)

    with caplog.at_level(logging.INFO, logger="services.presentation.backend.api"):
        response = client.get("/api/map/baked/manifest?mode=balanced_precise")

    assert response.status_code == 200
    assert any(
        "presentation.api_request route=/api/map/baked/manifest" in record.message
        and "mode=balanced_precise" in record.message
        for record in caplog.records
    )


def test_baked_tile_endpoint_logs_request_metrics(monkeypatch, caplog) -> None:
    client = _client(monkeypatch)

    with caplog.at_level(logging.INFO, logger="services.presentation.backend.api"):
        response = client.get("/api/map/baked/tiles/2026-04-17-phase-a/balanced_precise/0/0/0.mvt")

    assert response.status_code == 200
    assert any(
        "presentation.api_request route=/api/map/baked/tiles/{version}/{mode}/{z}/{x}/{y}.mvt" in record.message
        and "version=2026-04-17-phase-a" in record.message
        and "mode=balanced_precise" in record.message
        for record in caplog.records
    )


def test_baked_tile_index_endpoint_logs_request_metrics(monkeypatch, caplog) -> None:
    client = _client(monkeypatch)

    with caplog.at_level(logging.INFO, logger="services.presentation.backend.api"):
        response = client.get("/api/map/baked/tile-index?mode=balanced_precise")

    assert response.status_code == 200
    assert any(
        "presentation.api_request route=/api/map/baked/tile-index" in record.message
        and "mode=balanced_precise" in record.message
        for record in caplog.records
    )


def test_location_documents_endpoint_logs_request_metrics(monkeypatch, caplog) -> None:
    client = _client(monkeypatch)

    with caplog.at_level(logging.INFO, logger="services.presentation.backend.api"):
        response = client.get(
            "/api/map/location/00000000-0000-0000-0000-000000000001/documents?limit=80&offset=0"
        )

    assert response.status_code == 200
    assert any(
        "presentation.api_request route=/api/map/location/{location_id}/documents" in record.message
        and "limit=80" in record.message
        and "offset=0" in record.message
        for record in caplog.records
    )


def test_document_locations_endpoint_logs_request_metrics(monkeypatch, caplog) -> None:
    client = _client(monkeypatch)

    with caplog.at_level(logging.INFO, logger="services.presentation.backend.api"):
        response = client.get("/api/map/document/00000000-0000-0000-0000-000000000101/locations")

    assert response.status_code == 200
    assert any(
        "presentation.api_request route=/api/map/document/{document_id}/locations" in record.message
        and "document_id=00000000-0000-0000-0000-000000000101" in record.message
        for record in caplog.records
    )


def test_search_endpoint_logs_request_metrics(monkeypatch, caplog) -> None:
    client = _client(monkeypatch)

    with caplog.at_level(logging.INFO, logger="services.presentation.backend.api"):
        response = client.get("/api/search?q=scp-101&limit=5")

    assert response.status_code == 200
    assert any(
        "presentation.api_request route=/api/search" in record.message
        and "query_length=7" in record.message
        and "limit=5" in record.message
        for record in caplog.records
    )
