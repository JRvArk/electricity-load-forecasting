"""Phase 2 — Feature building.

Responsibility
    Turn raw observations into a feature table the model can train on. Read the
    feature spec (which lags, which rolling windows, calendar on/off, holiday
    country) from config so the same code works on any domain.

Target properties (write tests for these first)
    - No leakage: every feature at time t uses only information available strictly
      before t. (Lags and rolling windows must be shifted accordingly.)
    - No NaNs in the output: rows that can't be fully populated (the warm-up
      period for the largest lag/window) are dropped.
    - Predictor set is well-defined: a caller can ask which columns are predictors
      (everything except the timestamp and target).
    - Calendar + holiday features reflect the configured country.

Done criterion (shared with Phase 2 training)
    Two tracked training runs are visible and comparable in the MLflow UI.

Workflow (rung 3): design the interface, write tests pinning the properties,
implement to green, then diff against reference/.

Note: keep this computable on an in-memory frame without touching the DB — that
makes the leakage/NaN properties trivial to test. Persisting to DuckDB is a
separate concern.
"""

from forecaster.config import Config, load_config  # noqa: F401

# TODO(rung-3): design and implement.
# Make this module runnable as:  python -m forecaster.features.build
