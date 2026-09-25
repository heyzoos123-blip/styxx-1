# PREREG — protocol v5e: minted identity, stack-anchor attribution, and an exam that must see every refusal

Fathom Lab · 2026-09-24 · frozen before the v5e implementation exists. The spec is
`DESIGN_protocol_v5e_mint_anchor_2026_09_24.md` (committed at `bc4353e9`); the panel that produced
it is `protocol_v5e_design_panel.json`; the exam's brief is `DESIGN_protocol_v5e_exam_brief_2026_09_24.md`.

FROZEN_RUNNER_SHA256: ef4b4f668bca0b8f72b500dd103d0318786f7e5fc2916b1250f9926287ea3f52
FROZEN_MUTATION_GATE_SHA256: bd7769125fe836c7df6d031f1b6dbe189fc52f87158b067ac4aee23781546e72
FROZEN_RUN_PROTOCOL_V5_SHA256: 02a8286efc2217bec6ba4d788b701d6170d87f039b85934fa7763792919dc003
FROZEN_RUN_P1_SHA256: 656eb5ad047ea44eb63fdf10af83bd0947a18f1b84363c1a55576ffc0c81736d
FROZEN_P1_PREREG_SHA256: ef0f12f4426b31f17b7e82f85a8a872657a076c16dc8a6f7e0929524b45ddaeb
FROZEN_P1_RESULT_SHA256: 3b252f1dd2d61db12bbbbf1e9ff5b62efa1b6e528a0a2ca378972624801ce73b
FROZEN_POWER_QUARANTINED_SHA256: 00eacad5eadf50a80ebc16cd77417421e8c95966cd7609d0afe70964395227be
FROZEN_CORPUS_PROVENANCE_RESCORE_SHA256: 0646caf89813815d0f36f83a1cb2832e657ea426532cca387759c305e7e1d118
FROZEN_V5D_RESULT_SHA256: 26422974b8aae027286b41f48e32519f890b96973805a564b6819ceb8aaedfb4
FROZEN_V5D_PREREG_SHA256: 1e579f582a448fc9d715d87eb0ac71ec8dacd0a01b00a4e6bacc599396cb694d

## Why a redesign and not a fourth patch

Three red-team rounds against protocol v5 (`protocol_v5_redteam_audit.json`, rounds 1-3) closed every
instance they were shown and re-entered the same two classes by another door each time:

- **Target identity.** "Did the declared function run" was judged from code objects, which Python shares and
  re-instantiates through closures, factories, decorators with and without `functools.wraps`, clones and
  copies. Round 3's factory product passed because a frame cannot see default arguments.
- **Call attribution.** "Did it run inside this gate's section" leaked through threads, pools, asyncio tasks
  and context copies. Round 3's asyncio consumer passed because a copied ContextVar opened nothing.

A panel of three designers and two judges scored three redesigns against every finding of all three rounds.
Both judges chose the same design, and two of the three designers reached its identity primitive
independently. We verified that primitive ourselves on Python 3.10, 3.11, 3.12 and 3.13 before accepting it.

## What v5e is

**Identity by minting.** At trace entry each declared function gets a fresh code object,
`F.__code__ = F.__code__.replace()`, restored at exit. A frame counts for T iff it runs that exact object with
T's globals. Every route of rounds 1-3 into this class runs a *different* code object, so the class closes by
construction rather than by enumeration.

**Attribution by stack anchor.** Sections are calls (`cov.run`, `cov.run_async`). A call is credited to an
opening only if that opening's frame is on the call's own live `f_back` chain, before asyncio's dispatch frame.
No inherited state is ever read.

The spec states five residuals rather than claiming them closed (L-WHERE, L-CLONE, L-STUB, L-CACHE,
L-RUNTIME), and the exam pins each one's outcome so that a change in it is visible.

## What is frozen here, and what is new

**The exam runner and every file it depends on** are hashed above: the runner, the mutation gate, the corpus
differential, P1's committed harness, prereg and receipt, the quarantined module, the corpus census, and
the committed v5d receipt and prereg that X95 reads. The runner checks them against the lines above AS
FIRST COMMITTED, requires this file to be unchanged since, and uses git to require that this commit is an
ancestor of the first commit whose `styxx/protocol.py` carries the v5e tracer id.
Round 3 froze only the runner; its auditor pointed out that the retro and the differential also depended on
files the freeze did not cover.

**The exam must see every coded emission of an implementation that does not exist yet.** `mutation_gate.py`
deletes each refusal, recorded problem and note of the implementation in turn, and G6 requires the frozen exam
to detect every one. G7 requires every refusal to carry its complete literal code, so none can hide from the
mutator. Rounds 2 and 3 each found, by hand and after scoring, refusals no case exercised. The gate's positive
control on v5d (`mutation_gate_control_v5d.json`) found, mechanically, exactly the survivor round 3 found by
hand. This inverts the usual order: the implementation is constrained by the exam, not the other way round.

**Every hazard sweep carries a mutant that proves the sweep can see its hazard** (G9, G11). A sweep that
cannot detect a hang proves nothing by not finding one.

**The corpus differential includes the six nested-metrics receipts** under the frozen rule the erratum
(`ERRATUM_v5_hand_scored_claim_2026_09_24.md`) promised: exactly the results listed as `reproduced` in the
committed `corpus_provenance_rescore.json` are scored on their `metrics` dict. G4's bar is therefore 39, not 33.

## The exam as frozen

`run_protocol_v5e.py` was written by an independent author from the spec and the brief, attacked by two
reviewers (spec coverage; mutation against the design prototype), and revised: 155 violation cases,
36 valid cases, 11 pinned residuals, and three hazard sweeps each with a detection mutant. The reviewers
raised 5 blockers and 12 defects; every one was fixed or rejected with evidence. Against the reviewers'
107 mutants of the prototype, every one is detected except one equivalent mutant (removing the explicit
last-close hook removal, which the hook's own self-removal makes redundant). Dry runs against the
prototype passed on 3.10, 3.11, 3.12 and 3.13, except two cases where the prototype departs from the
spec (the NOT_EXERCISED message lacks the spec's fixed sentence); the exam follows the spec.

Stated before the implementation is written:
- **H1 reaches only deadlocks the implementation's own allocations can trigger.** A lock shared only by
  `_close` and the hook gives no hang against the prototype, so it would not be detected; the brief's
  original fresh-lock mutant is equivalent (CPython never re-enters a profile function).
- **The provenance walk's exact bound is not tested**: 2 hops are accepted and 17 refused, so "16 hops"
  and "16 links" both pass.
- **The spec's mutation-audit table was wrong in two rows**, found by the author and a reviewer:
  emptying `_by_code` at exit could not be seen by the listed case (X71c was added and sees it), and
  last-close removal is an equivalent mutant.

## What the exam assumes of the implementation, beyond the spec's prose

1. `Experiment._check_coverage` returns `{declared target: union count}`, and `Verdict.coverage`
   carries it per gate. Valid and residual cases compare it; it is the only place "union over
   openings" is visible.
2. Like `_hook`, the registries (`_MINTED`, `_BY_FN`, `_ANCHORS`, `_THREADS`) are module globals that
   the machinery reaches by global name at call time. X71c rebinds `_ANCHORS` for one `__exit__`.
3. `__exit__` empties `_by_code` before its first access to `_ANCHORS`, as the spec orders it.
4. `_STOP` is a plain module global the hook reads on every call event (the aux fuzzer's control sets it
   to None), and `_ACTIVE` is an int.
5. Every coded emission carries its complete literal code at the site that emits it (G7).

## Disclosed before any number exists

- **A prototype exists.** The design panel wrote a scratch prototype (not committed) to test the spec, and the
  exam's author dry-ran the exam against a shim of it to find plumbing bugs, following the spec wherever the two
  disagreed and logging each disagreement. The implementation that will be scored is written after this
  freeze, in `styxx/protocol.py`, and is not the prototype.
- **An exam case found wrong at dry run is not edited.** A corrected runner needs a new prereg with new frozen
  hashes, and the wrong case is published beside it, as v5c's `profile.runcall` case was.
- **Git proves order of commits, not order of writing.** This prereg's commit precedes the implementation's;
  nothing in the repository can prove the implementation was not drafted earlier. The prototype is the only
  implementation-like artefact that existed at freeze, and it is disclosed above.
- **Refusal deletion is a floor.** G6 cannot generate the non-refusal mutants rounds 2 and 3 also found (a
  dropped `gc.collect`, a hook reset on one exit path). Those remain the red team's job, and the spec's
  mutation-audit table lists the semantic mutants round 4 must run.

## What the winning branch licenses

`PROCEED_TO_RED_TEAM_ROUND_4__not_yet_shippable` licenses exactly that. Round 4 runs as a loop: attackers with
separate lenses (identity, attribution, hook lifecycle, cross-version, exam mutation), every finding reproduced
by an independent verifier before it counts, rounds repeating until one comes back empty. No shipping claim is
made before that loop ends, and no release is cut in this session.

## Stated limits

Everything in the spec's "Stated limits" and "Over-blocking, disclosed" sections, and everything carried from
attempts A and B, v5c and v5d: exercised is not tested; the trace is runner-written; declared gates only;
hardcoded values out of scope; child processes invisible.

```gates
{
 "gates": {
  "G_EXAM_FROZEN": {
   "metric": "exam_frozen",
   "op": ">=",
   "value": 1.0,
   "power_basis": "boolean identity of the runner and of every exam dependency against the sha256 values frozen in this document; anything else means the cases or their inputs could have been tuned after the freeze",
   "metric_means": "1.0 iff the sha256 of run_protocol_v5e.py and of each FROZEN_*_SHA256 file equals the value frozen here"
  },
  "G0_violations_refused_for_their_reason": {
   "metric": "frac_violation_cases_refused_with_expected_code",
   "op": ">=",
   "value": 1.0,
   "power_basis": "each violation case names its expected code in advance and is isolated so no other rule can decide it; below 1.0 means a violation reached a verdict, crashed, left state behind, or refused for another reason",
   "metric_means": "fraction of violation cases whose outcome is a refusal whose message begins with the case's expected [V5:CODE], with no leftover state",
   "exercises": [
    "styxx.protocol:Experiment._check_coverage",
    "styxx.protocol:_resolve_target",
    "styxx.protocol:_CoverageTracer._open",
    "styxx.protocol:_CoverageTracer.__exit__"
   ]
  },
  "G1_valid_cases_exact": {
   "metric": "frac_valid_cases_exact",
   "op": ">=",
   "value": 1.0,
   "power_basis": "valid cases satisfy the spec exactly and state their union counts, notes and ends in advance; a refusal is over-blocking and a wrong count means the property was not what passed",
   "metric_means": "fraction of valid cases that scored PASS with exactly the listed union counts, notes and ends, and no leftover state",
   "exercises": [
    "styxx.protocol:Experiment._check_coverage",
    "styxx.protocol:_CoverageTracer._open",
    "styxx.protocol:_CoverageTracer.record"
   ]
  },
  "G2_p1_retro_exact": {
   "metric": "p1_retro_exact",
   "op": ">=",
   "value": 1.0,
   "power_basis": "every previous v5 exam and every design prototype on 3.10-3.13 recorded exactly {styxx.power:reachable: 12} for P1's committed harness run unmodified; anything else means the retro did not test what it names",
   "metric_means": "1.0 iff P1's G4 with a v5 declaration refuses [V5:NOT_EXERCISED], its section records exactly {styxx.power:reachable: 12}, and the other four declared functions are named",
   "exercises": [
    "run_p1:degenerate"
   ]
  },
  "G3_no_v4_v5_disagreement": {
   "metric": "n_v4_v5_outcome_disagreements",
   "op": "<=",
   "value": 0,
   "power_basis": "v5e adds only keys no committed prereg uses; any disagreement with pinned v4 (98a5c368) over the pairable committed results, nested metrics dicts included per the frozen rule, is v5e changing what a frozen document means",
   "metric_means": "count of pairable committed results (with the six nested-metrics receipts scored on their metrics dict) whose outcome differs between pinned v4 and v5e"
  },
  "G4_population_reached": {
   "metric": "n_results_v5_scored",
   "op": ">=",
   "value": 39,
   "power_basis": "corpus_provenance_rescore.json measured 33 whole-receipt verdicts plus 6 nested-metrics verdicts; fewer means the differential's population shrank",
   "metric_means": "number of pairable committed results on which v5e returned a verdict"
  },
  "G5_residuals_as_documented": {
   "metric": "frac_residuals_as_documented",
   "op": ">=",
   "value": 1.0,
   "power_basis": "each documented residual (L-WHERE, L-CLONE, L-STUB, L-CACHE, L-RUNTIME, the P1 G1 companion) has a pinned outcome; a changed outcome is a spec change, not a pass or a fail",
   "metric_means": "fraction of residual cases whose outcome equals the documented outcome",
   "exercises": [
    "styxx.protocol:_CoverageTracer._open"
   ]
  },
  "G6_mutation_every_emission_observable": {
   "metric": "mutation_frac_detected",
   "op": ">=",
   "value": 1.0,
   "power_basis": "mutation_gate.py (frozen here) deletes every coded emission of the implementation one at a time; the implementation is written after this freeze, so it must contain no refusal, recorded problem or note the frozen exam cannot see. Its positive control on v5d found exactly the survivor round 3 found by hand",
   "metric_means": "fraction of coded-emission-deletion mutants detected by this exam in --mutation-mode (0.0 if the unmutated baseline is not clean)"
  },
  "G7_mutation_hygiene": {
   "metric": "mutation_hygiene_violations",
   "op": "<=",
   "value": 0,
   "power_basis": "a refusal whose message is not a literal complete code is invisible to the mutator; zero is achievable by writing each refusal with its own literal code",
   "metric_means": "count of GateSpecError raises in the v5 region whose message the mutator cannot see"
  },
  "G8_h1_no_hang": {
   "metric": "h1_hangs",
   "op": "<=",
   "value": 0,
   "power_basis": "round 3 deadlocked the v5d hook on 3.10/3.11 through a finalizer; the spec's hook and record() take no lock",
   "metric_means": "number of H1 sweep points (gen-0 thresholds 1-40 at _open, _close, record, the hook and __exit__) that hung past the watchdog"
  },
  "G9_h1_sweep_can_see_a_hang": {
   "metric": "h1_mutant_detected",
   "op": ">=",
   "value": 1,
   "power_basis": "a sweep that cannot detect the defect it sweeps for proves nothing; the H1 mutant takes a non-reentrant lock in the hook",
   "metric_means": "1 iff the H1 sweep run against the lock-taking hook mutant detected at least one hang"
  },
  "G10_h2_signal_exceptions_propagate": {
   "metric": "h2_propagated",
   "op": ">=",
   "value": 20,
   "power_basis": "round 3 lost signal-handler timeouts in 10-16 of 20 trials to an except Exception in the hook; the spec's hook has no handler",
   "metric_means": "number of 20 SIGALRM Timeout trials in which the exception reached the harness and the gate scored PASS"
  },
  "G11_h2_sweep_can_see_swallowing": {
   "metric": "h2_mutant_detected",
   "op": ">=",
   "value": 1,
   "power_basis": "the H2 mutant wraps the hook in except Exception; the sweep must see propagation drop below 20/20",
   "metric_means": "1 iff the H2 sweep run against the swallowing mutant saw fewer than 20 of 20 propagated"
  },
  "G12_h3_keyboard_interrupt": {
   "metric": "h3_ok",
   "op": ">=",
   "value": 5,
   "power_basis": "KeyboardInterrupt from a signal must reach the harness and leave no hook behind",
   "metric_means": "number of 5 trials in which KeyboardInterrupt propagated and no styxx hook remained installed"
  },
  "G13_no_crash": {
   "metric": "n_crashes",
   "op": "<=",
   "value": 0,
   "power_basis": "a crash inside a case is neither a pass nor a refusal; every case of the dry runs against the prototype completed",
   "metric_means": "count of cases (any family) whose run raised something other than the exam's own outcome, or hit the watchdog"
  }
 },
 "outcomes": [
  {
   "when": {
    "G_EXAM_FROZEN": false
   },
   "verdict": "INVALID__exam_not_the_frozen_exam"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": false
   },
   "verdict": "DO_NOT_SHIP__v5e_rewrites_frozen_history"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": false
   },
   "verdict": "INVALID__differential_population_shrank"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": true,
    "G7_mutation_hygiene": false
   },
   "verdict": "DO_NOT_SHIP__a_refusal_the_mutator_cannot_see"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": true,
    "G7_mutation_hygiene": true,
    "G13_no_crash": false
   },
   "verdict": "DO_NOT_SHIP__a_case_crashed"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": true,
    "G7_mutation_hygiene": true,
    "G13_no_crash": true,
    "G0_violations_refused_for_their_reason": false
   },
   "verdict": "DO_NOT_SHIP__a_violation_passed_or_refused_for_the_wrong_reason"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": true,
    "G7_mutation_hygiene": true,
    "G13_no_crash": true,
    "G0_violations_refused_for_their_reason": true,
    "G2_p1_retro_exact": false
   },
   "verdict": "DO_NOT_SHIP__misses_the_real_defect_it_was_built_for"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": true,
    "G7_mutation_hygiene": true,
    "G13_no_crash": true,
    "G0_violations_refused_for_their_reason": true,
    "G2_p1_retro_exact": true,
    "G5_residuals_as_documented": false
   },
   "verdict": "INVALID__a_documented_residual_changed__spec_change_needed"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": true,
    "G7_mutation_hygiene": true,
    "G13_no_crash": true,
    "G0_violations_refused_for_their_reason": true,
    "G2_p1_retro_exact": true,
    "G5_residuals_as_documented": true,
    "G6_mutation_every_emission_observable": false
   },
   "verdict": "DO_NOT_SHIP__the_exam_is_blind_to_a_coded_emission"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": true,
    "G7_mutation_hygiene": true,
    "G13_no_crash": true,
    "G0_violations_refused_for_their_reason": true,
    "G2_p1_retro_exact": true,
    "G5_residuals_as_documented": true,
    "G6_mutation_every_emission_observable": true,
    "G8_h1_no_hang": false
   },
   "verdict": "DO_NOT_SHIP__the_hook_can_hang"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": true,
    "G7_mutation_hygiene": true,
    "G13_no_crash": true,
    "G0_violations_refused_for_their_reason": true,
    "G2_p1_retro_exact": true,
    "G5_residuals_as_documented": true,
    "G6_mutation_every_emission_observable": true,
    "G8_h1_no_hang": true,
    "G9_h1_sweep_can_see_a_hang": false
   },
   "verdict": "INVALID__the_hang_sweep_cannot_see_a_hang"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": true,
    "G7_mutation_hygiene": true,
    "G13_no_crash": true,
    "G0_violations_refused_for_their_reason": true,
    "G2_p1_retro_exact": true,
    "G5_residuals_as_documented": true,
    "G6_mutation_every_emission_observable": true,
    "G8_h1_no_hang": true,
    "G9_h1_sweep_can_see_a_hang": true,
    "G10_h2_signal_exceptions_propagate": false
   },
   "verdict": "DO_NOT_SHIP__the_hook_swallows_exceptions"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": true,
    "G7_mutation_hygiene": true,
    "G13_no_crash": true,
    "G0_violations_refused_for_their_reason": true,
    "G2_p1_retro_exact": true,
    "G5_residuals_as_documented": true,
    "G6_mutation_every_emission_observable": true,
    "G8_h1_no_hang": true,
    "G9_h1_sweep_can_see_a_hang": true,
    "G10_h2_signal_exceptions_propagate": true,
    "G11_h2_sweep_can_see_swallowing": false
   },
   "verdict": "INVALID__the_swallow_sweep_cannot_see_swallowing"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": true,
    "G7_mutation_hygiene": true,
    "G13_no_crash": true,
    "G0_violations_refused_for_their_reason": true,
    "G2_p1_retro_exact": true,
    "G5_residuals_as_documented": true,
    "G6_mutation_every_emission_observable": true,
    "G8_h1_no_hang": true,
    "G9_h1_sweep_can_see_a_hang": true,
    "G10_h2_signal_exceptions_propagate": true,
    "G11_h2_sweep_can_see_swallowing": true,
    "G12_h3_keyboard_interrupt": false
   },
   "verdict": "DO_NOT_SHIP__keyboard_interrupt_mishandled"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": true,
    "G7_mutation_hygiene": true,
    "G13_no_crash": true,
    "G0_violations_refused_for_their_reason": true,
    "G2_p1_retro_exact": true,
    "G5_residuals_as_documented": true,
    "G6_mutation_every_emission_observable": true,
    "G8_h1_no_hang": true,
    "G9_h1_sweep_can_see_a_hang": true,
    "G10_h2_signal_exceptions_propagate": true,
    "G11_h2_sweep_can_see_swallowing": true,
    "G12_h3_keyboard_interrupt": true,
    "G1_valid_cases_exact": false
   },
   "verdict": "DO_NOT_SHIP__overblocks_or_miscounts_valid_harnesses"
  },
  {
   "when": {
    "G_EXAM_FROZEN": true,
    "G3_no_v4_v5_disagreement": true,
    "G4_population_reached": true,
    "G7_mutation_hygiene": true,
    "G13_no_crash": true,
    "G0_violations_refused_for_their_reason": true,
    "G2_p1_retro_exact": true,
    "G5_residuals_as_documented": true,
    "G6_mutation_every_emission_observable": true,
    "G8_h1_no_hang": true,
    "G9_h1_sweep_can_see_a_hang": true,
    "G10_h2_signal_exceptions_propagate": true,
    "G11_h2_sweep_can_see_swallowing": true,
    "G12_h3_keyboard_interrupt": true,
    "G1_valid_cases_exact": true
   },
   "verdict": "PROCEED_TO_RED_TEAM_ROUND_4__not_yet_shippable"
  }
 ],
 "smoke_verdict": "INVALID__smoke_plumbing_only"
}
```
