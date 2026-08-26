# Operations

Start the supported stack:

```powershell
docker compose -f infra/docker-compose.yml up --build
```

Endpoints: control API `http://localhost:8000`, control UI `http://localhost:5173`, presentation `http://localhost:8080`, pgAdmin `http://localhost:5050`.

Python dependencies are locked in `uv.lock`; frontend dependencies are locked in `package-lock.json`. Docker builds use frozen installs. Tippecanoe 2.79.0 is built in the application image.

Analytics publication writes `{version}/*.pmtiles` and `{version}/manifest.json`, validates every archive, then atomically replaces `current.json`. Failed builds remain invisible. The presentation container only reads this volume.

Location consolidation runs at the start of geocoder processing. It writes identity keys, maps aliases to the preferred entity, and redirects raw document links. The following analytics stage rebuilds presentation rows from those links.

PDF list previews use the snapshot WebP. Opening a document still streams the original PDF and supports byte ranges.

For an existing database, generate previews from stored PDFs without crawling again:

```powershell
python -m services.crawler.thumbnail_backfill
```

Raw snapshots and PDFs are not removed during geo/analytics/artifact rebuilds. BigQuery credentials and export setup are no longer part of operations.
