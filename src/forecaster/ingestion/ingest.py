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

import argparse
import datetime
import logging

import duckdb
import numpy as np
import pandas as pd

from forecaster.config import Config, SyntheticCfg, load_config  # noqa: F401  — you'll need these
from forecaster.ingestion.ingest_result import IngestResult

logger = logging.getLogger(__name__)


def _create_synthetic_data(
    synthetic_cfg: SyntheticCfg,
    backfill_days: int,
    timestamp_column_name: str,
    target_column_name: str,
) -> pd.DataFrame:
    last_hour = datetime.datetime.now(datetime.timezone.utc).replace(
        minute=0, second=0, microsecond=0
    )
    start_time = last_hour - datetime.timedelta(days=backfill_days)
    end_time = last_hour
    timestamps = pd.date_range(
        start=start_time, end=end_time, freq="1h", inclusive="left", tz="UTC"
    )
    hours = np.arange(len(timestamps))
    rng = np.random.default_rng(synthetic_cfg.seed)

    daily = synthetic_cfg.daily_amplitude * np.sin(2 * np.pi * (hours % 24) / 24 - np.pi / 2)
    weekly = synthetic_cfg.weekly_amplitude * (((timestamps.dayofweek < 5).astype(float)) - 0.5) * 2
    noise = rng.normal(0.0, synthetic_cfg.noise_sd, size=len(timestamps))
    value = synthetic_cfg.base_load + daily + weekly + noise

    return pd.DataFrame(
        {
            timestamp_column_name: timestamps,
            target_column_name: value,
        }
    )


def _retrieve_entsoe_data(
    backfill_days: int, api_token_env: str, area_code: str, include_tso_forecast: bool
) -> pd.DataFrame:
    """Pull hourly actual load for one bidding zone from the ENTSO-E Transparency
    Platform, optionally alongside the TSO's own day-ahead load forecast.

    Target properties (write tests for these first)
        - Returns the same raw schema as the synthetic source — the configured
          timestamp and target columns, hourly, strictly increasing, no duplicates
          — so the raw table's shape does not depend on the source. That property
          is what keeps everything downstream source-agnostic.
        - When ``include_tso_forecast`` is set, one extra column ``tso_forecast``
          carries the TSO's published day-ahead forecast for the same timestamp.
          It is a Phase 7 baseline, never a feature: it is not known at the
          forecast origin for the horizons it covers.
        - Backfill over ``backfill_days``. Some zones publish quarter-hourly;
          resample to the configured frequency.
        - Retry with backoff around the network call (a Phase 5 requirement).

    ``api_token_env`` is the name of the environment variable holding the token;
    read it here, never log it. Human implements.
    """
    pass


def load_data(cfg: Config, backfill_days: int) -> pd.DataFrame:
    if cfg.source.kind == "synthetic":
        return _create_synthetic_data(
            synthetic_cfg=cfg.source.source_cfg,
            backfill_days=backfill_days,
            timestamp_column_name=cfg.domain.timestamp_column,
            target_column_name=cfg.domain.target_column,
        )
    elif cfg.source.kind == "entsoe":
        return _retrieve_entsoe_data(
            backfill_days,
            api_token_env=cfg.source.source_cfg.api_token_env,
            area_code=cfg.source.source_cfg.area_code,
            include_tso_forecast=cfg.source.source_cfg.include_tso_forecast,
        )
    else:
        raise ValueError(f"Unknown source: {cfg.source.kind}")


def store_data(
    conn: duckdb.DuckDBPyConnection,
    data_df: pd.DataFrame,
    table_name: str,
    timestamp_column_name: str,
) -> None:
    conn.register("incoming", data_df)
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM incoming WHERE 1=0")
    # delete-then-insert overlapping keys = idempotent upsert
    conn.execute(
        f"DELETE FROM {table_name} WHERE {timestamp_column_name} IN"
        f"(SELECT {timestamp_column_name} FROM incoming)"
    )
    conn.execute(f"INSERT INTO {table_name} SELECT * FROM incoming")


def ingest(cfg: Config, backfill_days: int) -> None:
    start_time_ingestion = datetime.datetime.now(datetime.timezone.utc)
    logger.info(f"Starting ingestion for {backfill_days} days backfill at {start_time_ingestion}.")
    try:
        data_df = load_data(cfg, backfill_days)
        with duckdb.connect(cfg.storage.duckdb_path) as conn:
            store_data(conn, data_df, cfg.storage.raw_table, cfg.domain.timestamp_column)
        logger.info(f"Ingested {len(data_df)} rows into {cfg.storage.raw_table}.")
    except Exception as e:
        logger.error(f"Error occurred during ingestion: {e}")
        return IngestResult(
            source_cfg=cfg.source.source_cfg,
            backfill_days=backfill_days,
            error_occurred=True,
            message=f"Error occurred during ingestion: {e}",
            run_start_time=start_time_ingestion,
            run_end_time=datetime.datetime.now(datetime.timezone.utc),
            data_start_time=None,
            data_end_time=None,
        )

    logger.info(
        f"Ingestion completed successfully at {datetime.datetime.now(datetime.timezone.utc)}."
    )
    return IngestResult(
        source_cfg=cfg.source.source_cfg,
        backfill_days=backfill_days,
        error_occurred=False,
        message="Ingestion completed successfully.",
        run_start_time=start_time_ingestion,
        run_end_time=datetime.datetime.now(datetime.timezone.utc),
        data_start_time=data_df[cfg.domain.timestamp_column].min(),
        data_end_time=data_df[cfg.domain.timestamp_column].max(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest data into DuckDB.")
    parser.add_argument(
        "--backfill-days",
        type=int,
        required=True,
    )
    args = parser.parse_args()
    cfg: Config = load_config()
    ingest(cfg, args.backfill_days)
