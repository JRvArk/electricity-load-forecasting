"""Phase 5 & 6 — Orchestration.

Responsibility
    Tie the stages into scheduled, repeatable runs. Plain Python callables,
    invoked by systemd timers — the scheduler stays thin, so an orchestrator
    later would be a wrapper rather than a rewrite. Two entry points:
      - run_retrain(): ingest -> features -> train -> gated promote
      - run_monitor(): check drift, and trigger a retrain when it fires
    Both append to a run-history table in DuckDB — (run_id, flow, started_at,
    ended_at, status, model_version, promoted, reject_reason, drift_share).
    That table is the loop-termination state AND the run history that a
    scheduler UI would otherwise have provided.

Target properties (write tests / checks for these first)
    - The retrain flow reuses the Phase 3 promotion gate, so a worse model can
      never reach Production through orchestration either.
    - The monitor flow only triggers a retrain when the drift signal says so.
    - A persistently drifted store does not retrain forever. Drift fires, the
      retrain loses to the incumbent, the gate rejects it, drift is still there
      next run — the cycle is sustained by the gate working correctly. Pick a
      cooldown, a drift acknowledgement, or escalation after k rejections, and
      test that the loop terminates.
    - Flows are idempotent at the step level (they lean on the Phase 1 upsert and
      the registry, not ad-hoc state).
    - Ingest retries with backoff on transient API failure. systemd will not do
      this for you and the source is a network API.

Done criteria
    Phase 5 — a deliberately bad retrain cannot reach Production.
    Phase 6 — injecting drifted data into the store fires a retrain.

Workflow (rung 3): you reach this only after Phases 1-3 exist, so wire it against
the interfaces YOU designed there. Design the flows, then diff against reference/.
"""

# TODO(rung-3): design and implement the pipelines + the run-history table.
