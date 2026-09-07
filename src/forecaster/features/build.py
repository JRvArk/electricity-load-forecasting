"""Phase 2 — Feature building.

Responsibility
    Turn raw observations into a feature table the model can train on. Read the
    feature spec (which lags, which rolling windows, calendar on/off, holiday
    country) from config so the same code works on any domain.

Target properties (write tests for these first)
    - No leakage: every feature must use only information available AT THE
      FORECAST ORIGIN — not merely "strictly before the target timestamp".
      Those differ for every horizon beyond one step, and the config's
      lags [1, 2, 3] are leakage at a day-ahead horizon if read against the
      target. BLOCKED on BUILD_PLAN.md open decision A (horizon, and whether
      lags are origin-relative); the recommendation there is origin-relative
      lags with H = 24, which keeps the existing lag list valid.
      (Rolling windows must be shifted accordingly either way.)
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

import duckdb
import pandas as pd

from forecaster.config import Config, load_config  # noqa: F401

# TODO(rung-3): design and implement.
# Make this module runnable as:  python -m forecaster.features.build


def retrieve_data(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    pass


def _compute_lag(data: pd.DataFrame, lag: int) -> pd.DataFrame:
    pass


def _compute_rolling_window(data: pd.DataFrame, window: int) -> pd.DataFrame:
    pass


def _compute_holiday_feature(data: pd.DataFrame, country: str) -> pd.DataFrame:
    pass


def build_features(data: pd.DataFrame, config: Config) -> pd.DataFrame:
    pass


def persist_features(conn: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> None:
    pass


def main() -> None:
    config = load_config()
    with duckdb.connect(database=config.storage.duckdb_path) as conn:
        raw_data = retrieve_data(conn)
        features = build_features(raw_data, config)
        persist_features(conn, features)


if __name__ == "__main__":
    main()
