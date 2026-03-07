from services.geocoder.nominatim_client import infer_precision, normalize_geocoder_response


def test_normalize_geocoder_response_city_precision() -> None:
    payload = {
        "lat": "35.0116",
        "lon": "135.7681",
        "address": {
            "city": "Kyoto",
            "state": "Kyoto Prefecture",
            "country": "Japan",
        },
    }
    normalized = normalize_geocoder_response("Kyoto, Japan", payload)
    assert normalized["city"] == "Kyoto"
    assert normalized["region"] == "Kyoto Prefecture"
    assert normalized["country"] == "Japan"
    assert normalized["precision"] == "city"


def test_infer_precision_country() -> None:
    assert infer_precision(city=None, region=None, country="France") == "country"
