# Next steps

The ordered front of the work: **at most ten entries, one line each**, in the order their
dependencies allow, each pointing at the entry that holds the detail — a `D<n>` in
`DEFECTS.md`, a decision in `BUILD_PLAN.md`, a learning. This file holds *sequence*, never
content: if an entry needs a second sentence, the sentence belongs in one of the four logs and
the entry here is drifting from it.

**Scope** is the current pass, to the current done-criterion. The roadmap is `BUILD_PLAN.md`;
what is in flight is `git log -1`. **Done entries are deleted**, not struck — history lives in
git and in `DEFECTS.md`, and the value of this file is that it stays short. Kept current by the
session that lands a step, in the same commit; the human maintains none of it. Read at session
open, after `git log -1`.

---

## Phase 1 pass — done when: ingest twice over one window leaves the count unchanged, and re-ingesting a corrected value overwrites it, on the synthetic source

1. **Suite collects** — quarantine `test_build.py` with a module-level skip naming D9/D21 (the
   only module left that does not import). Target: `pytest` exits 0 with `tests_config` green and
   every ingest module collecting; today it is 63 collected, 1 collection error.
2. **`resolve_window`** — `VALID`/`REFUSED` tables first (fixed `NOW`, the `+02:00` and `+05:30`
   rows), then the function in `ingest.py`, the CLI thin over it, and the window blocks deleted
   from both sources. Closes D23; decide the `(–, end, N)` row beside decision E. Unblocks 3–7.
3. **`conftest.py` fixtures** — `FORECASTER_DUCKDB_PATH=":memory:"` at module scope;
   `make_synthetic`, `fixed_window`, `synthetic_frame`, `tmp_cfg`; delete the six pre-L5 fixtures
   and `load_config_for_test` from `test_ingest.py`. Closes D21, D8. See L8.
4. **Generator** — the six tests in `test_synthetic.py` (overlap and half-open fail first), then
   the daily term and the noise become functions of the timestamp. Closes D1, D2.
5. **Conformance guard** — one hand-built malformed frame per clause, then: sort by
   `(entity, ts)`, per-entity diff against `pd.Timedelta(cfg.domain.frequency)`, a named
   exception. Closes D17 (contract half), D22 (exception half). See L7.
6. **`store_data`** — tests: a frame without the timestamp column raises; two entities stored,
   one re-stored, the other survives; reordered columns land correctly. Then the qualified
   subquery, the `(ts, entity)` key, one transaction, explicit column list. Closes D18, D20, D6, D5.
7. **`ingest()` and `IngestResult`** — resolved half-open window and rows per entity; the
   conformance exception caught separately; `abs_path` on the DuckDB path. Its test *is* the
   done-criterion above. Closes D22, D4.
8. **ENTSO-E adapter** — fake client raising each of decision G's exceptions; one recorded frame
   (responses only, L1). Then index → column, entity column from config, two frames with the
   forecast routed to `raw_tso_table`, `PaginationError` split. Closes D25, D26, D17
   (translation). Last, and time-boxed hardest: the box allotted Phase 1 no hours.
9. **Out** — strike each defect with its commit; the README's "upsert on the timestamp key";
   `config.yaml`'s `frequency` and TSO "column" comments; the status block; push.
