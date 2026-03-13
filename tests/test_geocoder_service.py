from services.geocoder.repository import GeoLocationCacheEntry, PendingMention
from services.geocoder.service import _process_single_mention, process_all_mentions


class _DummyConn:
    pass


def test_process_single_mention_uses_cache(monkeypatch) -> None:
    mention = PendingMention(
        mention_id="m1",
        document_id="d1",
        normalized_location="Kyoto, Japan",
    )

    monkeypatch.setattr(
        "services.geocoder.service.get_geo_location_cache_entry",
        lambda conn, _: GeoLocationCacheEntry(
            location_id="loc-1",
            location_rank="city",
            osm_type="relation",
            osm_id=123,
            osm_boundingbox=[1.0, 2.0, 3.0, 4.0],
        ),
    )
    monkeypatch.setattr(
        "services.geocoder.service.link_document_location",
        lambda conn, **kwargs: "link-1",
    )

    status = _process_single_mention(_DummyConn(), mention)
    assert status == "linked"


def test_process_single_mention_unresolved(monkeypatch) -> None:
    mention = PendingMention(
        mention_id="m1",
        document_id="d1",
        normalized_location="Unknown Place",
    )

    monkeypatch.setattr(
        "services.geocoder.service.get_geo_location_cache_entry",
        lambda conn, _: None,
    )
    monkeypatch.setattr("services.geocoder.service.geocode_location", lambda _: None)

    status = _process_single_mention(_DummyConn(), mention)
    assert status == "unresolved"


def test_process_single_mention_refreshes_missing_identity(monkeypatch) -> None:
    mention = PendingMention(
        mention_id="m1",
        document_id="d1",
        normalized_location="Kyoto, Japan",
    )

    monkeypatch.setattr(
        "services.geocoder.service.get_geo_location_cache_entry",
        lambda conn, _: GeoLocationCacheEntry(
            location_id="loc-1",
            location_rank=None,
            osm_type=None,
            osm_id=None,
            osm_boundingbox=None,
        ),
    )
    monkeypatch.setattr(
        "services.geocoder.service.geocode_location",
        lambda _: {"normalized_location": "Kyoto, Japan", "latitude": 1.0, "longitude": 2.0},
    )
    monkeypatch.setattr("services.geocoder.service.save_geo_location", lambda conn, location: "loc-2")
    monkeypatch.setattr("services.geocoder.service.link_document_location", lambda conn, **kwargs: "link-1")

    status = _process_single_mention(_DummyConn(), mention, refresh_missing_identity=True)

    assert status == "geocoded_and_linked"


def test_process_all_mentions_resets_links_in_full_mode(monkeypatch) -> None:
    class DummyConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def commit(self):
            return None

        def rollback(self):
            return None

    mention = PendingMention(
        mention_id="m1",
        document_id="d1",
        normalized_location="Kyoto, Japan",
    )

    monkeypatch.setattr("services.geocoder.service.get_connection", lambda: DummyConn())
    monkeypatch.setattr("services.geocoder.service.clear_document_links_for_all_mentions", lambda _conn: 5)
    monkeypatch.setattr("services.geocoder.service.get_all_mentions", lambda _conn, **kwargs: [mention])
    monkeypatch.setattr(
        "services.geocoder.service._process_single_mention",
        lambda _conn, _mention, **kwargs: "linked",
    )

    result = process_all_mentions(limit=10, offset=0, reset_existing_links=True)

    assert result.processed == 1
    assert result.linked == 1
