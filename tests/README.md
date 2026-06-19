# tests/

Tests live here, written before the corresponding implementation — one of the
hard rules in this project (see `BUILD_PLAN.md`).

Per-phase loop: read the target properties in the module docstring, write tests
that pin them, implement until green, then diff against the reference solution.

`pyproject.toml` already points pytest at this directory with the right
pythonpath, so `pytest` just works.
