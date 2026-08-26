from __future__ import annotations

import contextlib
import json
import os
import socket
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import pytest
import uvicorn
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from services.presentation.backend import api
from services.presentation.backend.api import create_presentation_app
from services.presentation.backend.geometry_artifacts import GeometryArtifactStore
from services.presentation.backend.repository import ResolvedLocation


class BrowserPresentationRepo:
    def get_admin_boundaries_geojson(
        self,
        *,
        selected_location_id: str | None = None,
        highlighted_location_ids: tuple[str, ...] | list[str] | None = None,
    ) -> dict[str, Any]:
        features: list[dict[str, Any]] = []
        for location_id in [selected_location_id, *(highlighted_location_ids or ())]:
            if location_id:
                features.append(
                    self._feature(
                        location_id=location_id,
                        location_name=f"explicit-{location_id}",
                        rank="country",
                    ),
                )
        deduped = {feature["properties"]["location_id"]: feature for feature in features}
        return {"type": "FeatureCollection", "features": list(deduped.values())}

    def list_locations(self):
        return [
            {
                "location_id": UUID("00000000-0000-0000-0000-000000000001"),
                "name": "Baked Focus One",
                "latitude": 48.8566,
                "longitude": 2.3522,
                "precision": "city",
                "location_rank": "city",
                "document_count": 3,
                "parent_location_id": None,
            },
            {
                "location_id": UUID("00000000-0000-0000-0000-000000000002"),
                "name": "Baked Focus Two",
                "latitude": 50.1109,
                "longitude": 8.6821,
                "precision": "city",
                "location_rank": "city",
                "document_count": 2,
                "parent_location_id": None,
            },
        ]

    def resolve_location_for_documents(self, location_id):
        return ResolvedLocation(location_id=str(location_id), depth=0, location_rank="city")

    def get_location_name(self, location_id):
        return "Baked Focus"

    def list_location_documents(self, location_id, *, scope_rank: str, limit: int, offset: int):
        from services.presentation.backend.repository import ScopedLocationDocuments

        return ScopedLocationDocuments(
            scope_rank="city",
            location_count=1,
            total_items=0,
            items=[],
        )

    def get_document_card(self, document_id):
        return None

    def get_document_pdf(self, document_id):
        return None

    def list_document_locations(self, document_id):
        return []

    def list_density_points(self):
        return []

    def search(self, query: str, limit: int):
        return {"documents": [], "locations": []}

    def _feature(self, *, location_id: str, location_name: str, rank: str) -> dict[str, Any]:
        return {
            "type": "Feature",
            "properties": {
                "location_id": location_id,
                "location_rank": rank,
                "location_name": location_name,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[2.0, 46.0], [3.0, 46.0], [3.0, 47.0], [2.0, 46.0]]],
            },
        }


def _seed_baked_geometry(root: Path) -> tuple[str, str]:
    version = "2026-04-17-phase-c"
    mode = "balanced_precise"
    all_modes = ("full_precise", "balanced_precise", "simplified", "primitive")
    (root / version).mkdir(parents=True, exist_ok=True)
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
                "schema_version": "v2",
                "tile_format": "pmtiles",
                "min_zoom": 0,
                "max_zoom": 8,
                "modes": {
                    "full_precise": {
                        "path": f"{version}/full_precise.pmtiles",
                    },
                    "balanced_precise": {
                        "path": f"{version}/balanced_precise.pmtiles",
                    },
                    "simplified": {
                        "path": f"{version}/simplified.pmtiles",
                    },
                    "primitive": {
                        "path": f"{version}/primitive.pmtiles",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    for baked_mode in all_modes:
        # The browser regression verifies range transport and lifecycle wiring;
        # archive encoding itself is covered by analytics tests.
        (root / version / f"{baked_mode}.pmtiles").write_bytes(b"\x00" * 16_384)
    return version, mode


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextlib.contextmanager
def _run_browser_app():
    dist_dir = Path("services/presentation/frontend/dist").resolve()
    if not dist_dir.exists():
        pytest.skip("presentation dist is missing; run the frontend build first")

    original_static_dir = os.environ.get("PRESENTATION_STATIC_DIR")
    original_baked_root = os.environ.get("DOCMAP_PRESENTATION_ARTIFACT_ROOT")
    baked_root = Path(tempfile.mkdtemp(prefix="docmap-baked-browser-"))
    _seed_baked_geometry(baked_root)
    api.BOUNDARIES_CACHE.clear()
    os.environ["PRESENTATION_STATIC_DIR"] = str(dist_dir)
    os.environ["DOCMAP_PRESENTATION_ARTIFACT_ROOT"] = str(baked_root)

    app = create_presentation_app(
        repository_factory=BrowserPresentationRepo,
        artifact_store=GeometryArtifactStore(baked_root),
    )
    port = _find_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.1)
        else:
            raise RuntimeError("browser regression server did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        if original_static_dir is None:
            os.environ.pop("PRESENTATION_STATIC_DIR", None)
        else:
            os.environ["PRESENTATION_STATIC_DIR"] = original_static_dir
        if original_baked_root is None:
            os.environ.pop("DOCMAP_PRESENTATION_ARTIFACT_ROOT", None)
        else:
            os.environ["DOCMAP_PRESENTATION_ARTIFACT_ROOT"] = original_baked_root


def _api_requests(page) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []

    def handle_request(request) -> None:
        path = urlparse(request.url).path
        if not path.startswith("/api/map/"):
            return
        requests.append({
            "path": path,
            "query": parse_qs(urlparse(request.url).query),
            "range": request.headers.get("range"),
        })

    page.on("request", handle_request)
    return requests


@pytest.mark.skipif(not Path("services/presentation/frontend/dist").exists(), reason="presentation dist missing")
def test_browser_baked_normal_view_and_explicit_live_overlays() -> None:
    with _run_browser_app() as base_url:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch()
            except PlaywrightError as exc:
                pytest.skip(f"playwright chromium unavailable: {exc}")

            page = browser.new_page()
            requests = _api_requests(page)
            page_errors: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(base_url, wait_until="domcontentloaded")
            page.wait_for_function("() => Boolean(window.__DOCMAP_TEST_HOOKS__?.setViewport)")
            page.wait_for_function(
                """
                () => {
                  const debug = window.__DOCMAP_TEST_HOOKS__.getBoundaryDebug();
                  return Boolean(debug.bakedArchiveUrl);
                }
                """,
            )
            page.wait_for_timeout(400)
            assert any(request["path"] == "/api/map/baked/manifest" for request in requests)
            page.wait_for_timeout(1_000)
            startup_debug = page.evaluate("() => window.__DOCMAP_TEST_HOOKS__.getBoundaryDebug()")
            assert any(request["path"].endswith("/balanced_precise.pmtiles") for request in requests), (
                page_errors,
                startup_debug,
            )
            assert any(
                request["path"].endswith("/balanced_precise.pmtiles") and request["range"]
                for request in requests
            )
            assert not any(request["path"] == "/api/map/boundaries" for request in requests)
            page.wait_for_function(
                """
                () => {
                  const debug = window.__DOCMAP_TEST_HOOKS__.getBoundaryDebug();
                  return debug.sessionPrecisionMode === 'balanced_precise';
                }
                """
            )
            debug = page.evaluate("() => window.__DOCMAP_TEST_HOOKS__.getBoundaryDebug()")
            assert debug["sessionPrecisionMode"] == "balanced_precise"
            assert debug["defaultPrecisionMode"] == "balanced_precise"
            assert debug["bakedArchiveUrl"].endswith("/balanced_precise.pmtiles")

            requests.clear()
            page.evaluate("() => window.__DOCMAP_TEST_HOOKS__.setPrecisionMode('simplified')")
            page.wait_for_function(
                """
                () => {
                  const debug = window.__DOCMAP_TEST_HOOKS__.getBoundaryDebug();
                  return debug.sessionPrecisionMode === 'simplified';
                }
                """
            )
            assert any(
                request["path"] == "/api/map/baked/manifest" and request["query"].get("mode") == ["simplified"]
                for request in requests
            )
            page.wait_for_timeout(300)
            assert any(request["path"].endswith("/simplified.pmtiles") for request in requests)
            assert not any(request["path"] == "/api/map/boundaries" for request in requests)

            requests.clear()
            page.evaluate(
                "(viewport) => window.__DOCMAP_TEST_HOOKS__.setViewport(viewport)",
                {"zoom": 4.5, "west": 0, "east": 40, "south": 24, "north": 48},
            )
            page.evaluate(
                "(viewport) => window.__DOCMAP_TEST_HOOKS__.setViewport(viewport)",
                {"zoom": 4.5, "west": 20, "east": 60, "south": 24, "north": 48},
            )
            page.wait_for_timeout(300)
            assert not any(request["path"] == "/api/map/boundaries" for request in requests)

            requests.clear()
            page.evaluate(
                "(locationIds) => window.__DOCMAP_TEST_HOOKS__.setHighlightedLocationIds(locationIds)",
                ["00000000-0000-0000-0000-000000000001"],
            )
            page.wait_for_function(
                "() => window.__DOCMAP_TEST_HOOKS__.getBoundaryDebug().explicitBoundaryLocationIds.length === 1"
            )
            assert any(request["path"] == "/api/map/boundaries" for request in requests)
            boundary_queries = [request["query"] for request in requests if request["path"] == "/api/map/boundaries"]
            assert all("chunk_ids" not in query for query in boundary_queries)
            assert all("viewport_bucket" not in query for query in boundary_queries)
            assert any("highlighted_location_ids" in query for query in boundary_queries)

            requests.clear()
            page.evaluate(
                "(locationId) => window.__DOCMAP_TEST_HOOKS__.setPinnedLocationId(locationId)",
                "00000000-0000-0000-0000-000000000002",
            )
            page.wait_for_function(
                "() => window.__DOCMAP_TEST_HOOKS__.getBoundaryDebug().explicitBoundaryLocationIds.length === 2"
            )
            assert any(request["path"] == "/api/map/boundaries" for request in requests)
            boundary_queries = [request["query"] for request in requests if request["path"] == "/api/map/boundaries"]
            assert all("chunk_ids" not in query for query in boundary_queries)
            assert all("viewport_bucket" not in query for query in boundary_queries)
            assert any("selected_location_id" in query for query in boundary_queries)

            browser.close()
