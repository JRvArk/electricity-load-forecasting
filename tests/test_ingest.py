from pathlib import Path

import duckdb
import pandas as pd
import pytest
import yaml

from forecaster.config import _DEFAULT_CONFIG_PATH, Config, SyntheticCfg
from forecaster.ingestion.ingest import _create_synthetic_data, ingest, store_data
from forecaster.ingestion.ingest_result import IngestResult


@pytest.fixture(params=[1, 7, 90])
def days(request) -> int:
    return request.param


@pytest.fixture
def db_connection():
    conn = duckdb.connect()
    yield conn
    conn.close()


@pytest.fixture
def synthetic_cfg() -> SyntheticCfg:
    return SyntheticCfg(
        base_load=100, daily_amplitude=50, weekly_amplitude=20, noise_sd=10, seed=42
    )


@pytest.fixture
def table_name() -> str:
    return "raw_observations"


@pytest.fixture
def timestamp_column_name() -> str:
    return "ts"


@pytest.fixture
def target_column_name() -> str:
    return "load_mw"


@pytest.fixture
def synthetic_data_fixture(
    synthetic_cfg: SyntheticCfg, days: int, timestamp_column_name: str, target_column_name: str
) -> pd.DataFrame:
    return _create_synthetic_data(
        synthetic_cfg=synthetic_cfg,
        backfill_days=days,
        timestamp_column_name=timestamp_column_name,
        target_column_name=target_column_name,
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
    assert (
        synthetic_data.reset_index(drop=False).isna().sum().sum() == 0
    )  # No null values in the DataFrame


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
    row_count = db_connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    assert row_count == days * 24


def test_store_data_idempotency(
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
    count_after_first = db_connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    store_data(
        conn=db_connection,
        data_df=data,
        table_name=table_name,
        timestamp_column_name=timestamp_column_name,
    )
    count_after_second = db_connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
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
    cfg_path = path or _DEFAULT_CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    raw["storage"]["duckdb_path"] = ":memory:"  # Use in-memory DuckDB for tests
    source = raw["source"]["kind"]
    source_cfg = raw["source"][source]
    raw["source"] = {"kind": source, "source_cfg": source_cfg}
    return Config(**raw)
