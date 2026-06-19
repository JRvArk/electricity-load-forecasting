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

- **Storage:** DuckDB + parquet
- **Data:** synthetic generator (default, offline) | EIA open-data API v2 (live)
- **Model:** scikit-learn `HistGradientBoostingRegressor`
- **Tracking + registry:** MLflow
- **Serving:** FastAPI + Uvicorn
- **Orchestration:** Prefect
- **Monitoring:** Evidently
- **Cloud target:** Databricks Free Edition (serverless Jobs, Unity Catalog, Delta)

## The domain is swappable

Dataset choice lives in `config/config.yaml` alone — no module hardcodes
"electricity". The default source is a synthetic generator, so the entire system
runs with zero external dependencies (and tests/CI stay offline and deterministic).
Real data via the EIA open-data API (`source.kind: eia`) is opt-in for live runs.

## Run it

```bash
pip install -e ".[dev]"
python -m forecaster.ingestion.ingest --backfill-days 90   # land raw data
python -m forecaster.features.build                        # build features
python -m forecaster.training.train                        # train + track
uvicorn forecaster.serving.app:app --reload                # serve the model
pytest                                                     # tests
```
