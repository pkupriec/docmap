from __future__ import annotations

import logging
from dataclasses import dataclass

from services.common.db import get_connection
from services.geocoder.nominatim_client import geocode_location
from services.geocoder.repository import (
    PendingMention,
    get_geo_location_id_by_normalized_name,
    get_pending_mentions,
    link_document_location,
    save_geo_location,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeocodeBatchResult:
    processed: int
    geocoded: int
    linked: int
    unresolved: int


def process_pending_mentions(limit: int = 1000) -> GeocodeBatchResult:
    logger.info("geocoder.batch_start limit=%s", limit)
    with get_connection() as conn:
        pending = get_pending_mentions(conn, limit=limit)
        geocoded = 0
        linked = 0
        unresolved = 0

        for mention in pending:
            try:
                status = _process_single_mention(conn, mention)
                if status == "linked":
                    linked += 1
                elif status == "geocoded_and_linked":
                    geocoded += 1
                    linked += 1
                else:
                    unresolved += 1
            except Exception:
                unresolved += 1
                logger.exception(
                    "geocoder.mention_failed mention_id=%s normalized_location=%s",
                    mention.mention_id,
                    mention.normalized_location,
                )

        conn.commit()

    result = GeocodeBatchResult(
        processed=len(pending),
        geocoded=geocoded,
        linked=linked,
        unresolved=unresolved,
    )
    logger.info(
        "geocoder.batch_done processed=%s geocoded=%s linked=%s unresolved=%s",
        result.processed,
        result.geocoded,
        result.linked,
        result.unresolved,
    )
    return result


def _process_single_mention(conn, mention: PendingMention) -> str:
    cached_id = get_geo_location_id_by_normalized_name(conn, mention.normalized_location)
    if cached_id:
        link_document_location(
            conn,
            document_id=mention.document_id,
            location_id=cached_id,
            mention_id=mention.mention_id,
        )
        logger.info(
            "geocoder.cache_hit mention_id=%s normalized_location=%s",
            mention.mention_id,
            mention.normalized_location,
        )
        return "linked"

    geocoded = geocode_location(mention.normalized_location)
    if not geocoded:
        logger.warning(
            "geocoder.unresolved mention_id=%s normalized_location=%s",
            mention.mention_id,
            mention.normalized_location,
        )
        return "unresolved"

    location_id = save_geo_location(conn, geocoded)
    link_document_location(
        conn,
        document_id=mention.document_id,
        location_id=location_id,
        mention_id=mention.mention_id,
    )
    logger.info(
        "geocoder.geocoded mention_id=%s normalized_location=%s",
        mention.mention_id,
        mention.normalized_location,
    )
    return "geocoded_and_linked"
