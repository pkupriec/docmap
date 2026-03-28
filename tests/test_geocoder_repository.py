from __future__ import annotations

from dataclasses import dataclass

from services.geocoder import repository


@dataclass
class _DummyCursor:
    concordance_row: tuple[str] | None
    alias_rows: list[tuple[str, str]]
    query_log: list[str]
    _rows: list[tuple[object, ...]] | None = None

    def __enter__(self) -> "_DummyCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def execute(self, sql: str, params) -> None:
        self.query_log.append(sql)
        if "FROM geo_canonical_concordances" in sql:
            self._rows = [self.concordance_row] if self.concordance_row else []
            return
        if "FROM geo_canonical_aliases" in sql:
            self._rows = list(self.alias_rows)
            return
        self._rows = []

    def fetchone(self):
        if not self._rows:
            return None
        return self._rows[0]

    def fetchall(self):
        return list(self._rows or [])


class _DummyConn:
    def __init__(self, *, concordance_row: tuple[str] | None, alias_rows: list[tuple[str, str]]) -> None:
        self.query_log: list[str] = []
        self._cursor = _DummyCursor(
            concordance_row=concordance_row,
            alias_rows=alias_rows,
            query_log=self.query_log,
        )

    def cursor(self) -> _DummyCursor:
        return self._cursor


def test_resolve_canonical_identity_prefers_osm_concordance() -> None:
    conn = _DummyConn(concordance_row=("wof:101736545",), alias_rows=[("wof:999", "exact_name")])
    payload = {
        "normalized_location": "Russia",
        "location_rank": "country",
        "osm_type": "relation",
        "osm_id": 60189,
    }

    resolved = repository._resolve_canonical_identity(conn, payload)  # type: ignore[arg-type]

    assert resolved.canonical_id == "wof:101736545"
    assert resolved.resolution_method == "osm_identity"
    assert resolved.confidence == 100


def test_resolve_canonical_identity_uses_unique_safe_alias_fallback() -> None:
    conn = _DummyConn(concordance_row=None, alias_rows=[("wof:85633147", "exact_name")])
    payload = {
        "normalized_location": "Finland",
        "location_rank": "country",
        "osm_type": None,
        "osm_id": None,
    }

    resolved = repository._resolve_canonical_identity(conn, payload)  # type: ignore[arg-type]

    assert resolved.canonical_id == "wof:85633147"
    assert resolved.resolution_method == "strict_alias"
    assert resolved.confidence == 75


def test_resolve_canonical_identity_marks_ambiguous_alias() -> None:
    conn = _DummyConn(
        concordance_row=None,
        alias_rows=[("wof:85633147", "exact_name"), ("wof:123", "language_variant")],
    )
    payload = {
        "normalized_location": "Finland",
        "location_rank": "country",
        "osm_type": None,
        "osm_id": None,
    }

    resolved = repository._resolve_canonical_identity(conn, payload)  # type: ignore[arg-type]

    assert resolved.canonical_id is None
    assert resolved.resolution_method == "ambiguous_alias"
    assert resolved.confidence == 0

