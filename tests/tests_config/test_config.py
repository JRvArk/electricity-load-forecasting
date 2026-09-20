import copy
import traceback

import pytest
import yaml
from pydantic import ValidationError

from forecaster.config import DEFAULT_CONFIG_PATH, Config, load_config


@pytest.fixture(scope="session")
def committed_cfg():
    return load_config(DEFAULT_CONFIG_PATH)


@pytest.fixture(scope="session")
def committed_raw() -> dict:
    """The tracked config as a plain dict, so a test can break one key at a time."""
    with open(DEFAULT_CONFIG_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _with(raw: dict, dotted: str, value) -> dict:
    """A deep copy of `raw` with the key at `dotted` set to `value`."""
    out = copy.deepcopy(raw)
    *parents, leaf = dotted.split(".")
    node = out
    for key in parents:
        node = node[key]
    node[leaf] = value
    return out


def test_synthetic_entity_length(committed_cfg):
    assert len(committed_cfg.source.synthetic.entity_ids) >= 2


# The following test is such that CI and local test suite are red when
# the source is not deterministic in config.yaml.
def test_config_source(cfg):
    assert cfg.source.kind_cfg.kind == "synthetic"


def test_committed_config_validates(committed_raw):
    Config(**committed_raw)


SYNTH = ("source", "synthetic")
ENTSOE = ("source", "entsoe")
NL_ZONE = "10YNL----------L"

# Each case breaks one key of the committed config and names the location the
# error must be reported at. A field validator reports at the field; a model
# validator (two fields that must differ, a holdout shorter than the horizon)
# reports at the model, so those locations are one segment shorter.
REJECTED = [
    pytest.param("domain.frequency", "0.5h", ("domain", "frequency"), id="frequency-half-hour"),
    pytest.param("domain.frequency", "h", ("domain", "frequency"), id="frequency-bare-unit"),
    pytest.param("domain.frequency", "60min", ("domain", "frequency"), id="frequency-other-spelling"),
    pytest.param("domain.target_column", "load mw", ("domain", "target_column"), id="column-with-space"),
    pytest.param("domain.entity_column", "1st", ("domain", "entity_column"), id="column-leading-digit"),
    pytest.param("domain.target_column", "ts", ("domain",), id="columns-collide"),
    pytest.param("domain.name", "", ("domain", "name"), id="empty-domain-name"),
    pytest.param("source.synthetic.entity_ids", ["a", "a"], SYNTH + ("entity_ids",), id="synthetic-duplicate-ids"),
    pytest.param("source.synthetic.entity_ids", [], SYNTH + ("entity_ids",), id="synthetic-no-ids"),
    pytest.param("source.synthetic.entity_ids", ["a", ""], SYNTH + ("entity_ids", 1), id="synthetic-empty-id"),
    pytest.param("source.synthetic.noise_sd", -1.0, SYNTH + ("noise_sd",), id="negative-noise"),
    pytest.param("source.synthetic.seed", -1, SYNTH + ("seed",), id="negative-seed"),
    pytest.param("source.entsoe.entity_ids", [NL_ZONE, NL_ZONE], ENTSOE + ("entity_ids",), id="entsoe-duplicate-ids"),
    pytest.param("source.entsoe.api_key_env", "not a name", ENTSOE + ("api_key_env",), id="env-var-with-spaces"),
    pytest.param("storage.raw_table", "raw-observations", ("storage", "raw_table"), id="table-with-dash"),
    pytest.param("storage.feature_table", "raw_observations", ("storage",), id="tables-collide"),
    pytest.param("storage.duckdb_path", "", ("storage", "duckdb_path"), id="empty-db-path"),
    pytest.param("features.lags", [0, 1], ("features", "lags", 0), id="lag-zero"),
    pytest.param("features.lags", [1, -24], ("features", "lags", 1), id="lag-negative"),
    pytest.param("features.lags", [1, 1], ("features", "lags"), id="lag-duplicate"),
    pytest.param("features.rolling_windows", [24, 24], ("features", "rolling_windows"), id="window-duplicate"),
    pytest.param("features.holidays_country", "Netherlands", ("features", "holidays_country"), id="country-not-a-code"),
    pytest.param("training.horizon_hours", 0, ("training", "horizon_hours"), id="horizon-zero"),
    pytest.param("training.test_horizon_hours", 12, ("training",), id="holdout-shorter-than-horizon"),
    pytest.param("training.model", "xgboost", ("training", "model"), id="unknown-model"),
    pytest.param("training.primary_metric", "mape", ("training", "primary_metric"), id="unknown-metric"),
    pytest.param("training.random_state", -1, ("training", "random_state"), id="negative-random-state"),
    pytest.param("registry.production_stage", "production", ("registry", "production_stage"), id="stage-lowercase"),
    pytest.param("registry.model_name", "", ("registry", "model_name"), id="empty-model-name"),
    pytest.param("monitoring.drift_threshold", 1.5, ("monitoring", "drift_threshold"), id="threshold-above-one"),
    pytest.param("monitoring.drift_threshold", -0.1, ("monitoring", "drift_threshold"), id="threshold-negative"),
    pytest.param("monitoring.current_window_hours", 0, ("monitoring", "current_window_hours"), id="window-zero"),
    pytest.param("mlflow.experiment", "", ("mlflow", "experiment"), id="empty-experiment"),
    pytest.param("monitoring.drift_treshold", 0.5, ("monitoring", "drift_treshold"), id="unread-key-is-refused"),
]


@pytest.mark.parametrize("dotted, value, where", REJECTED)
def test_rejected_at_load(committed_raw, dotted, value, where):
    with pytest.raises(ValidationError) as excinfo:
        Config(**_with(committed_raw, dotted, value))
    locations = [tuple(err["loc"]) for err in excinfo.value.errors()]
    assert where in locations, f"expected an error at {where}, got {locations}"


# Values that look wrong at a glance but are legitimate, so a stricter validator
# added later has to argue with a test.
ACCEPTED = [
    pytest.param("features.lags", [], id="no-lag-features"),
    pytest.param("features.rolling_windows", [], id="no-rolling-features"),
    pytest.param("source.synthetic.entity_ids", ["only_one"], id="one-synthetic-entity"),
    pytest.param("source.synthetic.base_load", -5.0, id="negative-base-load"),
    pytest.param("source.synthetic.seed", 0, id="seed-zero"),
    pytest.param("training.test_horizon_hours", 24, id="holdout-equals-horizon"),
    pytest.param("monitoring.drift_threshold", 0.0, id="threshold-zero"),
    pytest.param("monitoring.drift_threshold", 1.0, id="threshold-one"),
    pytest.param("registry.production_stage", "Staging", id="stage-staging"),
    pytest.param("storage.duckdb_path", ":memory:", id="in-memory-db"),
]


@pytest.mark.parametrize("dotted, value", ACCEPTED)
def test_accepted_at_load(committed_raw, dotted, value):
    Config(**_with(committed_raw, dotted, value))


def test_pasted_token_is_refused_and_never_echoed(committed_raw):
    """LEARNINGS.md L1: the value of a credential must not reach a log by any
    route. A token pasted where the variable's *name* belongs is the likeliest
    way for one to reach the validation error, and the error is what gets
    logged.

    `hide_input_in_errors` scrubs every *rendered* form — `str`, `repr`, a
    traceback, a logger. The *structured* forms, `errors()` and `json()`, still
    carry the input unless asked not to; anything that serialises them (a run
    record, a JSON log) must pass `include_input=False`. Both halves are pinned.
    """
    token = "3f2a9c1e-7b4d-4e8a-9c2f-SECRET0000001"
    with pytest.raises(ValidationError) as excinfo:
        Config(**_with(committed_raw, "source.entsoe.api_key_env", token))
    err = excinfo.value

    rendered = str(err) + repr(err) + traceback.format_exception(err)[-1]
    assert token not in rendered
    assert "NAME" in str(err), "the message should say what the field is for"

    assert token not in repr(err.errors(include_input=False))
    assert token not in err.json(include_input=False)
    # The default structured forms are NOT safe; this is the trap, pinned so a
    # pydantic upgrade that changes it is noticed either way.
    assert token in repr(err.errors())
