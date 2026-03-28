from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.geocoder.scripts.refresh_canonical_dictionary import parse_records
from services.geocoder.service import refresh_canonical_dictionary, refresh_canonical_dictionary_from_env


def test_parse_records_reports_safe_alias_collisions_scoped_by_place_type() -> None:
    places = [
        {
            "canonical_id": "wof:1",
            "source": "wof",
            "source_id": "1",
            "place_type": "country",
            "canonical_name": "Finland",
            "aliases": [
                {"alias": "Finland", "alias_type": "exact_name"},
                {"alias": "Suomi", "alias_type": "language_variant"},
            ],
            "concordances": [{"external_source": "osm", "external_id": "relation:54224"}],
        },
        {
            "canonical_id": "wof:2",
            "source": "wof",
            "source_id": "2",
            "place_type": "country",
            "canonical_name": "Aland",
            "aliases": [
                {"alias": "Finland", "alias_type": "exact_name"},
                {"alias": "Finland", "alias_type": "unsafe_parent_ref"},
            ],
            "concordances": [{"external_source": "osm", "external_id": "relation:1650407"}],
        },
    ]

    records, diagnostics = parse_records(places, default_source="wof")

    assert len(records) == 2
    assert diagnostics["safe_alias_collision_count"] == 1
    assert diagnostics["safe_alias_collisions"] == {
        "country:exact_name:finland": ["wof:1", "wof:2"],
    }
    # unsafe_parent_ref should not be counted as a safe-alias collision
    assert "country:unsafe_parent_ref:finland" not in diagnostics["safe_alias_collisions"]


def test_parse_records_normalizes_region_to_admin_region() -> None:
    places = [
        {
            "canonical_id": "wof:3",
            "source_id": "3",
            "canonical_name": "California",
            "place_type": "region",
            "aliases": [{"alias": "California", "alias_type": "exact_name"}],
            "concordances": [],
        }
    ]

    records, diagnostics = parse_records(places, default_source="wof")

    assert len(records) == 1
    assert records[0].place_type == "admin_region"
    assert diagnostics["safe_alias_collision_count"] == 0


def test_refresh_canonical_dictionary_from_env_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CANONICAL_REFRESH_ON_GEOCODE", "0")

    report = refresh_canonical_dictionary_from_env()

    assert report["executed"] is False
    assert report["reason"] == "disabled"


def test_refresh_canonical_dictionary_from_env_raises_on_missing_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CANONICAL_REFRESH_ON_GEOCODE", "1")
    monkeypatch.setenv("CANONICAL_AUTOSEED_ON_EMPTY", "0")
    monkeypatch.setenv("CANONICAL_DICTIONARY_INPUT", "Z:/missing/canonical.json")

    with pytest.raises(FileNotFoundError):
        _ = refresh_canonical_dictionary_from_env()


def test_refresh_canonical_dictionary_autoseeds_when_input_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "canonical.json"
    input_path.write_text(json.dumps({"places": []}), encoding="utf-8")
    seed_source = tmp_path / "seed.geojson"
    seed_source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [],
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}
    source_build_called = {"value": False}

    def _fake_seed(**kwargs):
        output_path = kwargs["output_path"]
        output_path.write_text(
            json.dumps(
                {
                    "places": [
                        {
                            "canonical_id": "seed:country:testland",
                            "source": "seed",
                            "source_id": "country:testland",
                            "place_type": "country",
                            "canonical_name": "Testland",
                            "aliases": [{"alias": "Testland", "alias_type": "exact_name"}],
                            "concordances": [],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return {"places": 1, "aliases": 1, "concordances": 0}

    def _fake_build_source(_output_path):
        source_build_called["value"] = True
        return {"total_features": 0}

    def _fake_refresh(**kwargs):
        captured.update(kwargs)
        return {
            "counts": {"places": 1, "aliases": 1, "concordances": 0},
            "diagnostics": {"safe_alias_collision_count": 0},
        }

    monkeypatch.setenv("CANONICAL_DICTIONARY_INPUT", str(input_path))
    monkeypatch.setenv("CANONICAL_SEED_SOURCE", str(seed_source))
    monkeypatch.setenv("CANONICAL_AUTOSEED_ON_EMPTY", "1")
    monkeypatch.setenv("CANONICAL_BUILD_SEED_SOURCE_ON_REFRESH", "1")
    monkeypatch.setattr("services.geocoder.service.build_seed_source_dataset", _fake_build_source)
    monkeypatch.setattr("services.geocoder.service.build_seed_dictionary", _fake_seed)
    monkeypatch.setattr("services.geocoder.service.refresh_dictionary", _fake_refresh)

    report = refresh_canonical_dictionary(enabled=True)

    assert report["executed"] is True
    assert report["autoseeded"] is True
    assert report["autoseed_counts"] == {"places": 1, "aliases": 1, "concordances": 0}
    assert str(captured["input_path"]) == str(input_path.resolve())
    assert source_build_called["value"] is True


def test_refresh_canonical_dictionary_uses_geocoder_owned_seed_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "canonical.json"
    input_path.write_text(
        json.dumps(
            {
                "places": [
                    {
                        "canonical_id": "seed:country:testland",
                        "source": "seed",
                        "source_id": "country:testland",
                        "place_type": "country",
                        "canonical_name": "Testland",
                        "aliases": [{"alias": "Testland", "alias_type": "exact_name"}],
                        "concordances": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("CANONICAL_SEED_SOURCE", raising=False)
    monkeypatch.setenv("CANONICAL_DICTIONARY_INPUT", str(input_path))
    monkeypatch.setattr(
        "services.geocoder.service.refresh_dictionary",
        lambda **kwargs: {"counts": {}, "diagnostics": {}},
    )

    report = refresh_canonical_dictionary(enabled=True)

    assert report["executed"] is True
    assert "services\\geocoder\\assets\\canonical_seed_source.geojson" in report["seed_source_path"]
