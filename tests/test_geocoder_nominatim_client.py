import requests

from services.geocoder import nominatim_client
from services.geocoder.nominatim_client import (
    infer_location_rank,
    infer_precision,
    normalize_geocoder_response,
)


def test_normalize_geocoder_response_city_precision() -> None:
    payload = {
        "lat": "35.0116",
        "lon": "135.7681",
        "address": {
            "city": "Kyoto",
            "state": "Kyoto Prefecture",
            "country": "Japan",
        },
        "osm_type": "relation",
        "osm_id": "12345",
        "category": "place",
        "type": "city",
        "addresstype": "city",
        "place_rank": "16",
        "boundingbox": ["34.95", "35.08", "135.65", "135.90"],
    }
    normalized = normalize_geocoder_response("Kyoto, Japan", payload)
    assert normalized["city"] == "Kyoto"
    assert normalized["region"] == "Kyoto Prefecture"
    assert normalized["country"] == "Japan"
    assert normalized["precision"] == "city"
    assert normalized["location_rank"] == "city"
    assert normalized["osm_type"] == "relation"
    assert normalized["osm_id"] == 12345
    assert normalized["osm_category"] == "place"
    assert normalized["osm_place_type"] == "city"
    assert normalized["osm_addresstype"] == "city"
    assert normalized["osm_place_rank"] == 16
    assert normalized["osm_boundingbox"] == [34.95, 35.08, 135.65, 135.9]


def test_infer_precision_country() -> None:
    assert infer_precision(city=None, region=None, country="France") == "country"


def test_infer_location_rank_continent() -> None:
    assert (
        infer_location_rank(
            city=None,
            region=None,
            country=None,
            category="place",
            place_type="continent",
            addresstype="continent",
        )
        == "continent"
    )


def test_infer_location_rank_ocean() -> None:
    assert (
        infer_location_rank(
            city=None,
            region=None,
            country=None,
            category="natural",
            place_type="ocean",
            addresstype="ocean",
        )
        == "ocean"
    )


def test_infer_location_rank_ocean_does_not_match_substring_inside_word() -> None:
    assert (
        infer_location_rank(
            normalized_location="Seattle, United States",
            city=None,
            region=None,
            country="United States",
            category="place",
            place_type="city",
            addresstype="city",
        )
        == "country"
    )


def test_infer_location_rank_ocean_matches_token_boundary() -> None:
    assert (
        infer_location_rank(
            normalized_location="North Sea",
            city=None,
            region=None,
            country=None,
            category="natural",
            place_type="water",
            addresstype="water",
        )
        == "ocean"
    )


def test_build_query_variants_includes_city_country_fallback() -> None:
    variants = nominatim_client._build_query_variants("New York Stock Exchange, New York, United States")
    assert variants[0] == "New York Stock Exchange, New York, United States"
    assert "New York, United States" in variants


def test_retry_after_seconds_parses_number() -> None:
    assert nominatim_client._retry_after_seconds("2") == 2.0
    assert nominatim_client._retry_after_seconds(None) is None
    assert nominatim_client._retry_after_seconds("bad") is None


def test_geocode_location_returns_none_after_rate_limit(monkeypatch) -> None:
    class _Response:
        status_code = 429
        headers: dict[str, str] = {}

        def raise_for_status(self) -> None:
            raise requests.HTTPError("429")

    monkeypatch.setattr(nominatim_client, "_throttle_requests", lambda: None)
    monkeypatch.setattr(nominatim_client.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(nominatim_client.requests, "get", lambda *args, **kwargs: _Response())

    result = nominatim_client.geocode_location(
        "New York Stock Exchange, New York, United States",
        max_retries=2,
    )
    assert result is None
