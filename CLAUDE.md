# CLAUDE.md — electricity-load-forecasting

Instructions for Claude Code. Read this fully before touching anything.
The human-facing learning guide and phase roadmap live in `BUILD_PLAN.md`; defects found by
review, filed by the phase that fixes them, live in `DEFECTS.md` — read the section for the phase
you are working in before planning it. Two smaller logs sit alongside them: `REVISIT.md`, for what
is committed and not yet understood, and `LEARNINGS.md`, for mechanisms that had to be got right.
All four are described in *Writing it down*, below. `NEXT_STEPS.md` is not a log: it is the
ordered front of the current pass, at most ten one-line entries, and is where a session finds
what comes first.

## Status — read this before planning anything

**Current phase: 1**, in the pass that fixes D17–D23. Phase 1 runs on the synthetic source; the
ENTSO-E path is written but returns the client's native frame rather than the raw schema
(`DEFECTS.md` D17), so it cannot yet be run. **Phases 2–7 are unstarted** — `build.py` and
`train.py` are stubs with tests about a third written. Built in the order **2 → 3 → 5 → 7 → 4 →
6**; **finished means Phases 1–5 plus 7 with `GET /status` live**. The work is time-boxed at ~95
hours and runs on an x86-64 Linux VPS; **finishing is a hard constraint** — scope that threatens
it loses, every time. **Phase 9 is cut; Phase 8 is deferred**, not dismissed. The reasoning, the
box and the stop rule are in `BUILD_PLAN.md`.

This block states the phase and what is true of the code, nothing finer: what is outstanding is
`DEFECTS.md`, what is in flight is `git log -1`. It is kept current by the session that changes
the status, in the same commit — the human maintains none of it.

Two constraints on you. **Do not restore Phase 9 or fold it into 4–7**, and do not start Phase 8.
And **do not add a Linux track, reading list or curriculum** — the phases are the curriculum, and a
separate learning track has been explicitly refused.

## Repo boundary — everything here is addressed to a reader who has only this repo

- **Motivation is argued in project terms.** Why a phase exists, why one was cut, why the box is
  ~95 hours — justify it from what the system needs and what an unfinished system costs. Do not
  import reasons from outside the repo: no career targets, employers, courses, or other planning
  documents, and no naming of the places those live. If a reason cannot be stated in terms of this
  codebase, it is not a reason this file should carry.
- **Nothing about the person.** What the human does for work, what else they spend their time
  on, what they are aiming at, how they learn — none of it goes in any tracked file, and not in
  memory either. Budget and rate as planning quantities are fine: "~95 hours" and "6–12 hrs/wk"
  describe the project, not the week around it. The line is crossed the moment a sentence is
  about the human rather than about the system.
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

Three working agreements. **A file the human is still writing is a draft**: its collection errors
are not findings, and nothing is filed against it until the human says it is done — when it is
unclear which files are in flight, ask. What a session notices in one goes to *Draft observations*
at the foot of `DEFECTS.md`, unnumbered, so that a `D<n>` stays a claim about finished code; it is
promoted or deleted when the file is called done. The rule protects work in progress, and a
finding routed into a conversation instead is a finding that dies with the window.

**`tests/` is the human's, with two exceptions.** What a test asserts, which cases it carries,
what a fixture provides and at what scope — that is the design thinking rung 3 exists for, and it
stays the human's *even when a log spells the change out*. The session may do exactly two things
there: add or remove a **quarantine** marker, which changes whether a module runs and never what it
checks; and delete something a `DEFECTS.md` entry has already sentenced by name. Both cite the
entry in the same commit. Anything that adds a fixture, changes a scope, or changes an assertion is
the human's — the asymmetry decides it, since the cost of being too strict is two lines they type
anyway, and the cost of being too loose is the exercise the repo exists for.

**Mechanism before code**: open with the mental model and follow with the implementation, not the
reverse.

**Two things are the human's alone, even when asked.** The diff of their implementation against
`reference/` — do not read that directory until they have done the diff themselves and bring a
difference to discuss, since coaching shaped by it pre-empts the one comparison not shaped by how
the question was framed. And the Phase 6 failure drills — a traceback from a drill is diagnosed
from logs by the human before any code is touched, so do not interpret it for them. The reasoning
for both is in `BUILD_PLAN.md`, *Sessions*.

## Sessions — what carries between them, and how one opens

Nothing carries between sessions or machines except the repo. Working copies exist on more than
one machine, with different shells and interpreters, and between them the work lives on the
remote branch. Claude Code's auto-memory is per machine *and* per checkout path, is never read
from inside a repo, and `.claude/` is gitignored on purpose — so nothing load-bearing goes there,
and it is not moved into the tree (that was tried, under `.claude/memory/`, and travelled
nowhere).

A fresh session opens from three reads and no survey: this file; `git log -1`, whose message
says what is in flight by agreement with the human (`BUILD_PLAN.md`, *What a session needs from
you*); and `NEXT_STEPS.md`, the ordered front of the current pass, with the `DEFECTS.md` section
for the current phase behind it for detail. When writing that message: an
`In flight:` line describes committed, unfinished work — never the working tree, which no other
machine can see — and goes on the commit that carries the drafts, which is the last one before a
machine switch, not a mid-session commit of something else. If the human's first message states
where things are, that line wins over all three. If none of it yields the line "Phase N, here is
the state", the gap is in the repo and is closed in the repo. **A claim that something is undecided is
checked against the register before it is acted on or repeated.** Two of those three reads are
pointers: they carry the authority of being read first and none of the durability, and `git log -1`
is immutable besides, so a session's belief that a question is open keeps being asserted long after
the register has settled it. One read of the decision table is cheaper than re-opening a settled
decision — the more expensive mistake, because leaving something unsettled is visible and
re-deciding it looks like work (`LEARNINGS.md` L11). Stay in a session while a debug
loop is live — the failing output and what was already tried are its whole value — and when the
context compacts, say so and suggest commit-close-reopen.

The human hand-maintains nothing here. The status block, the four logs, the decision register and
`NEXT_STEPS.md` are kept current by the session that changes them, in the same commit — a step
landed is a line deleted from `NEXT_STEPS.md` in the commit that lands it. Ask only when a choice
cannot be made from the repo, and then write the answer into the file rather than leaving it in
the conversation — see *Writing it down*.

## Writing it down — immediately, and in the right file

**A session that settles something writes it down in the same turn it is settled** — not at the end
of the session, not when asked, not "once it is implemented", and **without asking permission
first**: write the entry and report it, since removing a paragraph is cheaper than a round trip to
authorise one. Judgement still applies to *whether* an entry is warranted; it does not apply to
whether to ask. Sessions here are short by
design, so nothing carries between them except the repo: a conclusion that lives only in a
conversation is gone when the window closes, and the next session pays to re-derive it or, worse,
decides it differently. The four logs are how context moves between machines and between sessions.

**Write the entry; do not ask whether to write it.** "Settled" means the question has an answer,
not that the answer has been agreed — an assistant that pauses for approval spends a turn on a
summary of the entry rather than on the entry, and the summary is the lossy version of exactly the
thing that was about to be written down. Review happens in the file, where the claim is concrete
enough to disagree with and carries an ID something can cite; a wrong entry gets corrected or
struck through there, which is what the format is for. This applies to all four logs, and to
entries about the human's own code — a defect found is filed, not offered.

Route it by what kind of thing it is:

- **`BUILD_PLAN.md`** — a *decision* and its basis. The register under *Open decisions* carries
  both: open ones in bold, settled ones struck through with the date taken. Phase boxes carry
  implementation guidance that is not itself a decision.
- **`DEFECTS.md`** — something *wrong* in code, config or a document that already exists, filed
  under the phase that fixes it, with the mechanism and the fix stated, and naming what it blocks.
  Strike it through when fixed and name the commit; never delete it.
- **`REVISIT.md`** — something *right* and *not yet understood*, with a pointer to the code and a
  trigger in the build order rather than a date.
- **`LEARNINGS.md`** — a *mechanism* worth carrying, generalised from the episode in this tree
  that forced it. Filed under the phase whose work produced it, so that finishing a phase and
  reading its section answers what building it taught; a **Pays off in** line carries the value
  across to any other phase that needs it.
- **`NEXT_STEPS.md`** — not a log but the *order* of the current pass: at most ten one-line
  entries, each pointing at the entry above that holds its detail, deleted when done. It never
  holds content; an ordering worked out in a conversation goes here in the same turn, for the
  same reason a decision goes in the register. It never says whether something is **decided**
  either: that is the register's word, and a pointer repeating it goes stale where the register
  cannot. The same holds for a commit message, and there it is worse — a commit message can never
  be corrected. Cite the decision and let it speak.

The bar for "settled" is low: if a question was answered and the answer changes what someone does,
it belongs in one of the four — **and an explanation given as coaching counts.** A mechanism the
human asked about and now understands is a `LEARNINGS.md` entry in the same turn; that they
understood it is not the test, because understanding leaves with the window. The test is whether
the next session would have to re-derive it. Then the commit that follows cites the entry — **if it
exists only in a conversation, it is not decided.**

An entry that would need this conversation in order to make sense is not finished. Each one is
written for a reader who has the repo and nothing else, which is the same standard as
*Repo boundary* above — and the reason these files work as the hand-off between one session and
the next.


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
