"""Typed config loading. Fully implemented — this is the spine everything reads.

`config/config.yaml` is the single source of truth for anything domain-specific.
No other module should hardcode dataset names, column names, or paths.

Values arrive in three layers, in increasing precedence:

1. **The file** — shape and defaults: columns, feature spec, horizon, thresholds.
   Identical in every environment, because a model trained against a different
   feature spec is not comparable to the incumbent it is meant to beat.
2. **A local overlay** — `config/local.yaml`, gitignored and optional, deep-merged
   over the file when it exists. This is where a working copy says "same system,
   but pointed at the live source", without editing a tracked file that everyone
   else and CI also read. It is inert exactly where it must be: being gitignored,
   it does not exist in a fresh clone, so it cannot make CI reach the network.
3. **The environment** — the few values that genuinely differ between a laptop, a
   container and a scheduled unit: where the database is, where MLflow is. See
   `_ENV_OVERRIDES`; the list is deliberately short, and *what the system is* is
   not on it — an environment variable can be set by a parent process, so it is
   the wrong place for anything that changes what the run means.
4. **The caller** — `load_config(path=...)`, or `$FORECASTER_CONFIG`, naming a
   config explicitly. Naming a file means meaning it, so an explicit config
   **skips the overlay** rather than being merged with someone's local state.

Secrets are in none of them: config carries the *name* of the variable holding a
credential, never the credential, so no dump of this object can leak one.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

logger = logging.getLogger(__name__)

#: Points at the config file to load, overriding discovery.
ENV_CONFIG_PATH = "FORECASTER_CONFIG"
#: Base for `Config.abs_path`, when the checkout layout cannot supply one.
ENV_PROJECT_ROOT = "FORECASTER_PROJECT_ROOT"

#: The only keys the environment may override, mapped to their path in the
#: config tree. Kept short on purpose: a config where anything can be overridden
#: from the environment is a config you can no longer read to know what ran.
#:
#: Both entries below are the same system on a different machine. `source.kind`
#: is deliberately absent — it is what the system *is*, and an environment that
#: could flip it could turn an offline test run into a live one from outside the
#: repo, silently, against hard convention 3. Use `$FORECASTER_CONFIG` instead.
_ENV_OVERRIDES: dict[str, tuple[str, ...]] = {
    "FORECASTER_DUCKDB_PATH": ("storage", "duckdb_path"),
    "FORECASTER_MLFLOW_TRACKING_URI": ("mlflow", "tracking_uri"),
}

#: The checkout layout: <repo>/config/config.yaml, a sibling of src/.
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
#: An optional, gitignored overlay beside the config it modifies.
_LOCAL_OVERLAY_NAME = "local.yaml"
#: The copy built into the wheel, for installs that are not a checkout.
_PACKAGED_CONFIG_NAME = "_default_config.yaml"


def _packaged_config_path() -> Path | None:
    """The config shipped inside the installed package, if there is one."""
    try:
        resource = files("forecaster") / _PACKAGED_CONFIG_NAME
        return Path(str(resource)) if resource.is_file() else None
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        return None


def default_config_path() -> Path:
    """Where the config comes from when the caller does not say.

    The checkout wins over the packaged copy so that editing `config/config.yaml`
    during development does what you expect; the packaged copy exists so that an
    install which is not a checkout — a slim image, a cluster — still runs.
    """
    from_env = os.environ.get(ENV_CONFIG_PATH)
    if from_env:
        return Path(from_env).expanduser().resolve()
    if _DEFAULT_CONFIG_PATH.is_file():
        return _DEFAULT_CONFIG_PATH
    packaged = _packaged_config_path()
    if packaged is not None:
        return packaged
    raise FileNotFoundError(
        f"no config file: {_DEFAULT_CONFIG_PATH} does not exist, no {_PACKAGED_CONFIG_NAME} "
        f"is packaged, and ${ENV_CONFIG_PATH} is unset"
    )


class DomainCfg(BaseModel):
    name: str
    target_column: str
    timestamp_column: str
    #: Names the column that distinguishes one series from another in the raw
    #: table. The schema is long: adding a series adds rows, never columns.
    entity_column: str
    frequency: str


class SyntheticCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["synthetic"] = "synthetic"
    #: One generated series per id. Keep at least two in any config the tests
    #: use: a grouping bug is invisible with a single group.
    entity_ids: list[str] = Field(min_length=1)
    base_load: float
    daily_amplitude: float
    weekly_amplitude: float
    noise_sd: float
    seed: int


class EntsoeCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["entsoe"] = "entsoe"
    #: Bidding zone codes. A list, never a bare string — `list("10YNL...")`
    #: silently yields sixteen single-character codes.
    entity_ids: list[str] = Field(min_length=1)
    #: The *name* of the environment variable holding the API key, never the key.
    #: Works identically under systemd, Docker and any cluster's secret store.
    api_key_env: str
    include_tso_forecast: bool = True


AnySourceCfg = SyntheticCfg | EntsoeCfg


class SourceCfg(BaseModel):
    """Every source block, always present and always validated; `kind` names the
    one in use.

    Holding all blocks rather than only the selected one means a typo in the
    ENTSO-E block fails at config load even on a synthetic run, instead of the
    first time someone flips `kind` — which, for the live source, is on the box
    rather than at a desk. Each block also carries its own `kind` tag, so
    `kind_cfg` is a discriminated union and branching on `kind_cfg.kind` narrows
    it to a concrete type.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["synthetic", "entsoe"]
    synthetic: SyntheticCfg
    entsoe: EntsoeCfg

    @property
    def kind_cfg(self) -> AnySourceCfg:
        """The block named by `kind`. Union-typed on purpose: branch on
        `kind_cfg.kind` to narrow it, or read `.synthetic` / `.entsoe` directly
        in code that has already branched."""
        return getattr(self, self.kind)

    @model_validator(mode="after")
    def _blocks_match_their_names(self) -> "SourceCfg":
        """A block reachable under one name but tagged another would let `kind`
        and the config it selects disagree — the failure this shape exists to
        make impossible. Guards against adding a field by copy-paste."""
        for name in type(self).model_fields:
            if name == "kind":
                continue
            block = getattr(self, name)
            if block.kind != name:
                raise ValueError(
                    f"source block {name!r} is a {type(block).__name__} tagged "
                    f"{block.kind!r}; the field name and the tag must agree"
                )
        return self


class StorageCfg(BaseModel):
    duckdb_path: str
    raw_table: str
    #: The TSO's published forecast lands in its own table rather than as a
    #: column on the raw table: a forecast is not an observation, and toggling
    #: it must not change the raw table's schema.
    raw_tso_table: str
    feature_table: str


class FeaturesCfg(BaseModel):
    lags: list[int]
    rolling_windows: list[int]
    calendar: bool
    holidays_country: str


class TrainingCfg(BaseModel):
    horizon_hours: int
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
    #: The file this object was loaded from. Provenance, so a run can report
    #: which config produced it rather than which config was expected.
    config_path: Path | None = None
    #: The overlay merged over `config_path`, when one applied. Recorded so a run
    #: says it was in play, rather than leaving someone to wonder why the numbers
    #: moved on one machine and not another.
    config_overlay: Path | None = None

    def abs_path(self, relative: str) -> Path:
        """Resolve a config-relative path against the project root."""
        return (self.project_root / relative).resolve()


def _overlay_for(cfg_path: Path) -> Path | None:
    """The local overlay beside `cfg_path`, if the working copy has one."""
    candidate = cfg_path.parent / _LOCAL_OVERLAY_NAME
    return candidate if candidate.is_file() else None


def _deep_merge(base: dict, over: dict) -> dict:
    """Merge `over` into a copy of `base`.

    Mappings merge key by key, so an overlay naming `source.kind` does not take
    the sibling source blocks with it. Everything else — scalars, and lists —
    replaces wholesale: a merged list is never what anyone meant, and a config
    whose lists half-merge is worse than one that cannot express the change.
    """
    merged = dict(base)
    for key, value in over.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def _apply_env_overrides(raw: dict) -> None:
    """Write allowlisted environment values into the raw tree, before validation.

    Before, not after, so an override is type-checked like any other config value
    and a bad one fails at load with the same message a bad file would give.
    """
    for env_name, keys in _ENV_OVERRIDES.items():
        value = os.environ.get(env_name)
        if value is None:
            continue
        node = raw
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value
        logger.info("config: %s overrides %s", env_name, ".".join(keys))


def _project_root_for(cfg_path: Path) -> Path:
    """The base `abs_path` resolves against.

    Derived from the file actually loaded, not from the default path, so a config
    loaded from elsewhere resolves its relative paths relative to itself. A
    packaged config has no checkout above it, so that case needs the environment
    or falls back to the working directory.
    """
    from_env = os.environ.get(ENV_PROJECT_ROOT)
    if from_env:
        return Path(from_env).expanduser().resolve()
    packaged = _packaged_config_path()
    if packaged is not None and cfg_path == packaged:
        logger.info("config: packaged config, resolving relative paths against the cwd")
        return Path.cwd()
    return cfg_path.parents[1]


def _env_snapshot() -> tuple[tuple[str, str], ...]:
    """The environment values that affect the result, for the cache key."""
    names = (ENV_CONFIG_PATH, ENV_PROJECT_ROOT, *_ENV_OVERRIDES)
    return tuple((name, os.environ[name]) for name in names if name in os.environ)


@lru_cache(maxsize=8)
def _load_config_cached(
    cfg_path: Path,
    overlay_path: Path | None,
    _mtime_ns: int,
    _overlay_mtime_ns: int,
    _env: tuple[tuple[str, str], ...],
) -> Config:
    """Do not delete the unread parameters.

    `_mtime_ns`, `_overlay_mtime_ns` and `_env` are never read in this body. They
    are here to be part of `lru_cache`'s key: the cached object must be
    invalidated when either file changes on disk or when an override in the
    environment changes, and the key is the only place that can express it. Drop
    them and the cache returns a config that is stale against its own file —
    which is the defect this replaced, and it fails silently.
    """
    with cfg_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if overlay_path is not None:
        with overlay_path.open("r", encoding="utf-8") as fh:
            raw = _deep_merge(raw, yaml.safe_load(fh) or {})
        logger.info("config: overlay applied from %s", overlay_path)
    _apply_env_overrides(raw)
    raw.setdefault("project_root", _project_root_for(cfg_path))
    raw.setdefault("config_path", cfg_path)
    raw.setdefault("config_overlay", overlay_path)
    return Config(**raw)


def load_config(path: str | Path | None = None) -> Config:
    """Load and validate the config, applying environment overrides.

    Cached on each file's path and modification time, so editing either between
    calls returns the edited config rather than a stale object — and on the
    environment, so a test that sets an override sees it.

    A config named explicitly, by argument or by `$FORECASTER_CONFIG`, is loaded
    as given: no overlay is merged over it.
    """
    named = path is not None or ENV_CONFIG_PATH in os.environ
    cfg_path = Path(path).expanduser().resolve() if path else default_config_path()
    overlay = None if named else _overlay_for(cfg_path)
    return _load_config_cached(
        cfg_path,
        overlay,
        cfg_path.stat().st_mtime_ns,
        overlay.stat().st_mtime_ns if overlay else 0,
        _env_snapshot(),
    )


load_config.cache_clear = _load_config_cached.cache_clear  # type: ignore[attr-defined]
