from __future__ import annotations

from dataclasses import dataclass, field

from services.geocoder import repository
from services.geocoder.identity import location_identity_key


@dataclass
class _DummyCursor:
    query_log: list[str] = field(default_factory=list)
    concordance_row: tuple[str] | None = None
    alias_candidate_rows: list[tuple[str, str, str, str | None, str | None]] = field(default_factory=list)
    alias_rows_by_id: dict[str, list[str]] = field(default_factory=dict)
    _rows: list[tuple[object, ...]] = field(default_factory=list)

    def __enter__(self) -> "_DummyCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def execute(self, sql: str, params) -> None:
        self.query_log.append(sql)
        if "FROM geo_canonical_concordances" in sql and "external_source = 'osm'" in sql:
            self._rows = [self.concordance_row] if self.concordance_row else []
            return
        if "FROM geo_canonical_aliases a" in sql and "JOIN geo_canonical_places" in sql:
            self._rows = list(self.alias_candidate_rows)
            return
        if "FROM geo_canonical_aliases" in sql and "canonical_id = ANY" in sql:
            canonical_ids = list(params[0])
            rows: list[tuple[object, ...]] = []
            for canonical_id in canonical_ids:
                for alias in self.alias_rows_by_id.get(str(canonical_id), []):
                    rows.append((canonical_id, alias))
            self._rows = rows
            return
        self._rows = []

    def fetchone(self):
        if not self._rows:
            return None
        return self._rows[0]

    def fetchall(self):
        return list(self._rows)


class _DummyConn:
    def __init__(
        self,
        *,
        concordance_row: tuple[str] | None = None,
        alias_candidate_rows: list[tuple[str, str, str, str | None, str | None]] | None = None,
        alias_rows_by_id: dict[str, list[str]] | None = None,
    ) -> None:
        self._cursor = _DummyCursor(
            concordance_row=concordance_row,
            alias_candidate_rows=alias_candidate_rows or [],
            alias_rows_by_id=alias_rows_by_id or {},
        )

    def cursor(self) -> _DummyCursor:
        return self._cursor


def test_city_identity_collapses_qualified_aliases_but_not_namesakes() -> None:
    common = {
        "precision": "city",
        "location_rank": "city",
        "region": "England",
        "country": "United Kingdom",
        "latitude": 51.5074456,
        "longitude": -0.1277653,
    }

    assert location_identity_key({**common, "normalized_location": "London, England"}) == location_identity_key(
        {**common, "normalized_location": "London, England, United Kingdom"}
    )
    assert location_identity_key({**common, "normalized_location": "London, United Kingdom"}) != location_identity_key(
        {
            **common,
            "normalized_location": "London, Ontario, Canada",
            "region": "Ontario",
            "country": "Canada",
            "latitude": 42.9836747,
            "longitude": -81.2496068,
        }
    )


def test_non_city_identity_prefers_canonical_then_osm() -> None:
    assert location_identity_key({"canonical_id": "ne:country:FIN", "osm_type": "relation", "osm_id": 1}) == (
        "canonical:ne:country:fin"
    )
    assert location_identity_key({"osm_type": "relation", "osm_id": "175342"}) == "osm:relation:175342"


def test_resolve_canonical_identity_prefers_osm_concordance() -> None:
    conn = _DummyConn(
        concordance_row=("wof:101736545",),
        alias_candidate_rows=[("wof:999", "exact_name", "Russia", None, None)],
    )
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
    assert resolved.reason_code == "deterministic_disambiguated"


def test_resolve_canonical_identity_uses_unique_safe_alias_fallback() -> None:
    conn = _DummyConn(alias_candidate_rows=[("wof:85633147", "exact_name", "Finland", None, None)])
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
    assert resolved.reason_code == "deterministic_disambiguated"


def test_resolve_canonical_identity_uses_deterministic_ambiguity_resolver_for_congo() -> None:
    conn = _DummyConn(
        alias_candidate_rows=[
            ("wof:country:COD", "exact_name", "Democratic Republic of the Congo", None, None),
            ("wof:country:COG", "exact_name", "Republic of the Congo", None, None),
        ],
        alias_rows_by_id={
            "wof:country:COD": ["congo", "democratic republic of the congo", "dr congo"],
            "wof:country:COG": ["congo", "republic of the congo"],
        },
    )
    payload = {
        "normalized_location": "Congo",
        "location_rank": "country",
        "country": "Democratic Republic of the Congo",
        "osm_type": None,
        "osm_id": None,
    }

    resolved = repository._resolve_canonical_identity(conn, payload)  # type: ignore[arg-type]

    assert resolved.canonical_id == "wof:country:COD"
    assert resolved.resolution_method == "deterministic_ambiguity_resolver"
    assert resolved.confidence > 0
    assert resolved.reason_code == "deterministic_disambiguated"


def test_resolve_canonical_identity_analogous_class_korea_is_deterministic() -> None:
    conn = _DummyConn(
        alias_candidate_rows=[
            ("wof:country:PRK", "exact_name", "North Korea", None, None),
            ("wof:country:KOR", "exact_name", "South Korea", None, None),
        ],
        alias_rows_by_id={
            "wof:country:PRK": ["korea", "north korea", "democratic people's republic of korea"],
            "wof:country:KOR": ["korea", "south korea", "republic of korea"],
        },
    )
    payload = {
        "normalized_location": "Korea",
        "location_rank": "country",
        "country": "Republic of Korea",
        "osm_type": None,
        "osm_id": None,
    }

    resolved = repository._resolve_canonical_identity(conn, payload)  # type: ignore[arg-type]

    assert resolved.canonical_id == "wof:country:KOR"
    assert resolved.resolution_method == "deterministic_ambiguity_resolver"
    assert resolved.reason_code == "deterministic_disambiguated"


def test_resolve_canonical_identity_marks_insufficient_signal_when_alias_is_ambiguous() -> None:
    conn = _DummyConn(
        alias_candidate_rows=[
            ("wof:country:GNQ", "exact_name", "Equatorial Guinea", None, None),
            ("wof:country:GIN", "exact_name", "Guinea", None, None),
        ],
        alias_rows_by_id={
            "wof:country:GNQ": ["guinea", "equatorial guinea"],
            "wof:country:GIN": ["guinea", "republic of guinea"],
        },
    )
    payload = {
        "normalized_location": "Guinea",
        "location_rank": "country",
        "country": "Guinea",
        "osm_type": None,
        "osm_id": None,
    }

    resolved = repository._resolve_canonical_identity(conn, payload)  # type: ignore[arg-type]

    assert resolved.canonical_id is None
    assert resolved.resolution_method == "ambiguous_alias_insufficient_signal"
    assert resolved.confidence == 0
    assert resolved.reason_code == "ambiguous_alias_insufficient_signal"


def test_resolve_canonical_identity_marks_conflicting_signal_when_scores_tie() -> None:
    conn = _DummyConn(
        alias_candidate_rows=[
            ("wof:admin:US-CA-001", "exact_name", "Springfield", "wof:country:USA", "wof:country:USA"),
            ("wof:admin:US-CA-002", "exact_name", "Springfield", "wof:country:USA", "wof:country:USA"),
        ],
        alias_rows_by_id={
            "wof:admin:US-CA-001": ["springfield"],
            "wof:admin:US-CA-002": ["springfield"],
            "wof:country:USA": ["united states", "usa"],
        },
    )
    payload = {
        "normalized_location": "Springfield",
        "location_rank": "admin_region",
        "country": "United States",
        "region": "Springfield",
        "osm_type": None,
        "osm_id": None,
    }

    resolved = repository._resolve_canonical_identity(conn, payload)  # type: ignore[arg-type]

    assert resolved.canonical_id is None
    assert resolved.resolution_method == "ambiguous_alias_conflicting_signal"
    assert resolved.confidence == 0
    assert resolved.reason_code == "ambiguous_alias_conflicting_signal"


def test_resolve_canonical_identity_is_replay_stable_for_ambiguous_alias() -> None:
    conn = _DummyConn(
        alias_candidate_rows=[
            ("wof:country:COG", "exact_name", "Republic of the Congo", None, None),
            ("wof:country:COD", "exact_name", "Democratic Republic of the Congo", None, None),
        ],
        alias_rows_by_id={
            "wof:country:COG": ["congo", "republic of the congo"],
            "wof:country:COD": ["congo", "democratic republic of the congo", "dr congo"],
        },
    )
    payload = {
        "normalized_location": "Congo",
        "location_rank": "country",
        "country": "Democratic Republic of the Congo",
        "osm_type": None,
        "osm_id": None,
    }

    first = repository._resolve_canonical_identity(conn, payload)  # type: ignore[arg-type]
    second = repository._resolve_canonical_identity(conn, payload)  # type: ignore[arg-type]

    assert first.canonical_id == "wof:country:COD"
    assert second.canonical_id == first.canonical_id
    assert second.resolution_method == first.resolution_method
    assert second.confidence == first.confidence
