from services.geocoder.repository import PendingMention
from services.geocoder.service import _process_single_mention


class _DummyConn:
    pass


def test_process_single_mention_uses_cache(monkeypatch) -> None:
    mention = PendingMention(
        mention_id="m1",
        document_id="d1",
        normalized_location="Kyoto, Japan",
    )

    monkeypatch.setattr(
        "services.geocoder.service.get_geo_location_id_by_normalized_name",
        lambda conn, _: "loc-1",
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
        "services.geocoder.service.get_geo_location_id_by_normalized_name",
        lambda conn, _: None,
    )
    monkeypatch.setattr("services.geocoder.service.geocode_location", lambda _: None)

    status = _process_single_mention(_DummyConn(), mention)
    assert status == "unresolved"
