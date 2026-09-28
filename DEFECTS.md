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

`create_synthetic_data` (now in `ingestion/sources/synthetic.py`; `_create_synthetic_data` when
this was filed) builds `hours = np.arange(len(timestamps))` and derives the daily term
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

*Amended after decision D.* The function still reads none of `entity_ids` and emits no entity
column — one unnamed series, whatever the config lists. Under the long schema it produces one
series **per entity**, and the pure function is of *(timestamp, entity, config)*: the entity has to
enter the value — an offset, or the seed — so that the two configured series **differ**. Two
identical series carry the entity column and still cannot fail a test that mixes them up, which is
the bug decision D's two-entity rule exists to catch.

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

### ~~D3 — A failed ingest reports success~~
**Fixed** in `842f03e`. `ingest()` was annotated `-> None` while returning an `IngestResult`, and
the `__main__` block discarded the result and fell off the end with exit code 0, so a scheduler
saw every failed run as clean. The annotation is now `-> IngestResult` and the entry point exits 1
when `error_occurred` is set. What the result *can* say about a failure is still D22.

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
incoming`, which is positional. Any frame with a column the table lacks fails on arity; any frame
with the same columns in a different order is inserted **silently misaligned**.

*Amended.* The trigger named when this was filed — turning on the TSO forecast column — is no
longer the design: the forecast has its own table (`storage.raw_tso_table`, D26). The live trigger
is nearer: D17 adds the entity column, and the existing `data/forecast.duckdb` was created from a
two-column frame. The first ingest after D17 lands fails on arity against that table, or — if the
database is deleted to get past it — the failure is deferred to the next column Phase 7 adds. So
this is filed in Phase 1 rather than Phase 7 for the same reason as before: an hour now, against a
blocked evening and a populated database to migrate later.

**Fix:** insert by explicit column list, and reconcile the table's columns with the incoming
frame's — add missing columns rather than assuming a match.

### D6 — The upsert is not atomic
**Blocks:** nothing yet; it is a correctness claim the repo makes.

`store_data` issues a DELETE and then an INSERT as two autocommitted statements. A crash between
them removes the overlapping rows and writes nothing back — a strictly worse outcome than not
having run. Hard convention 1 says a job can be re-run "without producing duplicates **or corrupt
state**", and this is the corrupt-state half.

**Fix:** wrap the delete and the insert in one transaction.

### ~~D7 — `load_config` caches across content changes, and resolves the root from the default path~~
**Fixed** in `8b60f21`. `@lru_cache` keyed on the path argument alone, so a config whose *contents*
changed between calls returned the stale object; and `project_root` was always derived from
`_DEFAULT_CONFIG_PATH`, so a config loaded from anywhere else resolved its relative paths against
the real repo root — wrong for exactly the case a temporary config exists to create.

The cache is now keyed on the file's modification time and on the overriding environment as well as
the path, `project_root` derives from the file actually loaded, and `load_config.cache_clear()`
remains available. The unread parameters that carry the key are `REVISIT.md` R1.

### D8 — The tests hardcode the domain
**Blocks:** nothing; it is the convention applied to its own tests.

`test_store_data_consistency` asserts on `stored_data["load_mw"]` where a `target_column_name`
fixture is already in scope. Convention 3 says no module hardcodes the domain, and a test that
does so is a test that will not survive the config being pointed somewhere else — which is the
property the convention exists to protect.

**Fix:** use the fixture.

### D17 — The two source functions do not share a contract
**Blocks:** running on `kind: entsoe` at all, and the Phase 1 done-criterion on the live source.

`_create_synthetic_data` is passed `timestamp_column_name` and `target_column_name` and builds a
frame to fit. `_retrieve_entsoe_data` is passed neither, and returns entsoe-py's native frame: the
timestamp in the **index** rather than a column, one value column named after each area code, and
`{area}_tso_forecast` where the docstring above it promises a single `tso_forecast`. Nothing in
that signature is aware that a raw schema exists, so nothing in it can conform to one.

The mismatch surfaces two functions later. `store_data` inserts positionally, so the first DOUBLE
column is cast into `ts`:

```
Conversion Error: Unimplemented type for cast (DOUBLE -> TIMESTAMP WITH TIME ZONE)
                  when casting from source column 10YNL----------L
```

which names neither the missing column nor the function that owed it. Source-independent schema is
the property Phase 1 exists to establish; it currently holds only because one source has been run.

**Fix:** one signature for every source — the configured column names reach each one, whether as
arguments or as the whole `Config` — and one shared conformance assertion applied to each source in
turn: columns are exactly the configured timestamp, **entity** and target; timestamps are tz-aware
and hourly; and they are strictly increasing with no duplicates **within each entity**.

It is **production code, called by the dispatcher**, not a test helper — a frame goes source →
assertion → `store_data`, on every run. Two reasons it belongs there rather than in the suite. A
test can only fail on the frames the fixtures carry, and a recorded fixture pins what the source
looked like the day it was recorded; the failure this catches is the day it stops looking like that,
which happens on the box. And a check the *dispatcher* owns cannot be skipped by a source added
later, whereas one each source calls for itself has to be remembered — which is the same shape as
the original defect, where nothing in the source's signature was aware a raw schema existed. The
assertion is the part that keeps a third source from drifting the same way; for a live source it
runs against a recorded frame, so CI stays offline. **A violation is fatal** (decision G): it means
the adapter is wrong rather than the world, so no retry helps and the next scheduled run repeats it
exactly. How much of the requested window landed is a separate question and is never fatal — that
is D22's job.

*Amended after decision D.* The clause originally read "the configured timestamp and target", and
monotonicity was stated globally — both written before the schema became long. A long frame stacking
two zones is not globally monotonic, so a bare `is_monotonic_increasing` check rejects a correct
frame; the property is per entity, and the entity column is part of the contract rather than an
extra.

*Status after `842f03e`.* The **signature half is done**: both sources live under
`ingestion/sources/` and take `(cfg, start, end, backfill_days)`, so each can see the configured
column names. The **contract half is not**, and no frame either source produces would pass the
assertion: `synthetic.py` emits timestamp and target with no entity column (D1, amended);
`entsoe.py` still returns the timestamp in the index, names its entity column `entity_id_observed`
by hand rather than reading `cfg.domain.entity_column`, and carries forecast rows (D26). The
assertion is what makes those three failures one error message at the dispatcher instead of a
DuckDB cast error two functions later.

### D18 — A frame without the timestamp column truncates the raw table instead of failing
**Blocks:** hard convention 1, and any history Phase 7 accumulates.

`store_data`'s upsert reads:

```sql
DELETE FROM <table> WHERE <ts> IN(SELECT <ts> FROM incoming)
```

When `incoming` has no such column, the inner `<ts>` does not fail to resolve — DuckDB binds it to
the **outer** table's column as a correlated reference. The subquery then yields the current row's
own timestamp, the predicate is true for every row, and the statement deletes the entire table
without raising. Observed: the raw table went from 72 rows to 0 on the first `kind: entsoe` run,
before the INSERT in D17 errored.

This is the corrupt-state half of convention 1 arriving by a different route than D6, and it is
worse than a crash: the job reports the INSERT's error while the DELETE has already succeeded.

**Fix:** qualify the subquery's column (`incoming.<ts>`), so a frame missing it is a binder error
rather than a truncation, and pin it with a test that calls `store_data` with a frame that lacks
the timestamp column.

### D20 — The upsert keys on the timestamp alone, against a table keyed on (timestamp, entity)
**Blocks:** hard convention 1 on any run carrying a subset of entities, and decision D's long schema.

Decision D makes the raw table long — one row per (timestamp, series), with `domain.entity_column`
naming the key. `store_data` is passed `timestamp_column_name` and nothing else, and deletes on
`WHERE <ts> IN (SELECT <ts> FROM incoming)`. So the key it upserts on is the timestamp, while the
key the table is actually keyed on is the pair.

It is *accidentally* correct while every frame carries every entity: the delete removes all
entities at the overlapping timestamps and the insert puts all of them back. It stops being correct
the first time a frame carries a subset — one zone re-fetched after a failed call, one zone
backfilled further than the others, a source that publishes one entity late. Then the delete removes
every entity's rows at those timestamps and the insert restores only the entity in the frame. The
others are gone, and nothing raises. It would show as a *falling* row count, which is exactly what
the Phase 1 done-criterion watches — so the criterion catches this, but only if a fixture can
express it.

The defect is invisible today because `_create_synthetic_data` produces a single unnamed series with
no entity column at all, so no existing test can express the case. That is the same reason decision D
requires fixtures to carry at least two entities.

**Fix:** pass the entity column alongside the timestamp column and delete on the pair. `IN` over two
columns needs a row constructor or an `EXISTS`/`USING` form rather than a scalar subquery — qualify
its columns while rewriting it (D18), and wrap it with the insert in one transaction (D6). Pin it
with a test that stores two entities, re-stores one of them alone, and asserts the other's rows
survive with their values unchanged. Two documents state the old key and go with the fix: the
README ("upsert on the timestamp key") and `ingest.py`'s docstring ("Key on the timestamp column").

### D21 — The test suite does not collect, behind a CI check that was already red
**Blocks:** every test in the repo, and the Phase 1 pass's own red-to-green.

The config layer landed ahead of the code that reads it, and two of its renames are unmet in the
tests:

- `tests/tests_ingest/test_ingest.py` imports `_DEFAULT_CONFIG_PATH`; `config.py` exports
  `DEFAULT_CONFIG_PATH`. An `ImportError` during collection, so none of that module's tests run.
- `SyntheticCfg` gained `entity_ids: list[str] = Field(min_length=1)` under decision D. Both
  `tests/tests_ingest/test_ingest.py` and `tests/tests_build/test_build.py` construct it by hand
  without one, so those fixtures raise `ValidationError: 1 validation error for SyntheticCfg /
  entity_ids / Field required`.
- The same module carries `load_config_for_test`, which reads the yaml itself and patches
  `storage.duckdb_path` to `:memory:`. It is the stale import's actual home, and it is a second
  loader: it skips the overlay, the environment overrides, `project_root` derivation and the
  `config_path` / `config_overlay` provenance, so what it returns is a `Config` the real loader
  cannot produce — a test passing against it is not evidence about the loader the code uses.
  `FORECASTER_DUCKDB_PATH` is in the override allowlist for exactly this substitution, so the seam
  already existed. Setting it at module scope in `tests/conftest.py`, beside `FORECASTER_CONFIG`,
  also makes reaching the real database impossible rather than merely discouraged. Note that each
  `duckdb.connect(":memory:")` is a separate database, so a test opening two connections wants a
  `tmp_path` file instead.

The part worth keeping is *why it was not noticed*. CI was already failing on **D9**'s `ruff` step,
and a check that is already red cannot report a new breakage — a red build carries one bit, and D9
had already spent it. Locally the suite was not run either: the `dev` extra is not installed in
every working copy, so `pytest` is simply absent on at least one of them. Both halves of the signal
were off at once, which is how a suite stops collecting and nothing says so.

**Fix:** the ingest tests are rewritten in this pass regardless (D17, D20, decision E), so take the
source block from the loaded config rather than constructing `SyntheticCfg` in a fixture — decision
D's two entities already live there, and a fixture that builds its own config is a second place for
the schema to drift. `tests/tests_build/test_build.py` inherits the same change although its phase
has not started. The general form is the reason D9 is worth clearing early: keep the red build at
one cause, or it stops being evidence.

*Status after `842f03e`.* The `_DEFAULT_CONFIG_PATH` import is fixed and `conftest.py` sets
`FORECASTER_CONFIG` at module scope (L2). Still open: `FORECASTER_DUCKDB_PATH` is not set there,
so any test that lets `ingest()` open `cfg.storage.duckdb_path` reaches `data/forecast.duckdb`;
and `test_build.py` now fails collection one rename later — it imports `_create_synthetic_data`
from `ingestion.ingest`, which is `create_synthetic_data` in `ingestion/sources/synthetic.py` with
a `cfg` parameter — while still constructing `SyntheticCfg` without `entity_ids`. The ingest test
module is mid-rewrite; its half of this entry is re-checked when that lands.

*Status, this pass.* Two of the three halves have moved. `FORECASTER_DUCKDB_PATH=":memory:"` is
set beside `FORECASTER_CONFIG` at module scope in `conftest.py` (`0738cc6`), so reaching the real
database is now impossible rather than discouraged. `test_build.py` is **quarantined**, not fixed:
a module-level `pytest.skip(..., allow_module_level=True)` sits above its imports — it has to
precede the failing import, since a module is executed in order to be collected — so the suite
collects and a Phase 2 module no longer aborts the whole run. What that buys is L4's property, one
red cause at a time, so the ingest rewrite's own failures are what the suite is reporting. The skip
is deleted when Phase 2 rewrites the module. This entry stays open on its third half: the pre-L5
fixtures and `load_config_for_test` in `test_ingest.py`.

### D23 — The run window is resolved twice, and inclusively
**Blocks:** decision E, hard convention 1, and testing the window at all.

Two defects in one place, because the second is a consequence of the first.

`create_synthetic_data` and `retrieve_entsoe_data` each resolve `(start, end, backfill_days)` into a
concrete window: the same `if start is None: assert backfill_days is not None; start = now floored
minus N days` block appears in both. Decision E made `[start, end)` the primitive and
`--backfill-days` sugar over it, and sugar resolved independently by every consumer is a rule with
as many implementations as callers. It is also why the window cannot be tested once: there is no
single thing to test.

`create_synthetic_data` then builds its index with `pd.date_range(..., inclusive="both")`. A one-day
window yields **25 rows**, and two adjacent one-day windows both contain the boundary hour:

```
inclusive=both  -> 25 rows, last=2026-03-02 00:00:00+00:00
inclusive=left  -> 24 rows, last=2026-03-01 23:00:00+00:00
adjacent windows overlap at 2026-03-02 00:00:00+00:00
```

Decision E requires half-open precisely so this cannot happen: an hour covered by two windows is an
hour the upsert has to repair on every run, and the repair hides whether the upsert is correct.

Validation is by bare `assert` besides, which `python -O` removes — so the hour-alignment checks are
not present in an optimised interpreter.

**Fix:** one `resolve_window(start, end, backfill_days, now=None) -> tuple[datetime, datetime]`,
called once before dispatch. Sources receive a resolved half-open window and never see
`backfill_days`. `inclusive="left"`. Raise rather than `assert`. The injected `now` is what makes
the sugar testable without depending on the wall clock.

*The window's rows, settled 2026-09-21* (decision E, amended). `backfill_days` is a **duration**,
not a second form, so the rule is: **exactly two of `(start, end, duration)` must be determinable,
with `end` defaulting to now floored to the hour.** Four rows are valid — `(start, end, –)`;
`(start, –, –)` → `[start, now_floor)`; `(–, end, N)` → `[end - N days, end)`; `(–, –, N)` →
`[now_floor - N days, now_floor)`. Three are refused: `(start, end, N)` as **over-determined**,
because `end - start` and `N` can disagree and a silent winner is the defect; `(–, end, –)` as
meaningless (L5); and the empty call.

Three consequences for the implementation. Only the two rows without an `end` read the injected
`now`, so `(–, end, N)` is testable with no clock at all. A window whose `end` lies in the future
is **not** refused — a source asked for it returns nothing, which is coverage 0 rather than a
failure (decision G), and on `kind: entsoe` the day-ahead forecast Phase 7 wants lives exactly
there. And the CLI's mutually exclusive group is the wrong shape either way: it covers
`--start_time` against `--backfill-days` while `--end_time` sits outside it, so it both permits
`(start, end, N)` and cannot be made to express the arity rule. The rule lives in
`resolve_window`, which raises; argparse stays thin over it (L5). `create_synthetic_data` already
resolves `(–, end, N)` the way this settles it — that block still goes, because the defect is
where it lives, not what it computes.

### D22 — `IngestResult` cannot express the gap decision E made it responsible for
**Blocks:** Phase 7's missing-hours signal, and Phase 5's run-history table.

Decision E states that `IngestResult` "records the resolved window alongside the realised extent,
because the gap between requested and landed is the missing-hours signal Phase 7 reads". The model
as filed carried `backfill_days`, `data_start_time` and `data_end_time`, and none of the three
did that job. *(Since `842f03e` it carries `backfill_days` and the requested `start_time` /
`end_time` — each `None` when the other form was used — and the realised-extent fields are gone
rather than fixed, so the object now says even less: nothing about what landed at all. The
analysis below stands; the fix is unchanged.)*

- **`backfill_days` is the sugar, not the primitive.** It cannot express a window that did not end
  at `now()` — which is every re-ingest of a historical range, the case the done-criterion is built
  around. A result that records the sugar cannot say what was actually asked for.
- **`data_start_time` / `data_end_time` are a min and a max**, so a window with a hole in the middle
  is indistinguishable from a complete one. 90 days requested, 88 landed with a two-day gap in
  February, reports the same two timestamps as a clean run. Under decision D's long schema it is
  worse: taken across entities, one complete series hides another that landed nothing.
- **There is no row count**, so the one cheap number that would separate those cases is absent too.

An ingest that silently lands short therefore reports success with plausible-looking fields. That is
the same shape as **D3** — a failure that is legible to the code and invisible to everything
downstream — one level up, in the result object rather than the exit code. It reaches Phase 5 as
well: the run-history table's `status` is meant to be derivable from what a step returns.

The same object flattens the **failure** side too, and decision G is what turns that from a
simplification into a defect. `ingest()` catches a bare `Exception` and sets one boolean, so a dead
network and a non-conformant frame produce the same result with a different string in `message` —
while G separated them on purpose: a failed call is contingent and a retry may fix it, a contract
violation is deterministic and a retry never will. Everything reading the result sees one
undifferentiated error and has to parse prose to recover the distinction. Phase 6's drills begin
from a log line, and this is the log line they would begin from.

**Fix:** carry the resolved window as the half-open pair it is, and a realised extent that a hole
can move — rows written is enough, since expected hours × entities against actual separates a short
window from a complete one without storing the missing hours themselves. And give the conformance
assertion its own exception type, caught separately, so the result records *which* fatal outcome
occurred rather than only that one did.

### D25 — The ENTSO-E adapter passes the variable's name as the token
**Blocks:** any run on `kind: entsoe`, and recording the fixture D17's live-source tests need.

`sources/entsoe.py` constructs `EntsoePandasClient(cfg.source.kind_cfg.api_key_env)`. That field
holds the **name** of the environment variable — `ENTSOE_TOKEN` — by design (`LEARNINGS.md` L1:
config names a secret and never contains it), so the client sends the literal string
`securityToken=ENTSOE_TOKEN` and every call is refused. The failure will present as a
`requests.HTTPError`, which decision G's table maps to "bad token, 5xx, network" — correctly, but
the cause is a missing line here, not a credential.

Before the move to `sources/`, the adapter read a yaml file under `secrets/`. L1 records that
file's migration to the environment and says the code reads the value at the point of use — but
`git log -S"os.environ["` over the ingestion package is empty on every branch: that read was never
committed. L1 is the design; this is the code not yet matching it.

**Fix:** `os.environ[cfg.source.entsoe.api_key_env]` at the point of use, raising a message that
names the variable and never its value when it is absent (L1, practice 5). Pin it with the fake
client D17's exception-mapping tests already need: set the variable with `monkeypatch`, and assert
the client was constructed with the environment's value, not the config's string.

### D26 — The ENTSO-E adapter lands the TSO forecast in the observations frame
**Blocks:** D17's assertion ever passing on the live source, and Phase 7's secondary baseline.

With `include_tso_forecast: true`, `retrieve_entsoe_data` concatenates the rows of
`query_load_forecast` onto the same frame as the actual load, tagging them with a second entity
column, `entity_id_tso_forecast`, while the observations carry `entity_id_observed`. The result has
two half-null entity columns and forecast rows interleaved with observations under one target
column, and it goes to `raw_observations`. `StorageCfg.raw_tso_table` exists precisely so that it
does not: *"a forecast is not an observation, and toggling it must not change the raw table's
schema"*. The config comment beside the flag still says "column", which is the design this code
implemented and the one the storage model replaced.

The defect is separate from D17, which is the shape of a frame, because the fix is a second
**destination**: the assertion can reject this frame, but only a routing decision fixes it.

**Fix:** the source returns the two series separately, each conforming to the same contract —
timestamp, entity, value — and `ingest` upserts the second into `raw_tso_table` through the same
`store_data` and the same (timestamp, entity) key. How the adapter returns two frames is the
human's interface call; that it returns two is not. Fix the config comment in the same commit.

### D27 — Decision E's arity rule does not settle `(start, –, duration)`, and the enumeration stops at seven cells
**Blocks:** step 1's `REFUSED` table — the row is either in it or not, and nothing in the repo says which.

Three flags make eight cells. D23's settled rows name seven: four valid, three refused. The eighth
— a start and a duration, no end — is in neither list, and the criterion it would be derived from
reads two ways:

- **The default counts.** `end` always defaults to now floored, so `(start, –, N)` has three
  determinable quantities and is refused as over-determined, exactly like `(start, end, N)`.
- **Only what is given counts.** `(start, –, N)` gives two, so it resolves to
  `[start, start + N days)` and never reads the clock.

The second reading is the better fit for the amendment's own argument: `(–, end, N)` was admitted
because a duration anchored to a given endpoint needs no clock, and that holds identically at the
other end. Admitting one and refusing the other makes `backfill_days` mean "before `end`" rather
than "the length of the window", which is not what the amendment says it is. But the amendment
does not say, and "exactly two determinable" is genuinely ambiguous once one of the three has a
default.

**Fix:** decide the cell, record it in the register beside E, and state all eight rows here.
Either way the CLI needs no new mechanism: D23 already puts the arity rule in `resolve_window`
and leaves argparse thin over it.

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

*Status.* The four `F401`s are gone — those imports were removed — and the check is still red,
now from the in-flight ingest test rewrite (an `I001` and five `F821`s that resolve when it
lands), with the collection errors in D21 queued behind it. Three causes in sequence, and the
check never transitioned once, which is L4 measured rather than predicted. Still filed here
because the Phase 2 tests are what eventually make it green for a reason rather than by absence.

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

*Amended after decision F.* The mechanism is now decided: the environment may override this one
value, through the allowlisted `FORECASTER_MLFLOW_TRACKING_URI`, which `config.py` writes into the
tree before validation. That leaves two concrete steps. `docker-compose.yml` still sets
`MLFLOW_TRACKING_URI` — MLflow's own variable, which bypasses config entirely — and must set the
allowlisted one instead. And `train.py`, when written, must take the URI from
`cfg.mlflow.tracking_uri` and pass it to `mlflow.set_tracking_uri()` explicitly, never rely on
MLflow reading the environment itself: the override is only visible in a run record if it went
through config.

---

## Phase 4 — Packaging

### D19 — The wheel packages whatever config the working tree held at build time
**Blocks:** Phase 4, and any image built anywhere but CI.

`[tool.hatch.build.targets.wheel.force-include]` copies `config/config.yaml` into the package as
`forecaster/_default_config.yaml`, so that an install which is not a checkout can still find a
config. The copy happens at **build** time and takes the working tree's version, uncommitted edits
included. Observed: with `kind: entsoe` edited into the tree, a locally built wheel packaged
`kind: entsoe` as its default, while the committed config said `synthetic`.

CI builds from a clean checkout, so a released artifact is correct. A wheel built by hand is not,
and nothing says so — the failure is an image that reaches for the network on first run, with the
value that sent it there invisible inside the package rather than in the repo.

The local overlay removes the *reason* to edit the tracked config, so this is now a trap rather
than a live bug. It is filed because the trap survives the mitigation: anyone who edits
`config/config.yaml` for an experiment and builds still ships that edit.

**Fix:** refuse to build from a dirty tree, or assert at image-build time that the packaged config
matches the committed one. Cheapest version is a step in the Phase 4 workflow that fails when
`git status --porcelain config/` is non-empty.

### D13 — The Dockerfile pins a build tool to `latest`
**Blocks:** nothing; it contradicts a stated convention.

`COPY --from=ghcr.io/astral-sh/uv:latest` puts an unpinned dependency into the build of a repo
whose first hard convention is reproducibility. The lockfile pins the Python dependencies and the
tool that resolves them floats. `docker-compose.yml` has the same defect one service over:
`image: ghcr.io/mlflow/mlflow:latest` — and that one is the tracking server, so a floating tag
there can change the registry's behaviour under a promotion gate that was tested against another.

**Fix:** pin a version tag on both.

### D24 — The environment that runs the tests is not the environment that was locked
**Blocks:** nothing yet; it is hard convention 2 applied to the toolchain, and it is a second way
for CI to go red on a commit that changed nothing (L4).

Two gaps with the same shape: the repo states an environment and then tests in a different one.

**The interpreter.** `pyproject.toml` says `requires-python = ">=3.11"` and nothing narrows it — no
`.python-version`, no upper bound. `uv sync` therefore takes whichever compatible interpreter it
finds, and on one working copy that is a managed **3.12**; CI asks `setup-python` for **3.11** and
the Dockerfile is `python:3.11-slim`. Anything 3.12-only — a PEP 695 `type` alias, a quote reused
inside an f-string — passes locally and fails in CI as a syntax error in code that just ran. Found
by reading the venv path in a local traceback (`cpython-3.12.12`) against `ci.yml`.

**The dependency set.** Every working copy installs with `uv sync`, which installs `uv.lock`
exactly. CI installs with `pip install -e ".[dev]"`, which resolves afresh from the ranges in
`pyproject.toml` and never reads the lockfile. So the lockfile — the reproducibility claim the repo
makes about its dependencies — is the one thing CI does not test, and a new pandas or DuckDB
release lands in CI on the morning it is published, on a commit that touched nothing. That is the
D9 failure shape arriving from outside the repo: a red build with no local reproduction.

**Fix:** a `.python-version` naming `3.11`, so `uv`, CI and the image agree on one interpreter —
one file, can land any time. And CI installs through `astral-sh/setup-uv` with
`uv sync --locked --extra dev`, then runs `uv run ruff check .` and `uv run pytest -q`, so what CI
tests is what the lockfile says. `--locked`, not `--frozen`: the first fails when the lock has
fallen behind `pyproject.toml`, the second installs the stale lock without a word — and CI is the
one place a forgotten re-lock should be loud. The four postures are `LEARNINGS.md` L6.

### ~~D14 — `docker-compose.yml` promised a Prefect worker~~
**Fixed** in `6262897`. The comment survived the decision to drop Prefect for systemd timers and
told a reader to extend the compose file with a worker that is not part of the design.

### ~~D15 — The documents still named the previous data source~~
**Fixed** in `6262897`. `CLAUDE.md` carried the old source in its status block, in hard convention
3 and in the tech stack, and `BUILD_PLAN.md`'s Phase 1 reasoned about that provider's
row-per-request pagination, which is not the shape of the current one.

---

## Inherited, not restated

- **Phase 5** cannot demonstrate what it is for until **D4** is fixed (D3, its companion, is
  done): a scheduler pointed at a database that may not be the real one.
- **Phase 7** cannot accumulate a trustworthy history until **D1** and **D5** are fixed: a headline
  that moves retroactively, and a schema that rejects the column the phase adds.

---

## Draft observations — not findings

A file the human is still writing is off-limits for a numbered entry until they call it done
(`CLAUDE.md`, *Your role*). That rule protects work in progress, and it used to route whatever a
session noticed into the conversation — the one place this repo says nothing may live. It lands
here instead.

**No `D<n>` id**, deliberately: an id is stable and citable, and these are notes about code that
is still moving. Each line names the file, the symptom, and the commit whose draft was read. When
the human calls a file done, every line against it is either promoted to a numbered entry or
deleted; a line that survives several passes without being promoted was noise.

*Against the ingestion drafts in `0738cc6`, read 2026-09-21.*

- **`ingest.py`, `__main__`** — `if not any() or sum:` sits above `parse_args`. `any()` with no
  arguments raises `TypeError`, so the entry point dies before parsing and `python -m
  forecaster.ingestion.ingest` cannot run at all. Reads like a leftover from before the mutually
  exclusive group.
- **`ingest.py`, `store_data`** — `data_observations` is bound only inside
  `if include_tso_forecast:`, which is `False` on the synthetic source, so
  `conn.register("incoming", data_observations)` is an `UnboundLocalError` on the default path.
  Separate from the TSO branch slicing the same frame twice, which the commit message names.
- **`ingest.py`, `_assert_conformance`** — two gaps against D17's clauses. Tz-awareness is not
  checked at all. And the per-entity diff is vacuous on a frame with one row per entity: the diff
  series is empty and `.all()` on an empty series is `True`, so the guard passes. The `== expected
  diff` test is otherwise a good economy — it catches non-hourly, duplicates (diff 0) and
  non-monotonic (negative diff) in one comparison.
- **`sources/entsoe.py`** — `data[ts].dt.tz_localize("UTC")` on a column that is already tz-aware
  raises `TypeError: Already tz-aware`. Verified in the installed client: `query_load` ends with
  `df.tz_convert(area.tz)`, so the index it returns carries the *area's* zone, not naive time. The
  conversion wanted is `tz_convert`, and D17's contract wants UTC.

*Against the ingestion drafts as they stand in the working tree, read 2026-09-24.*

- **`ingest.py`, `_resolve_time_window`** — the backfill branch assigns a `datetime` to
  `start_time`, and the next block hands that same name to `_parse_and_validate_time_arg`, whose
  `strptime` raises `TypeError: strptime() argument 1 must be str`. The `--backfill-days` path
  therefore cannot reach a window at all. It is the shape D23's fix dissolves: the function takes
  CLI strings, so parsing and resolution are one step and the already-resolved branch has nowhere
  to go.
- **`ingest.py`, `_parse_and_validate_time_arg`** — the bare `except ValueError` catches the
  on-the-hour `ValueError` raised three lines above it inside the same `try`, and re-labels it
  "Invalid time format", so a well-formed `2026-03-01 10:30:00` is reported as a format error.
  The on-the-hour rule is `resolve_window`'s besides (D23), not the argument parser's.

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
