import datetime

import numpy as np
import pandas as pd

from forecaster.config import Config


def create_synthetic_data(
    cfg: Config,
    start: datetime.datetime | None = None,
    end: datetime.datetime | None = None,
    backfill_days: int | None = None,
) -> pd.DataFrame:

    if start is None:
        assert backfill_days is not None, "If start is not specified, backfill_days must be provided."
        start = datetime.datetime.now(datetime.timezone.utc).replace(
            minute=0, second=0, microsecond=0
        ) - datetime.timedelta(days=backfill_days)

    assert (start.minute, start.second, start.microsecond) == (0, 0, 0), (
        "Start time must be at the beginning of an hour."
    )

    if end is None:
        end = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)

    assert (end.minute, end.second, end.microsecond) == (0, 0, 0), "End time must be at the beginning of an hour."

    assert cfg.source.kind_cfg.kind == "synthetic", "This function is only for synthetic data generation."
    synthetic_cfg = cfg.source.kind_cfg

    timestamps = pd.date_range(start=start, end=end, freq="1h", inclusive="both", tz="UTC")
    hours = np.arange(len(timestamps))
    rng = np.random.default_rng(synthetic_cfg.seed)

    daily = synthetic_cfg.daily_amplitude * np.sin(2 * np.pi * (hours % 24) / 24 - np.pi / 2)
    weekly = synthetic_cfg.weekly_amplitude * (((timestamps.dayofweek < 5).astype(float)) - 0.5) * 2
    noise = rng.normal(0.0, synthetic_cfg.noise_sd, size=len(timestamps))
    value = synthetic_cfg.base_load + daily + weekly + noise

    return pd.DataFrame(
        {
            cfg.domain.timestamp_column: timestamps,
            cfg.domain.target_column: value,
        }
    )
    pass
