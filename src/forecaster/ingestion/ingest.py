"""Phase 1 — Ingestion + storage.

Responsibility
    Pull hourly observations from the configured source and land them in the
    DuckDB raw table. Read everything domain-specific from config (column names,
    table name, source kind) — hardcode nothing.

Target properties (turn these into tests BEFORE you implement)
    - Idempotent: re-running over the same time window does not change the row
      count or corrupt existing rows. Key on the timestamp column.
    - Backfillable: can populate an arbitrary [start, end) range.
    - Source-independent schema: the raw table has the same shape no matter which
      source produced it. The default `synthetic` source must run with zero
      external dependencies.

Done criterion
    Running ingestion twice over the same range leaves the row count unchanged.

Workflow (rung 3)
    1. Design the interface yourself — decide the functions and their signatures.
    2. Write tests in tests/ that pin the properties above.
    3. Implement until green.
    4. Only then open reference/ and diff your design AND your test coverage
       against mine. Compare, don't copy.

Hint: for the synthetic source, a deterministic series with daily + weekly
seasonality plus noise is plenty. The modeling is not the point here.
"""

from forecaster.config import Config, load_config  # noqa: F401  — you'll need these

# TODO(rung-3): design and implement.
# Make this module runnable as:  python -m forecaster.ingestion.ingest
