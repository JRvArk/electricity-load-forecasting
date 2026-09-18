import datetime

import pandas as pd
from entsoe.entsoe import EntsoePandasClient

from forecaster.config import Config


def retrieve_entsoe_data(
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

    start_pd = pd.Timestamp(start)
    end_pd = pd.Timestamp(end)

    assert cfg.source.kind_cfg.kind == "entsoe", "This function is only for ENTSO-E data retrieval."

    client = EntsoePandasClient(cfg.source.kind_cfg.api_key_env)
    data = pd.DataFrame()

    entity_ids_list = (
        cfg.source.kind_cfg.entity_ids
        if isinstance(cfg.source.kind_cfg.entity_ids, list)
        else [cfg.source.kind_cfg.entity_ids]
    )

    for entity in entity_ids_list:
        df = client.query_load(
            entity,
            start=start_pd,
            end=end_pd,
        )
        df.columns = [cfg.domain.target_column]  # Rename the column to the target column name
        df["entity_id_observed"] = entity  # Add a column to identify the entity
        data = pd.concat([data, df], axis=0)

    if cfg.source.kind_cfg.include_tso_forecast:
        for entity in list(entity_ids_list):
            df_forecast = client.query_load_forecast(
                entity,
                start=start_pd,
                end=end_pd,
            )
            df_forecast.columns = [cfg.domain.target_column]  # Rename the column to the target column name
            df_forecast["entity_id_tso_forecast"] = entity  # Add a column to identify the entity
            data = pd.concat([data, df_forecast], axis=0)

    return data
