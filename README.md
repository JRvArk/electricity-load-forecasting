# electricity-load-forecasting

An MLOps-first electricity-load-forecasting service. The forecasting model is a
commodity by design — the learning surface is the production system around it:
idempotent ingestion, tracked training, a model registry with an earned-promotion
gate, a serving API, orchestration, drift monitoring, and an automated retrain loop.

The whole pipeline runs on a synthetic data source with **zero external
dependencies**, so you can build the entire system before wiring a real dataset.

## Quickstart

```bash
pip install -e ".[dev]"

python -m forecaster.ingestion.ingest --backfill-days 90   # Phase 1: land raw data
python -m forecaster.features.build                        # Phase 2: build features
python -m forecaster.registry.promote                      # Phase 2-3: train, register, gate
uvicorn forecaster.serving.app:app --reload                # Phase 3: serve
pytest                                                     # tests
```

## The build

Implemented through Phase 3 (runnable spine on synthetic data). Phases 4–7 are
stubbed with fixed contracts and `TODO(phase-N)` markers.

See **CLAUDE.md** for the design axioms, hard conventions, full phase-by-phase
roadmap with done-criteria, and the working agreement for Claude Code. Read it
before changing anything.
