import pytest

from forecaster.config import DEFAULT_CONFIG_PATH, load_config


@pytest.fixture(scope="session")
def committed_cfg():
    return load_config(DEFAULT_CONFIG_PATH)


def test_synthetic_entity_length(committed_cfg):
    assert len(committed_cfg.source.synthetic.entity_ids) >= 2


# The following test is such that CI and local test suite are red when
# the source is not deterministic in config.yaml.
def test_config_source(cfg):
    assert cfg.source.kind_cfg.kind == "synthetic"
