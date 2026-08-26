from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Sequence

import pytest

from services.analytics.baked_geometry_assets import _prune_old_releases, build_baked_geometry_assets


class _DummyCursor:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str) -> None:
        self.sql = sql

    def fetchall(self):
        return self.rows


class _DummyConn:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self) -> _DummyCursor:
        return _DummyCursor(self.rows)


def _rows():
    return [
        (
            "00000000-0000-0000-0000-000000000001",
            "country",
            {
                "type": "Feature",
                "properties": {
                    "location_name": "Testland",
                    "country_name": "unused",
                    "match_strategy": "unused",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 0.0]]],
                },
            },
        )
    ]


def _output_path(command: Sequence[str]) -> Path:
    value = next(item for item in command if item.startswith("--output="))
    return Path(value.split("=", 1)[1])


def test_build_generates_atomic_pmtiles_release_with_minimal_properties(tmp_path: Path) -> None:
    commands: list[list[str]] = []
    source_payloads: list[dict] = []

    def runner(command: Sequence[str]) -> None:
        commands.append(list(command))
        source_payloads.append(json.loads(Path(command[-1]).read_text(encoding="utf-8")))
        _output_path(command).write_bytes(b"PMTiles\x03fixture")

    root = tmp_path / "geometry"
    progress: list[tuple[int, int]] = []
    result = build_baked_geometry_assets(
        _DummyConn(_rows()),  # type: ignore[arg-type]
        assets_root=root,
        command_runner=runner,
        tippecanoe_binary="tippecanoe-test",
        on_progress=lambda completed, total: progress.append((completed, total)),
    )

    assert result.version.startswith("v2-")
    assert result.total_archives == 4
    assert set(result.modes) == {"full_precise", "balanced_precise", "simplified", "primitive"}
    assert progress == [(0, 4), (1, 4), (2, 4), (3, 4), (4, 4)]
    assert all(item.path.is_file() for item in result.modes.values())
    assert all("--no-clipping" not in command for command in commands)
    assert all("--include=location_id" in command for command in commands)

    properties = source_payloads[0]["features"][0]["properties"]
    assert properties == {
        "location_id": "00000000-0000-0000-0000-000000000001",
        "location_rank": "country",
        "location_name": "Testland",
    }

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["tile_format"] == "pmtiles"
    assert manifest["layer"] == "boundaries"
    assert manifest["modes"]["balanced_precise"]["path"].endswith("/balanced_precise.pmtiles")
    pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
    assert pointer["current_version"] == result.version


def test_identical_input_reuses_published_release(tmp_path: Path) -> None:
    calls = 0

    def runner(command: Sequence[str]) -> None:
        nonlocal calls
        calls += 1
        _output_path(command).write_bytes(b"PMTiles\x03fixture")

    root = tmp_path / "geometry"
    first = build_baked_geometry_assets(
        _DummyConn(_rows()),  # type: ignore[arg-type]
        assets_root=root,
        command_runner=runner,
        tippecanoe_binary="tippecanoe-test",
    )
    second = build_baked_geometry_assets(
        _DummyConn(_rows()),  # type: ignore[arg-type]
        assets_root=root,
        command_runner=lambda _command: (_ for _ in ()).throw(AssertionError("must reuse release")),
        tippecanoe_binary="tippecanoe-test",
    )

    assert calls == 4
    assert first.version == second.version


def test_failed_build_is_not_published(tmp_path: Path) -> None:
    calls = 0

    def runner(command: Sequence[str]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic tippecanoe failure")
        _output_path(command).write_bytes(b"PMTiles\x03fixture")

    root = tmp_path / "geometry"
    with pytest.raises(RuntimeError, match="synthetic"):
        build_baked_geometry_assets(
            _DummyConn(_rows()),  # type: ignore[arg-type]
            assets_root=root,
            command_runner=runner,
            tippecanoe_binary="tippecanoe-test",
        )

    assert not (root / "current.json").exists()
    assert not list(root.glob("v2-*"))
    assert not list(root.glob(".*.building-*"))


def test_archive_budget_rejects_pathological_output(tmp_path: Path) -> None:
    def runner(command: Sequence[str]) -> None:
        _output_path(command).write_bytes(b"PMTiles\x03" + b"x" * 64)

    with pytest.raises(RuntimeError, match="exceeds budget"):
        build_baked_geometry_assets(
            _DummyConn(_rows()),  # type: ignore[arg-type]
            assets_root=tmp_path / "geometry",
            mode_options={"balanced_precise": ("--simplification=2",)},
            command_runner=runner,
            tippecanoe_binary="tippecanoe-test",
            max_archive_bytes=32,
        )


def test_release_retention_keeps_current_and_latest_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "geometry"
    for version in ("v2-old", "v2-previous", "v2-current"):
        release = root / version
        release.mkdir(parents=True)
        (release / "manifest.json").write_text("{}", encoding="utf-8")

    # The active pointer wins even when its directory is not the newest by mtime.
    os.utime(root / "v2-current", ns=(1_000_000_000_000_000_000,) * 2)
    os.utime(root / "v2-old", ns=(2_000_000_000_000_000_000,) * 2)
    os.utime(root / "v2-previous", ns=(3_000_000_000_000_000_000,) * 2)
    (root / "unrelated").mkdir()
    monkeypatch.setenv("DOCMAP_PRESENTATION_ARTIFACT_RETENTION", "2")

    _prune_old_releases(root, current_version="v2-current")

    assert (root / "v2-current").is_dir()
    assert (root / "v2-previous").is_dir()
    assert not (root / "v2-old").exists()
    assert (root / "unrelated").is_dir()
