# Verification

Install reproducibly:

```powershell
uv --system-certs sync --frozen --extra dev
npm --prefix services/presentation/frontend ci
```

Run static and unit checks:

```powershell
uv run --frozen --extra dev pytest -q
npm --prefix services/presentation/frontend run typecheck
npm --prefix services/presentation/frontend run build
docker compose -f infra/docker-compose.yml config --quiet
docker build -t docmap-app .
docker build -f Dockerfile.presentation -t docmap-presentation .
```

Database verification uses a clean Postgres volume plus startup migrations, then exercises one queued run and command lease reclaim. Presentation verification checks manifest fetch, PMTiles `206` ranges, exact selection overlays, search cancellation, PDF ranges, and thumbnail delivery.

Performance acceptance for a representative existing dataset:

- cold UI becomes interactive within 2 seconds;
- initial transferred presentation geometry is at most 5 MiB;
- first exact geometry appears within 3 seconds;
- pan, select, and search have no multi-second main-thread stall;
- the refactored scenarios are at least 5x faster than the preserved pre-refactor baseline.

Generated PMTiles must pass header, size-budget, clipping, deterministic-version, and atomic-failure tests. Four modes must remain selectable without preloading all tiles.
