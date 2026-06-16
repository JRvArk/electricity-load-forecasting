"""Phase 2 — Training with experiment tracking.

Responsibility
    Train the commodity model on the feature table, evaluate it honestly, and log
    the run to MLflow. No model may exist outside a tracked run.

Target properties (write tests / checks for these first)
    - Honest split: evaluation is on a held-out tail of the series, never on data
      the model trained on, and the series order is preserved (no shuffling).
    - Reproducible: the same config + data produces the same metrics.
    - Fully logged: params, the holdout metric(s), and enough to identify the
      exact feature spec used (e.g. a hash of the feature config) all land in the
      MLflow run, plus the model artifact itself.

Done criterion
    Two runs are visible and comparable in the MLflow UI.

Workflow (rung 3): design the interface, decide what to assert, implement to
green, then diff against reference/.

Reminder: a plain HistGradientBoostingRegressor is the right model. If you reach
for something fancier, you've drifted from the goal.
"""

from forecaster.config import Config, load_config  # noqa: F401

# TODO(rung-3): design and implement.
# Make this module runnable as:  python -m forecaster.training.train
