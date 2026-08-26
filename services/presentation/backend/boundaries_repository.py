from __future__ import annotations

import json
import logging
import time
from contextlib import AbstractContextManager
from typing import Any, Callable
from uuid import UUID

from psycopg import Connection

logger = logging.getLogger(__name__)
ConnectionProvider = Callable[[], AbstractContextManager[Connection]]


class BoundariesRepository:
    def __init__(self, connection_provider: ConnectionProvider) -> None:
        self._connect = connection_provider

    def get_admin_boundaries_geojson(
        self,
        *,
        selected_location_id: str | UUID | None = None,
        highlighted_location_ids: tuple[str, ...] | list[str] | None = None,
    ) -> dict[str, Any]:
        location_ids = sorted(
            {
                str(value)
                for value in [selected_location_id, *(highlighted_location_ids or ())]
                if value is not None and str(value).strip()
            }
        )
        if not location_ids:
            return {"type": "FeatureCollection", "features": []}

        started = time.perf_counter()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT feature_json
                    FROM bi_admin_boundaries
                    WHERE location_id = ANY(%s::uuid[])
                    ORDER BY location_id ASC
                    """,
                    [location_ids],
                )
                rows = cur.fetchall()

        features: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            feature = self._parse_feature(row[0] if row else None)
            if feature is None:
                continue
            properties = feature.get("properties")
            location_id = str(properties.get("location_id") or "") if isinstance(properties, dict) else ""
            if location_id and location_id in seen:
                continue
            if location_id:
                seen.add(location_id)
            features.append(feature)
        logger.info(
            "presentation.boundaries_repo_fetch explicit_ids=%s rows=%s features=%s total_ms=%.2f",
            len(location_ids),
            len(rows),
            len(features),
            (time.perf_counter() - started) * 1000.0,
        )
        return {"type": "FeatureCollection", "features": features}

    @staticmethod
    def _parse_feature(payload: object) -> dict[str, Any] | None:
        if isinstance(payload, dict):
            feature = payload
        elif isinstance(payload, (str, bytes, bytearray)):
            try:
                feature = json.loads(payload)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
        else:
            return None
        if not isinstance(feature, dict):
            return None
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            return None
        return {
            "type": "Feature",
            "properties": feature.get("properties") if isinstance(feature.get("properties"), dict) else {},
            "geometry": {"type": geometry.get("type"), "coordinates": geometry.get("coordinates")},
        }
