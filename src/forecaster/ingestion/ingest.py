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
import sys

import duckdb
import pandas as pd

from forecaster.config import Config, EntsoeCfg, SyntheticCfg, load_config  # noqa: F401  — you'll need these
from forecaster.ingestion.ingest_result import IngestResult
from forecaster.ingestion.sources.entsoe import retrieve_entsoe_data
from forecaster.ingestion.sources.synthetic import create_synthetic_data

logger = logging.getLogger(__name__)


def _parse_time_arg(time_str: str) -> datetime.datetime:
    """Parse a time argument in simple format, interpreted as UTC."""
    try:
        return datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid time format: {time_str}. Expected format: 'YYYY-MM-DD HH:MM:SS'.")


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
    table_name: str,
    timestamp_column_name: str,
) -> None:
    conn.register("incoming", data_df)
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM incoming WHERE 1=0")
    # delete-then-insert overlapping keys = idempotent upsert
    conn.execute(
        f"DELETE FROM {table_name} WHERE {timestamp_column_name} IN(SELECT {timestamp_column_name} FROM incoming)"
    )
    conn.execute(f"INSERT INTO {table_name} SELECT * FROM incoming")


def ingest(
    cfg: Config, start_time: datetime.datetime | None, end_time: datetime.datetime | None, backfill_days: int | None
) -> IngestResult:
    start_time_ingestion = datetime.datetime.now(datetime.timezone.utc)

    if start_time is None and end_time is None and backfill_days is None:
        raise ValueError("Either --start_time, --end_time, or --backfill-days must be specified.")

    arg_dict = {}
    for arg_name, arg_value in [("start_time", start_time), ("end_time", end_time), ("backfill_days", backfill_days)]:
        if arg_value is not None:
            arg_dict[arg_name] = arg_value

    try:
        data_df = load_data(cfg, **arg_dict)
        with duckdb.connect(cfg.storage.duckdb_path) as conn:
            store_data(conn, data_df, cfg.storage.raw_table, cfg.domain.timestamp_column)
        logger.info(f"Ingested {len(data_df)} rows into {cfg.storage.raw_table}.")
    except Exception as e:
        logger.error(f"Error occurred during ingestion: {e}")
        return IngestResult(
            source_cfg=cfg.source.kind_cfg,
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
    parser.add_argument(
        "--backfill-days",
        type=int,
        required=False,
        help="Number of days to backfill. If not provided, --start_time must be specified.",
        default=None,
    )
    parser.add_argument(
        "--start_time",
        type=str,
        required=False,
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
    if not any([arg in ["--backfill-days", "--start_time"] for arg in sys.argv]):
        parser.error("At least one of --backfill-days, --start_time must be provided.")
    args = parser.parse_args()

    if args.start_time:
        start_time = _parse_time_arg(args.start_time)
    else:
        start_time = None

    if args.end_time:
        end_time = _parse_time_arg(args.end_time)
    else:
        end_time = None

    cfg: Config = load_config()

    ingest_result = ingest(cfg, backfill_days=args.backfill_days, start_time=start_time, end_time=end_time)
    if ingest_result.error_occurred:
        logger.error(f"Ingestion failed: {ingest_result.message}")
        sys.exit(1)
