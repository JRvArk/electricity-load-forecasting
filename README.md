# electricity-load-forecasting

An MLOps-first hourly electricity-load forecasting service. The model is a
commodity by design — the learning surface is the production system around it:
idempotent ingestion, tracked training, a registry with an earned-promotion gate,
a serving API, orchestration, drift monitoring, and an automated retrain loop.

This repo is a **rung-3 learning scaffold**. The load-bearing modules under
`src/forecaster/` are thin stubs that state each module's responsibility and target
properties. You design the interfaces, write the tests, and implement each phase
yourself. A complete worked solution lives in `reference/`, to be opened only after
your own tests for a phase are green. Read **CLAUDE.md** before touching anything —
it holds the design axioms, the fade ladder, the working agreement, and the full
phase roadmap (Phases 1–9).

The pipeline runs on a synthetic data source with zero external dependencies — keep
tests and CI on it. Real data via the EIA open-data API (`source.kind: eia`) is
opt-in for live runs.

## Target entrypoints (work once you build each phase)

```bash
pip install -e ".[dev]"
python -m forecaster.ingestion.ingest --backfill-days 90   # Phase 1
python -m forecaster.features.build                        # Phase 2
python -m forecaster.training.train                        # Phase 2
uvicorn forecaster.serving.app:app --reload                # Phase 3
pytest                                                     # your tests
```
