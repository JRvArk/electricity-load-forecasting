# tests/ — yours to write

This is where your tests go. At rung 3 the workflow for every phase is:

  1. Read the target properties in the module docstring (and the done-criterion
     in CLAUDE.md).
  2. Write the tests HERE that pin those properties — before you implement.
  3. Implement until green.
  4. Diff against reference/ (your tests AND your code).

`pyproject.toml` already points pytest at this directory with the right
pythonpath, so `pytest` just works once you add files.
