"""Phase 3 — Serving.

Responsibility
    Expose the current Production model over HTTP. The framework requires you to
    expose a FastAPI application object named `app` (so it runs under
    `uvicorn forecaster.serving.app:app`). Everything else — request/response
    shape, how you hold model state — you design.

Target behaviour (write tests for these first)
    - Health: a health endpoint reports liveness and whether a model is loaded.
    - Predict: a predict endpoint returns a forecast for a feature row, and
      returns a clean error (not a crash) when no Production model exists yet.
    - Reload: the running service can pick up a newly promoted model WITHOUT a
      restart or redeploy. This is the crux of the Phase 3 done criterion.

Done criterion
    Promote a new version, hit reload, and predictions change — no restart.

Workflow (rung 3): design the API, write tests (the cold-start "no model -> clean
error" and the reload behaviour are the ones worth pinning), implement to green,
then diff against reference/.
"""

from forecaster.config import load_config  # noqa: F401

# TODO(rung-3): design and implement. Must expose a FastAPI `app`.
