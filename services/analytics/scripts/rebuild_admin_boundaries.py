from __future__ import annotations

import json
import os
from pathlib import Path

from services.analytics.baked_geometry_assets import build_baked_geometry_assets
from services.analytics.geometry_assets import build_admin_boundaries_asset
from services.analytics.scripts.build_admin_boundaries_source import build_source_dataset
from services.common.db import get_connection


def _default_source_path() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "admin_boundaries_source.geojson"


def _should_refresh_source() -> bool:
    value = str(os.getenv("DOCMAP_ADMIN_BOUNDARIES_REFRESH_SOURCE", "1")).strip().lower()
    return value not in {"0", "false", "no"}


def main() -> int:
    source_path = Path(os.getenv("DOCMAP_ADMIN_BOUNDARIES_SOURCE", str(_default_source_path())))
    refreshed_source = _should_refresh_source() or not source_path.exists()
    if refreshed_source:
        source_stats = build_source_dataset(source_path)
    else:
        source_stats = {"skipped_refresh": True}

    with get_connection() as conn:
        result = build_admin_boundaries_asset(conn, source_path=source_path)
        baked_result = build_baked_geometry_assets(conn)
        conn.commit()

    print(
        json.dumps(
            {
                "source_path": str(source_path),
                "refreshed_source": refreshed_source,
                "source_stats": source_stats,
                "features_written": result.features_written,
                "matched_by_rank": result.matched_by_rank,
                "total_by_rank": result.total_by_rank,
                "output_path": str(result.output_path),
                "coverage_path": str(result.coverage_path),
                "baked_geometry_version": baked_result.version,
                "baked_geometry_manifest_path": str(baked_result.manifest_path),
                "baked_geometry_total_archives": baked_result.total_archives,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
