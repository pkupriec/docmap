# Configuration

Required:

- `DATABASE_URL`

Common pipeline settings:

- `OLLAMA_HOST`, `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_THINK_LEVEL`, `OLLAMA_NUM_PREDICT`
- `EXTRACTOR_MODEL`
- `GEOCODER_URL`, `GEOCODER_USER_AGENT`, `GEOCODER_MIN_INTERVAL_SECONDS`
- `CANONICAL_*` variables from `.env.example`

Presentation and artifacts:

- `DOCMAP_PRESENTATION_ARTIFACT_ROOT` (Compose: `/data/presentation_geometry`)
- `DOCMAP_PRESENTATION_MAX_ARCHIVE_BYTES` (default 512 MiB per archive)
- `DOCMAP_PRESENTATION_ARTIFACT_RETENTION` (default 2: active release plus one rollback release)
- `TIPPECANOE_BIN` (image: `/usr/local/bin/tippecanoe`)
- `DB_POOL_MIN_SIZE` and `DB_POOL_MAX_SIZE` (defaults 1 and 8)
- `PRESENTATION_STATIC_DIR`

Control execution:

- `PIPELINE_COMMAND_LEASE_SECONDS`
- `DOCMAP_EXPORTER`; unset means the built-in no-op export stage

Development-only reset flags are `DB_RESET_ON_START` and `DB_DROP_TABLES_ON_START`. Never enable destructive reset flags against a database containing data you intend to keep.
