import datetime

from pydantic import BaseModel

from forecaster.config import EntsoeCfg, SyntheticCfg


class IngestResult(BaseModel):
    source_cfg: SyntheticCfg | EntsoeCfg
    backfill_days: int
    error_occurred: bool
    message: str
    run_start_time: datetime.datetime
    run_end_time: datetime.datetime
    data_start_time: datetime.datetime | None
    data_end_time: datetime.datetime | None
