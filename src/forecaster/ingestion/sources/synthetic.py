import datetime

import numpy as np
import pandas as pd

from forecaster.config import Config


def create_synthetic_data(
    cfg: Config,
    start_time: datetime.datetime | None = None,
    end_time: datetime.datetime | None = None,
    backfill_days: int | None = None,
) -> pd.DataFrame:

    if start_time is None:
        if end_time is None:
            end_time = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
            start_time = end_time - datetime.timedelta(days=backfill_days)
        else:
            start_time = end_time - datetime.timedelta(days=backfill_days)
    else:
        if end_time is None:
            end_time = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)

    if not (len(cfg.source.kind_cfg.entity_ids) >= 2) or not isinstance(cfg.source.kind_cfg.entity_ids, list):
        raise ValueError("Synthetic data generation requires at least two entity IDs in a list.")

    synthetic_cfg = cfg.source.kind_cfg

    timestamps = pd.date_range(start=start_time, end=end_time, freq="1h", inclusive="left", tz="UTC")
    hours = np.arange(len(timestamps))

    randomly_generated_seeds = np.random.SeedSequence(synthetic_cfg.seed).spawn(len(cfg.source.kind_cfg.entity_ids))

    data = pd.DataFrame()
    for entity, seed in zip(cfg.source.kind_cfg.entity_ids, randomly_generated_seeds):
        temp_df = pd.DataFrame(
            {cfg.domain.entity_column: [entity] * len(timestamps), cfg.domain.timestamp_column: timestamps}
        )

        rng = np.random.default_rng(seed)

        daily = synthetic_cfg.daily_amplitude * np.sin(2 * np.pi * (hours % 24) / 24 - np.pi / 2)
        weekly = synthetic_cfg.weekly_amplitude * (((timestamps.dayofweek < 5).astype(float)) - 0.5) * 2
        noise = rng.normal(0.0, synthetic_cfg.noise_sd, size=len(timestamps))
        values = synthetic_cfg.base_load + daily + weekly + noise
        temp_df[cfg.domain.target_column] = values
        data = pd.concat([data, temp_df], axis=0, ignore_index=True)

    return data
