from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from services.presentation.backend import api
from services.presentation.backend.api import create_presentation_app
from services.presentation.backend.repository import ResolvedLocation


class PresentationRepo:
    last_boundaries_minimal: bool | None = None
    last_boundaries_rank_filter: str | None = None
    last_boundaries_geometry_detail: str | None = None
    boundaries_calls: int = 0

    def get_admin_boundaries_geojson(
        self,
        *,
        minimal: bool = False,
        rank_filter: str = "default",
        geometry_detail: str = "full",
    ):
        PresentationRepo.last_boundaries_minimal = minimal
        PresentationRepo.last_boundaries_rank_filter = rank_filter
        PresentationRepo.last_boundaries_geometry_detail = geometry_detail
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
    monkeypatch.setattr(api, "PresentationRepository", PresentationRepo)
    monkeypatch.setattr(api, "run_startup_migrations", lambda: None)
    api.BOUNDARIES_CACHE.clear()
    PresentationRepo.boundaries_calls = 0
    PresentationRepo.last_boundaries_minimal = None
    PresentationRepo.last_boundaries_rank_filter = None
    PresentationRepo.last_boundaries_geometry_detail = None
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
    assert PresentationRepo.last_boundaries_geometry_detail == "full"


def test_boundaries_lite_endpoint(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/map/boundaries?lite=1&rank_filter=all&geometry_detail=full")

    assert response.status_code == 200
    assert PresentationRepo.last_boundaries_minimal is True
    assert PresentationRepo.last_boundaries_rank_filter == "all"
    assert PresentationRepo.last_boundaries_geometry_detail == "full"


def test_boundaries_endpoint_uses_in_process_cache(monkeypatch) -> None:
    client = _client(monkeypatch)

    response1 = client.get("/api/map/boundaries?lite=1&rank_filter=default&geometry_detail=full")
    response2 = client.get("/api/map/boundaries?lite=1&rank_filter=default&geometry_detail=full")

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert PresentationRepo.boundaries_calls == 1


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
