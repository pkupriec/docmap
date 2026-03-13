from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from services.common.db import get_connection
from services.geocoder.nominatim_client import geocode_location
from services.geocoder.repository import (
    GeoLocationCacheEntry,
    PendingMention,
    clear_document_links_for_all_mentions,
    get_all_mentions,
    get_geo_location_cache_entry,
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


MentionCallback = Callable[[int, int, int, int, PendingMention, str | None, str | None], None]
StopCallback = Callable[[], bool]


def process_pending_mentions(
    limit: int = 1000,
    *,
    offset: int = 0,
    on_mention: MentionCallback | None = None,
    should_stop: StopCallback | None = None,
) -> GeocodeBatchResult:
    logger.info("geocoder.batch_start mode=pending limit=%s offset=%s", limit, offset)
    with get_connection() as conn:
        pending = get_pending_mentions(conn, limit=limit, offset=offset)
    return _process_mentions(
        mentions=pending,
        on_mention=on_mention,
        should_stop=should_stop,
        refresh_missing_identity=False,
    )


def process_all_mentions(
    limit: int = 1000,
    *,
    offset: int = 0,
    reset_existing_links: bool = False,
    refresh_missing_identity: bool = False,
    on_mention: MentionCallback | None = None,
    should_stop: StopCallback | None = None,
) -> GeocodeBatchResult:
    logger.info(
        (
            "geocoder.batch_start mode=all limit=%s offset=%s "
            "reset_existing_links=%s refresh_missing_identity=%s"
        ),
        limit,
        offset,
        reset_existing_links,
        refresh_missing_identity,
    )
    with get_connection() as conn:
        if reset_existing_links and offset == 0:
            cleared = clear_document_links_for_all_mentions(conn)
            conn.commit()
            logger.info("geocoder.batch_reset_links_cleared=%s", cleared)
        mentions = get_all_mentions(conn, limit=limit, offset=offset)
    return _process_mentions(
        mentions=mentions,
        on_mention=on_mention,
        should_stop=should_stop,
        refresh_missing_identity=refresh_missing_identity,
    )


def _process_mentions(
    *,
    mentions: list[PendingMention],
    on_mention: MentionCallback | None,
    should_stop: StopCallback | None,
    refresh_missing_identity: bool,
) -> GeocodeBatchResult:
    with get_connection() as conn:
        geocoded = 0
        linked = 0
        unresolved = 0
        processed_count = 0

        total = len(mentions)
        for idx, mention in enumerate(mentions, start=1):
            if should_stop and should_stop():
                logger.info("geocoder.batch_stop_requested processed=%s total=%s", idx - 1, total)
                break
            processed_count = idx
            try:
                status = _process_single_mention(
                    conn,
                    mention,
                    refresh_missing_identity=refresh_missing_identity,
                )
                # Atomic unit of work is one mention: commit each item independently.
                conn.commit()
                if status == "linked":
                    linked += 1
                elif status == "geocoded_and_linked":
                    geocoded += 1
                    linked += 1
                else:
                    unresolved += 1
                if on_mention:
                    on_mention(idx, total, geocoded, linked, mention, status, None)
            except Exception:
                # Ensure transaction state is reset so later mentions can continue.
                conn.rollback()
                unresolved += 1
                logger.exception(
                    "geocoder.mention_failed mention_id=%s normalized_location=%s",
                    mention.mention_id,
                    mention.normalized_location,
                )
                if on_mention:
                    on_mention(idx, total, geocoded, linked, mention, None, "mention_failed")

    result = GeocodeBatchResult(
        processed=processed_count,
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


def _process_single_mention(
    conn,
    mention: PendingMention,
    *,
    refresh_missing_identity: bool = False,
) -> str:
    cached = get_geo_location_cache_entry(conn, mention.normalized_location)
    if cached:
        if _should_refresh_missing_identity(cached, refresh_missing_identity=refresh_missing_identity):
            geocoded = geocode_location(mention.normalized_location)
            if geocoded:
                location_id = save_geo_location(conn, geocoded)
                link_document_location(
                    conn,
                    document_id=mention.document_id,
                    location_id=location_id,
                    mention_id=mention.mention_id,
                )
                logger.info(
                    (
                        "geocoder.cache_refresh_success mention_id=%s normalized_location=%s "
                        "old_location_id=%s new_location_id=%s"
                    ),
                    mention.mention_id,
                    mention.normalized_location,
                    cached.location_id,
                    location_id,
                )
                return "geocoded_and_linked"

            link_document_location(
                conn,
                document_id=mention.document_id,
                location_id=cached.location_id,
                mention_id=mention.mention_id,
            )
            logger.warning(
                (
                    "geocoder.cache_refresh_failed_fallback_link mention_id=%s "
                    "normalized_location=%s location_id=%s"
                ),
                mention.mention_id,
                mention.normalized_location,
                cached.location_id,
            )
            return "linked"

        link_document_location(
            conn,
            document_id=mention.document_id,
            location_id=cached.location_id,
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


def _should_refresh_missing_identity(cache_entry: GeoLocationCacheEntry, *, refresh_missing_identity: bool) -> bool:
    if not refresh_missing_identity:
        return False
    has_rank = bool(cache_entry.location_rank)
    has_osm_identity = bool(cache_entry.osm_type and cache_entry.osm_id is not None)
    has_bbox = cache_entry.osm_boundingbox is not None
    return not (has_rank and has_osm_identity and has_bbox)
