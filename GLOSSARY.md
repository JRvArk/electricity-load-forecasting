# Glossary

What a word means **in this repo**. Not a syllabus and not a course: an index into the prose the
four logs already contain, so that an entry written for "a reader who has the repo and nothing
else" (`CLAUDE.md`, *Writing it down*) actually meets that bar.

**It lags the repo and never leads it.** Four rules keep it that way:

1. **A term enters only when it is already load-bearing in a tracked file**, and its entry names
   where. Nothing enters because it might be useful later — a term with no anchor is a term this
   project does not yet use, and defining it here would be the separate learning track that has
   been refused.
2. **Defined as used here**, not in general. Where this repo's usage is narrower than the
   industry's, the narrow one is what goes in, because that is the one the files mean.
3. **Two or three sentences.** If a term needs more than that, it needs a `LEARNINGS.md` entry and
   the line here becomes a pointer to it. This file is a lookup, not a second `LEARNINGS.md`.
4. **Alphabetical, not by phase.** Filing by phase serves the question "what did building this
   teach me"; a glossary serves "what does this word mean", and that question arrives in no order.

Kept current by the session that introduces a term, in the same commit — the same rule as the four
logs. A session that uses an unanchored word in a tracked file either anchors it here or picks a
word that needs no entry.

---

**adapter** — the module that translates one source's native output into this repo's raw schema, so
that nothing downstream can tell which source produced a row. `sources/entsoe.py` is one and
`sources/synthetic.py` is the other. That the translation is missing from the first is `DEFECTS.md`
D17; see also D25.

**allowlist** — a closed list of what is permitted, where anything not named is refused. Used in
`config.py` as `_ENV_OVERRIDES`, mapping the two environment variables that may override config to
their key paths; `source.kind` is deliberately absent (decision F). `LEARNINGS.md` L9.

**the box** — the project's ~95-hour time budget, and the constraint that overrides scope arguments.
`BUILD_PLAN.md` states it and the stop rule; `DEFECTS.md` D16 is an arithmetic complaint about its
stated rate floor.

**case table** — the enumeration of input cases and their expected outcomes, written *before* the
function that satisfies them. `NEXT_STEPS.md` step 1 calls for `resolve_window`'s `VALID`/`REFUSED`
tables first, then the function. `LEARNINGS.md` L12 is about when a table earns its own tests
rather than being driven through a caller.

**challenger / incumbent** — the newly trained model and the one currently in `Production`. The
promotion gate compares them on a shared holdout, and a challenger that loses does not serve
(`CLAUDE.md`, convention 4). The pair is why Phase 6's retrain loop needs a termination mechanism
(decision B): a challenger can lose forever.

**conformance** — whether a frame matches the raw schema: the right columns, tz-aware timestamps,
one row per (timestamp, entity) at the configured frequency. Checked by `_assert_conformance`; a
violation is fatal and never retried, because it is deterministic and ours (decision G). The
contract's clauses are `DEFECTS.md` D17.

**contract** — what a unit promises about its inputs, its outputs and its failures, as distinct from
how it keeps the promise. Tests pin the contract; they do not pin the steps, because the steps may
be rewritten without any promise changing (`LEARNINGS.md` L12, practice 4). Decision G is a contract
statement: which conditions are fatal and which are reported.

**coupling** — when a change in one place forces a change in another that had no behavioural reason
to change. A test that names a private helper is coupled to it: renaming the helper breaks a green
test although the program behaves identically. That cost is the whole argument for testing through
the front door by default (`LEARNINGS.md` L12).

**deep merge** — combining two mappings key by key rather than replacing one wholesale, so an
overlay can set one value without restating the rest. `config.py`'s `_deep_merge` merges mappings
and replaces lists and scalars whole, because a half-merged list is never what anyone meant.
`LEARNINGS.md` L9.

**discriminated union** — a set of alternative shapes, each carrying a tag field that says which one
it is, so a validator can pick the right shape from the tag. `SourceCfg` holds every source block
and a `kind` naming one. `LEARNINGS.md` L9 has why every block is held rather than only the named
one.

**done-criterion** — the single observable check that ends a phase, stated before the phase begins.
Phase 1's is: ingesting twice over one window leaves the row count unchanged. `BUILD_PLAN.md`,
*Approach*; the current pass's sits at the head of `NEXT_STEPS.md`.

**draft observation** — a finding against a file the human is still writing, recorded unnumbered at
the foot of `DEFECTS.md` rather than as a `D<n>`. The distinction keeps a `D<n>` a claim about
finished code; a draft observation is promoted or deleted when the file is called done
(`CLAUDE.md`, *Your role*).

**entity** — the series a row belongs to, named by `domain.entity_column`. Adding a zone adds rows,
never columns (decision D). Fixtures must carry at least two entities or nothing entity-aware is
actually exercised.

**entry point** — the command that starts a module as a program, here
`python -m forecaster.<area>.<module>` running the code under `if __name__ == "__main__":`. The
convention is fixed; what sits behind it is the human's to design (`CLAUDE.md`, *How to run*).

**fixture** — a pytest function whose return value a test receives by naming it as a parameter, used
for anything a test *depends on* rather than *chooses*. Its **scope** (`function`, `module`,
`session`) decides how often it is rebuilt and therefore whether state leaks between tests. A
**factory fixture** returns a function instead of a value, so each test can ask for the variant it
needs. `LEARNINGS.md` L8 and L10.

**front door** — the public function a test drives the code through, as opposed to reaching a
private helper directly. Testing through it costs nothing on refactor and is the default;
`LEARNINGS.md` L12 gives the two reasons to go below it.

**guard** — a function whose only job is to refuse input that violates a contract, raising rather
than returning. `_assert_conformance` is one. It uses `raise`, not `assert`, because it states a
rule about the world rather than a claim about our own code — `LEARNINGS.md` L7.

**half-open window** — a range `[start, end)` that includes its start and excludes its end, so
consecutive windows abut without overlapping or gapping. It is ingestion's primitive (decision E),
and the reason a 24-hour window holds exactly 24 hourly rows.

**holdout** — data withheld from training and used to judge a model, shared between incumbent and
challenger so the comparison means something. `CLAUDE.md` convention 4; the config validates that it
covers the forecast horizon.

**idempotent** — re-running a job on the same inputs leaves the same state, with no duplicates and
no corruption. `CLAUDE.md` convention 1, and Phase 1's done-criterion is the test of it. Achieved in
`store_data` by upsert rather than append.

**long schema** — one row per (timestamp, series) with a column naming the series, as opposed to one
column per series. Decision D: adding a zone adds rows, so no schema migration follows a new entity,
and `build.py` needs a `groupby` from the start rather than a rewrite later.

**module boundary** — the line between what a module promises to callers and what is private to it,
marked by convention with a leading underscore. The underscore governs who may *call* a function,
not who may *observe* one: a test inside the boundary is entitled to look (`LEARNINGS.md` L12).

**overlay** — a gitignored file whose values are merged over the tracked config, holding *what this
machine points at* while the tracked file holds *what the system is*. `config/local.yaml`;
`LEARNINGS.md` L9 has the three-layer scheme and why naming a config skips the overlay.

**parametrize** — pytest's decorator for running one test body against several inputs, each reported
as its own case. Use it for what a test *chooses*; use a fixture for what it *depends on*.
`LEARNINGS.md` L8.

**pointer / authority** — a file that helps you find a thing (`NEXT_STEPS.md`, a commit message)
versus the file that owns it (the decision register, `DEFECTS.md`). A pointer goes stale and the
thing it points at does not, so a claim read in a pointer is checked against the authority before it
is acted on. `LEARNINGS.md` L11.

**primitive / sugar** — the general form an interface is actually built on, and the convenient
shorthand that resolves to it. In ingestion the half-open window is the primitive and
`--backfill-days N` is sugar over it (decision E). Sugar that cannot express the primitive is a
design error, which is what decision E was taken to prevent.

**promotion gate** — the check a retrained model must pass on the shared holdout before it reaches
the `Production` stage. `CLAUDE.md` convention 4: a worse model must never serve. It is a predicate
with a case table, which makes it the kind of unit `LEARNINGS.md` L12 says to test directly.

**provenance** — a date recorded on a decision already taken (*"decided 2026-09-07"*), which is the
only use of a date this repo allows. Everything forward-looking is expressed as budget, rate and
ordering instead (`CLAUDE.md`, *No forward dates*).

**quarantine** — a pytest marker that stops a test module from running without changing what it
asserts. One of exactly two things a session may do inside `tests/`, and it cites the `DEFECTS.md`
entry that sentenced it in the same commit (`CLAUDE.md`, *Your role*).

**raw schema** — the shape of the raw table, identical no matter which source produced the rows:
`domain.timestamp_column`, `domain.target_column`, `domain.entity_column`, long, tz-aware, at
`domain.frequency`. It is what an adapter translates into and what a conformance guard refuses
violations of.

**rung 3** — the working level this repo is built at: the target properties are given, and the
interface, the tests and the implementation are the human's, with `reference/` diffed only
afterwards. The loop is in `BUILD_PLAN.md`, *Approach*, and repeated in each module's docstring;
which modules run at this level and which are delegated is *Hand-written or delegated*.

**stub** — a module that exists with its docstring and target properties and no implementation, so
that the interface question is posed before the code is written. `build.py` and `train.py` are stubs
(`CLAUDE.md`, *Status*).

**upsert** — insert a row, or replace the existing one with the same key, in a single operation, so
that re-running cannot duplicate. `store_data` does it as delete-then-insert on the overlapping
keys. That the key must be `(timestamp, entity)` rather than the timestamp alone is `DEFECTS.md`
D18 and D20.
