"""Phase 5 & 6 — Orchestration.

Responsibility
    Tie the stages into scheduled, repeatable runs with Prefect. Two flows:
      - a retrain flow: ingest -> features -> train -> gated promote
      - a monitor flow: check drift, and trigger the retrain flow when it fires

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

Done criteria
    Phase 5 — a deliberately bad retrain cannot reach Production.
    Phase 6 — injecting drifted data into the store fires a retrain.

Workflow (rung 3): you reach this only after Phases 1-3 exist, so wire it against
the interfaces YOU designed there. Design the flows, then diff against reference/.
"""

# TODO(rung-3): design and implement the Prefect flows.
