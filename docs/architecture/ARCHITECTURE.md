# Architecture

DocMap is a PostgreSQL-backed pipeline with two HTTP applications.

```text
control UI -> control API -> command queue -> orchestrator
                                            |
                                            v
                         crawl -> extract -> geocode -> analytics -> export
                                                        |          |
                                                        v          v
                                                     Postgres   PMTiles
                                                        ^          |
                                                        |          v
                                             presentation API -> MapLibre UI
```

The Compose stack keeps these services:

- `postgres`: PostGIS source of truth.
- `app`: control API plus command worker/orchestrator.
- `control-ui`: operator UI.
- `presentation`: read-only API plus built frontend.
- `canonical-refresh`: optional offline dictionary tool.
- `pgadmin`: local database administration.

The app and presentation containers share one named artifact volume. Analytics publishes immutable version directories and atomically swaps `current.json`; presentation mounts the volume read-only.

Presentation startup opens a bounded `psycopg_pool`, configures read-only transactions, and performs no migration. The control application owns startup schema patches.

Interactive geometry is split by purpose:

- the base map reads one selected PMTiles precision archive through HTTP byte ranges;
- exact geometry for click, selection, and highlight is fetched on demand by explicit location ID;
- points, search results, and document relationships come from compact JSON APIs.
