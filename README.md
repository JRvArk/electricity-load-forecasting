# electricity-load-forecasting

An MLOps-first service for short-horizon **hourly electricity-load forecasting**.
The model itself is deliberately plain — a gradient booster — because the model is
treated as a commodity artifact that flows through a system. The engineering is the
product: a reproducible, idempotent pipeline that ingests data, builds features,
trains and tracks models, gates promotion on measured performance, serves the
current production model over an API, and watches itself for drift to trigger
retraining.

## What it does

- **Idempotent ingestion** — hourly observations land in DuckDB via upsert on the
  timestamp key. Re-running a backfill never duplicates or corrupts rows, and late
  upstream revisions overwrite cleanly.
- **Reproducible training** — every model is produced by a tracked MLflow run with
  logged params, metrics, and the exact feature-config hash. No model exists
  outside the tracking store.
- **Earned promotion** — a retrained model only reaches `Production` if it beats the
  incumbent on a holdout metric. A worse model never serves.
- **Live serving** — a FastAPI service loads whichever version is at `Production`
  from the registry, with a reload endpoint. Changing the production version changes
  predictions with no code change and no redeploy.
- **Orchestration** — Prefect flows run ingest → features → train → promote on a
  schedule.
- **Drift monitoring + auto-retrain** — Evidently watches data and prediction drift
  on a rolling window and fires a retrain when drift crosses a configured threshold.
- **Live evaluation** — every prediction is persisted and joined to actuals as they
  arrive, producing a realized-error series tracked over time against a day-ahead
  baseline.

## Architecture

```
config/config.yaml         # single source of truth for domain/dataset
src/forecaster/
  ingestion/ingest.py      # pull -> raw store, idempotent upsert
  features/build.py        # raw -> feature table (lags, rolling, calendar)
  training/train.py        # feature table -> tracked MLflow run
  registry/promote.py      # register + earned-promotion gate
  serving/app.py           # FastAPI serving the Production model
  monitoring/drift.py      # drift signal -> retrain trigger
  orchestration/flows.py   # Prefect flows tying it together
```

## Tech stack

The system is built on a portable open-source stack, then lifted to a serverless
cloud platform without rewriting the core logic — the same code runs locally and on
Databricks.

| Concern | Local (open-source) | Cloud (Databricks Free Edition) |
| --- | --- | --- |
| Storage | DuckDB + parquet | Delta |
| Tracking + registry | MLflow (file store) | MLflow + Unity Catalog (`@champion` aliases) |
| Serving | FastAPI + Uvicorn | Model Serving endpoint |
| Orchestration | Prefect flows | Databricks Jobs / Workflows |
| Monitoring | Evidently | runs in a Job (or Lakehouse Monitoring) |

- **Data:** synthetic generator (default, offline) | EIA open-data API v2 (live)
- **Model:** scikit-learn `HistGradientBoostingRegressor` — plain by design

The local→cloud lift is a deliberate showcase: because the stack is OSS, migration
is a matter of repointing infrastructure (MLflow tracking URI, registry, schedulers)
rather than rebuilding — and the promotion gate logic survives intact, only its
mechanism changes (MLflow stages → Unity Catalog aliases).

## The domain is swappable

Dataset choice lives in `config/config.yaml` alone — no module hardcodes
"electricity". The default source is a synthetic generator, so the entire system
runs with zero external dependencies (and tests/CI stay offline and deterministic).
Real data via the EIA open-data API (`source.kind: eia`) is opt-in for live runs.

## Run it

Each command works once the corresponding phase is implemented (see `BUILD_PLAN.md`).
The stubs are present but empty — that's intentional; implementing them is the exercise.

```bash
uv sync --extra dev
python -m forecaster.ingestion.ingest --backfill-days 90   # Phase 1 — land raw data
python -m forecaster.features.build                        # Phase 2 — build features
python -m forecaster.training.train                        # Phase 2 — train + track
mlflow ui                                                  # Phase 2 — inspect runs
uvicorn forecaster.serving.app:app --reload                # Phase 3 — serve the model
pytest                                                     # your tests
```
