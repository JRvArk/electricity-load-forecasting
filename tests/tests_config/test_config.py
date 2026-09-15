from forecaster.config import load_config
from forecaster.config import DEFAULT_CONFIG_PATH
import pytest


def test_load_config_validates():
    cfg = load_config(path=DEFAULT_CONFIG_PATH)


@pytest.fixture
def cfg():
    return load_config(path=DEFAULT_CONFIG_PATH)


def test_synthetic_entity_length(cfg):
    assert len(cfg.source.synthetic.entity_ids) >= 2


# The following test is such that CI and local test suite are red when
# the source is not deterministic in config.yaml.
def test_config_source(cfg):
    assert cfg.source.kind_cfg.kind == "synthetic"
