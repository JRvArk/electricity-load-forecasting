# CLAUDE.md — electricity-load-forecasting

Instructions for Claude Code. Read this fully before touching anything.
The human-facing learning guide and phase roadmap live in `BUILD_PLAN.md`.

## Status — read this before planning anything

Parked 2026-09-01, **un-parked 2026-09-07**. **Phase 1 is implemented on the synthetic source**
(the EIA retrieval path is a stub); **Phase 2 is in progress** — tests written, `build.py` and
`train.py` still stubs; **Phase 3 is open**. Phases 4–7 are the current work: **70–80 hours,
time-boxed**, at 6–12 hrs/wk, run on an x86-64 Linux VPS rather than the laptop. **Finishing is a
hard constraint** — scope that threatens it loses, every time. **Phase 9 is cut** (it had no
terminal state and this project needs one); **Phase 8 is deferred**, not dismissed. Reasoning and
the stop rule are in `BUILD_PLAN.md`.

Two consequences for you. **Do not restore Phase 9 or fold it into 4–7**, and do not start
Phase 8. And **do not add a Linux track, reading list or curriculum** — the phases are the
curriculum, and a separate learning track has been explicitly refused.

## Repo boundary — everything here is addressed to a reader who has only this repo

- **Motivation is argued in project terms.** Why a phase exists, why one was cut, why the box is
  70–80 hours — justify it from what the system needs and what an unfinished system costs. Do not
  import reasons from outside the repo: no career targets, employers, courses, or other planning
  documents, and no naming of the places those live. If a reason cannot be stated in terms of this
  codebase, it is not a reason this file should carry.
- **No forward dates.** A date is allowed only as provenance on a decision already taken
  (*"decided 2026-09-07"*). Everything else is expressed as budget, rate and ordering — "70–80
  hours", "6–12 hrs/wk", "queued behind Phase 7" — which is what the plan actually needs in order
  to be actionable, and which stays true when the calendar moves. Scheduling belongs to whatever
  is doing the scheduling; this repo is not it.
- **Sibling repos are referred to obliquely** — "a companion project" — and only where the point
  genuinely needs them.

This is a hygiene rule, not a secrecy one: a plan that reads as self-contained is a plan whose
reasoning survives being read cold, by someone else or by you in a year.

## What this project is

A production ML service for short-horizon **hourly demand forecasting** (anchor
domain: electricity load). The forecasting task is a *vehicle*. The actual point
of this project is everything **around** the model: ingestion, feature building,
experiment tracking, a model registry, a serving API, orchestration, drift
monitoring, and an automated retrain loop.

Design axiom: **the model is a commodity artifact that flows through a system.**
A boring gradient booster is the correct choice. Do not spend effort on model
sophistication — spend it on reproducibility, idempotency, and operational
correctness. If you ever feel the urge to add a fancy model, that's a signal
you've drifted from the goal.

## Hard conventions (do not violate)

1. **Idempotency.** Any job can be re-run on the same inputs without producing
   duplicates or corrupt state. Ingestion upserts; it never blindly appends.
2. **Reproducibility.** Every model is produced by a tracked run with logged
   params, metrics, and the exact feature config. No model exists outside MLflow.
3. **The domain is swappable.** Dataset choice lives in `config/config.yaml`
   only. No module hardcodes "electricity". A synthetic generator is the default
   source so the system runs with zero external dependencies — keep tests and CI
   on it (they must stay offline and deterministic). Real data (EIA, `kind: eia`)
   is opt-in for live runs.
4. **Promotion is earned.** A retrained model only reaches the `Production` stage
   if it beats the incumbent on a holdout metric. A worse model must never serve.
5. **Type hints everywhere. Tests for every phase before moving on.**

## Your role

Coach, not implementer. You may critique interfaces, review test coverage, explain
concepts, and help debug failures the human has already engaged with. Do not write
phase implementations — that is the entire point of the repo.

## Tech stack

- Storage: DuckDB + parquet (`data/`)
- Data: synthetic generator (default, offline) | EIA open data API v2 (live)
- Model: scikit-learn (`HistGradientBoostingRegressor`) — intentionally plain
- Tracking + registry: MLflow (local file store under `mlruns/`)
- Serving: FastAPI + Uvicorn
- Orchestration: **systemd timers** (decided 2026-09-07 — Prefect dropped; reasoning in `BUILD_PLAN.md` Phase 5)
- Monitoring: Evidently
- CI: GitHub Actions
- Config: Pydantic + YAML
- Dependencies: uv (`uv sync --extra dev` to install)
- Cloud target (Phase 8, **deferred**): Databricks Free Edition (perpetual, serverless, free)

## Directory map

```
config/config.yaml         # the ONLY place domain/dataset is chosen
src/forecaster/
  config.py                # GIVEN: loads + validates config.yaml (plumbing, no learning)
  ingestion/ingest.py      # human implements: pull -> raw store, idempotent
  features/build.py        # human implements: raw -> feature table
  training/train.py        # human implements: feature table -> tracked MLflow run
  registry/promote.py      # human implements: register + earned-promotion gate
  serving/app.py           # human implements: FastAPI serving the Production model
  monitoring/drift.py      # human implements: drift signal
  orchestration/flows.py   # human implements: plain-Python pipelines, run by systemd timers
tests/                     # human writes tests here, BEFORE implementing
reference/                 # worked solution — exists locally, gitignored
data/                      # parquet + duckdb (gitignored except .gitkeep)
```

## How to run

```bash
uv sync --extra dev
python -m forecaster.ingestion.ingest --backfill-days 90   # Phase 1
python -m forecaster.features.build                        # Phase 2
python -m forecaster.training.train                        # Phase 2
uvicorn forecaster.serving.app:app --reload                # Phase 3
pytest                                                     # tests
```

The module-as-script convention (`python -m forecaster.<area>.<module>`) and the
`uvicorn ...app:app` target are fixed; the internals behind them are the human's
to design.
