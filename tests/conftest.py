import os

import pytest

from forecaster.config import DEFAULT_CONFIG_PATH, load_config

os.environ["FORECASTER_CONFIG"] = str(DEFAULT_CONFIG_PATH)


@pytest.fixture(scope="session")
def cfg():
    return load_config()


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
