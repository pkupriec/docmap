from __future__ import annotations

import json

from services.analytics.scripts import rebuild_admin_boundaries


class _DummyConn:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self) -> None:
        self.committed = True


class _DummyResult:
    def __init__(self, tmp_path) -> None:
        self.features_written = 12
        self.matched_by_rank = {"country": 3, "ocean": 2}
        self.total_by_rank = {"country": 5, "ocean": 2}
        self.output_path = tmp_path / "admin_boundaries.geojson"
        self.coverage_path = tmp_path / "admin_boundaries.coverage.json"


def test_rebuild_admin_boundaries_script_runs_source_and_asset_builders(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    source_path = tmp_path / "admin_boundaries_source.geojson"
    conn = _DummyConn()
    result = _DummyResult(tmp_path)

    monkeypatch.setenv("DOCMAP_ADMIN_BOUNDARIES_SOURCE", str(source_path))
    monkeypatch.setattr(
        rebuild_admin_boundaries,
        "build_source_dataset",
        lambda path: {"total_features": 34, "path_matches": str(path == source_path)},
    )
    monkeypatch.setattr(rebuild_admin_boundaries, "get_connection", lambda: conn)
    monkeypatch.setattr(
        rebuild_admin_boundaries,
        "build_admin_boundaries_asset",
        lambda db_conn, source_path=None: result,
    )
    monkeypatch.setattr(
        rebuild_admin_boundaries,
        "build_baked_geometry_assets",
        lambda db_conn: type(
            "BakeR",
            (),
            {
                "version": "v1-test",
                "manifest_path": tmp_path / "presentation_geometry" / "v1-test" / "manifest.json",
                "total_archives": 4,
            },
        )(),
    )

    exit_code = rebuild_admin_boundaries.main()

    assert exit_code == 0
    assert conn.committed is True

    payload = json.loads(capsys.readouterr().out)
    assert payload["source_path"] == str(source_path)
    assert payload["refreshed_source"] is True
    assert payload["source_stats"]["total_features"] == 34
    assert payload["features_written"] == 12
    assert payload["matched_by_rank"] == {"country": 3, "ocean": 2}
    assert payload["total_by_rank"] == {"country": 5, "ocean": 2}
    assert payload["baked_geometry_version"] == "v1-test"
    assert payload["baked_geometry_total_archives"] == 4


def test_rebuild_admin_boundaries_script_can_reuse_existing_source(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    source_path = tmp_path / "admin_boundaries_source.geojson"
    source_path.write_text('{"type":"FeatureCollection","features":[]}\n', encoding="utf-8")
    conn = _DummyConn()
    result = _DummyResult(tmp_path)

    monkeypatch.setenv("DOCMAP_ADMIN_BOUNDARIES_SOURCE", str(source_path))
    monkeypatch.setenv("DOCMAP_ADMIN_BOUNDARIES_REFRESH_SOURCE", "0")
    monkeypatch.setattr(
        rebuild_admin_boundaries,
        "build_source_dataset",
        lambda path: (_ for _ in ()).throw(AssertionError("source refresh should be skipped")),
    )
    monkeypatch.setattr(rebuild_admin_boundaries, "get_connection", lambda: conn)
    monkeypatch.setattr(
        rebuild_admin_boundaries,
        "build_admin_boundaries_asset",
        lambda db_conn, source_path=None: result,
    )
    monkeypatch.setattr(
        rebuild_admin_boundaries,
        "build_baked_geometry_assets",
        lambda db_conn: type(
            "BakeR",
            (),
            {
                "version": "v1-test",
                "manifest_path": tmp_path / "presentation_geometry" / "v1-test" / "manifest.json",
                "total_archives": 4,
            },
        )(),
    )

    exit_code = rebuild_admin_boundaries.main()

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["refreshed_source"] is False
    assert payload["source_stats"] == {"skipped_refresh": True}
    assert payload["baked_geometry_total_archives"] == 4
