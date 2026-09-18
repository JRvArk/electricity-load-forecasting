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
absent.

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
