import datetime

from pydantic import BaseModel

from forecaster.config import AnySourceCfg


class IngestResult(BaseModel):
    source_cfg: AnySourceCfg
    entity_ids: list[str] | str
    ingested_hours_per_entity: dict[str, int] | None
    start_time: datetime.datetime | None
    end_time: datetime.datetime | None
    backfill_days: int | None
    error_occurred: bool
    message: str
    run_start_time: datetime.datetime
    run_end_time: datetime.datetime
