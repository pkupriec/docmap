from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from services.presentation.backend import api as api_module
from services.presentation.backend.api import create_presentation_app
from services.presentation.backend.geometry_artifacts import GeometryArtifactStore
from services.presentation.backend.repository import (
    LocationDocumentsResult,
    ResolvedLocation,
    ScopedLocationDocuments,
)


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000101")
LOCATION_ID = UUID("00000000-0000-0000-0000-000000000001")
PDF = b"%PDF-1.7\n"
THUMBNAIL = b"RIFF-webp"


def seed_geometry(root: Path) -> GeometryArtifactStore:
    version = "2026-08-26"
    version_root = root / version
    version_root.mkdir(parents=True)
    archive = version_root / "balanced_precise.pmtiles"
    archive.write_bytes(b"0123456789")
    (root / "current.json").write_text(
        json.dumps({"current_version": version, "manifest": f"{version}/manifest.json"}),
        encoding="utf-8",
    )
    (version_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "tile_format": "pmtiles",
                "min_zoom": 0,
                "max_zoom": 8,
                "modes": {
                    "balanced_precise": {
                        "path": f"{version}/balanced_precise.pmtiles",
                        "byte_size": archive.stat().st_size,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return GeometryArtifactStore(root)


class FakeRepository:
    range_calls: list[tuple[int, int]] = []
    boundary_calls = 0

    def list_locations(self):
        return [{
            "location_id": LOCATION_ID,
            "name": "Paris, France",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "precision": "city",
            "location_rank": "city",
            "document_count": 3,
            "parent_location_id": None,
        }]

    def get_admin_boundaries_geojson(self, *, selected_location_id=None, highlighted_location_ids=None):
        FakeRepository.boundary_calls += 1
        ids = sorted({value for value in [selected_location_id, *(highlighted_location_ids or ())] if value})
        return {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"location_id": value}, "geometry": {"type": "Polygon", "coordinates": []}}
            for value in ids
        ]}

    def get_location_documents(self, location_id, *, limit, offset):
        return LocationDocumentsResult(
            resolved=ResolvedLocation(location_id=str(location_id), depth=0, location_rank="city"),
            location_display="Paris, France",
            scoped=ScopedLocationDocuments(
                scope_rank="city",
                location_count=1,
                total_items=1,
                items=[self.get_document_card(DOCUMENT_ID)],
            ),
        )

    def get_document_card(self, document_id):
        return {
            "document_id": document_id,
            "scp_number": "SCP-101",
            "canonical_scp_id": "scp-101",
            "scp_url": "https://scp-wiki.wikidot.com/scp-101",
            "location_display": "Paris, France",
            "pdf_url": f"/api/map/document/{document_id}/pdf",
            "thumbnail_url": f"/api/map/document/{document_id}/thumbnail",
        }

    def get_document_pdf_size(self, document_id):
        return len(PDF)

    def get_document_pdf(self, document_id):
        return PDF

    def get_document_pdf_range(self, document_id, *, start, length):
        FakeRepository.range_calls.append((start, length))
        return PDF[start : start + length]

    def get_document_thumbnail(self, document_id):
        return THUMBNAIL

    def list_document_locations(self, document_id):
        return [{
            "document_id": document_id,
            "location_id": LOCATION_ID,
            "name": "Paris, France",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "precision": "city",
            "location_rank": "city",
            "evidence_quote": "near Paris",
            "mention_count": 2,
        }]

    def list_density_points(self):
        return [{"latitude": 48.8566, "longitude": 2.3522, "document_count": 3}]

    def search(self, query, limit):
        return {"documents": [self.get_document_card(DOCUMENT_ID)], "locations": self.list_locations()}


def client(tmp_path: Path) -> TestClient:
    FakeRepository.range_calls.clear()
    FakeRepository.boundary_calls = 0
    app = create_presentation_app(
        repository_factory=FakeRepository,
        artifact_store=seed_geometry(tmp_path / "geometry"),
    )
    return TestClient(app)


def test_locations_and_document_discovery(tmp_path) -> None:
    api = client(tmp_path)

    locations = api.get("/api/map/locations")
    documents = api.get(f"/api/map/location/{LOCATION_ID}/documents")

    assert locations.status_code == 200
    assert locations.json()[0]["name"] == "Paris, France"
    assert documents.status_code == 200
    assert documents.json()["items"][0]["scp_number"] == "SCP-101"


def test_boundaries_accept_only_explicit_ids_and_cache_canonical_shape(tmp_path) -> None:
    api = client(tmp_path)
    first = api.get(
        "/api/map/boundaries",
        params={
            "selected_location_id": str(LOCATION_ID),
            "highlighted_location_ids": "00000000-0000-0000-0000-000000000003,00000000-0000-0000-0000-000000000002",
        },
    )
    second = api.get(
        "/api/map/boundaries",
        params={
            "selected_location_id": str(LOCATION_ID),
            "highlighted_location_ids": "00000000-0000-0000-0000-000000000002,00000000-0000-0000-0000-000000000003",
        },
    )

    assert first.status_code == second.status_code == 200
    assert len(first.json()["features"]) == 3
    assert FakeRepository.boundary_calls == 1
    assert api.get("/api/map/boundaries?bbox=0,0,1,1").status_code == 422


def test_pmtiles_manifest_and_range_delivery(tmp_path) -> None:
    api = client(tmp_path)

    manifest = api.get("/api/map/baked/manifest")
    partial = api.get(manifest.json()["archive_url"], headers={"Range": "bytes=2-5"})

    assert manifest.status_code == 200
    assert manifest.json()["tile_format"] == "pmtiles"
    assert "tile_url_template" not in manifest.json()
    assert partial.status_code == 206
    assert partial.content == b"2345"
    assert partial.headers["content-range"] == "bytes 2-5/10"
    assert api.get("/api/map/baked/tile-index").status_code == 404


def test_pdf_range_is_fetched_as_database_slice(tmp_path) -> None:
    api = client(tmp_path)

    response = api.get(f"/api/map/document/{DOCUMENT_ID}/pdf", headers={"Range": "bytes=0-3"})

    assert response.status_code == 206
    assert response.content == b"%PDF"
    assert response.headers["content-range"] == "bytes 0-3/9"
    assert FakeRepository.range_calls == [(0, 4)]


def test_pdf_rejects_multiple_ranges(tmp_path) -> None:
    response = client(tmp_path).get(
        f"/api/map/document/{DOCUMENT_ID}/pdf",
        headers={"Range": "bytes=0-1,3-4"},
    )

    assert response.status_code == 416
    assert response.headers["content-range"] == "bytes */9"


def test_search_and_document_locations(tmp_path) -> None:
    api = client(tmp_path)

    search = api.get("/api/search?q=paris")
    links = api.get(f"/api/map/document/{DOCUMENT_ID}/locations")

    assert search.status_code == 200
    assert search.json()["documents"][0]["document_id"] == str(DOCUMENT_ID)
    assert links.status_code == 200
    assert links.json()[0]["location_id"] == str(LOCATION_ID)


def test_document_thumbnail_is_served_as_webp(tmp_path) -> None:
    api = client(tmp_path)

    card = api.get(f"/api/map/document/{DOCUMENT_ID}")
    thumbnail = api.get(card.json()["thumbnail_url"])

    assert card.json()["thumbnail_url"].endswith("/thumbnail")
    assert thumbnail.status_code == 200
    assert thumbnail.headers["content-type"] == "image/webp"
    assert thumbnail.content == THUMBNAIL


def test_lifespan_opens_read_only_pool_and_closes_it(monkeypatch, tmp_path) -> None:
    calls: list[object] = []

    class FakePool:
        def open(self):
            calls.append("open")

        def wait(self):
            calls.append("wait")

        def close(self):
            calls.append("close")

        def connection(self):
            raise AssertionError("health check must not acquire a database connection")

    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setattr(
        api_module,
        "create_connection_pool",
        lambda **kwargs: calls.append(kwargs) or FakePool(),
    )
    monkeypatch.setattr(api_module, "PresentationRepository", FakeRepository)
    app = create_presentation_app(artifact_store=seed_geometry(tmp_path / "geometry"))

    with TestClient(app) as api:
        assert api.get("/healthz").status_code == 200

    assert calls == [{"read_only": True}, "open", "wait", "close"]
