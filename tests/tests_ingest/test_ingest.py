from pathlib import Path

import duckdb
import pandas as pd
import pytest
import yaml

from forecaster.config import DEFAULT_CONFIG_PATH, Config
from forecaster.ingestion.ingest import ingest, store_data
from forecaster.ingestion.ingest_result import IngestResult
from forecaster.ingestion.sources.synthetic import create_synthetic_data


# TO CONFTEST??
@pytest.fixture
def db_connection():
    conn = duckdb.connect()
    yield conn
    conn.close()


# =========================== store_data() tests ===========================


def test_store_data_row_count(
    db_connection: duckdb.DuckDBPyConnection,
    days: int,
    table_name: str,
    synthetic_data_fixture: pd.DataFrame,
    timestamp_column_name: str,
) -> None:
    data = synthetic_data_fixture
    store_data(
        conn=db_connection,
        data_df=data,
        table_name=table_name,
        timestamp_column_name=timestamp_column_name,
    )
    row_count = db_connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    assert row_count is not None
    row_count = row_count[0]
    assert row_count == days * 24


def test_store_data_idempotency(
    db_connection: duckdb.DuckDBPyConnection,
    table_name: str,
    synthetic_data_fixture: pd.DataFrame,
    timestamp_column_name: str,
) -> None:
    data = synthetic_data_fixture
    conn = db_connection
    store_data(
        conn=conn,
        data_df=data,
        table_name=table_name,
        timestamp_column_name=timestamp_column_name,
    )
    count_after_first = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    assert count_after_first is not None
    count_after_first = count_after_first[0]
    store_data(
        conn=db_connection,
        data_df=data,
        table_name=table_name,
        timestamp_column_name=timestamp_column_name,
    )
    count_after_second = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    assert count_after_second is not None
    count_after_second = count_after_second[0]
    assert count_after_second == count_after_first  # Should not increase after second ingestion


def test_store_data_integrity(
    db_connection: duckdb.DuckDBPyConnection,
    table_name: str,
    synthetic_data_fixture: pd.DataFrame,
    timestamp_column_name: str,
) -> None:
    data = synthetic_data_fixture
    store_data(
        conn=db_connection,
        data_df=data,
        table_name=table_name,
        timestamp_column_name=timestamp_column_name,
    )
    stored_data = db_connection.execute(f"SELECT * FROM {table_name}").fetchdf()
    pd.testing.assert_frame_equal(
        data.sort_values(timestamp_column_name).reset_index(drop=True),
        stored_data.sort_values(timestamp_column_name).reset_index(drop=True),
        check_like=True,
        check_dtype=False,
    )  # Allow for minor dtype differences


def test_store_data_consistency(
    db_connection: duckdb.DuckDBPyConnection,
    table_name: str,
    synthetic_data_fixture: pd.DataFrame,
    timestamp_column_name: str,
) -> None:
    data = synthetic_data_fixture
    store_data(
        conn=db_connection,
        data_df=data,
        table_name=table_name,
        timestamp_column_name=timestamp_column_name,
    )
    stored_data = db_connection.execute(f"SELECT * FROM {table_name}").fetchdf()
    assert (
        stored_data[timestamp_column_name].diff().dropna() > pd.Timedelta(0)
    ).all()  # Timestamps should be strictly increasing
    assert stored_data["load_mw"].notnull().all()


# =========================== ingest() tests ===========================


def test_ingest(cfg, backfill_days: int) -> None:
    ingest_result = ingest(cfg, backfill_days=backfill_days)
    assert isinstance(ingest_result, IngestResult)
