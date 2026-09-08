# Defect log

Things found wrong in code, config or documents that already exist, filed under **the phase that
fixes them**. Not a backlog of features and not a plan: every entry below is an observed property
of something already in the repo, with the mechanism and the fix stated, so that fixing it is a
task rather than an investigation.

It exists because this repo is built in phases with a fixed box, and a defect found in Phase 1 is
usually cheapest to fix in Phase 1 and most expensive to discover in Phase 7. Filing by fixing
phase — rather than by where the failure shows up — is the whole point of the format. Each entry
names what it **blocks**, which is what stops a cheap fix being deferred into the phase it breaks.

It is also the honest half of the README's *How this was built*. A reader evaluating this code
should be able to see what a review found and what happened next; a repo with no defect log has
either not been reviewed or is not saying.

**Convention.** Add an entry when a review or a failure turns up something concrete. Strike it
through when it is fixed and name the commit. Do not delete entries — the record of what was
wrong is the part worth keeping. Entries are `D<n>`, stable, so a commit can cite one.

*Opened 2026-09-08, from a full read of the source, the tests, the CI run and the container
config.*

---

## Phase 1 — Ingestion + storage

The one implemented module, so these are live rather than latent.

### D1 — The synthetic series is a function of row position, not of timestamp
**Blocks:** the Phase 1 done-criterion, and Phase 7.

`_create_synthetic_data` builds `hours = np.arange(len(timestamps))` and derives the daily term
from `hours % 24`. That index starts at the window's first row, and the window starts at
`now()` floored to the hour minus the backfill, so the daily phase is anchored to **the hour the
job happens to run**. The noise is drawn positionally from the seeded generator, so it moves the
same way. The weekly term is the exception — it reads `timestamps.dayofweek` and is stable — which
is exactly what makes this hard to see: two runs disagree on part of the series and agree on the
rest.

So the same timestamp carries a different value on every run, and the upsert dutifully overwrites
the old one. Hard convention 1 fails on the default source. Worse for the phase's own criterion:
that criterion was deliberately strengthened from "row count unchanged" to *"re-ingesting a
corrected value overwrites it"*, and on this generator a corrected value and a corrupted value are
indistinguishable — the stronger criterion cannot be tested on the source it was written for.

It reaches Phase 7 directly. The realised-error series is computed from stored history; if a
re-ingest rewrites past values, the headline number moves retroactively. On the live source the
values come from the API and this does not bite. On the synthetic source — the default, and what
tests, CI and every offline demonstration use — it does.

**Fix:** derive the daily term from `timestamps.hour`, and make the noise a deterministic function
of the timestamp (seed per row from the epoch hour, or hash the timestamp) rather than of the row
index. The generator should be a pure function of the timestamp and the config, and nothing else.

### D2 — No test pins the property D1 breaks
**Blocks:** D1's fix landing safely.

`test_create_synthetic_data_determinism` calls the generator twice microseconds apart. Both calls
share a `last_hour`, so they agree, and the test passes. It pins reproducibility *within a call
pair*, not value-stability across runs, which is the property that matters.
`test_store_data_idempotency` passes the *same frame* to `store_data` twice: it exercises the SQL
upsert correctly and never touches the composition that fails.

**Fix:** a test that generates over one window, generates again over a different window that
overlaps it, and asserts the overlapping timestamps carry identical values. That is the property
the done-criterion is really asserting, and no current test can fail on it.

### D3 — A failed ingest reports success
**Blocks:** Phase 5.

`ingest()` is annotated `-> None` and returns an `IngestResult`. It catches every exception,
returns a result with `error_occurred=True`, and the `__main__` block discards the return value
and falls off the end — exit code 0. Anything that reads exit codes, which is what a scheduler
does, sees a clean run.

**Fix:** correct the annotation, and exit non-zero from the entry point when `error_occurred` is
set. A timer that cannot see failure has no failure to log, and the log is the Phase 6 exercise.

### D4 — Relative paths are resolved against the process's working directory
**Blocks:** Phase 5.

`ingest()` opens `duckdb.connect(cfg.storage.duckdb_path)` with the raw config string, although
`config.py` provides `abs_path()` for exactly this. `mlflow.tracking_uri: file:./mlruns` has the
same shape. Run from the repo root it works; run from a unit file with a different
`WorkingDirectory` it silently creates a second, empty database beside the real one.

This is the canonical "works in the shell, dies under the timer" failure, and Phase 5 exists partly
to teach it — but it is cheaper to fix here than to diagnose there.

**Fix:** resolve every config-relative path through `Config.abs_path` at the point of use.

### D5 — `store_data` freezes the raw table's schema from the first frame it ever sees
**Blocks:** Phase 7.

`CREATE TABLE IF NOT EXISTS <table> AS SELECT * FROM incoming WHERE 1=0` gives the table whatever
columns the first incoming frame had; every later write is `INSERT INTO <table> SELECT * FROM
incoming`, which is positional. Turning on the TSO forecast column adds a column to the incoming
frame and the insert fails on arity against a table created without it.

The defect is in Phase 1 and it detonates in Phase 7, which is the reason it is filed here: it is
an hour now, against a blocked evening and a populated database to migrate later.

**Fix:** insert by explicit column list, and reconcile the table's columns with the incoming
frame's — add missing columns rather than assuming a match.

### D6 — The upsert is not atomic
**Blocks:** nothing yet; it is a correctness claim the repo makes.

`store_data` issues a DELETE and then an INSERT as two autocommitted statements. A crash between
them removes the overlapping rows and writes nothing back — a strictly worse outcome than not
having run. Hard convention 1 says a job can be re-run "without producing duplicates **or corrupt
state**", and this is the corrupt-state half.

**Fix:** wrap the delete and the insert in one transaction.

### D7 — `load_config` caches across content changes, and resolves the root from the default path
**Blocks:** test isolation.

`@lru_cache` keys on the path argument, so a config whose *contents* change between calls returns
the stale object. Separately, `project_root` is always derived from `_DEFAULT_CONFIG_PATH`, so a
config loaded from somewhere else still resolves its relative paths against the real repo root —
which makes `abs_path` wrong for exactly the case a temporary config exists to create.

**Fix:** derive `project_root` from the path actually loaded, and give the loader a way to bypass
or clear the cache.

### D8 — The tests hardcode the domain
**Blocks:** nothing; it is the convention applied to its own tests.

`test_store_data_consistency` asserts on `stored_data["load_mw"]` where a `target_column_name`
fixture is already in scope. Convention 3 says no module hardcodes the domain, and a test that
does so is a test that will not survive the config being pointed somewhere else — which is the
property the convention exists to protect.

**Fix:** use the fixture.

---

## Phase 2 — Features + training

### D9 — CI is red
**Blocks:** every push, and any pull request to the default branch.

`ruff check .` exits non-zero: one `I001` (unsorted import block) and four `F401`s in
`tests/test_build.py`, for `build_features`, `persist_features`, `_compute_rolling_window` and
`_compute_holiday_feature`. The imports are honest placeholders for tests not yet written, so they
resolve themselves as this phase lands — but until then the required `test` check fails on the
default branch, and a failing required check is indistinguishable from a broken build to anyone
reading the repo.

**Fix:** write the tests, which is the phase. If the phase runs long, the interim option is a
scoped per-file ignore with a comment saying why — never a blanket one, and never by deleting the
imports, which are the phase's own to-do list.

### D10 — `test_compute_lag` will error rather than fail
**Blocks:** the first green run of this phase.

It asserts `lagged_df[f"lag_{lag}"].iloc[lag:] == synthetic_data[target].iloc[:-lag]`. Those are
two Series with different indexes, and pandas raises on comparing them rather than returning
element-wise `False`. So the moment `_compute_lag` returns something real, the test raises a
`ValueError` and the failure says nothing about lags.

**Fix:** compare `.values`, or `reset_index(drop=True)` on both sides.

### D11 — `test_build_features` is a bare `pass`
**Blocks:** trusting the suite.

It reports green under a name that claims the phase's central behaviour is covered. An empty test
is worse than a missing one: a missing test is visible in the count, a passing empty test is not.

**Fix:** implement it, or mark it `xfail`/`skip` with a reason until it is written.

### D12 — Two sources of truth for the MLflow tracking URI
**Blocks:** the first tracked run, and the containerised service agreeing with it.

`config/config.yaml` sets `mlflow.tracking_uri: file:./mlruns`. `docker-compose.yml` sets
`MLFLOW_TRACKING_URI: http://mlflow:5000` on the api service. MLflow reads the environment variable
on its own, so whichever of the two `train.py` honours decides the answer, and the other silently
does nothing: the container can end up writing to a local file store while the tracking service
serves a different one, with no error anywhere.

Convention 3 says config is the only place these choices are made. This is a Phase 2 decision even
though the conflicting value lives in a Phase 4 file, because it is settled the moment the first
tracked run is written.

**Fix:** decide and state it — config wins and the compose variable goes, or the environment wins
and the config key is documented as a default. Either is defensible; having both is not.

---

## Phase 4 — Packaging

### D13 — The Dockerfile pins a build tool to `latest`
**Blocks:** nothing; it contradicts a stated convention.

`COPY --from=ghcr.io/astral-sh/uv:latest` puts an unpinned dependency into the build of a repo
whose first hard convention is reproducibility. The lockfile pins the Python dependencies and the
tool that resolves them floats.

**Fix:** pin a version tag.

### ~~D14 — `docker-compose.yml` promised a Prefect worker~~
**Fixed** in `6262897`. The comment survived the decision to drop Prefect for systemd timers and
told a reader to extend the compose file with a worker that is not part of the design.

### ~~D15 — The documents still named the previous data source~~
**Fixed** in `6262897`. `CLAUDE.md` carried the old source in its status block, in hard convention
3 and in the tech stack, and `BUILD_PLAN.md`'s Phase 1 reasoned about that provider's
row-per-request pagination, which is not the shape of the current one.

---

## Inherited, not restated

- **Phase 5** cannot demonstrate what it is for until **D3** and **D4** are fixed: a scheduler that
  cannot observe failure, pointed at a database that may not be the real one.
- **Phase 7** cannot accumulate a trustworthy history until **D1** and **D5** are fixed: a headline
  that moves retroactively, and a schema that rejects the column the phase adds.

---

## Plan, not code

### D16 — The box's stated rate floor does not reach the finish line
**Blocks:** nothing yet; it is an arithmetic claim in `BUILD_PLAN.md`.

The box is stated as "~95 hours … 8–16 weeks at that rate against a twelve-week term, so the rate is
close to binding". At the bottom of the rate range it is not close: twelve weeks at the lower rate
is 72 hours, against roughly 75 for the finish line alone before the drift-and-retrain phase is
counted. The honest floor for Phases 1–5 plus 7 is nearer 6.5 hrs/wk **sustained**, and running at
the bottom of the range for the whole term does not reach it — it only works if the earlier weeks
run higher.

**Fix:** one sentence in `BUILD_PLAN.md`'s box, replacing "close to binding" with the floor the
arithmetic actually gives. Left to the author, since what counts as binding is a judgement about
the plan rather than a fact about the code.
