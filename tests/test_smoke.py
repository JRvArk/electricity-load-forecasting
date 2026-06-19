"""Smoke test so CI has something to collect before any phase is built.

Exercises only `config.py` — the GIVEN plumbing spine, not a learning phase.
Replace/extend with real phase tests as you implement each module.
"""
from __future__ import annotations

from forecaster.config import load_config


def test_config_loads_and_defaults_to_synthetic() -> None:
    cfg = load_config()
    assert cfg.source.kind == "synthetic"
    assert cfg.domain.name
    assert cfg.source.eia.respondent
