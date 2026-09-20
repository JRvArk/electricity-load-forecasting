import pandas as pd
import pytest

from forecaster.config import SyntheticCfg
from forecaster.ingestion.sources.synthetic import create_synthetic_data


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
    synthetic_data = create_synthetic_data(
        synthetic_cfg=synthetic_cfg,
        backfill_days=days,
        timestamp_column_name=timestamp_column_name,
        target_column_name=target_column_name,
    )
    assert synthetic_data.reset_index(drop=False).isna().sum().sum() == 0  # No null values in the DataFrame


def test_create_synthetic_data_columns(
    synthetic_cfg: SyntheticCfg, days: int, timestamp_column_name: str, target_column_name: str
) -> None:
    synthetic_data = create_synthetic_data(
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
    synthetic_data = create_synthetic_data(
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
    assert create_synthetic_data(
        synthetic_cfg=synthetic_cfg,
        backfill_days=days_for_determinism,
        timestamp_column_name=timestamp_column_name,
        target_column_name=target_column_name,
    ).equals(
        create_synthetic_data(
            synthetic_cfg=synthetic_cfg,
            backfill_days=days_for_determinism,
            timestamp_column_name=timestamp_column_name,
            target_column_name=target_column_name,
        )
    )  # Should produce the same output for the same input
