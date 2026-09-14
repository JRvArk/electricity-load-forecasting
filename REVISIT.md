# Revisit log

Things in this repo that work, are committed, and are not yet fully understood by the person who
owns them. One entry per subject, with a pointer to the code and a question that can be answered
by reading it.

It exists because the alternative is worse. Code that arrived faster than the understanding of it
is a real category in a project built under a fixed box — some of it is delegated by design, some
of it is a mechanism met once in passing — and the honest options are to slow down until every
line is understood, or to record the gap and close it deliberately. The first does not finish. The
second only works if the gap is written down, because an unrecorded gap is indistinguishable from
knowledge until something breaks on top of it.

It is also a filter on what may be delegated. A mechanism that can be explained back is owned; one
that cannot is borrowed. Entries here name what is currently borrowed.

**Scope.** Every entry points at code, config or a decision **in this repo**. This is not a
reading list and not a syllabus — the phases are the curriculum, and a separate learning track has
been refused. If a subject cannot be anchored to a file in this tree, it does not belong here.

**Not the other two logs.** `DEFECTS.md` is for things that are *wrong* and name a fix.
`BUILD_PLAN.md` holds decisions and their basis. This file is for things that are *right* and not
yet understood; a subject moves out of here by being explained, not by being changed.

**Convention.** Entries are `R<n>`, stable, so a commit can cite one. Each names **where** the
code is and **when** to come back — a trigger in the build order, never a date, because the
trigger is what makes it actionable. Strike an entry through when it can be explained without
reading the answer; keep it in place, since what was once unclear is worth knowing about the
next reader too.

---

## R1 — Unread function parameters that are load-bearing, via `lru_cache`

**Where:** `src/forecaster/config.py:269-302` — `_load_config_cached`, `_env_snapshot`, `load_config`.
**Revisit when:** before Phase 5, since the failure this prevents is a scheduled job reading a
config that is stale against its own file, and Phase 5 is where jobs stop being run by hand.

`_load_config_cached` takes `_mtime_ns` and `_env` and never reads either. They are not dead: they
are part of `lru_cache`'s key. `lru_cache` memoises on the *arguments*, so a value that is never
used inside the body still decides whether a call returns the cached object or re-parses the file.

The two facts worth being able to state without looking:

1. **Why a cache needs a key wider than its inputs.** The function's output depends on things that
   are not arguments — the bytes on disk, and a handful of environment variables. Neither is
   visible to the cache. Passing them in *as* arguments is how a dependency that would otherwise
   be invisible becomes part of the identity of the call.
2. **Why the failure is silent.** Deleting them does not raise. Every call still succeeds and
   returns a valid `Config`; it is simply the wrong one, indefinitely. That shape — correct types,
   correct-looking values, stale content — is what makes this worth a note rather than a comment.

Observed, with a cache keyed on the path alone (left) against the key as written (right):

```
initial          first  | first
after an edit    first  | edited
after an env     data/… | /srv/prod.duckdb
```

**Check yourself:** predict what `load_config()` returns, in each of three cases, before running
anything — (a) the yaml is edited between two calls, (b) `FORECASTER_DUCKDB_PATH` is set between
two calls, (c) `load_config.cache_clear()` is called between two calls. Then try them. If all
three predictions were right, this entry can be struck.

**Adjacent, and only worth chasing if the above was easy:** the cache also makes every caller of
`load_config()` share one object rather than six equal ones. Nothing in the tree depends on that
today. Ask what would break if it stopped being true — that question is the difference between
knowing what a cache does and knowing what this one is for.
