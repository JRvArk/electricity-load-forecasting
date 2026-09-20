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
import re
import sys

import duckdb
import pandas as pd

from forecaster.config import Config, EntsoeCfg, SyntheticCfg, load_config  # noqa: F401  — you'll need these
from forecaster.ingestion.ingest_result import IngestResult
from forecaster.ingestion.sources.entsoe import retrieve_entsoe_data
from forecaster.ingestion.sources.synthetic import create_synthetic_data

logger = logging.getLogger(__name__)


def _parse_and_validate_time_arg(time_str: str) -> datetime.datetime:
    """Parse a time argument in simple format, interpreted as UTC."""

    try:
        time = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
        if (time.minute, time.second) != (0, 0):
            raise ValueError(f"Time must be at the beginning of an hour, got {time_str}.")
        return time
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid time format: {time_str}. Expected format: 'YYYY-MM-DD HH:MM:SS'.")


def _resolve_time_window(
    start_time: str | None,
    end_time: str | None,
    backfill_days: int | None,
) -> tuple[datetime.datetime, datetime.datetime]:
    """Resolve the start and end times based on the provided arguments."""

    if start_time is None and backfill_days is None:
        raise ValueError("If start_time is not specified, backfill_days must be provided.")
    elif start_time is None:
        start_time = datetime.datetime.now(datetime.timezone.utc).replace(
            minute=0, second=0, microsecond=0
        ) - datetime.timedelta(days=backfill_days)

    if start_time is not None:
        start_time = _parse_and_validate_time_arg(start_time)

    if end_time is not None:
        end_time = _parse_and_validate_time_arg(end_time)
    else:
        end_time = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)

    return start_time, end_time


def _assert_conformance(cfg: Config, data_df: pd.DataFrame) -> None:
    """Assert that the data_df conforms to the expected schema defined in cfg."""
    expected_columns = [cfg.domain.timestamp_column, cfg.domain.target_column, cfg.domain.entity_column]
    actual_columns = data_df.columns.to_list()

    if len(actual_columns) != len(expected_columns):
        raise ValueError(
            f"DataFrame has {len(actual_columns)} columns, but expected {len(expected_columns)} columns. "
            f"Expected: {expected_columns}, Actual: {actual_columns}"
        )

    for col in expected_columns:
        if col not in actual_columns:
            raise ValueError(
                f"DataFrame columns do not match expected schema. Expected: {expected_columns}, Actual: {actual_columns}"
            )

    sorted_df = data_df.sort_values(by=[cfg.domain.entity_column, cfg.domain.timestamp_column])

    # CHECK AND FIX
    grouped_sorted_df = sorted_df.groupby(cfg.domain.entity_column)
    time_diffs = grouped_sorted_df[cfg.domain.timestamp_column].diff().dropna()
    expected_diff = pd.Timedelta(cfg.domain.frequency)
    if not (time_diffs == expected_diff).all():
        raise ValueError(
            f"DataFrame timestamps are not hourly. Expected difference: {expected_diff}, Actual differences: {time_diffs.unique()}"
        )


def load_data(
    cfg: Config, start_time: datetime.datetime | None, end_time: datetime.datetime | None, backfill_days: int | None
) -> pd.DataFrame:

    arg_dict = {}
    for arg_name, arg_value in [("start", start_time), ("end", end_time), ("backfill_days", backfill_days)]:
        if arg_value is not None:
            arg_dict[arg_name] = arg_value

    if cfg.source.kind_cfg.kind == "synthetic":
        return create_synthetic_data(cfg, **arg_dict)
    elif cfg.source.kind_cfg.kind == "entsoe":
        return retrieve_entsoe_data(cfg, **arg_dict)
    else:
        raise ValueError(f"Unknown source: {cfg.source.kind}")


def store_data(
    conn: duckdb.DuckDBPyConnection,
    data_df: pd.DataFrame,
    cfg: Config,
) -> None:

    include_tso_forecast = getattr(cfg.source.kind_cfg, "include_tso_forecast", False)
    if include_tso_forecast:
        data_observations = data_df[[cfg.domain.timestamp_column, cfg.domain.target_column, cfg.domain.entity_column]]
        data_tso_forecast = data_df[[cfg.domain.timestamp_column, cfg.domain.target_column, cfg.domain.entity_column]]

    conn.register("incoming", data_observations)
    conn.execute(f"CREATE TABLE IF NOT EXISTS {cfg.storage.raw_table} AS SELECT * FROM incoming WHERE 1=0")
    # delete-then-insert overlapping keys = idempotent upsert
    conn.execute(
        f"DELETE FROM {cfg.storage.raw_table} WHERE {cfg.domain.timestamp_column} IN(SELECT {cfg.domain.timestamp_column} FROM incoming)"
    )
    conn.execute(f"INSERT INTO {cfg.storage.raw_table} SELECT * FROM incoming")

    if include_tso_forecast:
        conn.register("tso_forecast", data_tso_forecast)
        conn.execute(f"INSERT INTO {cfg.storage.raw_tso_table} SELECT * FROM tso_forecast")
        conn.execute(
            f"DELETE FROM {cfg.storage.raw_tso_table} WHERE {cfg.domain.timestamp_column} IN(SELECT {cfg.domain.timestamp_column} FROM tso_forecast)"
        )
        conn.execute(f"INSERT INTO {cfg.storage.raw_tso_table} SELECT * FROM tso_forecast")


def ingest(
    cfg: Config, start_time: datetime.datetime | None, end_time: datetime.datetime | None, backfill_days: int | None
) -> IngestResult:
    start_time_ingestion = datetime.datetime.now(datetime.timezone.utc)

    arg_dict = {}
    for arg_name, arg_value in [("start_time", start_time), ("end_time", end_time), ("backfill_days", backfill_days)]:
        if arg_value is not None:
            arg_dict[arg_name] = arg_value

    try:
        data_df = load_data(cfg, **arg_dict)
        _assert_conformance(cfg, data_df)
        ingested_hours_per_entity = data_df.groupby(cfg.domain.entity_column).size().to_dict()
        with duckdb.connect(cfg.storage.duckdb_path) as conn:
            store_data(conn, data_df, cfg.storage.raw_table, cfg.domain.timestamp_column)
        ingested_hours_per_entity = data_df.groupby(cfg.domain.entity_column).size().to_dict()
        logger.info(
            f"Ingested {len(data_df)} rows into {cfg.storage.raw_table}. Ingested hours per entity: {ingested_hours_per_entity}"
        )
    except Exception as e:
        logger.error(f"Error occurred during ingestion: {e}")
        return IngestResult(
            source_cfg=cfg.source.kind_cfg,
            entity_ids=cfg.source.kind_cfg.entity_ids,
            ingested_hours_per_entity=None,  # THIS IS NOT NECESSARILY TRUE, I THINK, SINCE IT COULD FAIL MID-WAY. WHAT TO DO WHEN THAT HAPPENS? CLEAR THE TABLE FOR THAT TIME RANGE?
            backfill_days=backfill_days,
            error_occurred=True,
            message=f"Error occurred during ingestion: {e}",
            run_start_time=start_time_ingestion,
            run_end_time=datetime.datetime.now(datetime.timezone.utc),
            start_time=start_time,
            end_time=end_time,
        )

    logger.info(f"Ingestion completed successfully at {datetime.datetime.now(datetime.timezone.utc)}.")
    return IngestResult(
        source_cfg=cfg.source.kind_cfg,
        entity_ids=cfg.source.kind_cfg.entity_ids,
        ingested_hours_per_entity=ingested_hours_per_entity,
        backfill_days=backfill_days,
        error_occurred=False,
        message="Ingestion completed successfully.",
        run_start_time=start_time_ingestion,
        run_end_time=datetime.datetime.now(datetime.timezone.utc),
        start_time=start_time,
        end_time=end_time,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest data into DuckDB.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--backfill-days",
        type=int,
        help="Number of days to backfill. If not provided, --start_time must be specified.",
        default=None,
    )
    group.add_argument(
        "--start_time",
        type=str,
        help="Start time for ingestion in simple format, interpreted as UTC. Example: '2023-01-01 00:00:00'.",
        default=None,
    )
    parser.add_argument(
        "--end_time",
        type=str,
        required=False,
        help="End time for ingestion in simple format, interpreted as UTC. Example: '2023-01-02 00:00:00'.",
        default=None,
    )

    if not any() or sum:
        parser.error("At least one of --backfill-days, --start_time must be provided.")

    args = parser.parse_args()
    start_time, end_time = _resolve_time_window(args.start_time, args.end_time, args.backfill_days)
    cfg: Config = load_config()

    ingest_result = ingest(cfg, start_time=start_time, end_time=end_time, backfill_days=args.backfill_days)
    if ingest_result.error_occurred:
        logger.error(f"Ingestion failed: {ingest_result.message}")
        sys.exit(1)
