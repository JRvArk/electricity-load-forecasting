"""Phase 6 — Drift monitoring.

Responsibility
    Detect when the recent data has drifted far enough from a reference period
    that the Production model can no longer be trusted, and surface that as a
    signal the orchestration layer can act on.

Target properties (write tests for these first)
    - Windows come from config: reference vs current window sizes are
      cfg.monitoring.reference_window_hours / current_window_hours.
    - The drift decision is a threshold on a measurable quantity (e.g. share of
      drifted features), compared against cfg.monitoring.drift_threshold.
    - The output is a small, stable structure the orchestration flow can consume
      (a clear "should retrain" boolean plus the number behind it).

Done criterion
    Injecting drifted data into the store visibly flips the retrain signal.

BLOCKED until two decisions are made (BUILD_PLAN.md, Open decisions B and C):
    the loop-termination mechanism, and a drift_threshold value with a stated
    basis. 0.5 is a placeholder, and most features here are transforms of one
    series so they drift together. Both are inputs to the done criterion above.

Workflow (rung 3): design the interface, write tests with a clearly-drifted and a
clearly-stable fixture, implement to green. Note: there is NO reference for this
module — it was never implemented, so here you are fully on your own. Good.
"""

from forecaster.config import Config, load_config  # noqa: F401

# TODO(rung-3): design and implement using Evidently.
