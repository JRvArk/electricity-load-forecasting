# CLAUDE.md — electricity-load-forecasting

Instructions for Claude Code. Read this fully before touching anything.
The human-facing learning guide and phase roadmap live in `BUILD_PLAN.md`; defects found by
review, filed by the phase that fixes them, live in `DEFECTS.md` — read the section for the phase
you are working in before planning it.

## Status — read this before planning anything

Parked 2026-09-01, **un-parked 2026-09-07**. **Phase 1 is implemented on the synthetic source**
(the ENTSO-E retrieval path is a stub); **Phase 2 is stubs** — every body in `build.py` is `pass`,
`train.py` likewise, tests about a third written; **Phase 3 is open**; **Phases 4–7 are
unstarted**. That is one module of seven *(status corrected 2026-09-08; the earlier block
overstated it)*. The remaining work is **time-boxed**, at 6–12 hrs/wk, run on an x86-64 Linux VPS
rather than the laptop. **Finishing is a
hard constraint** — scope that threatens it loses, every time. **Phase 9 is cut** (it had no
terminal state and this project needs one); **Phase 8 is deferred**, not dismissed. Reasoning and
the stop rule are in `BUILD_PLAN.md`.

Two consequences for you. **Do not restore Phase 9 or fold it into 4–7**, and do not start
Phase 8. And **do not add a Linux track, reading list or curriculum** — the phases are the
curriculum, and a separate learning track has been explicitly refused.

## Repo boundary — everything here is addressed to a reader who has only this repo

- **Motivation is argued in project terms.** Why a phase exists, why one was cut, why the box is
  ~95 hours — justify it from what the system needs and what an unfinished system costs. Do not
  import reasons from outside the repo: no career targets, employers, courses, or other planning
  documents, and no naming of the places those live. If a reason cannot be stated in terms of this
  codebase, it is not a reason this file should carry.
- **No forward dates.** A date is allowed only as provenance on a decision already taken
  (*"decided 2026-09-07"*). Everything else is expressed as budget, rate and ordering — "~95
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
   on it (they must stay offline and deterministic). Real data (ENTSO-E, `kind: entsoe`)
   is opt-in for live runs.
4. **Promotion is earned.** A retrained model only reaches the `Production` stage
   if it beats the incumbent on a holdout metric. A worse model must never serve.
5. **Type hints everywhere. Tests for every phase before moving on.**

## Your role

Coach on the hand-written modules, implementer on the delegated ones — the split is in
`BUILD_PLAN.md`, *Hand-written or delegated* (decided 2026-09-08). On the hand-written
modules: critique interfaces, review test coverage, explain concepts, help debug failures the
human has already engaged with, and do not write the implementation — that is the point of the
repo. On the delegated ones — Phase 4 configuration, Phase 7 plumbing — implement against tests
the human wrote first, and expect the result to be reviewed against them before merge.

## Where the work happens

The default for this repo is a **Claude Code session, in the repo**. Its problems are
operational and their evidence is output that already exists: a container that won't run on the
target architecture, a unit that works in a shell and dies under the timer, a permissions error
three layers down. A chat window sees only what gets pasted, and pasting is where the
load-bearing detail gets dropped.

Chat is the exception rather than the rule here, and it earns its place on the rare question
whose answer is in the human's understanding rather than in the repo — what a promotion gate is
actually protecting against, why a drift metric behaves the way it does. There are few of those:
this is implementation against interfaces that are already fixed. For the same reason the project
gets no dedicated synced chat project — the substance is code and runtime output, and the parts
worth discussing (`reference/`, `data/`, the journal on the box) are gitignored or not in the repo
at all, so syncing it would share the least useful half.

**Sessions are short and single-purpose.** A long-running one accumulates history irrelevant to
the current problem, pays to carry it every turn, and when its context is compacted it discards
whichever half is not currently hot — usually the half that mattered. Three triggers for starting
a fresh session, and note that none of them is "a phase ended":

- **The files change.** Phase 3's registry work and Phase 4's Dockerfile share nothing, so
  re-reading two files costs less than carrying twenty turns about a different part of the tree.
  Phases 5 and 6 genuinely do overlap — the run-history table feeds loop termination — so those
  can sit in one session, and a single phase can take three.
- **The context compacted.** At that point the fine detail being paid for is already gone, so
  continuing means full price for a summary. Commit, close, reopen.
- **Before the Phase 6 drills.** A session that just wrote the code will be asked what the
  traceback means. Start the drills cold, or with no session at all.

Against all three: **stay in the session while a debug loop is live.** Its whole value is that the
failing output, what was already tried, and why it didn't work are here.

A fresh session opens by *stating* where things are — "Phase 5, the timer fires but the unit exits
203" — not by asking for a survey. That one line is worth ten file reads.

**Two things do not go to a model at all**, because their entire value is in doing them
unassisted:

1. **The `reference/` diff.** A complete independent implementation is a better teacher than a
   conversation, because it is not shaped by how the question was framed. Compare against it
   before asking anything.
2. **The Phase 6 failure drills.** Diagnosing from logs *before touching code* is the whole
   exercise. Asking what a traceback means defects from the one part of this project that is hard
   to acquire anywhere else.

**A chat that settles something produces a commit.** Open decisions B and C land in the register
in `BUILD_PLAN.md`, with the basis stated. If it exists only in a conversation, it is not decided.

Whether this project is worth the time it is taking is not this repo's business — see
*Repo boundary*.

## Tech stack

- Storage: DuckDB + parquet (`data/`)
- Data: synthetic generator (default, offline) | ENTSO-E Transparency Platform API (live,
  decided 2026-09-08 — it replaced a US-only source)
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
                           #   (the Phase 7 predictions table, join and GET /status: delegated)
  monitoring/drift.py      # human implements: drift signal
  orchestration/flows.py   # human implements: plain-Python pipelines, run by systemd timers
tests/                     # human writes tests here, BEFORE implementing — delegated modules too
Dockerfile, docker-compose.yml, .github/workflows/ci.yml   # delegated: Phase 4 configuration
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
