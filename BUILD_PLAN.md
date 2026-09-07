# Build plan — electricity-load-forecasting

Personal roadmap and methodology notes for this project.

## Status — un-parked, finishing January 2027

Parked 2026-09-01 alongside a causal-inference engine, on the grounds that neither was on the
critical path. **Un-parked 2026-09-07**, for this repo only — the sibling stays archived.

The reason it came back: the career target is now **quant research in two employer clusters**,
prop firms and **energy trading houses**, and this is the engineering artifact for the second.
It is also the cheapest remaining artifact, because most of it is already built.

- **Slot:** **January 2027** — four weeks with no university course in them, between semester-1
  finals in mid-December and semester 2 starting in February. The one genuinely open block in
  the year.
- **Budget:** **70–80 hours, time-boxed.**
- **Scope:** **Phase 3 close-out through Phase 7.** Phase 3 is still open, so that is real work
  rather than a formality.
- **Venue:** a rented x86-64 Linux VPS, not the laptop — see *Where this runs*, below.
- **After January it is done.** It goes on the CV and gets written up; it is not maintained as a
  rolling project. That is what cutting Phase 9 is for.

### The time box, fixed before starting

70–80 hours across the remaining phases, set **in advance**. The number is a judgement, not a
researched estimate — its entire value is that it was fixed before the work began.

**Stop rule:** at the box limit, ship what is done and record the rest as the finding.
Under-delivering against a stated target is a result. An unbounded finish is not.

## Approach

Each phase owns a single done-criterion. I stop when it's met — that's a clean
save point. The loop per phase:

1. Read the module docstring (target properties) and the done-criterion below.
2. Design the interface — decide functions and signatures before writing any code.
3. Write tests in `tests/` that pin those properties — before implementing.
4. Implement in `src/forecaster/...` until tests pass.
5. Diff my implementation against the reference solution (`reference/`, local only).
   Compare approach and test coverage; two things to look at separately:
   - **My implementation vs. the reference** — different paths to the same contract.
   - **My tests vs. the reference tests** — properties I missed are gaps in how I
     thought about correctness. Often more instructive than any code difference.

I'm deliberately working at a level where properties are specified but function
signatures and test design are mine to figure out. The design thinking is part of
the exercise.

## Phase roadmap

### Phase 1 — Ingestion + storage
Implement `ingestion/ingest.py`. Default source is the synthetic generator. Land
hourly rows in DuckDB via upsert on the timestamp key. Support backfill over a
date range.
**Done when:** running ingest twice over the same range leaves row count unchanged.

When I later flip `kind: eia`, the same upsert must hold up against real-world
mess: paginated responses (EIA caps rows per request), missing hours, and late
revisions, where a previously-published hour comes back with a corrected value.
The upsert must overwrite on the timestamp key, not just skip-if-exists.

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
Implement `orchestration/flows.py`: a Prefect flow that runs ingest → features
→ train → promote on a schedule. Promotion uses the Phase 3 gate.
**Done when:** a deliberately bad retrain cannot reach `Production`.

### Phase 6 — Monitoring + auto-retrain
Implement `monitoring/drift.py` with Evidently (data drift + prediction drift on
a rolling window). Wire a Prefect flow that runs the drift check and triggers the
Phase 5 retrain flow when drift crosses the configured threshold.
**Done when:** injecting drifted data into the store visibly fires a retrain.

### Phase 7 — Live evaluation & performance-over-time
Real forecasting has delayed actuals: at time t I predict hours t+1…t+H, but
those actuals only arrive later. Every prediction gets persisted (target timestamp
+ model version + value), and when the actual for that timestamp lands, I join the
two and compute realized error. The rolling realized-error series — plotted against
EIA's own day-ahead forecast (`forecast_type: DF`) as a baseline — is the
performance-over-time showcase. This also surfaces the gap between backtest error
(what `train.py` reports on a holdout) and live error on genuinely unseen hours.
Target: a predictions table keyed by (target_ts, model_version) that joins to
actuals to yield realized error.
**Done when:** I can show realized error accumulating over time vs. the baseline.

### Phase 8 — Cloud deployment (Databricks Free Edition) — **deferred, not cut**

> **Deferred 2026-09-07, on scope rather than merit.** The argument for it is real: the platform
> is free and perpetual, the phase has a genuine done-criterion, and it would make the Phase 7
> performance view **always-on without a laptop awake** — which is presentation value, not
> platform engineering. It is out of January because it re-platforms a system that already
> works, and 70–80 hours does not stretch to it. Revisit after January as a *presentation*
> decision. Do not start it; do not delete it.
Lift the working local system onto Databricks Free Edition (perpetual, free,
serverless). The Phase 7 showcase becomes always-on: a scheduled Job runs
ingest → score → evaluate → drift-check without my laptop being awake.

What changes vs. the local stack:
- MLflow tracking URI → managed Databricks URI
- Registry → Unity Catalog (`databricks-uc`), promotion via aliases (e.g. `@champion`)
  instead of MLflow stages — gate logic survives, only the mechanism updates
- FastAPI serving → Model Serving endpoint
- Prefect flows → Databricks Jobs / Workflows
- DuckDB/parquet → Delta

It's serverless-only (no cluster to size), so that's a real design constraint to
work through rather than just copy.
**Done when:** a scheduled cloud Job keeps the live performance view current on its own.

### Phase 9 — Experimentation & feature enrichment — **cut 2026-09-07**

> **Cut, and this is the point of the cut.** The heading used to read *(ongoing)*. A phase with
> no terminal state means the project has no terminal state, and this project needs one: it goes
> on a CV in spring 2027 and gets pointed at in applications. What follows is not a phase of
> building the system — it is what the finished system is *for*, kept here because that is worth
> knowing and worth writing up. Nothing below is January work.
This is the payoff of building everything above: improving the model is now a safe,
instrumented loop. I can run a new model or new features as a challenger, let the
promotion gate decide on merit, and watch live error. A worse idea simply never
gets promoted.

What this covers:
- **Model bake-offs** — swap in alternatives, compare via the same tracked metric.
- **Feature enrichment** — weather forecasts are the interesting case. At prediction
  time for hour t+h I only have a *forecast* of the weather, not the actual, so
  weather features must use forecasted values (and ideally train on the forecasts
  that were historically available), or I reintroduce leakage. Open-Meteo is a
  free, keyless source to start with.