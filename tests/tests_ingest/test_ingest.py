from pathlib import Path

import duckdb
import pandas as pd
import pytest
import yaml

from forecaster.config import DEFAULT_CONFIG_PATH, Config, SyntheticCfg
from forecaster.ingestion.sources.synthetic import create_synthetic_data
from forecaster.ingestion.ingest import ingest, store_data
from forecaster.ingestion.ingest_result import IngestResult


# TO CONFTEST??
@pytest.fixture
def db_connection():
    conn = duckdb.connect()
    yield conn
    conn.close()


@pytest.fixture
def start_time_none() -> None:
    return None


@pytest.fixture
def end_time_none() -> None:
    return None


@pytest.fixture
def backfill_days_none() -> None:
    return None


@pytest.fixture(params=["2021-01-01 00:00:00", "2021-06-01 00:00:00", "2021-12-31 00:00:00"])
def start_time(request) -> str:
    return request.param


@pytest.fixture(params=["2021-01-02 00:00:00", "2021-06-02 00:00:00", "2022-01-01 00:00:00"])
def end_time(request) -> str:
    return request.param


@pytest.fixture(params=[3, 7, 90])
def backfill_days(request) -> int:
    return request.param


# @pytest.fixture
# def synthetic_cfg() -> SyntheticCfg:
#     return SyntheticCfg(base_load=100, daily_amplitude=50, weekly_amplitude=20, noise_sd=10, seed=42)


@pytest.mark.parametrize()
@pytest.fixture
def synthetic_data_fixture(cfg: Config, days: int) -> pd.DataFrame:
    """Fixture to create synthetic data for testing."""

    return create_synthetic_data(
        cfg=cfg,
        backfill_days=days,
    )


### FIX: every test function need not be parametrized


# ========================= _create_synthetic_data() tests ===========================


def test_create_synthetic_data_is_pd_df(
    synthetic_data_fixture: pd.DataFrame,
) -> None:
    synthetic_data = synthetic_data_fixture
    assert isinstance(synthetic_data, pd.DataFrame)


def test_create_synthetic_data_row_count(synthetic_data_fixture: pd.DataFrame, days: int) -> None:
    synthetic_data = synthetic_data_fixture
    expected_row_count = days * 24  # Assuming hourly data
    assert len(synthetic_data) == expected_row_count


def test_create_synthetic_data_non_null_values(
    synthetic_cfg: SyntheticCfg, days: int, timestamp_column_name: str, target_column_name: str
) -> None:
    synthetic_data = _create_synthetic_data(
        synthetic_cfg=synthetic_cfg,
        backfill_days=days,
        timestamp_column_name=timestamp_column_name,
        target_column_name=target_column_name,
    )
    assert synthetic_data.reset_index(drop=False).isna().sum().sum() == 0  # No null values in the DataFrame


def test_create_synthetic_data_columns(
    synthetic_cfg: SyntheticCfg, days: int, timestamp_column_name: str, target_column_name: str
) -> None:
    synthetic_data = _create_synthetic_data(
        synthetic_cfg=synthetic_cfg,
        backfill_days=days,
        timestamp_column_name=timestamp_column_name,
        target_column_name=target_column_name,
    )
    expected_columns = {timestamp_column_name, target_column_name}
    assert set(synthetic_data.columns) == expected_columns


def test_create_synthetic_data_ts_increasing(
    synthetic_cfg: SyntheticCfg, days: int, timestamp_column_name: str, target_column_name: str
) -> None:
    synthetic_data = _create_synthetic_data(
        synthetic_cfg=synthetic_cfg,
        backfill_days=days,
        timestamp_column_name=timestamp_column_name,
        target_column_name=target_column_name,
    )
    assert (
        synthetic_data[timestamp_column_name].diff().dropna() > pd.Timedelta(0)
    ).all()  # Timestamps should be strictly increasing


@pytest.mark.parametrize("days_for_determinism", [1, 7, 90])
def test_create_synthetic_data_determinism(
    synthetic_cfg: SyntheticCfg,
    days_for_determinism: int,
    timestamp_column_name: str,
    target_column_name: str,
) -> None:
    assert _create_synthetic_data(
        synthetic_cfg=synthetic_cfg,
        backfill_days=days_for_determinism,
        timestamp_column_name=timestamp_column_name,
        target_column_name=target_column_name,
    ).equals(
        _create_synthetic_data(
            synthetic_cfg=synthetic_cfg,
            backfill_days=days_for_determinism,
            timestamp_column_name=timestamp_column_name,
            target_column_name=target_column_name,
        )
    )  # Should produce the same output for the same input


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


def test_ingest(days: int) -> None:
    cfg = load_config_for_test()
    ingest_result = ingest(cfg, backfill_days=days)
    assert isinstance(ingest_result, IngestResult)


def load_config_for_test(path: str | Path | None = None) -> Config:
    """Load the configuration for testing purposes."""
    cfg_path = path or DEFAULT_CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    raw["storage"]["duckdb_path"] = ":memory:"  # Use in-memory DuckDB for tests
    return Config(**raw)
