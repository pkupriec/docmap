from __future__ import annotations

import json
import os
from pathlib import Path

from services.analytics.geometry_assets import backfill_merged_generic_ocean_boundaries
from services.common.db import get_connection


def _default_source_path() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "admin_boundaries_source.geojson"


def main() -> int:
    source_path = Path(os.getenv("DOCMAP_ADMIN_BOUNDARIES_SOURCE", str(_default_source_path())))
    with get_connection() as conn:
        updated_rows = backfill_merged_generic_ocean_boundaries(conn, source_path=source_path)
        conn.commit()

    print(json.dumps({"source_path": str(source_path), "updated_rows": updated_rows}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
