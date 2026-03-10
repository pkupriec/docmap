from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from services.presentation.backend import api
from services.presentation.backend.api import create_presentation_app
from services.presentation.backend.repository import ResolvedLocation


class PresentationRepo:
    def list_locations(self):
        return [
            {
                "location_id": UUID("00000000-0000-0000-0000-000000000001"),
                "name": "Paris, France",
                "latitude": 48.8566,
                "longitude": 2.3522,
                "precision": "city",
                "document_count": 3,
                "parent_location_id": UUID("00000000-0000-0000-0000-000000000011"),
            }
        ]

    def resolve_location_for_documents(self, location_id):
        return ResolvedLocation(location_id=str(location_id), depth=0)

    def list_location_documents(self, location_id):
        return [
            {
                "document_id": UUID("00000000-0000-0000-0000-000000000101"),
                "scp_object_id": UUID("00000000-0000-0000-0000-000000000201"),
                "title": "SCP-101",
                "url": "https://scp-wiki.wikidot.com/scp-101",
                "preview_text": "Recovered near Paris.",
                "evidence_quote": "near Paris",
                "mention_count": 2,
            }
        ]

    def list_document_locations(self, document_id):
        return [
            {
                "document_id": document_id,
                "location_id": UUID("00000000-0000-0000-0000-000000000001"),
                "name": "Paris, France",
                "latitude": 48.8566,
                "longitude": 2.3522,
                "precision": "city",
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


def test_locations_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(api, "PresentationRepository", PresentationRepo)
    monkeypatch.setattr(api, "run_startup_migrations", lambda: None)
    app = create_presentation_app()
    client = TestClient(app)

    response = client.get("/api/map/locations")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "Paris, France"
    assert payload[0]["location_id"] == "00000000-0000-0000-0000-000000000001"


def test_location_documents_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(api, "PresentationRepository", PresentationRepo)
    monkeypatch.setattr(api, "run_startup_migrations", lambda: None)
    app = create_presentation_app()
    client = TestClient(app)

    response = client.get("/api/map/location/00000000-0000-0000-0000-000000000001/documents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fallback_depth"] == 0
    assert payload["items"][0]["title"] == "SCP-101"


def test_document_locations_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(api, "PresentationRepository", PresentationRepo)
    monkeypatch.setattr(api, "run_startup_migrations", lambda: None)
    app = create_presentation_app()
    client = TestClient(app)

    response = client.get("/api/map/document/00000000-0000-0000-0000-000000000101/locations")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["name"] == "Paris, France"


def test_density_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(api, "PresentationRepository", PresentationRepo)
    monkeypatch.setattr(api, "run_startup_migrations", lambda: None)
    app = create_presentation_app()
    client = TestClient(app)

    response = client.get("/api/map/overlays/density")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["document_count"] == 3

