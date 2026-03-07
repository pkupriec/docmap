from services.geocoder.normalization import normalize_location_name


def test_normalize_country_directional_prefix() -> None:
    assert normalize_location_name("western Mongolia", "country") == "Mongolia"


def test_normalize_city_leading_context() -> None:
    assert normalize_location_name("a village near Brno", "city") == "Brno"


def test_normalize_country_rural_prefix() -> None:
    assert normalize_location_name("rural France", "country") == "France"


def test_normalize_admin_region_directional_prefix() -> None:
    assert normalize_location_name("Northern Siberia", "admin_region") == "Siberia"
