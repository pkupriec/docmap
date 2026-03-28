from __future__ import annotations

import logging
import os
import json
from dataclasses import dataclass
from pathlib import Path
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
from services.geocoder.scripts.build_canonical_seed_source import build_seed_source_dataset
from services.geocoder.scripts.generate_canonical_seed import build_seed_dictionary
from services.geocoder.scripts.refresh_canonical_dictionary import refresh_dictionary


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeocodeBatchResult:
    processed: int
    geocoded: int
    linked: int
    unresolved: int


MentionCallback = Callable[[int, int, int, int, PendingMention, str | None, str | None], None]
StopCallback = Callable[[], bool]


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def refresh_canonical_dictionary_from_env() -> dict[str, object]:
    return refresh_canonical_dictionary(enabled=None)


def refresh_canonical_dictionary(*, enabled: bool | None) -> dict[str, object]:
    if enabled is None:
        enabled = _env_flag("CANONICAL_REFRESH_ON_GEOCODE", False)
    if not enabled:
        return {"executed": False, "reason": "disabled"}

    default_input = Path(__file__).resolve().parent / "assets" / "canonical_dictionary.json"
    input_path = Path(os.getenv("CANONICAL_DICTIONARY_INPUT", str(default_input))).resolve()
    source = os.getenv("CANONICAL_DICTIONARY_SOURCE", "wof").strip().lower() or "wof"
    report_env = os.getenv("CANONICAL_REFRESH_REPORT_PATH", "").strip()
    report_path = Path(report_env).resolve() if report_env else None
    replace_source = _env_flag("CANONICAL_REFRESH_REPLACE_SOURCE", True)
    autoseed_on_empty = _env_flag("CANONICAL_AUTOSEED_ON_EMPTY", True)
    build_seed_source_on_refresh = _env_flag("CANONICAL_BUILD_SEED_SOURCE_ON_REFRESH", True)
    seed_source_default = Path(__file__).resolve().parent / "assets" / "canonical_seed_source.geojson"
    seed_source_path = Path(
        os.getenv("CANONICAL_SEED_SOURCE", str(seed_source_default))
    ).resolve()

    autoseeded = False
    autoseed_counts: dict[str, int] = {}
    place_count = 0
    if input_path.exists():
        try:
            payload = json.loads(input_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("places"), list):
                place_count = len(payload["places"])
            elif isinstance(payload, list):
                place_count = len(payload)
        except json.JSONDecodeError:
            place_count = 0

    needs_seed = (not input_path.exists()) or place_count == 0
    if needs_seed and autoseed_on_empty:
        seed_feature_count = 0
        if seed_source_path.exists():
            try:
                seed_payload = json.loads(seed_source_path.read_text(encoding="utf-8"))
                features = seed_payload.get("features") if isinstance(seed_payload, dict) else None
                if isinstance(features, list):
                    seed_feature_count = len(features)
            except json.JSONDecodeError:
                seed_feature_count = 0

        if (not seed_source_path.exists() or seed_feature_count == 0) and build_seed_source_on_refresh:
            build_seed_source_dataset(seed_source_path)
        elif not seed_source_path.exists() or seed_feature_count == 0:
            raise FileNotFoundError(
                "canonical seed source is missing/empty and automatic build is disabled: "
                f"{seed_source_path}"
            )
        autoseed_counts = build_seed_dictionary(
            source_path=seed_source_path,
            output_path=input_path,
            source=source,
        )
        autoseeded = True
    elif needs_seed:
        if not input_path.exists():
            raise FileNotFoundError(f"canonical dictionary input does not exist: {input_path}")
        raise ValueError(
            "canonical dictionary input exists but is empty; enable CANONICAL_AUTOSEED_ON_EMPTY or provide data"
        )

    report = refresh_dictionary(
        input_path=input_path,
        source=source,
        report_path=report_path,
        replace_source=replace_source,
    )
    return {
        "executed": True,
        "source": source,
        "input_path": str(input_path),
        "report_path": str(report_path) if report_path is not None else None,
        "replace_source": replace_source,
        "autoseeded": autoseeded,
        "autoseed_counts": autoseed_counts,
        "seed_source_path": str(seed_source_path),
        "counts": report.get("counts", {}),
        "diagnostics": report.get("diagnostics", {}),
    }


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
        force_full_refresh=False,
    )


def process_all_mentions(
    limit: int = 1000,
    *,
    offset: int = 0,
    reset_existing_links: bool = False,
    refresh_missing_identity: bool = False,
    force_full_refresh: bool = False,
    on_mention: MentionCallback | None = None,
    should_stop: StopCallback | None = None,
) -> GeocodeBatchResult:
    logger.info(
        (
            "geocoder.batch_start mode=all limit=%s offset=%s "
            "reset_existing_links=%s refresh_missing_identity=%s force_full_refresh=%s"
        ),
        limit,
        offset,
        reset_existing_links,
        refresh_missing_identity,
        force_full_refresh,
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
        force_full_refresh=force_full_refresh,
    )


def _process_mentions(
    *,
    mentions: list[PendingMention],
    on_mention: MentionCallback | None,
    should_stop: StopCallback | None,
    refresh_missing_identity: bool,
    force_full_refresh: bool,
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
                    force_full_refresh=force_full_refresh,
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
    force_full_refresh: bool = False,
) -> str:
    cached = get_geo_location_cache_entry(conn, mention.normalized_location)
    if cached:
        if force_full_refresh:
            geocoded = geocode_location(mention.normalized_location)
            if not geocoded:
                logger.warning(
                    (
                        "geocoder.full_refresh_unresolved mention_id=%s "
                        "normalized_location=%s old_location_id=%s"
                    ),
                    mention.mention_id,
                    mention.normalized_location,
                    cached.location_id,
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
                (
                    "geocoder.full_refresh_success mention_id=%s normalized_location=%s "
                    "old_location_id=%s new_location_id=%s"
                ),
                mention.mention_id,
                mention.normalized_location,
                cached.location_id,
                location_id,
            )
            return "geocoded_and_linked"

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
    has_canonical = bool(cache_entry.canonical_id)
    has_candidates = bool(cache_entry.geocode_candidates)
    return not (has_rank and has_osm_identity and has_bbox and has_canonical and has_candidates)
