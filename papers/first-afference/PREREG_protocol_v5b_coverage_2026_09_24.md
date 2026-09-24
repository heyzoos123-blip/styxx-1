# PREREG — protocol v5, attempt B: the same exam, with a corpus gate that measures what it names

Fathom Lab · 2026-09-24 · frozen after run 1 of `PREREG_protocol_v5_coverage_2026_09_24.md`
(`a98e4572`) and before run 2 of anything.

## What happened to attempt A

Attempt A's scored run (`protocol_v5_result_run1.json`, commit `b79e2c7d`) returned
**`DO_NOT_SHIP__v5_rewrites_frozen_history`**. G0 (24/24), G1 (9/9) and G2 (P1's G4 refused)
passed; G3 failed on exactly one corpus result, `disjoint-worlds/open_set_read_result.json`,
committed `VOID__null_mapper_separates` and re-scored `RAISED:GateSpecError`.

**That verdict stands and is not edited.** What it measured is recorded here, because the
successor gate depends on it:

- **v4 raises identically.** Upstream `styxx/protocol.py` at `98a5c368`, sha256 `45da869e…`,
  raises `GateSpecError: prereg has no ```gates block` on the same file. v5 did not cause the diff.
- **The file was never protocol-produced.** `run_open_set_read.py` writes
  `"prereg_commit": "45d7ae5"` as a literal and builds its own `gates` dict by hand; its prereg
  states its gates in prose. The corpus filter both the v4 and v5 exams used admits any result
  carrying the keys `prereg_commit` and `gates` — it read **the shape of a protocol receipt as
  protocol provenance**. The file was committed on 2026-09-01, after v4's exam ran, which is why
  v4's G3 never saw it.
- **The metric therefore measured the wrong population.** "Verdicts that differ when re-scored
  under v5" was meant as "verdicts v5 changes". Against a committed verdict that the protocol never
  produced, the two come apart, and this file is where they did.

This is the E1 shape again (a gate over the wrong population), recorded against the author of
this document.

## What changes, and what does not

- **The implementation does not change.** `styxx/protocol.py` must hash to
  `652dd0898570d04e9a4ad92e7fdd04d60e0ed5d5f130a49d060ed55ebda29a35` at run time — the exact bytes
  attempt A scored. The runner records the hash and G_IMPL refuses anything else.
- **G0, G1 and G2 are unchanged** in metric, bar, and declared coverage.
- **G3 is replaced by a differential that needs no provenance heuristic.** Every committed
  `papers/*/*_result.json` whose `prereg` field names a file that exists beside it is scored twice
  — by the pinned v4 implementation (loaded from `git show 98a5c368:styxx/protocol.py`, hash
  checked) and by v5 — and the two **outcomes** are compared. An outcome is the verdict string, or
  `RAISED:<ExceptionType>:<message>`. The population is now *every* pairable result, not the
  key-shape-filtered subset, so it is strictly larger than attempt A's. A result both versions
  refuse identically is agreement: v5 did not change what that document means.
- **The old measurement is still reported**, ungated: the count of results whose v5 outcome
  differs from the committed verdict string, and which ones, so the reader can see attempt A's
  number beside attempt B's.

The risk this introduces, stated before the number exists: a differential against v4 cannot see a
defect v4 and v5 share. That is the correct scope for "does v5 rewrite history", and the wrong one
for "is the corpus sound" — which this exam does not claim to measure.

```gates
{"gates": {"G_IMPL_unchanged": {"metric": "impl_matches_attempt_a", "op": ">=", "value": 1.0,
             "power_basis": "boolean identity check on the bytes attempt A scored; anything else would make attempt B an exam of a different instrument",
             "metric_means": "1.0 if sha256(styxx/protocol.py) at run time equals 652dd089..., else 0.0"},
           "G0_mutants_refused": {"metric": "frac_violation_mutants_refused", "op": ">=", "value": 1.0,
             "exercises": ["styxx.protocol:Experiment._check_coverage", "styxx.protocol:coverage_trace"],
             "power_basis": "unchanged from attempt A: each mutant is a code path the implementation controls completely",
             "metric_means": "fraction of constructed violation mutants on which the machinery raised rather than returned a verdict"},
           "G1_valid_still_scores": {"metric": "frac_valid_cases_scored", "op": ">=", "value": 1.0,
             "exercises": ["styxx.protocol:Experiment._check_coverage", "styxx.protocol:coverage_trace"],
             "power_basis": "unchanged from attempt A: valid cases satisfy their declarations exactly",
             "metric_means": "fraction of correct-declaration cases that scored without refusal"},
           "G2_p1_retro_refused": {"metric": "p1_retro_case_refused", "op": ">=", "value": 1.0,
             "power_basis": "unchanged from attempt A: P1's committed audit states its harness exercised only reachable()",
             "metric_means": "1.0 if P1's G4 with a v5 exercises declaration refuses against a traced re-run of run_p1.degenerate() on the quarantined module"},
           "G3_no_v4_v5_disagreement": {"metric": "n_v4_v5_outcome_disagreements", "op": "<=", "value": 0,
             "power_basis": "v5 adds only optional keys no committed prereg uses, so a correct implementation agrees with v4 on every document; any disagreement is v5 changing what a frozen document means",
             "metric_means": "count of pairable committed results whose outcome (verdict string or exception type+message) under pinned v4 differs from the outcome under v5"}},
 "outcomes": [{"when": {"G_IMPL_unchanged": false}, "verdict": "INVALID__not_the_instrument_attempt_a_scored"},
              {"when": {"G_IMPL_unchanged": true, "G3_no_v4_v5_disagreement": false}, "verdict": "DO_NOT_SHIP__v5_rewrites_frozen_history"},
              {"when": {"G_IMPL_unchanged": true, "G3_no_v4_v5_disagreement": true, "G0_mutants_refused": false}, "verdict": "DO_NOT_SHIP__an_unexercised_gate_reached_a_verdict"},
              {"when": {"G_IMPL_unchanged": true, "G3_no_v4_v5_disagreement": true, "G0_mutants_refused": true, "G2_p1_retro_refused": false}, "verdict": "DO_NOT_SHIP__misses_the_real_defect_it_was_built_for"},
              {"when": {"G_IMPL_unchanged": true, "G3_no_v4_v5_disagreement": true, "G0_mutants_refused": true, "G2_p1_retro_refused": true, "G1_valid_still_scores": false}, "verdict": "DO_NOT_SHIP__overblocks_valid_declarations"},
              {"when": {"G_IMPL_unchanged": true, "G3_no_v4_v5_disagreement": true, "G0_mutants_refused": true, "G2_p1_retro_refused": true, "G1_valid_still_scores": true}, "verdict": "PROCEED_TO_RED_TEAM__not_yet_shippable"}],
 "smoke_verdict": "INVALID__smoke_plumbing_only"}
```

## Unchanged from attempt A

The winning branch licenses a red team, not a release. Every stated limit in attempt A stands —
and one of them now has a real case: P1's G1, declared against `order_stat_bar`, is **not**
refused, because `reachable()` calls `order_stat_bar` once on the b48 case and discards its
influence on the flag. Exercised is not tested.
