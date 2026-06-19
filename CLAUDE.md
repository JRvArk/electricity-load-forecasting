# CLAUDE.md — electricity-load-forecasting

Handoff guide for Claude Code. Read this fully before touching anything.

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

This is a deliberate counterpart to a separate, theory-heavy project (the causal
effect engine). Here there is no theory to derive. The difficulty is all wiring.

## Hard conventions (do not violate)

1. **Idempotency.** Any job can be re-run on the same inputs without producing
   duplicates or corrupt state. Ingestion upserts; it never blindly appends.
2. **Reproducibility.** Every model is produced by a tracked run with logged
   params, metrics, and the exact feature config. No model exists outside MLflow.
3. **The domain is swappable.** Dataset choice lives in `config/config.yaml`
   only. No module hardcodes "electricity". A synthetic generator is the default
   source so the system runs with zero external dependencies — keep tests and CI
   on it (they must stay offline and deterministic). Real data (EIA, `kind: eia`)
   is opt-in for live runs. Wiring that split cleanly is itself the lesson: test
   against a deterministic fake, run against the real thing.
4. **Promotion is earned.** A retrained model only reaches the `Production` stage
   if it beats the incumbent on a holdout metric. A worse model must never serve.
5. **Type hints everywhere. Tests for every phase before moving on.**

## Tech stack

- Storage: DuckDB + parquet (`data/`)
- Data: synthetic generator (default, offline) | EIA open data API v2 (live)
- Model: scikit-learn (`HistGradientBoostingRegressor`) — intentionally plain
- Tracking + registry: MLflow (local file store under `mlruns/`)
- Serving: FastAPI + Uvicorn
- Orchestration: Prefect
- Monitoring: Evidently
- CI: GitHub Actions
- Config: Pydantic + YAML
- Cloud target (Phase 8): Databricks Free Edition (perpetual, serverless, free)

## Directory map

```
config/config.yaml         # the ONLY place domain/dataset is chosen
src/forecaster/
  config.py                # GIVEN: loads + validates config.yaml (plumbing, no learning)
  ingestion/ingest.py      # YOU: pull -> raw store, idempotent
  features/build.py        # YOU: raw -> feature table
  training/train.py        # YOU: feature table -> tracked MLflow run
  registry/promote.py      # YOU: register + earned-promotion gate
  serving/app.py           # YOU: FastAPI serving the Production model
  monitoring/drift.py      # YOU: drift signal (no reference exists — fully yours)
  orchestration/flows.py   # YOU: Prefect flows tying it together
tests/                     # YOU: write your tests here, BEFORE implementing
reference/                 # worked solution — DO NOT OPEN until your phase is green
data/                      # parquet + duckdb (gitignored except .gitkeep)
```

## How to learn from this (read before building)

This repo is set up for **rung 3** of a fade ladder. The point is that *you* do
the design thinking, not that you make a pre-written bar go green.

For every phase, the loop is:

1. Read the module docstring (target properties) and the phase done-criterion below.
2. Design the interface yourself — decide the functions and their signatures.
3. Write your tests in `tests/` that pin the properties — **before** implementing.
4. Implement in `src/forecaster/...` until your tests pass.
5. **Only now** open the matching file in `reference/`. Diff your implementation
   AND your test coverage against mine. Compare; never copy.

The fade ladder, so you can dial support to your energy on a given day:

1. Reference code visible — pure worked example, lowest load.
2. Tests given, you implement.
3. **Properties given, you write tests then code. ← you are here (default).**
4. Phase name + axioms only — you decide which properties even matter.

To raise support on a depleted evening, open `reference/` sooner. To raise the
challenge, cover a module's docstring and work from the done-criterion alone.
What `reference/` is for is spelled out in `reference/README.md`.

## Build order — implement phase by phase, do not skip ahead

Each phase has a single **done-criterion**. Stop when it's met; that's a clean
save point for a low-energy session. The stubs state each module's responsibility
and target properties but deliberately omit function signatures — designing those
is part of the work.

### Phase 1 — Ingestion + storage
Implement `ingestion/ingest.py`. Default source is the synthetic generator. Land
hourly rows in a DuckDB table via upsert on the timestamp key. Support backfill
over a date range.
**Done when:** running ingest twice over the same range leaves row count unchanged.

When you later flip `kind: eia`, the same upsert must hold up against *real-world*
mess: paginated responses (EIA caps rows per request), missing hours, and — the
interesting one — **late revisions**, where a previously-published hour comes back
with a corrected value. Your upsert must overwrite on the timestamp key, not just
skip-if-exists. That requirement is exactly why idempotency was the Phase 1 axiom.

### Phase 2 — Features + baseline + tracking
Implement `features/build.py` (lag features, rolling means, hour/day/month,
holiday flag) and `training/train.py` (train `HistGradientBoostingRegressor`,
log params + MAE/RMSE + the feature config hash to MLflow).
**Done when:** two runs are visible and comparable in the MLflow UI.

### Phase 3 — Registry + serving
Implement `registry/promote.py` (register the run's model) and `serving/app.py`
(`GET /health`, `POST /predict`). The app loads the model currently at the
`Production` stage from the MLflow registry at startup, with a reload endpoint.
**Done when:** changing which version is `Production` changes predictions with no
code change and no redeploy.

### Phase 4 — Containerize + CI
Flesh out `Dockerfile` and `docker-compose.yml` (service + mlflow). Make
`.github/workflows/ci.yml` run lint + pytest and build the image.
**Done when:** `docker compose up` yields a working `/predict` from a clean clone.

### Phase 5 — Orchestration
Implement `orchestration/flows.py`: a Prefect flow that runs ingest -> features
-> train -> promote on a schedule. Promotion uses the Phase 3 gate.
**Done when:** a deliberately bad retrain cannot reach `Production`.

### Phase 6 — Monitoring + auto-retrain
Implement `monitoring/drift.py` with Evidently (data drift + prediction drift on
a rolling window). Wire a Prefect flow that runs the drift check and triggers the
Phase 5 retrain flow when drift crosses the configured threshold.
**Done when:** injecting drifted data into the store visibly fires a retrain.

### Phase 7 — Live evaluation & performance-over-time
Real forecasting has **delayed actuals**: at time t you predict hours t+1…t+H, but
those actuals only arrive later. So you can't score a live forecast immediately.
Persist every prediction (target timestamp + model version + value), and when the
actual for that timestamp lands, join the two and compute realized error. The
rolling realized-error series — ideally plotted against EIA's own day-ahead
forecast (`forecast_type: DF`) as a baseline — is your performance-over-time
showcase. Note the gap this exposes: backtest error (what `train.py` reports on a
holdout) and live error (on genuinely unseen future hours) routinely differ.
Target property: a predictions table keyed by (target_ts, model_version) that
joins to actuals to yield realized error. (You design the schema and the join.)
**Done when:** you can show realized error accumulating over time vs. the baseline.

### Phase 8 — Cloud deployment (Databricks Free Edition)
Lift the working local system onto Databricks Free Edition (perpetual, free,
serverless). The payoff is that the Phase 7 showcase becomes *always-on*: a
scheduled Job runs ingest → score → evaluate → drift-check without your laptop
being awake. The migration mostly proves why the stack is OSS: point MLflow at the
managed tracking URI; the registry becomes Unity Catalog (`databricks-uc`); FastAPI
serving becomes a Model Serving endpoint; Prefect flows become Jobs; DuckDB/parquet
becomes Delta. Two genuine changes to design through, not copy: it's serverless-only
(no cluster to size), and promotion moves from MLflow **stages** to Unity Catalog
**aliases** (e.g. `@champion`) — so your `promote.py` gate logic survives but its
mechanism updates. This track fits the fade ladder differently: properties and
done-criteria still drive it, but "design the interface" becomes "design the
deployment topology," and tests become smoke tests against deployed resources.
**Done when:** a scheduled cloud Job keeps the live performance view current on its own.

### Phase 9 — Experimentation & feature enrichment (ongoing, not a milestone)
This is the point of having built everything above: improving the model is now a
*safe, instrumented loop*, not a risky edit. The registry + earned-promotion gate +
live evaluation mean you can try a new model or new features as a challenger, let
the gate decide on merit, and watch live error — a worse idea simply never gets
promoted. So this isn't a phase you "finish"; it's the steady state you operate in.
What it covers: model bake-offs (swap in alternatives, compare honestly via the
same tracked metric), and feature enrichment — notably **weather forecasts**, which
carry their own lesson. At prediction time for hour t+h you only have a *forecast*
of the weather for t+h, not the actual, so weather features must use forecasted
values (and ideally train on the forecasts that were available historically), or
you reintroduce leakage — the same "only information available at decision time"
discipline as delayed actuals. A free, keyless source like Open-Meteo is a
reasonable candidate when you get here.
**No done-criterion — this is the machine doing its job.**

## How to run (these are the target entrypoints — they work once you build each phase)

```bash
pip install -e ".[dev]"
python -m forecaster.ingestion.ingest --backfill-days 90   # Phase 1 (you build)
python -m forecaster.features.build                        # Phase 2
python -m forecaster.training.train                        # Phase 2
uvicorn forecaster.serving.app:app --reload                # Phase 3
pytest                                                     # your tests
```

The module-as-script convention (`python -m forecaster.<area>.<module>`) and the
`uvicorn ...app:app` target are fixed; the internals behind them are yours to design.

## Working agreement

This repo is a *learning* artifact at rung 3 (see "How to learn from this"). The
human writes the implementations and the tests. That is the entire point.

- The load-bearing modules are yours to design and implement. Do not hand them to
  an AI to write — that reproduces the fluency illusion this setup exists to avoid.
- If you use an AI assistant here, its job is **coach, not implementer**: it may
  critique your interface, review your test coverage, explain a concept, or help
  debug a failure you've already engaged with — it must not write the phase for you.
- Write your tests before the implementation, in `tests/`.
- Touch only the phase you're on.
- Keep `config.yaml` the single source of truth for anything domain-specific.
- Open `reference/` for a module only after your tests for it are green.
- When a phase's done-criterion is met, that's a clean stopping point.
