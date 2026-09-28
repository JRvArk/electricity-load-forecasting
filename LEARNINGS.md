# Learnings

Mechanisms this project had to get right, written down once, in general terms, from the specific
episode that forced them.

It is the counterpart to `REVISIT.md`. That file holds what is committed and not yet understood;
this one holds what *is* understood and is worth carrying — the reasoning that would otherwise
survive only as a line of code whose motivation is invisible six weeks later. A subject moves from
one file to the other by being explained.

**Scope.** Every entry begins with something that happened in this tree: a command that was run, a
defect that was found, a decision that was taken. The generalisation at the end of an entry has to
be earned by that episode. This is not a syllabus and not a reading list — the phases are the
curriculum, and a separate learning track has been refused. An entry that could have been written
without this repo existing does not belong here.

**Convention.** Entries are `L<n>`, stable, and each states **what happened**, **the mechanism**,
and **the practice** that generalises. Entries are not struck through: unlike a defect or an open
question, a learning has no terminal state.

**Filed by the phase whose work produced it** — not by the phase it is most useful in. The point of
the grouping is that finishing a phase and reading its section answers "what did building this
teach me", which is a question about where you were, not where the knowledge later applies. Where an
entry pays off somewhere else, it says so in a **Pays off in** line, so the cross-phase value is not
lost to the filing. Sections appear as entries arrive; a phase with nothing under it has no heading
rather than an empty one. Numbering runs across the whole file, so an entry keeps its id wherever it
sits.

---

## Phase 1 — Ingestion + storage

The live source arrives here, which is what makes a credential and a test suite that must stay
offline both Phase 1 problems rather than later ones.

### L1 — File modes, and where a credential lives
**Pays off in:** Phase 4 and Phase 5. A container and a systemd unit both hand a
process environment variables and neither hands it a file at a fixed path.

#### What happened

The ENTSO-E API key was kept at `secrets/secrets.yaml` inside the repo, read by path in
`ingest.py`, and protected by a `.gitignore` rule added after the file already existed. It was
mode `644`. Checking `git log --all -S` confirmed it had never been committed, so nothing needed
rotating; the design had simply been relying on luck.

It was migrated to `~/.config/forecaster/env`, mode `600` in a directory of mode `700`, and the
repo copy deleted. `config/config.yaml` names the variable — `source.entsoe.api_key_env:
ENTSOE_TOKEN` — and the code reads the value from the environment at the point of use.

*Correction.* That last clause described the design, not the tree: the environment read was never
committed, and the adapter as moved to `sources/entsoe.py` passes the variable's *name* to the
client — `DEFECTS.md` D25. The mechanism below is unchanged; what it shows is that a migration
done in a working copy and described in a log is not the same as one that landed, and the
check is `git log -S` on the tree, not the memory of having done it.

#### The mechanism: what 600 and 700 mean

A Unix file has three sets of permissions — **owner**, **group**, **everyone else** — and each set
is three bits: read (4), write (2), execute (1), summed into one octal digit. The leading `0` is
just octal notation.

```
600  ->  6 0 0  ->  rw- --- ---  ->  -rw-------
700  ->  7 0 0  ->  rwx --- ---  ->  drwx------
644  ->  6 4 4  ->  rw- r-- r--  ->  -rw-r--r--   (what the repo copy was)
```

So `600` is "the owner may read and write it; nobody else may do anything". `644` is the default
for a newly created file on most systems, and the last two digits are the problem: every other
account on the machine could read that key.

On a **directory** the bits mean something different, which is the part worth internalising:

- **read** on a directory means *list the names inside it*
- **execute** means *traverse it* — resolve a path through it to reach something inside
- so `700` is the directory equivalent of `600`: the owner can list and enter, nobody else can do
  either. A directory with `600` would be listable and useless, because nothing inside could be
  opened.

Two related mechanisms that matter in practice:

- **`umask`** subtracts bits from the mode a program requests at creation time. It is why files
  usually land at `644` rather than `666`.
- **Creating with the mode, rather than fixing it afterwards.** The migration used
  `os.open(path, O_WRONLY|O_CREAT|O_EXCL, 0o600)`, not "write the file, then `chmod` it". Between
  those two steps the file exists and is world-readable, and a secret written into that window has
  already been exposed. `O_EXCL` additionally makes the call fail rather than clobber an existing
  file.

#### The mechanism: how the key reaches the code

Four steps, each of which can be checked independently:

1. **The config names the variable, and never holds the value.**
   `source.entsoe.api_key_env: ENTSOE_TOKEN`.
2. **The value lives in a file outside the tree**, `~/.config/forecaster/env`, as
   `ENTSOE_TOKEN=...`, mode `600`.
3. **A shell loads it into the environment.** `set -a` makes every subsequent assignment exported,
   so `set -a; . ~/.config/forecaster/env; set +a` turns the file's lines into environment
   variables and then stops the auto-export.
4. **The code reads it at the point of use**, `os.environ[cfg.source.entsoe.api_key_env]`, and
   passes it straight to the client. It never becomes a field on a config object.

Step 4 is the one carrying the weight here. `IngestResult` embeds a whole source-config object and
is destined for a persisted run history; MLflow logs params; logs print config. Had the key been a
config *field*, all three would contain it. Because config holds only the name, a full
`model_dump_json()` contains `'api_key_env': 'ENTSOE_TOKEN'` and nothing else.

#### What an environment variable does not protect against

Worth stating, because "it's in an env var" gets treated as a conclusion:

- `/proc/<pid>/environ` exposes it to the same user, and to root.
- **Every child process inherits it.**
- Anything that dumps `os.environ`, interpolates it into a URL, or includes it in an exception
  message leaks it into logs.
- Exporting it by hand puts it in shell history — which is why it lives in a file that is sourced,
  not in a command that is typed.
- **A recorded HTTP interaction captures it.** `entsoe-py` passes the key as a query parameter —
  `securityToken` in `_base_request`'s params — so a saved request URL, a VCR-style cassette, or a
  debug log of the call *is* the credential, committed. Record responses, never requests; scrub the
  URL if the recording format carries one. This matters here because keeping CI offline means
  recording a live response once (`DEFECTS.md` D17), which is precisely the moment the trap is set.
- Loading it from a shell profile puts it in the environment of *every* process started on that
  machine. Loading it per-session keeps the blast radius to that shell and its children.
- **A validation error echoes its input.** pydantic renders `input_value='…'` into every
  `ValidationError`, so a token pasted into `api_key_env` — the likeliest mistake in a field that
  names a variable — would be printed by the very error meant to refuse it. `config.py` sets
  `hide_input_in_errors=True` on the **top-level** model: a nested model's setting is ignored,
  because the error is rendered with the config of the model that was *called*. That scrubs every
  rendered form — `str`, `repr`, a traceback, a log line — but not the structured ones:
  `err.errors()` and `err.json()` still carry the input unless called with `include_input=False`.
  A run record or a JSON log that serialises a validation error has to pass that flag. Pinned in
  `tests/tests_config`, both halves.

The property achieved is "not in the repo, not in any dump, not in any artifact" — not "safe from
someone with a shell on the box".

#### The practice

1. **Config names secrets; it never contains them.** The indirection is what makes leaking one
   structurally impossible rather than a thing to remember.
2. **Secrets live outside the source tree.** A `.gitignore` rule is a mitigation, not a design —
   it protects a file that should not have been there.
3. **Create with the restrictive mode atomically**, never write-then-`chmod`.
4. **Read at the point of use.** A credential that never enters a long-lived object cannot be
   serialised out of one.
5. **Fail loudly, naming the variable and never the value**, when it is missing.
6. **Pick the one mechanism that exists in every environment.** A file at a fixed path exists on a
   laptop and nowhere else; systemd's `EnvironmentFile=`, a container's `--env` and a cluster's
   secret store all produce environment variables, so code that reads the environment moves
   without changes.
7. **"Never committed" is a claim to check, not to assume** — `git log --all -S'<fragment>'`. If it
   ever was committed, rewriting history does not recall the clones that already have it: rotate
   the credential instead.


### L2 — Where setup runs decides whether it runs in time
**Pays off in:** Phase 3. `uvicorn forecaster.serving.app:app` needs a module-level `app`, so
that module resolves config at import — the case an autouse fixture cannot reach.

#### What happened

`config/local.yaml` is merged over the tracked config whenever a bare `load_config()` resolves the
default path, which is right for a working copy and wrong for a test suite: every test would
inherit whichever source that machine happened to be pointed at. The insulation is one line setting
`$FORECASTER_CONFIG`, because a named config skips the overlay.

The question was where to put that line — and the first instinct, an `autouse` session fixture, is
too late.

#### The mechanism

pytest imports `conftest.py` during **collection**, before it imports any test module. Fixtures, by
contrast, run after collection, immediately around the tests that use them. So module-level code in
a `conftest.py` is the only thing that is guaranteed to have run before a test module's `import`
statements execute.

That matters whenever importing the code under test has a side effect. It does here: `uvicorn
forecaster.serving.app:app` requires a module-level `app` object, so building it will resolve
configuration at import time. A test that does `from forecaster.serving.app import app` reads the
config before a single fixture has run, and an autouse fixture setting the environment would have
missed it — producing a failure whose cause is a file the test never mentions.

Two smaller facts from the same corner:

- **Tests in a `conftest.py` are not collected.** A `test_` function there is silently never run —
  no error, no warning. Renaming a test module to `conftest.py` deletes its coverage.
- **Fixtures resolve by name, nearest first, and a shadowed one is not an error.** Two files
  disagreeing about what `cfg` means is legal and silent, which is the same failure shape.

#### The practice

1. **Ask when setup runs, not just whether it runs.** Import-time side effects need import-time
   setup; a fixture is not early enough, and the symptom is a failure that points at the wrong file.
2. **Put process-wide environment setup at module scope in the topmost `conftest.py`**, so no
   subdirectory can be added later that forgets it.
3. **`autouse` is for side effects, not for values.** A fixture whose return nobody requests is
   either doing nothing or doing something hidden.
4. **Insulate the suite from developer-local state explicitly.** Anything gitignored — an overlay, a
   credential, a database — is state CI does not have, so a test that reads it passes for different
   reasons on different machines.


### L3 — A memo is only correct if its key names everything the answer depends on
**Pays off in:** Phase 3. A `uvicorn` process is long-lived, so what the cache does with an edited
config stops being a detail and becomes an operational property.

#### What happened

`load_config` was memoised with `@lru_cache(maxsize=1)` on the path argument. Its result depends on
much more than the path — the bytes in the file, an optional overlay beside it, and a handful of
environment variables — so a config edited between two calls returned the object built from the
previous contents. That was `DEFECTS.md` D7, and it is invisible: every call still returns a valid
`Config`, just the wrong one.

#### The mechanism

`lru_cache` keys on the arguments and on nothing else. It cannot see a file, a clock, or an
environment. So the fix is not a cleverer cache; it is to make the function's arguments name every
input, and let a wrapper compute them:

```python
def load_config(path=None):                      # not cached
    ...
    return _load_config_cached(                  # cached
        cfg_path, overlay, cfg_path.stat().st_mtime_ns,
        overlay.stat().st_mtime_ns if overlay else 0, _env_snapshot(),
    )
```

Three of those five are never read in the body. They exist to be part of the key.

Observed, with `cache_info()` after each call:

```
two calls, same args      -> hits=1, misses=1, currsize=1   same object: True
a different path          -> hits=1, misses=2, currsize=2
same path, env changed    -> hits=1, misses=3, currsize=3
env changed again         -> hits=1, misses=4, currsize=4
env removed -> back to a  -> hits=2, misses=4, currsize=4   same object as first: True
file edited               -> hits=2, misses=5, currsize=5
```

Four properties worth taking from that:

- **Invalidation is non-match, not eviction.** A changed file does not clear anything; it produces a
  different key that misses. The old entry stays.
- **So entries can be re-matched.** Line five removed an environment variable, which returned the key
  to its earlier value — the call hit and returned the *identical object* from line one. A memo
  whose key goes back is a memo that comes back.
- **`maxsize` bounds the accumulation**, and eviction costs a re-parse and nothing else.
- **`st_mtime_ns` rather than a content hash** is deliberate: `stat()` is cheap enough to do on every
  call, and reading the file to hash it would defeat the point. Nanosecond resolution avoids the
  one-second-granularity collision. The honest gap is a tool that rewrites content while preserving
  mtime — some restores, `rsync` without `--checksum` — which this cache cannot see.

#### The consequence nobody asks about until it bites

Because mtime is in the key, a **long-running** process picks up an edited config on its next call,
with no restart. For a scheduled job that exits between runs this is irrelevant. For the Phase 3
serving process it is a behaviour change mid-flight: a model is loaded against one config and the
next request may resolve a different one. That is a property to decide about, not a bug — a serving
process may well want configuration to be fixed at startup and to require a restart, which means
reading the config once at import rather than calling `load_config()` per request.

#### The practice

1. **Write down what the answer depends on, then check the key contains all of it.** Path, file
   contents, environment, and anything else outside the arguments. A memo keyed on a subset is not a
   cache; it is a stale-value generator with good performance numbers.
2. **Prefer a cheap proxy for "has it changed" over the real thing**, as long as the proxy is
   honest about what it misses — `stat()` over hashing — and state the gap where the code is.
3. **Keep the cached function private and the wrapper public.** The wrapper is where inputs get
   collected; a caller reaching the cached function directly can pass a mismatched key and get a
   wrong answer with no error.
4. **Decide explicitly whether a long-lived process should see configuration change under it.**
   Picking it up automatically and requiring a restart are both defensible; not having chosen is not.
5. **Shared cached objects should be immutable.** One caller mutating a memoised value corrupts it
   for every later caller in the process — which is why `Config` is frozen.


### L4 — A check that is already failing cannot report a new failure
**Pays off in:** Phase 4, where CI becomes the thing the repo asks a reader to trust, and Phase 6,
where a threshold has to be chosen that can still move.

#### What happened

The test suite stopped collecting — a stale import after a rename, plus fixtures constructing a
model that had gained a required field — and nothing said so. Both detectors were dark at once, for
unrelated reasons:

- **CI was already red** on `ruff`, filed as D9 and left open. The run had been failing for several
  commits, so the build going from failing-for-one-reason to failing-for-three changed nothing
  anybody could see.
- **Locally the suite was not run**, because the `dev` extra is not installed in every working copy,
  so `pytest` is simply absent on at least one machine.

#### The mechanism

A pass/fail check carries **one bit**. Its information is in the *transition*, not the level: red
tells you something is wrong only if it was green the moment before. Once a check is red for a known
reason, every further breakage arrives into a state that already looks the same, and the check has
stopped being an instrument — it is now a label.

This is why "we know about that failure, ignore it" is a more expensive decision than it sounds. The
cost is not the one known defect; it is every *unknown* defect the check can no longer report, for
as long as it stays red. A known-failing check has to be fixed, or removed, or split so the rest of
it still carries signal — leaving it red and remembered is the one option that silently disables it.

The same shape appears wherever a signal saturates: a log line that always appears, an alert that
fires every day, a threshold set where it trips constantly. In each case the reader adapts, and the
adaptation is indistinguishable from the signal being switched off.

#### Where it bites next, in this repo

`monitoring.drift_threshold` is a placeholder of `0.5`, and open decision **C** asks for a value
with a stated basis. That is this mechanism in its predictive form: most features here are
transforms of one series, so they drift together, and a threshold that most windows exceed produces
a retrain trigger that fires constantly — which is a saturated signal, not a sensitive one. The
threshold has to be chosen so that tripping remains *informative*, which is a stronger requirement
than it being defensible.

#### The practice

1. **Treat a red check as an outage of the check**, not as a known-failing test. Fix, delete, or
   quarantine it so the remainder still transitions.
2. **Count your independent detectors, and assume they fail independently.** Two were meant to cover
   this — CI and a local run — and neither was working, for reasons that had nothing to do with each
   other. Two detectors are only two if you know both are live.
3. **Prefer a check that can go green.** A check that has never passed in this working copy carries
   no information about anything, and the absence of a baseline hides that.
4. **When choosing a threshold, ask what fraction of normal operation trips it** before asking
   whether the value is defensible. A signal that is usually on is off.


### L5 — Dependent parameters belong to one function, not to every caller
**Pays off in:** Phase 5, where a unit file passes a window on the command line, and Phase 7, which
reads the window back out of run history.

#### What happened

Ingestion takes `start`, `end` and `backfill_days`, and they are not independent: `[start, end)` is
the primitive and `--backfill-days N` is sugar meaning `end = now floored to the hour`, `start = end
- N days`. The two forms are mutually exclusive, `end` alone is meaningless, and neither form may be
absent. *(That is decision E as it stood when this was written; E has since been amended and its
current rows are in the register and in D23. The mechanism below does not depend on which rows are
valid — only on there being a table of them.)*

The question that surfaced this was how to parametrise a test across their combinations. The honest
answer was that the test was hard to write because the code was wrong: both source modules resolved
the window themselves, so the rule had two implementations and no single subject to test.

#### The mechanism

**Stacked `@pytest.mark.parametrize` decorators produce a cartesian product.** Three parameters over
three values each is twenty-seven cases, and when the parameters are dependent, most of those cells
are not scenarios — they are impossible states. A suite full of impossible states is worse than a
small one: it is slow, it is unreadable, and its size reads as thoroughness.

The count is the trap. Twenty-seven passing cases feels like coverage; it is one rule exercised
twenty-seven times in nearby ways, while the cases that actually break the rule — a window spanning
a daylight-saving transition, a naive timestamp against a tz-aware store, `N = 0` — are absent
unless somebody thought of them. **Cases are chosen, not generated.**

So when parameters are dependent, the unit of parametrisation is the *scenario*, not the variable:
one `parametrize` over whole input tuples with `pytest.param(..., id="...")` for readable names, and
a second table for inputs that must raise. And the structural half matters more than the test half —
a rule about how parameters relate is a function. Extracted, it is pure, its entire behaviour is a
small table, and every caller downstream takes the resolved value and cannot disagree about it.

Two mechanical notes from the same corner:

- **A fixture cannot be parametrised with `@pytest.mark.parametrize`.** Marks apply to tests. A
  fixture varies through `@pytest.fixture(params=[...])` and `request.param`, or by a test
  parametrising it with `indirect=True`.
- **A function that reads the clock cannot be tested without owning the clock.** `now` as an
  injectable parameter turns "the sugar resolves against now" from a flaky assertion into a
  deterministic one.

#### A worked instance of "chosen, not generated": the two timezone rows

The window's value checks — tz-aware, on the hour, `start < end` — look like they are about
absence and arithmetic. Two rows that no product would contain show that one of them is about
*representation*:

- `2026-03-29 03:00+02:00` — Amsterdam, just after the spring clock change — is a **valid** input
  and must come back as `01:00Z`. It pins that the resolver *normalises* to UTC rather than merely
  tolerating an aware offset, which is a different property from "refuses naive".
- `2026-03-01 10:00+05:30` is on the hour in its own zone and **half past** in UTC, so it belongs
  in the refused table. "On the hour" is only invariant across timezones whose offset is a whole
  number of hours; `+05:30`, `+05:45` and `+08:45` exist, and so did fractional historical offsets.

The second row decides an *order of operations* inside the function: convert to UTC first, check
the hour second. Checked the other way round, the `+05:30` input passes and the store receives a
timestamp at `04:30Z` — no error anywhere, and D17's hourly check downstream is the first thing to
notice, one function too late to say why. That is the pattern to look for when choosing cases:
a property that seems intrinsic to a value but actually depends on how the value is written down
is a property whose check has a *correct position* relative to the normalisation, and one row on
each side of that position is what pins it.

#### A worked instance of stating the rule: the eighth cell

Decision E's amendment stated the rule as a count — *exactly two of `(start, end, duration)` must
be determinable, with `end` defaulting to now* — and the count left one cell of eight in neither
list (D27). `(start, –, N)` gives two and has three determinable, and the sentence does not say
which it counts. Underneath is a question every default raises once a rule counts parameters: is
the default a **value**, which counts, or a **fallback**, consulted only when what was given falls
short? Both are coherent, and a count cannot say which it means — its reader picks one without
noticing there was a choice.

It was settled as a value (E, amended 2026-09-28), and the useful move was the restatement that
allowed: *exactly one of `start` and `duration`, with `end` optional*. That sentence contains no
count, so there is no cell it cannot place, and it exposed something the count had hidden: the
CLI's required mutually exclusive group over `--start_time` and `--backfill-days` already was that
rule, cell for cell, while D23 said it could not be made to express it. That does not make argparse
the place for the rule — `ingest()` has callers argparse never sees, which is the rest of this
entry — but exclusion and optionality can be checked against a parser, a case table and a
docstring by reading them, where a count has to be enumerated first.

The tie-break between the two readings generalises too. Refusing an input no caller needs is the
reversible side: admitting it later breaks nobody, and refusing it later breaks whoever came to
rely on it.

#### The practice

1. **If a test is awkward to parametrise, suspect the design before the test.** Awkwardness usually
   means the rule under test does not live anywhere in particular.
2. **Extract the relationship between dependent parameters into one function**, and let everything
   downstream take the resolved value. Duplicated resolution is duplicated rules.
3. **Parametrise over scenarios, and name them.** `ids` are what make a failure readable in the run
   output.
4. **Keep the invalid cases in their own table**, asserting the error rather than the result. They
   are the half that documents what the interface refuses.
5. **Assert invariants, not literals**, where the invariant is the actual requirement: `end - start
   == timedelta(days=n)`, `end.minute == 0`, `start < end`.
6. **Choose the hard cases deliberately** — boundaries, transitions, zero, and the forms the
   interface is supposed to reject. Nothing about a parameter matrix will find them for you.
7. **When a property depends on representation, put one case on each side of the normalisation.**
   An aware non-UTC input that must come back as UTC, and one whose "on the hour" survives only in
   its own zone: together they fix where the check sits, not just that it exists.
8. **State a rule over dependent parameters as exclusion and optionality**, not as a count of how
   many must be present. A count is ambiguous the moment one parameter has a default; "exactly one
   of these two, that one optional" is not, and it maps onto a parser and a case table directly.
9. **Between admitting and refusing an input no caller needs, refuse.** Widening an interface is
   compatible and narrowing it is not, so the refusal is the decision that can still be revisited.


### L6 — A lockfile pins only the paths that read it
**Pays off in:** Phase 4, where CI and the image become what the repo asks a reader to trust, and
Phase 5, where the unit on the box is a fourth environment built by a fourth path.

#### What happened

A local pytest traceback named the interpreter it ran under — a `uv`-managed **3.12** — and
`ci.yml` asks `setup-python` for **3.11**. Reading on: CI installs with `pip install -e ".[dev]"`,
which resolves from the version ranges in `pyproject.toml`, while every working copy installs with
`uv sync`, which installs `uv.lock` exactly. So the two greens the repo relies on — "passes here"
and "passes in CI" — were claims about two different environments, and the lockfile, the artifact
that exists to make them one environment, was read by one of them. Filed as `DEFECTS.md` D24.

Nothing had broken. That is the point: the gap is invisible until a dependency releases or a
3.12-only construct gets written, and then the failure arrives on a commit that changed nothing,
with no local reproduction.

#### The mechanism

An environment is not something a repo *has*; it is the output of a **path** — an installer,
reading some spec, on some interpreter. This repo has four such paths: a working copy, the CI job,
the image build, and eventually the scheduled unit. "Reproducible" is a property of the set, and
the set is as pinned as its least-pinned member. A lockfile that one path reads and another ignores
has pinned one machine.

Two distinct things need pinning, and a lockfile does only one of them. It resolves the
**packages** — for the whole `requires-python` range, so it is equally valid on 3.11 and 3.12 and
says nothing about which one runs. The **interpreter** is pinned separately (`.python-version`) or
not at all.

And the paths that do read the lockfile can hold it in different postures, which only differ in
the case that matters — someone edited `pyproject.toml` and did not re-lock:

| posture | with a stale lock | belongs in |
|---|---|---|
| **ignore** — `pip install -e .` | never sees it; resolves from ranges | nowhere the lock is the claim |
| **trust** — `uv sync --frozen` | installs it silently; the environment lags the spec | an image build that copied the lock in and should build exactly that |
| **verify** — `uv sync --locked` | **fails**, naming the lock as stale | CI — the one place a forgotten re-lock should be loud |
| **re-lock** — bare `uv sync` | re-resolves and rewrites the lock | a working copy, where re-locking is the intended act |

The failure shape when this is wrong is L4's: a check that transitions for a reason that is not
the code. A red CI run on a docs-only commit is the environment moving under the check, and the
first question is which path built it, not what the commit changed.

#### The practice

1. **Enumerate the paths that build an environment** — laptop, CI, image, box — and check that
   each reads the same pin. Reproducibility is the minimum over that list, not the best case.
2. **Pin the interpreter and the packages separately**; the lockfile only does the second.
3. **Choose the posture per path deliberately.** Verify in CI, trust in an image build, re-lock on
   a working copy. A stale lock should fail exactly once, in CI, and never be installed silently or
   rewritten silently anywhere a human is not watching.
4. **Two greens in two environments are two claims.** They compose into one guarantee only when the
   environments are the same, and the evidence for that is the pin, not the greens.
5. **A red on a commit that changed nothing is an environment question first** — the same order as
   the Phase 6 drills: rule out the world before reading the code.


### L7 — `assert` is a claim about your own code; `raise` is a rule about the world
**Pays off in:** Phase 3, where a raised type becomes an HTTP status and an `AssertionError`
becomes a 500; Phase 5, where a unit's exit code is derived from *which* exception escaped; and
Phase 6, whose drills start from a log line — `AssertionError` is the one that says nothing.

#### What happened

Both source modules validated their window with bare `assert` — start on the hour, end on the
hour, `backfill_days` present — and `DEFECTS.md` D23 noted in passing that `python -O` removes
them. The question came back with weight while the D17 conformance check was being written in the
dispatcher: is the check on the frame an `assert` or an `if … raise`? D17 had already answered it
without saying so. The check has to run on the box, on every ingest, because the failure it
catches is the day the source stops looking like the fixture; and D22 needs to tell that failure
apart from a dead network. Neither is something an `assert` can do.

#### The mechanism

`assert` is a debugging aid the interpreter is *permitted to delete*. Under `python -O`, or with
`PYTHONOPTIMIZE=1` in the environment — which a unit file or a container can set without touching
the code — every `assert` statement is compiled out: condition, message, side effects, all of it.
So an `assert` says, to the reader and to the interpreter alike, "this may be skipped without
changing what the program means". For an invariant of your own logic that is true: skipping
"after this loop `i == n`" changes nothing for a correct program. For a check on input it is
false: skipping "the frame is hourly" changes the program from one that rejects malformed frames
to one that stores them.

The second half is the type. Every `assert` raises `AssertionError`, so a caller cannot tell "not
hourly" from "not sorted" from someone's `assert x is not None` three modules away. A `raise`
names a class, and that class is part of the function's *interface*: it is what a caller catches,
what a result object records, what an exit code is derived from, and what appears on the first
line of the log. The distinction D22 draws — a contract violation is deterministic and ours, a
failed call is contingent and the world's — exists at runtime only if the two are different
types.

The heuristic that decides between them: **whose fault is it when this fires?** If a bug in the
function being written — `assert`. If the input, the caller, or the environment — `raise`, with
a type that names the contract. The conformance check is the interesting case because a violation
*is* our bug (the adapter is wrong), yet it is detected on external data at runtime and must never
be skippable; that makes it a contract check, and the fault heuristic asks who broke the
contract, not who will fix it.

Two facts from the same corner:

- **In tests, `assert` is exactly right.** pytest rewrites `assert` statements at import to
  report both sides of a failed comparison, and no one runs a suite under `-O`. The same project
  therefore uses both, split by directory: `raise` under `src/`, `assert` under `tests/`.
- **`assert (cond, "message")` never fails.** A parenthesised pair is a two-tuple, and a non-empty
  tuple is truthy. The form is `assert cond, "message"`; the parentheses, if any, go around the
  message alone. Linters flag it; it is worth knowing why.

#### The practice

1. **`assert` for invariants of the code being written; `raise` for contracts on what it
   receives.** If deleting the check would change behaviour for any *valid* program, it is not an
   assert.
2. **Give a contract its own exception type**, and treat that type as interface: it is what
   callers, result objects, exit codes and log lines are built from.
3. **Assume something upstream may set `-O`.** Not because it is likely, but because the code
   should not have to know whether it did.
4. **Keep `assert` for the tests**, where it is the better tool, and let the directory boundary
   carry the rule.


### L8 — A fixture is a dependency; `parametrize` is a multiplier
**Pays off in:** Phase 2, whose feature tests need a populated store as a dependency and horizons
as cases; Phase 3, where the app under test is a fixture and the registry is monkeypatched; and
every phase after, since `monkeypatch`, `tmp_path` and `caplog` are how the rest of the suite
stays offline.

#### What happened

The ingest test rewrite hit `Failed: Marks cannot be applied to fixtures` at collection — a
`@pytest.mark.parametrize` stacked on a `@pytest.fixture`, trying to give a fixture cases. The
same file had reached L5's 27-cell product by a different route: three fixtures with `params=`,
one per window argument, each multiplying every test that requested it. And a fixture requested a
`days` fixture that existed only in a sibling test module, which is not a place fixture lookup
goes. All three come from one confusion: two mechanisms that both put values into a test's
parameters, and do different jobs at different times.

#### The mechanism

**A fixture answers "what does this test need?"** Each parameter name on a test is a *request*;
pytest resolves it by name, walking from the test module up through each `conftest.py` above it
to plugins and built-ins — never sideways into a sibling module, and nearest definition wins,
silently. Fixtures request other fixtures, so a graph is resolved per test, then setup runs,
the test runs, and teardown (everything after `yield`) runs in reverse, even on failure.

**`@pytest.mark.parametrize` answers "how many times, with what inputs?"** It multiplies one
function into N collected items with the listed values bound directly — no lookup, no provider.
It happens at **collection**, before any fixture is resolved. That ordering is why a mark cannot
go on a fixture: marks are metadata on *test items*, and a provider function is never one. It is
also why the resolution rule per parameter reads: supplied by parametrize → bind it; otherwise
find a fixture; neither → `fixture not found`.

The two overlap in **`@pytest.fixture(params=[...])`**, which moves the multiplier into the
provider. Every test that requests that fixture runs once per value, and so does every test
requesting a fixture that requests it — transitive, and invisible at the test. That is right when
the values are independent and every consumer should see each one; it is wrong when the values
are dependent (a window is one thing, not three) or only some tests care. Then the test owns the
cases, and a fixture that must vary per case takes them through **`indirect=True`** (the value is
routed into a fixture of the same name via `request.param`) or, more simply, is a **factory** —
a fixture that returns a function, so each test calls it with the input that test needs and
nothing is multiplied.

**Scope** is the other axis. A session-scoped fixture is built once per run; a function-scoped
one per test. Anything tests *write to* — a DuckDB connection — stays function-scoped, or tests
start depending on which ran first. A higher scope cannot request a lower one (`ScopeMismatch`);
a session fixture wanting a temp file uses `tmp_path_factory`. `autouse=True` runs without being
requested, after collection, for side effects only (L2).

The rest of the `@pytest.mark` family is metadata of other kinds: `skip`/`skipif` (do not run),
`xfail` (expected failure — with `strict=True`, or a test that starts passing stays quietly
marked broken, L4 in miniature), `usefixtures` (a side-effect fixture without an argument),
`filterwarnings`, and registered custom marks selected with `-m`. `pytest.param(..., id=...,
marks=...)` is what makes a scenario table readable in the run output.

Built-ins this repo depends on: `tmp_path` (a fresh directory per test — every bare
`duckdb.connect()` is a *separate* in-memory database, so two connections need a file),
`monkeypatch` (`setenv` for a credential, `setattr` to replace a client method with a fake,
`chdir` — all undone at teardown), `request` (only meaningful inside a fixture), and `caplog`
(captured log records — how "names the variable, never the value" gets asserted).

#### The practice

1. **Fixtures for fixed dependencies, `parametrize` for chosen cases.** Config, a fresh
   connection, a factory are fixtures; windows, malformed frames, exception types are cases.
2. **Never a `params=` fixture for a dependent parameter**, and be aware that one multiplies
   every consumer, transitively. If only some tests care, the cases belong on those tests.
3. **A fixture that must vary per case is a factory or `indirect=True`** — not a marked fixture,
   which is an error, and not a fixture per value, which is a matrix.
4. **Match scope to mutability.** Read-only and expensive: session. Written to: function.
5. **Shared fixtures live in the `conftest.py` above every module that uses them**; lookup goes
   up, not sideways, and a nearer same-named fixture shadows without warning.
6. **`xfail` is `strict=True`** or it becomes a permanent hidden green.


### L9 — How the config layer is built, and how to build the next one
**Pays off in:** Phase 3, where the serving process decides whether it reads config once at
import (L3's consequence); Phases 4 and 5, where the environment layer is what a Dockerfile,
a compose file and a unit's `EnvironmentFile=` actually set; and the next project that needs a
config module, which can start from the checklist at the end instead of from this file's history.
Explaining this is also how `REVISIT.md` R2 gets struck.

#### What happened

`src/forecaster/config.py` was not designed once. It accreted through a sequence of things going
wrong: a cache that returned a stale object (D7 → L3); a secret kept in a yaml file in the tree
(L1); the tracked config being edited to `kind: entsoe` and that edit ending up inside a built
wheel (D19), which produced the overlay; the question of what the environment may change
(decision F); a regex parsing a frequency string at the point of use, which produced the
validation pass; and, during that pass, the discovery that `hide_input_in_errors` on a nested
model hides nothing. Each answered one question a config module has to answer. Read together,
the answers are the design, and the design is what transfers.

#### The mechanism — seven questions, and the tool that answers each

**1. Where does the file come from?** Three shapes of installation want three answers, in
order: a caller naming a file (`load_config(path)` or `$FORECASTER_CONFIG`), a checkout
(`Path(__file__).resolve().parents[2] / "config" / "config.yaml"` — the module knows where it
sits in the tree), and an installed wheel with no checkout above it, where
`importlib.resources.files("forecaster") / "_default_config.yaml"` finds the copy that
`pyproject.toml`'s `force-include` packaged. `default_config_path()` is that order, and the
object records which one won (`config_path`) — provenance, so a run can say what it actually
read. `pathlib` throughout: `resolve()`, `expanduser()`, `parents[n]`, `is_file()`.

**2. How do layers combine, and which may change what?** The axes were decided before the
schema, and the code follows them. *What the system is* — columns, feature spec, horizon,
thresholds — is the tracked file, identical everywhere by being in git. *What it points at* is
the gitignored overlay `config/local.yaml`, deep-merged over the file by `_deep_merge`
(mappings merge key by key; lists and scalars replace wholesale — a half-merged list is never
what anyone meant), and skipped when a config is *named*, because naming a file means meaning
it. *Where things live* is the environment, through `_ENV_OVERRIDES`: an allowlist mapping a
variable name to a key path, applied by `_apply_env_overrides` **before** validation so an
override is type-checked like any other value. The allowlist is two entries long on purpose,
and `source.kind` is not on it: a parent process can set an environment variable, so the
environment must not be able to change what a run *means* (decision F, R2).

**3. What shape is it?** One pydantic `BaseModel` per section, composed into `Config`. The
vocabulary, each with the reason it is used here:

- `ConfigDict(extra="forbid", frozen=True)` on every model. `extra="forbid"` makes a key nothing
  reads an error, because a key nobody reads looks like configuration and is not — it catches a
  typo in the overlay too. `frozen=True` on every model, not only the outer one, because
  `cfg.domain.target_column = ...` would otherwise be legal on a memoised object shared by every
  caller in the process (L3, practice 5).
- `Literal["a", "b"]` for a closed set (`source.kind`, `training.model`, `primary_metric`,
  `production_stage`): adding a value is a visible decision, and a wrong one fails at load rather
  than at the API that would have rejected it.
- `Annotated[type, AfterValidator(fn)]` for a constraint used in more than one place —
  `Identifier`, `UniqueIds`, `HourList`. The alias *is* the documentation: a field typed
  `Identifier` says what it must be without a validator on every model. `AfterValidator` runs
  after pydantic's own type coercion, so `fn` sees a `str`, never raw yaml.
- pydantic's constrained types where one exists — `PositiveInt`, `NonNegativeInt`,
  `NonNegativeFloat` — and `Field(min_length=, ge=, le=)` for the rest. `Field(default_factory=)`
  for a default that has to be computed.
- `@field_validator("name")` + `@classmethod` for a rule about one field (`frequency`,
  `holidays_country`); `@model_validator(mode="after")` for a rule *between* fields — three
  columns that must differ, a holdout that must cover the horizon. After-mode runs on the
  constructed object, so the validator reads `self.x`.
- A **discriminated union by tag**: every source block carries `kind: Literal["synthetic"]`
  (a default, so the yaml need not repeat it), `SourceCfg` holds *all* blocks and a `kind` naming
  one, and `kind_cfg` returns the named block typed as the union. Holding every block means a
  typo in the live block fails on an offline run, at a desk, rather than on the box. The
  `_blocks_match_their_names` validator is the guard against the one way this shape can lie: a
  field named `entsoe` holding a block tagged `synthetic`.
- `from __future__ import annotations` so the annotations are strings and forward references
  (`"DomainCfg"` in a validator's return type) cost nothing; `Annotated` and `Literal` from
  `typing`.
- A lazy `import holidays` *inside* the one validator that needs it, so the config module — which
  everything imports — stays cheap to import.

**4. What is validated, and what is not?** The rule in the module docstring: validate what would
otherwise fail **later** or **silently**, and nothing else. Later: numbers numpy or sklearn
reject at first use (a negative seed, a negative scale), names MLflow rejects at promotion time.
Silently: a column name with a space reaching an SQL f-string, two storage keys naming one table
so the feature build overwrites the observations, a step size the rest of the config assumes
(`frequency` is pinned to `"1h"` because every other duration is counted in hours). Not
validated: whether a path exists or a URI answers. Those are facts about the machine at runtime,
and a validator that checks them makes the config unloadable in exactly the environments — CI, a
test with a temp path — that the layers exist to serve.

**5. How does it fail?** With one `ValidationError` carrying every failure at once, each with a
`loc` tuple naming the field (`("training", "horizon_hours")`) or, for a model validator, the
model (`("training",)`). Two consequences. Tests assert on `loc`, not on message text — the
location is the contract, the wording is not. And the error echoes its input by default, which
for a config that names a credential's variable is a leak the moment someone pastes the
credential instead. `hide_input_in_errors=True` is therefore set on `Config` — **the top-level
model, because pydantic renders with the config of the model that was called**, and setting it
on `EntsoeCfg` hid nothing. The flag scrubs every rendered form; the structured `errors()` and
`json()` still carry `input` unless passed `include_input=False` (L1). Validators that can safely
name the offending value do so in their own message; `_env_var_name` deliberately does not.

**6. How is it cached, and what invalidates it?** `load_config` is a thin public wrapper that
computes the key — path, overlay path, both files' `st_mtime_ns`, and a snapshot of the
environment variables that matter — and calls a private `lru_cache`d function whose unread
parameters exist to be part of that key (L3). `cache_clear` is re-exported so a test can reset
it. The consequence a long-lived process has to decide about: an edited file is picked up on the
next call with no restart.

**7. What does it say about itself, and what does it never say?** `project_root`, derived from
the file actually loaded (not the default path — D7's second half) so `abs_path()` resolves
relative paths against the right checkout, with the packaged case falling back to the working
directory. `config_path` and `config_overlay`, so a run record can name what was in play. And
never a secret: `api_key_env` is the *name* of a variable, read from the environment at the point
of use (L1), so a full `model_dump_json()` of this object contains nothing to rotate.

#### The accompanying files, and what each one is for

`config/config.yaml` — the system; its comments carry the *reasons* for values, which is where
a threshold's basis lives (decision C). `config/local.yaml` — gitignored, per machine, the live
flip; created at provisioning alongside the credential file. `pyproject.toml`'s
`[tool.hatch.build.targets.wheel.force-include]` — the packaged copy (and D19's trap).
`tests/conftest.py` — `$FORECASTER_CONFIG` and `$FORECASTER_DUCKDB_PATH` set at *module scope*,
so no test can inherit a working copy's overlay or reach the real database (L2, D21).
`tests/tests_config/test_config.py` — the committed file loads; a `_with(raw, "a.b.c", value)`
helper that deep-copies the committed dict and changes one key, so a test config can differ
from the real one only where it says; a `REJECTED` table with one row per validator asserting
the `loc`; an `ACCEPTED` table of borderline values a stricter validator would have to argue
with; and the L1 test, pinning both the safe and the unsafe error forms. How that file is
built is the next section.

#### How the tests are built

The module answers two different questions, and each needs its own baseline.

**Two baselines: the object and the dict.** `committed_cfg` is `load_config(DEFAULT_CONFIG_PATH)`
— the validated, frozen object — and is what a test about *values* reads (the synthetic source
has at least two entities). `committed_raw` is `yaml.safe_load` of the same file — a plain
mutable dict — and is what every test about *validation* starts from. The split is forced:
validation is a property of raw input, so it has to be tested by handing the schema something
raw, and the object cannot be that something because `frozen=True` makes it unmutable on
purpose. Both are session-scoped: read once, never written to, and `_with` copies before it
touches anything. A third, `cfg` from the top `conftest.py`, goes through the full loader under
`$FORECASTER_CONFIG` and is what `test_config_source` reads to pin `kind == "synthetic"` — the
tripwire that keeps the suite offline on every machine, through the same path a run takes.

**Cases construct `Config(**raw)`, not `load_config(path)`.** Every rejected and accepted row
calls the schema directly. That removes the loader from the question: no temp file per case, no
overlay, no environment allowlist, and no cache key — a case that went through `load_config`
would need a distinct path or a `cache_clear()` per row, or the second row would hit the first
row's entry (L3). The loader is exercised once, by `committed_cfg` and by `cfg`, where the
question actually is "does the committed file load through the real path".

**`_with` is derive-and-change-one.** Deep-copy the committed dict, split the dotted path,
walk the parents, set the leaf. Every test config is therefore the real one plus exactly the
edit the row names, so when the committed file gains a section or renames a key, the whole
table follows without being touched — and a test can never pass because of some second
difference nobody wrote down. It is the same move a factory with defaults makes (L10): the
baseline is shared, the delta is the test's.

**`REJECTED` has three columns because the `loc` is the assertion.** `(dotted, value, where)`,
one row per validator, each a `pytest.param` with an `id` that names the rule
(`holdout-shorter-than-horizon`, not `case-24`). The `where` column is where the mechanism
shows: a `field_validator` reports at the field, `("domain", "frequency")`; a `model_validator`
reports at the *model*, one segment shorter, `("domain",)` for two columns that collide,
`("training",)` for a holdout shorter than the horizon; a constraint on a list element reports
with the index, `("features", "lags", 0)`. Reading the column is reading which kind of
validator each rule is. The last row, `unread-key-is-refused`, is a plausible typo of a real key
and exists to pin `extra="forbid"`.

**The assertion is membership, not equality.** `Config(**_with(...))` inside
`pytest.raises(ValidationError)`, then `locations = [tuple(err["loc"]) for err in
excinfo.value.errors()]` and `assert where in locations`. Pydantic collects *every* failure into
one error, and breaking one key can legitimately produce more than one — a wrong `frequency`
fails its own validator and may trip a model validator that reads it — so asserting the full list
would couple the test to the cascade rather than to the rule. And it is the `loc` that is
asserted, never message text: the location is the contract, the wording is free to change.

**`ACCEPTED` has two columns and no `raises`.** `(dotted, value)`, construction succeeds, done.
Its rows are values a stricter validator would refuse — an empty `lags` list, a negative
`base_load`, `drift_threshold` at exactly `0.0` and `1.0`, `":memory:"` as a path. The table is
the argument against over-validation, held in a form that fails if someone tightens a rule
without deciding to: the boundary values are the point, since a `ge=0` written as `gt=0` fails
`threshold-zero` and nothing else.

**The L1 test pins the trap as well as the fix.** It pastes a token where the variable's name
belongs, and asserts the token is absent from every *rendered* form — `str`, `repr`, the last
line of `traceback.format_exception` — and from `errors(include_input=False)` and
`json(include_input=False)`. Then it asserts the token *is* present in the default `errors()`.
That last assertion looks backwards and is the important one: it documents that the structured
form is unsafe, so a pydantic upgrade that changes the default in either direction turns the
test red and gets read, rather than silently changing what a serialised error carries.

#### The practice — building the next one

1. **Decide the axes before the schema.** What the system *is* goes in one tracked file. What
   it *points at* is an overlay that cannot reach a clone. *Where things live* is an
   environment allowlist, short, and never containing anything that changes what a run means.
2. **One model per section; `extra="forbid"` and `frozen=True` on all of them.** Every field
   required unless a default is a genuine default.
3. **Closed sets are `Literal`s; reusable constraints are `Annotated` aliases; one-field rules
   are `field_validator`s; relationships are `model_validator`s.** Use pydantic's constrained
   types before writing your own.
4. **Validate what fails later or silently. Leave runtime facts to runtime.** Write the rule in
   the module docstring, so the next validator added is held to it.
5. **Apply overrides before validation**, so an override is checked like a file value.
6. **Discovery order: named → checkout → packaged. Record which won.**
7. **Cache behind a key that names every input** — files by mtime, environment by snapshot —
   with a public wrapper and a private cached function.
8. **Config names secrets and never holds them; hide inputs in errors on the top model;
   `include_input=False` wherever an error is serialised.**
9. **Test the committed file, one rejected row per validator asserting `loc`, an accepted table
   for the borderline, and derive every test config from the committed one.**
10. **A discriminated union for "one of several backends": hold every block, tag each, and
    guard the tag against the field name.**


### L10 — A factory fixture separates what a test depends on from what a test chooses
**Pays off in:** Phase 2, whose feature tests need a raw frame per scenario — a gap, a DST
transition, a window shorter than the longest lag — and a populated store built from it; Phase 3,
where a test client is built per test against a monkeypatched registry; and Phase 6, whose drift
tests need a baseline frame and a shifted frame from the same generator in one test.

#### What happened

The ingest test rewrite (L8) had three `params=` fixtures, one per window argument, and every
test that touched any of them ran once per value — a product nobody had chosen. The way out was
`make_synthetic_data` in `tests/conftest.py`: a session-scoped fixture that takes `cfg` and
returns a *function*. A test that needs a frame calls it with the window that test needs; a test
that needs two frames calls it twice; a test that needs none does not request it and is
multiplied by nothing. L8 named the shape in a clause. This entry is how it works and how to
build the next one.

#### The mechanism

A plain fixture is a **value**: pytest calls the fixture function once per scope, binds the
return to the test's parameter, and the inputs that produced it are fixed where the fixture is
written. A factory fixture is a **function**: the fixture stage resolves the dependencies and
closes over them, and the *test* supplies the inputs when it calls. The two stages carry
different things, and that is the whole idea:

```python
@pytest.fixture(scope="session")
def make_synthetic_data(cfg):                      # fixture stage: dependencies, resolved by lookup
    def _make(start_time: datetime, end_time: datetime) -> pd.DataFrame:
        return create_synthetic_data(cfg=cfg, start_time=start_time, end_time=end_time)
    return _make                                   # the value bound to the test is the function

def test_hourly(make_synthetic_data):
    frame = make_synthetic_data(START, START + timedelta(days=3))   # call stage: the case
```

Functionally `_make` is `functools.partial(create_synthetic_data, cfg=cfg)`: the fixture graph
supplied `cfg`, the closure holds it, and the test never has to request `cfg` itself to build a
frame. What the test writes is exactly the part that varies. Four properties follow.

**Scope attaches to the wiring, not to the values.** The factory is `scope="session"` and that
is safe, because what is shared across the run is an immutable function over a frozen `Config`
(L3, practice 5). Every call returns a *fresh* frame, so a test that sorts one in place or adds
a column corrupts nothing for the next test. A session-scoped fixture returning the frame itself
would be the opposite: one mutable object, every consumer, order-dependent failures. The factory
gives session-scoped setup with function-scoped results — the combination L8 practice 4 wants
and a value fixture cannot provide.

**One test, several objects.** Determinism is "two calls with the same inputs are equal";
idempotency is "ingest a window, then an overlapping one, and the row count is the union"; a
gap test is "a frame with an hour removed". Each needs more than one frame, or a frame the test
has shaped, and a value fixture yields exactly one, already made. The count and the shape are
the test's business, so the constructor belongs to the test.

**Cases stay on the test, where they are chosen.** With a factory, `parametrize` lists the
scenarios and the factory turns each into an object — the L5 table of named windows with no
`params=` fixture multiplying anything, transitively or otherwise:

```python
@pytest.mark.parametrize("days", [pytest.param(1, id="one-day"), pytest.param(90, id="backfill")])
def test_row_count(make_synthetic_data, cfg, days):
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)
    frame = make_synthetic_data(end - timedelta(days=days), end)
    assert len(frame) == days * 24 * len(cfg.source.kind_cfg.entity_ids)
```

Multiplication is visible at the test that asked for it. A test that does not care about the
window calls the factory once with a default and is one item.

**The name says which parameters are callables.** `make_*` for a factory, a noun for a value.
A test signature `(make_synthetic_data, cfg, tmp_path)` reads as "a constructor, a config, a
directory" without opening `conftest.py`, and `Callable[[datetime, datetime], pd.DataFrame]` as
the return annotation tells a reader the call shape.

#### Building the next one

Two extensions carry most of what later phases need.

**Defaults, so the common case is a bare call.** A factory whose every argument has a default
lets a test that does not care write `make_synthetic_data()` and a test that cares override one
thing. It is the same move as `_with(raw, "a.b.c", value)` in `tests/tests_config`: derive from
the baseline, change what the test is about, and nothing else. Keyword-only (`*`) so a caller
cannot pass a window positionally and get the arguments crossed:

```python
@pytest.fixture(scope="session")
def make_synthetic_data(cfg):
    def _make(*, end: datetime = END, days: int = 3, entity_ids: list[str] | None = None) -> pd.DataFrame:
        ...
    return _make
```

**Teardown, when what it makes must be closed.** A factory that opens something — a DuckDB
connection to a file under `tmp_path`, an MLflow run — keeps a list of what it made, `yield`s
the function, and closes everything after. Then the scope has to drop to function, because the
list is now mutable state and the connections belong to one test:

```python
@pytest.fixture
def make_conn(tmp_path):
    opened: list[duckdb.DuckDBPyConnection] = []
    def _make(name: str = "store") -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect(str(tmp_path / f"{name}.duckdb"))
        opened.append(conn)
        return conn
    yield _make
    for conn in opened:
        conn.close()
```

The Phase 2 shape composes the two: `make_synthetic_data` builds the frame, `make_conn` opens
the store, and a `populated_store` fixture calls both and returns the connection — a *value*
fixture again, because most feature tests want the same populated store and want it once. The
factories are the layer underneath that lets the handful of tests with an unusual frame build
their own without a second fixture per case.

#### The practice

1. **Fixture returns a function when the test must choose the inputs or the count.** Otherwise
   a value is simpler; do not make every fixture a factory.
2. **Close over dependencies; take the case as arguments.** The fixture graph supplies what is
   fixed, the call supplies what varies, and the test requests neither more nor less than that.
3. **Session scope is safe only while the factory returns fresh objects and holds no mutable
   state.** The moment it tracks what it made for teardown, it is function-scoped.
4. **Keyword-only arguments with defaults**, so the common call is empty and the specific call
   names what it changes.
5. **`make_*` names the factories**; the return annotation gives the call shape.
6. **Pair a factory with `parametrize`**, not with `params=`: the table of cases sits on the
   test, and the factory turns a row into an object.


### L11 — A pointer can go stale; the thing it points at cannot
**Pays off in:** every session open, since two of the three opening reads are pointers — and
Phase 6, where the run-history table becomes a second place the same question can be asked and
answered differently.

#### What happened

Decision E fixes ingestion's run window. Whether `(–, end, N)` — an explicit `end` with
`--backfill-days` — was a legal combination looked like an open question: the `0738cc6` commit
message called it *"a row decision E did not make"*, and `NEXT_STEPS.md` step 1 said *"decide the
`(–, end, N)` row beside decision E"*. A session read the whole repo, reached row E, and carried
the question forward as open anyway — then quoted E's own settling clause back as an argument for
which way to decide it, without noticing the clause *was* the decision.

E settles it twice: *"the sugar resolves to `end` = now floored to the hour"* leaves no supplied
`end` to honour, and *"the two forms are mutually exclusive"* forbids mixing the two. (The row was
later reopened deliberately and E amended — but on the merits, by the person who owns the design,
which is a different act from never having read it.)

#### The mechanism

`CLAUDE.md` gives each file one job, and the jobs differ in *durability*:

| file | holds | goes stale when |
|---|---|---|
| `BUILD_PLAN.md` register | the decision and its basis | never — an amendment edits it in place, with a date |
| `DEFECTS.md` | an observed property of the code, and its fix | the code changes; the entry is struck, not deleted |
| `NEXT_STEPS.md` | *sequence only*, never content | continuously — entries are deleted as they land |
| a commit message | what was true of the tree at that commit | immediately — it is immutable and the repo is not |

The last two are **pointers**. They are the fastest way to find the thing, and that is exactly
why a claim inside them about the thing is dangerous: it reads with the authority of the file's
position in the workflow — first thing a session reads — and none of the file's durability. A
commit message in particular can never be corrected. It says what one session believed on one
evening, and it keeps saying it after the belief is wrong.

The failure mode is not "I did not read the authority". It is **reading the authority through a
prior claim about it**, which is a different act: the claim supplies the conclusion and the
reading supplies only corroboration, so a contradiction arrives looking like a detail. It is the
same shape as `L1`'s correction — *a migration described in a log is not a migration that landed*
— one level up: a note about the register is not the register.

Reading everything does not fix this, and the episode is the proof: the session read the whole
repo, E included, and still carried the question forward. **Contradiction-finding is an operation
over pairs; reading is an operation over documents.** A complete read produces one summary per
file and never forms the pair, so "read it all" buys coverage and not consistency. Consistency is
a separate pass with the pairs named — a claim in a pointer, checked against the file that owns
that kind of claim.

Two things made this instance harder to catch than the general shape. The position had already
been **stated to the human** before the authority was read, and a view that has been asserted is
not re-opened by a later read; it is confirmed by one. And the register **strikes through settled
rows**, which correctly means "not your decision to make" and incorrectly reads as "history, skim
it" — while a settled row is exactly what must be read closely when something nearby claims there
is an open question inside it. The formatting that makes the register scannable is what makes a
settled row's operative clause skimmable.

There is a converse to the rule this repo already states. *"If it exists only in a conversation,
it is not decided"* has a second half: **if it exists in the register, it is decided**, and a
session's job is to find it there rather than re-open it. Re-opening a settled decision costs
more than leaving one unsettled, because the second is visible and the first looks like work.

#### The practice

1. **Route a question by its kind, then read the file that owns that kind.** "Is this decided?"
   is answered in the register and nowhere else — not by a commit message, not by the ordering
   file, not by the absence of a defect entry.
2. **Treat "X is not decided" as a claim to check, not a fact to inherit** — the same standing as
   L1's *"never committed"*. Checking costs one read of one table.
3. **When a pointer and its target disagree, the target wins and the pointer gets fixed** in the
   same turn. A stale pointer that is merely noticed will be re-read by the next session.
4. **Read the authority before forming the question, not after.** A conclusion carried into a
   document turns reading into confirmation, and the sentence that contradicts it reads as a
   detail.
5. **Notice when evidence is being spent on persuasion.** Quoting the deciding clause as support
   for a recommendation is the signal that the clause was never treated as deciding anything.
6. **A complete read is not a consistency check.** If contradictions between documents matter,
   name the pairs and check them deliberately; no amount of reading each file produces it as a
   by-product.
7. **State a position after reading the authority, not before.** Once it has been said out loud
   the later read can only confirm it.

### L12 — A helper earns its own tests when the front door is the expensive way in
**Pays off in:** Phase 3's promotion gate and Phase 6's drift signal. Both are predicates with a
case table behind a caller that does I/O, which is the shape this entry is about.

#### What happened

`tests/tests_ingest/test_ingest.py` covered `store_data` with four tests and `ingest` with one,
and nothing else in the module. Of the five draft observations standing against the ingestion
drafts at the foot of `DEFECTS.md`, four were against `_resolve_time_window` and
`_assert_conformance` — the two functions with the most branching, and the two that no test in the
file could reach. Every one of them was found by reading the code, not by running it.

`NEXT_STEPS.md` had already decided the matter without stating the rule: step 1 builds
`resolve_window`'s `VALID`/`REFUSED` tables before the function, and step 4 builds one hand-built
malformed frame per clause of the conformance guard. Both are direct tests of functions the module
spells with a leading underscore — and step 1 writes the name without one.

#### The mechanism: coupling cost against reachability cost

Testing through the public entry point costs nothing on refactor. A test that names `ingest()`
survives a helper being renamed, inlined or split, because it never mentioned the helper. A test
that names `_resolve_time_window` goes red when that function stops existing, although the
program's behaviour is unchanged. That is the entire price of testing below the front door, and it
is why the default runs the other way.

Two costs push back, and either one alone is enough to pay it.

**Reachability.** Some cases are cheap to construct at the helper and expensive to construct at
the caller. Driving the conformance guard's gap clause through `ingest()` means making the
generator emit a gap — a fake source built solely to exercise a guard. Handing the guard a
hand-built frame is three lines. The gap between those two numbers is the reachability cost, and it
is paid once per case.

**Combinatorics.** A helper can have more interesting cases than its caller has interesting
outcomes. `resolve_window` has a table — start only, backfill only, both, neither, non-hour-aligned,
offset-bearing, naive — against perhaps two outcomes of `ingest()` worth asserting. Running the
table through the caller multiplies every row by a generator run and a database connection, and
every failure reports the caller's name rather than the row that broke. Localisation is not a
side benefit here; a case table whose failures all say "ingest returned the wrong thing" has given
up the reason it was a table.

The underscore does not decide any of this. It is a convention about who may *call* a function,
not who may *observe* one, and a test inside the module's boundary is entitled to look. What it
does carry is a signal: **a helper that repeatedly earns its own case table is not a helper.** It
is a unit with a contract of its own, and the name should lose the underscore — which is what step
1 had already done to `resolve_window` in passing.

The converse bounds it. A function extracted purely so that its caller reads well — one
expression, no branches, no rejection cases — has no contract separate from the caller's and gets
no tests of its own. `load_data`'s dispatch is nearly that; the one rule it owns is the raise on an
unknown kind.

#### The practice

1. **Default to the public entry point**, so the test survives the refactor. Go below it only for
   a named reason.
2. **Go below it when a case is expensive to reach from outside** — when exercising one clause
   would mean building a fake collaborator whose only job is to be wrong.
3. **Go below it when the helper's case table is wider than the caller's outcomes.** Multiplying a
   table by the caller's I/O buys nothing and loses the failure's address.
4. **Pin the contract, not the steps.** "Which frames are refused, and with what exception", never
   "it calls `groupby`" — asserting steps reintroduces exactly the coupling the default was
   avoiding.
5. **Treat a helper that keeps earning tests as a naming defect.** Drop the underscore, or move it
   to its own module; the tests were telling you where a boundary already is.
6. **A function extracted for readability is covered by its caller.** No branches and no rejections
   means no contract of its own.


### L13 — Convert at the boundary; an inner function takes domain types, not the text they arrived as
**Pays off in:** Phase 5, where the scheduled flow calls the same rule in-process with no command
line anywhere; Phase 7, which reads a window back out of run history as timestamps; and Phase 3,
where a request body is the boundary and the model's input is the domain type.

#### What happened

The draft `_resolve_time_window(start_time: str | None, end_time: str | None, backfill_days: int
| None)` both parsed CLI text and applied decision E's arity rule. Two symptoms came from that one
choice. The backfill branch computed a `datetime` and handed it to the string parser on the next
line — `TypeError: strptime() argument 1 must be str`, so the `--backfill-days` path could not
produce a window at all. And when the `VALID`/`REFUSED` tables were being written, the two rows
that matter most for timezones (L5, practice 7) turned out to be *inexpressible*: the parser is
`strptime("%Y-%m-%d %H:%M:%S")` followed by `.replace(tzinfo=utc)`, which cannot represent
`+02:00` at all, and silently relabels any offset as UTC.

#### The mechanism

A program has **boundaries** — a command line, an HTTP request, a yaml file, a database row — where
information arrives as text, and an **interior** where it is a value with properties. Conversion
belongs at the boundary, once, and everything inward takes the domain type. Four things follow, and
the last is the one that is easy to miss.

**The type is a claim about who may call it.** `str` admits `"banana"`; `datetime` carries
tz-awareness and hour-alignment as properties that can be *checked* rather than parsed. A signature
of `(datetime | None, datetime | None, int | None, datetime)` says "I take instants"; a signature of
`(str | None, ...)` says "I take whatever the CLI happened to hand me", and the CLI is one caller of
several. Phase 5's flow has no command line; making it `str(dt)` a value so an inner function can
parse it back is a round trip whose only possible outcome is loss.

**Two rules in one function multiply their cases.** Parsing answers "what does this text mean" and
fails on format; resolution answers "what window do these three mean" and fails on arity. Together,
every arity row would need a malformed-string variant to be honest — the same multiplication L5
refused one level up. Apart, each has a small table of its own.

**The output type should be admissible as input.** `resolve_window` returns `tuple[datetime,
datetime]`; a version taking strings could not be fed its own result, so "re-resolving an already
resolved window is identity" is not even statable. An interface whose output cannot be its input is
usually one that converted in the wrong place.

**What the boundary type can express bounds what the tests can say.** This is the consequence worth
carrying. The two timezone rows exist to pin *where* normalisation sits relative to the hour check —
and with `str` arguments they cannot be written, because the chosen format has no offset field. The
test would not fail; it would be absent, and its absence would look like a decision nobody made.
A weak boundary type does not merely inconvenience the tests — **it silently removes cases from
what they are able to assert.**

#### The practice

1. **Convert at the boundary, once.** `argparse`'s `type=` is the designated hook, the same role
   pydantic plays for yaml in `config.py` (L9) and a request model plays for HTTP.
2. **Inner functions take domain types.** Ask which callers exist besides the one in front of you;
   in a scheduled system there is always at least one with no text anywhere.
3. **Keep format failures at the boundary and domain failures inside.** A bad format is a usage
   error naming the flag; a bad window is the rule's own exception (L7), translated back into a
   usage error by the entry point.
4. **Check that the output type is admissible as input**, and prefer the signature where it is.
5. **Before choosing a boundary format, ask which cases it makes unwriteable.** If a hard case
   cannot be expressed in the type the function accepts, the type is the thing to change.
