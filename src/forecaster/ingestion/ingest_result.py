from pydantic import BaseModel
import datetime

from forecaster.config import SyntheticCfg, EiaCfg, EntsoeCfg


class IngestResult(BaseModel):
    source_cfg: SyntheticCfg | EiaCfg | EntsoeCfg
    backfill_days: int
    error_occurred: bool
    message: str
    run_start_time: datetime.datetime
    run_end_time: datetime.datetime
    data_start_time: datetime.datetime | None
    data_end_time: datetime.datetime | None
