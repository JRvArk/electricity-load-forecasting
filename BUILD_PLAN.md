# Build plan — electricity-load-forecasting

Personal roadmap and methodology notes for this project.

## Status — un-parked, finishing January 2027

Parked 2026-09-01 alongside a causal-inference engine, on the grounds that neither was on the
critical path. **Un-parked 2026-09-07**, for this repo only — the sibling stays archived.

The reason it came back: the career target is now **quant research in two employer clusters**,
prop firms and **energy trading houses**, and this is the engineering artifact for the second.
It is also the cheapest remaining artifact, because most of it is already built.

- **Slot:** **September–December 2026**, at 6–12 hrs/wk alongside semester 1 *(moved from January
  on 2026-09-07)*. This project holds the term-time project slot because its remaining work is
  implementation against fixed interfaces, which survives being picked up and put down in six-hour
  weeks. The vol-surface engine takes the concentrated January block instead — its Phase 1 is
  exploratory analysis that wants sustained attention.
- **Budget:** **70–80 hours, time-boxed** — which is 7–13 weeks at 6–12 hrs/wk, so it fits the
  term with margin.
- **Deadline, and it is real.** The first internship applications may go out in **December 2026**.
  This is the artifact they would carry: it is already on the CV, so it is the repo a reader
  clicks, and a finished running system reads very differently from a half-built one. Its write-up
  joins the VRP and Greenchoice notes in the December post-finals window.
- **Scope:** **Phase 3 close-out through Phase 7.** Phase 3 is still open, so that is real work
  rather than a formality.
- **Venue:** a rented x86-64 Linux VPS, not the laptop — provisioned **in September**, day one.
  See *Where this runs*, below.
- **After December it is done.** It goes on the CV and gets written up; it is not maintained as a
  rolling project. That is what cutting Phase 9 is for.

### The time box, fixed before starting

70–80 hours across the remaining phases, set **in advance**. The number is a judgement, not a
researched estimate — its entire value is that it was fixed before the work began.

**Split, fixed in advance** — so an overrun is visible while there is still time to act on it,
rather than in December with an application pending: Phase 3 close-out ~20, Phase 4 ~10, Phase 5 ~15, Phase 6 ~20, Phase 7 ~15.
The shape matters more than the numbers: Phases 6 and 7 carry the most unknowns and the least
reference material, and Phase 4 is the one that is mostly configuration.

**Stop rule:** at the box limit, ship what is done and record the rest as the finding.

### Open decisions — resolve before the phase they gate

Nothing here is hard, and all three are cheap to settle. They are listed because each one is
easier to decide now than to discover mid-phase, and two of them gate a phase's done-criterion.

| # | Decision | Gates | Why it cannot be deferred into the phase |
|---|---|---|---|
| ~~**A**~~ | ~~Forecast horizon and lag frame~~ — **decided 2026-09-07: $H = 24$, lags from the forecast origin** | ~~Phase 2~~ | Settled. Reasoning in the Phase 2 box |
| **B** | **Loop-termination mechanism** — cooldown, drift acknowledgement, or escalation after *k* rejections | **Phase 6** | Phase 6's done-criterion now requires that a persistently drifted store stops retraining. Without a choice there is no criterion to test |
| **C** | **`drift_threshold` value and its basis** | **Phase 6** | 0.5 is a placeholder. Most features here are transforms of one series, so they drift together and "half of them" ≈ "the series drifted". Fix a value *with a stated reason*, the way the vol-surface thresholds were fixed in advance |

A is settled. **Do not start Phase 6 with B and C open.** Both feed its done-criterion directly, and deciding
them under time pressure at hour 60 of an 80-hour box is how a threshold ends up being whatever
made the test pass.
Under-delivering against a stated target is a result. An unbounded finish is not.

## Where this runs — a VPS, and Linux as a by-product

From day one — September, not January — the project runs on a rented **x86-64 Linux VPS**
(~€4/month), not the laptop. One evening to provision: create the instance, add an SSH key, disable root and password
login, enable a firewall, install `tmux`.

This is a **venue decision, not a new commitment.** Linux fluency is wanted and a separate
"learn Linux" thread has been deliberately refused, because it would compete with the
mathematics. It does not need to be a thread — the remaining phases *are* the curriculum:

- **Phase 4 containerisation** meets the **ARM64 trap** immediately: the laptop is Apple
  Silicon, the VPS is x86-64, so an image built locally will not run there.
  `docker buildx build --platform linux/amd64` is the fix, and understanding *why* is the
  lesson.
- **Phase 5 orchestration** is a scheduler on a real machine (see the open decision in Phase 5).
- **Phase 6 monitoring** is reading logs on a box that is not in front of you.

**Yield rule.** If Linux starts becoming the project rather than the venue, fall back to local
Docker and finish the pipeline. The deliverable is the service; Linux is the by-product.

**One more job for the same box.** A companion project needs `perf` profiling in summer 2027,
and Apple Silicon does not expose hardware performance counters. This VPS is the obvious
candidate — but cheap VPSs are KVM guests, where counters are often not exposed either. Run
`perf stat -e cycles,instructions,cache-misses` on it **the day it exists**, ten months before it
is needed. Ten minutes now, or an expensive surprise in July.

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
**Done when:** running ingest twice over the same range leaves row count unchanged, **and
re-ingesting a corrected value overwrites it.** The count test alone is too weak — a
skip-if-exists implementation passes it and still fails the late-revision requirement below,
which is the one that actually bites on real data.

When I later flip `kind: eia`, the same upsert must hold up against real-world
mess: paginated responses (EIA caps rows per request), missing hours, and late
revisions, where a previously-published hour comes back with a corrected value.
The upsert must overwrite on the timestamp key, not just skip-if-exists.

### Phase 2 — Features + baseline + tracking

> **[DECIDED 2026-09-07 — $H = 24$, lags measured from the forecast origin.]** Neither was defined
> anywhere: there was no `horizon` key in `config.yaml`, and `test_horizon_hours` is the holdout
> length, not a horizon.
>
> It matters concretely. `build.py`'s no-leakage property reads *"every feature at time $t$ uses
> only information available strictly before $t$"*, which is correct for a **one-step** model and
> wrong otherwise. Phase 7 says *"at time $t$ I predict hours $t+1 \dots t+H$"*, and the EIA
> baseline is `DF` — a **day-ahead** forecast, so $H \approx 24$. At $H = 24$, a lag-1 feature on
> the target timestamp needs the value at $t+23$, which does not exist when you predict. **`lags:
> [1, 2, 3]` would be leakage**, and silently: the backtest would look excellent and live error
> would not match it. Phase 7 exists to surface exactly that gap, which is a slow and expensive way
> to learn it.
>
> **The resolution is a definition, not a config change.** Lags are measured from the **forecast
> origin**: lag-1 means "the most recent observed value at forecast time", which is available at
> every horizon. The existing list `[1, 2, 3, 24, 48, 168]` therefore stays valid exactly as
> written — nothing in it was wrong, only the frame it was read in.
>
> **$H = 24$**, matching the EIA day-ahead baseline and the README's "short-horizon" claim. It is
> also the version that is a forecasting problem: at $H = 1$ hourly load is close to a persistence
> problem and a seasonal-naive baseline is nearly unbeatable, so there would be nothing to
> demonstrate.
>
> **What this makes concrete.** `config.yaml` gains `horizon_hours: 24`. Each training row becomes
> (origin $t$, horizon $h \in 1\dots24$, target at $t+h$), with $h$ itself a feature — one model
> across horizons rather than 24 models, which is simpler and lets the model learn that error grows
> with $h$. `build.py`'s leakage property is stated against the **origin**, not the target
> timestamp. And Phase 7's realized-error series becomes naturally two-dimensional: error by
> horizon, which is a better plot than a single line and shows where the model degrades.
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

> **The gate must compare on the same holdout, and this is easy to get wrong.**
> `training.test_horizon_hours: 168` holds out the last week. The challenger is scored on the last
> week of *today's* data; the incumbent's stored metric was computed on the last week of data as it
> stood *when it was trained*. Those are different evaluation sets, so comparing the two stored
> numbers is not a comparison — a challenger can win because its week happened to be calmer.
>
> **So the gate re-scores the incumbent on the challenger's holdout** and compares both on that one
> set. Comparing stored metrics is the intuitive implementation and it is wrong. Make it an explicit
> test: one model, two holdouts of differing difficulty, must not be judged better on the easier
> one.

### Phase 4 — Containerize + CI
Flesh out `Dockerfile` and `docker-compose.yml` (service + mlflow). Make
`.github/workflows/ci.yml` run lint + pytest and build the image.
**Done when:** `docker compose up` yields a working `/predict` from a clean clone.

### Phase 5 — Orchestration
Implement `orchestration/flows.py`: a plain-Python pipeline that runs ingest → features → train →
promote, invoked on a schedule by a systemd timer. ("Flow" here is generic, not Prefect vocabulary —
the filename stays for continuity.) Promotion uses the Phase 3 gate.
**Done when:** a deliberately bad retrain cannot reach `Production`.

> **[DECIDED 2026-09-07 — systemd timers.]** Prefect is dropped from the stack.
>
> **Why, in order of weight.** *Linux is the point of the venue*, and systemd is where it gets
> learned: unit files, `OnCalendar`, `systemctl list-timers`, `journalctl -u`, exit codes,
> `OnFailure=` chaining — plus the two Phase 6 drills fall straight out of the unit file
> (`MemoryMax=` is the OOM drill, `User=` plus ownership is the permissions drill). And the single
> most instructive Linux lesson available here only exists under systemd: **it works in your shell
> and fails under the timer** — different `$PATH`, no shell profile, no interactive environment.
>
> *Prefect's retries work against Phase 6.* Its headline feature is making transient failures
> invisible; Phase 6's acceptance test is breaking things deliberately and diagnosing from logs
> before touching code. You would have to switch off the thing you were paying for.
>
> *You end up on systemd either way* — a self-hosted Prefect worker needs a unit to keep it alive
> across reboots. So the real comparison was *Prefect and systemd* against *systemd*.
>
> *Both systemd modes get covered anyway*: `Type=oneshot` + timer for the pipeline here, and a
> long-running `Restart=always` service for the Phase 3 FastAPI app.
>
> **What is given up, honestly.** Declarative retries and backoff — see the requirement below,
> which is where they go instead. And a run-history UI, replaced by something better in the same
> requirement. Neither loss is a Linux consideration.

**Requirements this creates.** All three are scheduler-agnostic; none of them come free now.

1. **A run-history table in DuckDB** — `(run_id, flow, started_at, ended_at, status, model_version,
   promoted, reject_reason, drift_share)`. It is needed regardless of scheduler because Phase 6's
   loop-termination state has to live somewhere, and it is a better artifact than an orchestrator
   screenshot: queryable, version-controllable, and yours. It also feeds the `GET /status`
   endpoint and the Phase 7 write-up.
2. **Retry with backoff around the external API call**, in Python, in the ingest step. systemd will
   not do this for you, and ingest talks to a network API. Roughly twenty lines, and error handling
   you would want anyway.
3. **Keep the pipeline as plain functions and the scheduler thin.** `run_retrain()` and
   `run_monitor()` as ordinary callables invoked by `python -m forecaster.orchestration.…`. The
   unit file should be fifteen lines that call one thing. That keeps the decision cheap to reverse:
   an orchestrator, if one is ever wanted, becomes a wrapper rather than a rewrite.

### Phase 6 — Monitoring + auto-retrain

> **Blocked until open decisions B and C are settled** (see *Open decisions*, above). B is the
> loop-termination mechanism, C is the `drift_threshold` basis. Both are inputs to this phase's
> done-criterion, not outputs of it.
Implement `monitoring/drift.py` with Evidently (data drift + prediction drift on
a rolling window). Wire a monitor entry point that runs the drift check and triggers the
Phase 5 retrain flow when drift crosses the configured threshold.
**Done when:** injecting drifted data into the store visibly fires a retrain — end to end, not only
a unit fixture — **and a persistently drifted store does not retrain forever** — **and** the four
failure drills below have each been diagnosed from logs alone.

**Deliberate failure is the acceptance test, not an extra.** Break it on purpose, then find the
cause *from logs before touching code*. This is the part almost nobody can discuss in an
interview, and it is nearly free once the thing runs on a real box:

| Drill | What it teaches |
|---|---|
| Fill the disk (`fallocate`) and watch the job fail | `df -h`, `du -sh /* \| sort -h` — the cause of a large share of mystery failures |
| Revoke read permission on the data directory | Reading a traceback back to a permissions cause |
| Cap container memory until the job is OOM-killed | The evidence is in `dmesg` / `journalctl -k`, not in the application log |
| Point the schedule at a script that does not exist | What the scheduler's own status output actually tells you |

**The diagnostic order worth memorising:** is the disk full, was it OOM-killed, is it a
permissions problem — in that order, before reading any code.

> **The retrain loop has no exit as specified.** Drift fires → retrain → the challenger loses to the
> incumbent on the shared holdout → the gate correctly rejects it → Production is unchanged → drift
> is still there next run → retrain again. Nothing in the design breaks that cycle, and the gate
> doing its job is exactly what sustains it.
>
> Pick one and write it down before implementing: a **cooldown** (no retrain within N hours of a
> rejected one), a **drift acknowledgement** (the firing state is recorded and not re-triggered
> until it clears), or **escalation** (after k rejected retrains, stop retrying and raise an alert).
> All three read their state from the Phase 5 run-history table, which is why that table is a
> requirement rather than a nicety.
> Escalation is the one worth having in an interview: a challenger that repeatedly cannot beat the
> incumbent on drifted data is telling you something a retrain will not fix.

### Phase 7 — Live evaluation & performance-over-time
Real forecasting has delayed actuals: at time t I predict hours t+1…t+H, but
those actuals only arrive later. Every prediction gets persisted (target timestamp
+ model version + value), and when the actual for that timestamp lands, I join the
two and compute realized error. The rolling realized-error series, plotted against a
baseline, is the performance-over-time showcase.

**The baseline has to be source-agnostic, and EIA's `DF` is not.** `config.yaml` exposes
`forecast_type: DF` under `source.eia` only, while `kind: synthetic` is the default and the source
CI and tests must stay on. A phase whose headline deliverable only exists on live EIA data cannot be
tested offline, which breaks hard convention 3. **Primary baseline: seasonal naive** — the value at
$t-168\text{h}$, same hour last week. It needs no extra data, works on any source including
synthetic, and is a genuinely hard baseline for hourly load. **Keep EIA's `DF` as a second baseline
when `kind: eia`**, because beating a real published day-ahead forecast is the better story — it is
just not the one the gate can depend on. This also surfaces the gap between backtest error
(what `train.py` reports on a holdout) and live error on genuinely unseen hours.
Target: a predictions table keyed by (target_ts, model_version) that joins to
actuals to yield realized error.
**Done when:** I can show realized error accumulating over time vs. the seasonal-naive baseline, on
the synthetic source, offline.

**How this gets shared, since there is no orchestrator UI.** A `GET /status` endpoint on the Phase 3
service — current Production version, last N runs from the run-history table, drift state, realized
error. If the VPS is reachable that is a **live URL** for the write-up, which beats a screenshot of
anything. Read-only, and echo nothing from the environment. The stronger artifact is still the
numbers in prose: *"over N nightly runs the gate promoted x challengers and rejected y — here are
the rejections I think were wrong."*

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
- systemd timers → Databricks Jobs / Workflows
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