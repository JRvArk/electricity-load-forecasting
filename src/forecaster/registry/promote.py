"""Phase 3 — Model registry + earned promotion.

Responsibility
    Register a tracked run's model in the MLflow registry, and promote it to the
    Production stage only when it earns the spot.

Target properties (write tests for these first)
    - Earned promotion: a challenger reaches Production only if it beats the
      current incumbent on the configured primary metric (lower is better).
    - Cold start: with no incumbent, the first acceptable model is promoted.
    - A worse model never displaces a better incumbent.

Done criterion
    Changing which version is Production changes served predictions with no code
    change and no redeploy.

Workflow (rung 3): design the interface, write tests pinning the gate logic
(this is the highest-value test in the project — make the "worse model is
rejected" case explicit), implement to green, then diff against reference/.
"""

from forecaster.config import Config, load_config  # noqa: F401

# TODO(rung-3): design and implement.
