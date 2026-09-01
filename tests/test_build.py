from forecaster.ingestion.ingest import _create_synthetic_data
import pytest
import duckdb
import pandas as pd

from forecaster.features.build import (
    build_features,
    retrieve_data,
    persist_features,
    _compute_lag,
    _compute_rolling_window,
    _compute_holiday_feature,
)
from forecaster.config import SyntheticCfg, load_config


# === Fixtures ===


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def db_connection():
    conn = duckdb.connect()
    yield conn
    conn.close()


@pytest.fixture
def timestamp_column_name(cfg):
    return cfg.domain.timestamp_column


@pytest.fixture
def target_column_name(cfg):
    return cfg.domain.target_column


@pytest.fixture(params=[1, 7, 90])
def days(request):
    return request.param


@pytest.fixture
def synthetic_data(days: int, timestamp_column_name: str, target_column_name: str) -> pd.DataFrame:
    synthetic_cfg = SyntheticCfg(base_load=100, daily_amplitude=50, weekly_amplitude=20, noise_sd=10, seed=42)
    return _create_synthetic_data(
        synthetic_cfg=synthetic_cfg,
        backfill_days=days,
        timestamp_column_name=timestamp_column_name,
        target_column_name=target_column_name,
    )


@pytest.fixture
def cfg_lags(cfg):
    lags = cfg.features.lags
    return lags


# ===== Test build features =====


def test_build_features(synthetic_data: pd.DataFrame, cfg_lags: list):
    pass


# ===== Test retrieve data =====


def test_retrieve_data_nonempty(db_connection: duckdb.DuckDBPyConnection) -> None:
    with db_connection as conn:
        df = retrieve_data(conn)
        assert not df.empty


def test_retrieve_data_columns(
    db_connection: duckdb.DuckDBPyConnection, timestamp_column_name: str, target_column_name: str
) -> None:
    with db_connection as conn:
        df = retrieve_data(conn)
        assert set(df.columns) == {timestamp_column_name, target_column_name} or set(df.columns) == {
            target_column_name,
            timestamp_column_name,
        }


def test_retrieve_data_timestamp_dtype(db_connection: duckdb.DuckDBPyConnection, timestamp_column_name: str) -> None:
    with db_connection as conn:
        df = retrieve_data(conn)
        assert pd.api.types.is_datetime64_any_dtype(df[timestamp_column_name])


def test_retrieve_data_timestamp_sorted(db_connection: duckdb.DuckDBPyConnection, timestamp_column_name: str) -> None:
    with db_connection as conn:
        df = retrieve_data(conn)
        assert df[timestamp_column_name].is_monotonic_increasing


def test_retrieve_data_no_duplicates(db_connection: duckdb.DuckDBPyConnection, timestamp_column_name: str) -> None:
    with db_connection as conn:
        df = retrieve_data(conn)
        assert df[timestamp_column_name].is_unique


def test_retrieve_data_no_missing_values(db_connection: duckdb.DuckDBPyConnection) -> None:
    with db_connection as conn:
        df = retrieve_data(conn)
        assert not df.isnull().values.any()


def test_retrieve_data_target_dtype(db_connection: duckdb.DuckDBPyConnection, target_column_name: str) -> None:
    with db_connection as conn:
        df = retrieve_data(conn)
        assert df[target_column_name].dtype in [float, int]


# ==== Test persist features =====


# ==== Test compute lag =====
def test_compute_lag(synthetic_data: pd.DataFrame, cfg_lags: list, target_column_name: str) -> None:
    for lag in cfg_lags:
        lagged_df = _compute_lag(synthetic_data, lag)
        assert f"lag_{lag}" in lagged_df.columns
        assert lagged_df[f"lag_{lag}"].isnull().sum() == lag
        assert (lagged_df[f"lag_{lag}"].iloc[lag:] == synthetic_data[target_column_name].iloc[:-lag]).all()


# === Test compute rolling window =====


# === Test compute holiday feature =====
