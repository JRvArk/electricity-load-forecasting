from datetime import datetime
import os
import pandas as pd
import pytest

from forecaster.config import DEFAULT_CONFIG_PATH, load_config
from forecaster.ingestion.sources.synthetic import create_synthetic_data

os.environ["FORECASTER_CONFIG"] = str(DEFAULT_CONFIG_PATH)
os.environ["FORECASTER_DUCKDB_PATH"] = ":memory:"  # Use in-memory DuckDB for testing


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(params=[3, 7, 90], scope="session")
def backfill_days(request) -> int:
    return request.param


@pytest.fixture(scope="session")
def target_column_name(cfg):
    return cfg.domain.target_column


@pytest.fixture(scope="session")
def timestamp_column_name(cfg):
    return cfg.domain.timestamp_column


@pytest.fixture(scope="session")
def obs_table_name(cfg):
    return cfg.storage.raw_table


@pytest.fixture(scope="session")
def tso_forecast_table_name(cfg):
    return cfg.storage.raw_tso_table


@pytest.fixture(scope="session")
def make_synthetic_data(cfg):
    def _make(start_time: datetime, end_time: datetime) -> pd.DataFrame:
        return create_synthetic_data(
            cfg=cfg,
            start_time=start_time,
            end_time=end_time,
        )

    return _make
