from __future__ import annotations

from services.analytics.scripts import build_admin_boundaries_source as source_builder


def test_country_aliases_are_strict_and_do_not_use_sovereign_name_as_safe_alias() -> None:
    raw_features = [
        {
            "type": "Feature",
            "properties": {
                "NAME_EN": "Aland",
                "NAME_LONG": "Aland Islands",
                "FORMAL_EN": "Aland Islands",
                "ADMIN": "Finland",
                "SOVEREIGNT": "Finland",
                "ADM0_A3": "ALD",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]],
            },
        }
    ]

    features, _aliases = source_builder._build_country_features(raw_features)

    assert len(features) == 1
    props = features[0]["properties"]
    assert props["canonical_id"] == "ne:country:ALD"
    assert "Finland" not in props["safe_aliases"]
    assert "Finland" not in props["aliases"]
    assert "Finland" in props["unsafe_aliases"]

