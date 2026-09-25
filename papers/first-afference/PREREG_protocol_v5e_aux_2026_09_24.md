# PREREG — protocol v5e, auxiliary gates: the rule on random programs, two implementations, four Pythons

Fathom Lab · 2026-09-24 · frozen in the same commit as `PREREG_protocol_v5e_mint_anchor_2026_09_24.md`,
before the v5e implementation exists. Scored by `aux_v5e.py`.

FROZEN_AUX_SHA256: 99283b8b26240371f25102efa164477ba3f646b141920b602d889b25c2b068b6
FROZEN_FUZZER_SHA256: 29a371c54cc98c2d52174228b6b01bbac109fd21317a9a7ef5e63b28ef86c89b
FROZEN_RUNNER_SHA256: ef4b4f668bca0b8f72b500dd103d0318786f7e5fc2916b1250f9926287ea3f52

## Why a second prereg

The main exam checks one implementation against hand-written cases. Three questions it cannot answer are
answered here, each by a frozen harness:

1. **Does the implementation follow the attribution RULE, or only the cases someone thought of?**
   `fuzz_v5e.py` runs 3000 seeded random harness programs (sections, raising sections, threads, parallel
   thread groups, pools, recursion, exceptions, generators, event loops run inside a segment, asyncio
   tasks, gather, to_thread, direct awaits, and decoys that share code with real targets). The generator
   places every call itself and computes the exact expected trace; the implementation must match it on
   every program and leave nothing behind.
2. **Can the fuzzer see a broken rule at all?** Its first version could not: against the design
   prototype with the dispatch cut removed it found 0 disagreements in 300 programs, because every event
   loop it generated ran at the top (`protocol_v5e_fuzz_controls.json`). The final version sees a missing
   cut (44/600), a credit rule that ignores the stack (245/600) and missing minting (600/600). Here the
   control runs against the REAL implementation: with `_STOP` disabled after each trace starts, the
   fuzzer must find disagreements (A4).
3. **Is the exam tuned to one implementation?** A second implementation, written after this freeze by a
   separate agent from the frozen spec alone, in its own git worktree at this commit, must pass the frozen
   exam, match the oracle, and produce normalized traces identical to the primary's on every program.
   Both implementations share the spec, which contains code sketches, so they are not independent of the
   spec's own errors; they are independent of each other's.

And **four Pythons**: the frozen exam's case outcomes must be identical on 3.10, 3.11, 3.12 and 3.13
outside the declared version-keyed cases, and the fuzzer must find nothing on any of them.

## Verdicts

A `SPEC_AMBIGUOUS__` or `EXAM_OR_SPEC_DEFECT__` verdict is a finding about the frozen artefacts, not about
either implementation, and is reported as such. Neither licenses editing the frozen exam or fuzzer; a
correction needs a new prereg.

```gates
{
 "gates": {
  "A_FROZEN": {
   "metric": "aux_frozen",
   "op": ">=",
   "value": 1.0,
   "power_basis": "boolean identity of aux_v5e.py, fuzz_v5e.py and run_protocol_v5e.py against the sha256 values frozen here",
   "metric_means": "1.0 iff all three files hash to their FROZEN_*_SHA256 values"
  },
  "A1_fuzz_population": {
   "metric": "fuzz_n_programs",
   "op": ">=",
   "value": 3000,
   "power_basis": "3000 seeded programs ran in about 5 s on the prototype; fewer means the rule was checked on less than was frozen",
   "metric_means": "number of seeded random harness programs run against the primary implementation"
  },
  "A2_fuzz_matches_oracle": {
   "metric": "fuzz_oracle_disagreements",
   "op": "<=",
   "value": 0,
   "power_basis": "the oracle is the frozen attribution rule computed from each program's structure; the design prototype matched it on every program; any disagreement is the implementation departing from the rule it was frozen to",
   "metric_means": "count of programs whose record differs from the oracle in any section's union counts, opening ends, problems or ambiguous counters"
  },
  "A3_fuzz_no_leftovers": {
   "metric": "fuzz_leftovers",
   "op": "<=",
   "value": 0,
   "power_basis": "after every program the profiler, the registries and every fixture's code object must be as they were; zero is what the spec's lifecycle promises",
   "metric_means": "count of programs after which any tracer state or minted code remained"
  },
  "A4_fuzz_sees_a_missing_cut": {
   "metric": "fuzz_control_no_cut_disagreements",
   "op": ">=",
   "value": 1,
   "power_basis": "the fuzzer's first version could not see a missing dispatch cut (protocol_v5e_fuzz_controls.json); a fuzzer that cannot see the defect proves nothing by not finding it",
   "metric_means": "count of programs that disagree with the oracle when the implementation's _STOP is disabled after each trace starts"
  },
  "A5_second_implementation_passes_the_exam": {
   "metric": "nversion_exam_clean",
   "op": ">=",
   "value": 1.0,
   "power_basis": "an exam tuned to one implementation would fail an independent one; a second implementation written from the frozen spec alone must pass every case, the residuals and the P1 retro",
   "metric_means": "1.0 iff the frozen exam, run in full against nversion_v5e/protocol_nv.py, passes every case with the retro exact and no crashes"
  },
  "A6_second_implementation_matches_oracle": {
   "metric": "nversion_fuzz_oracle_disagreements",
   "op": "<=",
   "value": 0,
   "power_basis": "the oracle does not depend on the implementation",
   "metric_means": "count of fuzz programs on which the second implementation's record differs from the oracle"
  },
  "A7_two_implementations_agree": {
   "metric": "nversion_trace_diffs",
   "op": "<=",
   "value": 0,
   "power_basis": "two independent implementations of one frozen spec should produce the same normalized traces; a difference is a spec ambiguity or a defect in one",
   "metric_means": "count of fuzz programs whose normalized traces (per-section openings, ends, note codes, problem codes) differ between the two implementations"
  },
  "A8_four_pythons": {
   "metric": "crossversion_n_versions",
   "op": ">=",
   "value": 4,
   "power_basis": "the spec claims identical behaviour on 3.10-3.13; all four interpreters exist in this environment",
   "metric_means": "number of Python versions on which the frozen exam produced case outcomes"
  },
  "A9_identical_across_pythons": {
   "metric": "crossversion_diffs",
   "op": "<=",
   "value": 0,
   "power_basis": "outside the declared version-keyed cases, the spec's behaviour is version-independent",
   "metric_means": "count of cases whose outcome differs between versions, plus fuzz oracle disagreements summed over the versions"
  }
 },
 "outcomes": [
  {
   "when": {
    "A_FROZEN": false
   },
   "verdict": "INVALID__aux_not_the_frozen_aux"
  },
  {
   "when": {
    "A_FROZEN": true,
    "A1_fuzz_population": false
   },
   "verdict": "INVALID__fuzz_population_short"
  },
  {
   "when": {
    "A_FROZEN": true,
    "A1_fuzz_population": true,
    "A4_fuzz_sees_a_missing_cut": false
   },
   "verdict": "INVALID__the_fuzzer_cannot_see_a_missing_cut"
  },
  {
   "when": {
    "A_FROZEN": true,
    "A1_fuzz_population": true,
    "A4_fuzz_sees_a_missing_cut": true,
    "A8_four_pythons": false
   },
   "verdict": "INVALID__fewer_than_four_pythons"
  },
  {
   "when": {
    "A_FROZEN": true,
    "A1_fuzz_population": true,
    "A4_fuzz_sees_a_missing_cut": true,
    "A8_four_pythons": true,
    "A2_fuzz_matches_oracle": false
   },
   "verdict": "DO_NOT_SHIP__the_implementation_departs_from_the_frozen_rule"
  },
  {
   "when": {
    "A_FROZEN": true,
    "A1_fuzz_population": true,
    "A4_fuzz_sees_a_missing_cut": true,
    "A8_four_pythons": true,
    "A2_fuzz_matches_oracle": true,
    "A3_fuzz_no_leftovers": false
   },
   "verdict": "DO_NOT_SHIP__state_left_behind"
  },
  {
   "when": {
    "A_FROZEN": true,
    "A1_fuzz_population": true,
    "A4_fuzz_sees_a_missing_cut": true,
    "A8_four_pythons": true,
    "A2_fuzz_matches_oracle": true,
    "A3_fuzz_no_leftovers": true,
    "A5_second_implementation_passes_the_exam": false
   },
   "verdict": "EXAM_OR_SPEC_DEFECT__an_independent_implementation_fails_the_exam"
  },
  {
   "when": {
    "A_FROZEN": true,
    "A1_fuzz_population": true,
    "A4_fuzz_sees_a_missing_cut": true,
    "A8_four_pythons": true,
    "A2_fuzz_matches_oracle": true,
    "A3_fuzz_no_leftovers": true,
    "A5_second_implementation_passes_the_exam": true,
    "A6_second_implementation_matches_oracle": false
   },
   "verdict": "EXAM_OR_SPEC_DEFECT__an_independent_implementation_departs_from_the_rule"
  },
  {
   "when": {
    "A_FROZEN": true,
    "A1_fuzz_population": true,
    "A4_fuzz_sees_a_missing_cut": true,
    "A8_four_pythons": true,
    "A2_fuzz_matches_oracle": true,
    "A3_fuzz_no_leftovers": true,
    "A5_second_implementation_passes_the_exam": true,
    "A6_second_implementation_matches_oracle": true,
    "A7_two_implementations_agree": false
   },
   "verdict": "SPEC_AMBIGUOUS__two_independent_implementations_disagree"
  },
  {
   "when": {
    "A_FROZEN": true,
    "A1_fuzz_population": true,
    "A4_fuzz_sees_a_missing_cut": true,
    "A8_four_pythons": true,
    "A2_fuzz_matches_oracle": true,
    "A3_fuzz_no_leftovers": true,
    "A5_second_implementation_passes_the_exam": true,
    "A6_second_implementation_matches_oracle": true,
    "A7_two_implementations_agree": true,
    "A9_identical_across_pythons": false
   },
   "verdict": "DO_NOT_SHIP__behaviour_depends_on_the_python_version"
  },
  {
   "when": {
    "A_FROZEN": true,
    "A1_fuzz_population": true,
    "A4_fuzz_sees_a_missing_cut": true,
    "A8_four_pythons": true,
    "A2_fuzz_matches_oracle": true,
    "A3_fuzz_no_leftovers": true,
    "A5_second_implementation_passes_the_exam": true,
    "A6_second_implementation_matches_oracle": true,
    "A7_two_implementations_agree": true,
    "A9_identical_across_pythons": true
   },
   "verdict": "PROCEED__the_rule_holds_for_two_implementations_on_four_pythons"
  }
 ],
 "smoke_verdict": "INVALID__smoke_plumbing_only"
}
```
