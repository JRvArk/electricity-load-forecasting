"""Typed config loading. Fully implemented — this is the spine everything reads.

`config/config.yaml` is the single source of truth for anything domain-specific.
No other module should hardcode dataset names, column names, or paths.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"


class DomainCfg(BaseModel):
    name: str
    target_column: str
    timestamp_column: str
    frequency: str


class SyntheticCfg(BaseModel):
    base_load: float
    daily_amplitude: float
    weekly_amplitude: float
    noise_sd: float
    seed: int


class EntsoeCfg(BaseModel):
    api_token_env: str
    area_code: str


class SourceCfg(BaseModel):
    kind: str
    synthetic: SyntheticCfg
    entsoe: EntsoeCfg


class StorageCfg(BaseModel):
    duckdb_path: str
    raw_table: str
    feature_table: str


class FeaturesCfg(BaseModel):
    lags: list[int]
    rolling_windows: list[int]
    calendar: bool
    holidays_country: str


class TrainingCfg(BaseModel):
    model: str
    test_horizon_hours: int
    primary_metric: str
    random_state: int


class RegistryCfg(BaseModel):
    model_name: str
    production_stage: str


class MonitoringCfg(BaseModel):
    reference_window_hours: int
    current_window_hours: int
    drift_threshold: float


class MlflowCfg(BaseModel):
    tracking_uri: str
    experiment: str


class Config(BaseModel):
    domain: DomainCfg
    source: SourceCfg
    storage: StorageCfg
    features: FeaturesCfg
    training: TrainingCfg
    registry: RegistryCfg
    monitoring: MonitoringCfg
    mlflow: MlflowCfg

    project_root: Path = Field(default_factory=lambda: _DEFAULT_CONFIG_PATH.parents[1])

    def abs_path(self, relative: str) -> Path:
        """Resolve a config-relative path against the project root."""
        return (self.project_root / relative).resolve()


@lru_cache(maxsize=1)
def load_config(path: str | Path | None = None) -> Config:
    cfg_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    with cfg_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return Config(**raw)
