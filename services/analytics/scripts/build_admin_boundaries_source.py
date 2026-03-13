from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

COUNTRIES_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    "ne_50m_admin_0_countries.geojson"
)
REGIONS_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    "ne_50m_admin_1_states_provinces.geojson"
)
OCEANS_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    "ne_50m_geography_marine_polys.geojson"
)
CONTINENTS_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
    "ne_50m_geography_regions_polys.geojson"
)

CONTINENT_NAMES = {
    "africa",
    "antarctica",
    "asia",
    "europe",
    "north america",
    "south america",
    "oceania",
    "australia",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_output_path() -> Path:
    return _repo_root() / "services" / "analytics" / "assets" / "admin_boundaries_source.geojson"


def _fetch_geojson(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=120) as response:
        payload = response.read()
    return json.loads(payload.decode("utf-8"))


def _string_values(properties: dict[str, Any], *, prefix: str | None = None) -> list[str]:
    values: list[str] = []
    for key, value in properties.items():
        if not isinstance(value, str):
            continue
        if prefix and not key.lower().startswith(prefix):
            continue
        text = value.strip()
        if not text:
            continue
        values.append(text)
    return values


def _dedupe_preserve(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item.strip())
    return result


def _first_nonempty(properties: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = properties.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _build_country_features(raw_features: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    features: list[dict[str, Any]] = []
    aliases_by_adm0: dict[str, list[str]] = {}
    for feature in raw_features:
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            continue
        if str(geometry.get("type")) not in {"Polygon", "MultiPolygon"}:
            continue
        props = feature.get("properties") or {}
        country_name = _first_nonempty(
            props,
            ["NAME_EN", "NAME", "ADMIN", "NAME_LONG", "SOVEREIGNT", "FORMAL_EN"],
        )
        if not country_name:
            continue
        country_aliases = _dedupe_preserve(
            [country_name]
            + _string_values(props, prefix="name_")
            + _string_values(props, prefix="NAME_")
            + [str(props.get("ADMIN", "")), str(props.get("SOVEREIGNT", "")), str(props.get("FORMAL_EN", ""))]
        )
        adm0_a3 = _first_nonempty(props, ["ADM0_A3", "ISO_A3", "SOV_A3", "GU_A3"])
        if adm0_a3:
            aliases_by_adm0[adm0_a3] = country_aliases
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "location_rank": "country",
                    "location_name": country_name,
                    "country_name": country_name,
                    "aliases": country_aliases,
                },
                "geometry": geometry,
            }
        )
    return features, aliases_by_adm0


def _build_region_features(
    raw_features: list[dict[str, Any]],
    country_aliases_by_adm0: dict[str, list[str]],
) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for feature in raw_features:
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            continue
        if str(geometry.get("type")) not in {"Polygon", "MultiPolygon"}:
            continue
        props = feature.get("properties") or {}
        region_name = _first_nonempty(props, ["name_en", "name", "name_local", "woe_name", "gn_name"])
        country_name = _first_nonempty(props, ["admin", "geonunit", "region"])
        if not region_name or not country_name:
            continue

        region_aliases = _dedupe_preserve(
            [region_name]
            + _string_values(props, prefix="name_")
            + [str(props.get("woe_name", "")), str(props.get("gn_name", "")), str(props.get("name_alt", ""))]
        )
        country_aliases = _dedupe_preserve([country_name])
        adm0_a3 = _first_nonempty(props, ["adm0_a3"])
        if adm0_a3 and adm0_a3 in country_aliases_by_adm0:
            country_aliases = _dedupe_preserve(country_aliases + country_aliases_by_adm0[adm0_a3])

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "location_rank": "admin_region",
                    "location_name": region_name,
                    "region_name": region_name,
                    "country_name": country_name,
                    "aliases": region_aliases,
                    "region_aliases": region_aliases,
                    "country_aliases": country_aliases,
                },
                "geometry": geometry,
            }
        )
    return features


def _build_ocean_features(raw_features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for feature in raw_features:
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            continue
        if str(geometry.get("type")) not in {"Polygon", "MultiPolygon"}:
            continue
        props = feature.get("properties") or {}
        ocean_name = _first_nonempty(props, ["name_en", "name", "label"])
        if not ocean_name:
            continue
        aliases = _dedupe_preserve(
            [ocean_name]
            + _string_values(props, prefix="name_")
            + [str(props.get("namealt", "")), str(props.get("label", ""))]
        )
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "location_rank": "ocean",
                    "location_name": ocean_name,
                    "aliases": aliases,
                },
                "geometry": geometry,
            }
        )
    return features


def _build_continent_features(raw_features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for feature in raw_features:
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            continue
        if str(geometry.get("type")) not in {"Polygon", "MultiPolygon"}:
            continue
        props = feature.get("properties") or {}
        name = _first_nonempty(props, ["NAME_EN", "NAME", "LABEL"])
        region = _first_nonempty(props, ["REGION", "SUBREGION"])
        marker = (name or region or "").strip().lower()
        if marker not in CONTINENT_NAMES:
            continue
        continent_name = name or region
        if not continent_name:
            continue
        aliases = _dedupe_preserve(
            [continent_name]
            + _string_values(props, prefix="NAME_")
            + [str(props.get("REGION", "")), str(props.get("SUBREGION", ""))]
        )
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "location_rank": "continent",
                    "location_name": continent_name,
                    "aliases": aliases,
                },
                "geometry": geometry,
            }
        )
    return features


def build_source_dataset(output_path: Path) -> dict[str, int]:
    countries_raw = _fetch_geojson(COUNTRIES_URL)
    regions_raw = _fetch_geojson(REGIONS_URL)
    oceans_raw = _fetch_geojson(OCEANS_URL)
    continents_raw = _fetch_geojson(CONTINENTS_URL)

    country_features, country_aliases_by_adm0 = _build_country_features(countries_raw.get("features") or [])
    region_features = _build_region_features(regions_raw.get("features") or [], country_aliases_by_adm0)
    ocean_features = _build_ocean_features(oceans_raw.get("features") or [])
    continent_features = _build_continent_features(continents_raw.get("features") or [])

    all_features = country_features + region_features + continent_features + ocean_features
    all_features.sort(
        key=lambda feature: (
            str(feature.get("properties", {}).get("location_rank", "")),
            str(feature.get("properties", {}).get("country_name", "")),
            str(feature.get("properties", {}).get("location_name", "")),
        )
    )

    payload = {"type": "FeatureCollection", "features": all_features}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "countries": len(country_features),
        "regions": len(region_features),
        "continents": len(continent_features),
        "oceans": len(ocean_features),
        "total_features": len(all_features),
    }


def main() -> int:
    output_path = _default_output_path()
    if len(sys.argv) > 1:
        output_path = Path(sys.argv[1]).resolve()

    stats = build_source_dataset(output_path)
    print(json.dumps({"output_path": str(output_path), "stats": stats}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
