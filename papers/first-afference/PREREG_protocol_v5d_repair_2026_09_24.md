# PREREG — protocol v5, round 3: the exam is frozen with the prereg, before the repair exists

Fathom Lab · 2026-09-24 · frozen after red-team round 2 (`protocol_v5_redteam_audit.json`,
key `round_2`) and before any round-3 change to `styxx/protocol.py`.

FROZEN_RUNNER_SHA256: ae6ac686c174435e3f0d7e5eca3af7fe24fa7df5a10240e05efbf6ab3a135a37

## What round 2 found

Round 2 ran after v5c scored `PROCEED_TO_RED_TEAM_ROUND_2` (`3bdd5a22`). Every round-1 blocker
held as tested — on Python 3.10, 3.11, 3.12 and 3.13 — and three new ones did not:

- **R2-B1.** The shared-code check ran once, at construction. A decorator without
  `functools.wraps` applied to a new function at runtime was credited as the declared function
  (`score_all never called -> VERDICT PASS`).
- **R2-B2.** A pool worker started in section A belonged to A for life, so while A and B were both
  open, B's pooled call was credited to A.
- **R2-B3.** Threads started during a trace kept an inert hook for the rest of their lives
  (8.2x slower profiled calls in a worker).

Plus defects: a target reached through an instance bypassed the INHERITED rule; two
`functools.wraps` siblings of one inner function stood in for each other; `ContextVar.reset` in a
foreign context escaped as `ValueError`; `check_metrics` on a non-dict raised; a hook dropped by a
RecursionError refused with the wrong reason and leaked the thread hook; several correct harness
shapes were refused without disclosure.

**The exam, mutation-tested with 53 mutants of the implementation, let five survive.** The
worst: counting a call after its section closed **failed open**, and no case could see it,
because the only closed-section case put its late call in a gate that never declared the
target. The others: non-string keys tested in one of three places; "check_metrics reports, never
raises" was a same-code shadow; alias targets untested; the parallel case deadlocked instead of
failing. **And the process defect that matters most here: the v5c cases were committed with the
implementation.** The spec was frozen; the exam was not.

## What is frozen here, and why it is different

**The exam runner `run_protocol_v5d.py` is committed in this same commit, and its sha256 is the
line above.** G_EXAM_FROZEN scores 1.0 only if the runner that produces the result is byte-identical
to it. The round-3 implementation is written after this commit, against cases it cannot change.

## The repairs, specified before they are written

| finding | repair | code |
|---|---|---|
| R2-B1 | on every hit of a target's code, the frame must be the declared function's: `f_globals` is its `__globals__` and each free variable is its closure's object; otherwise the call goes to an `impostors` bucket and counts for nothing. At every section close, garbage is collected and the holder check re-runs. | `SHARED_CODE` at close |
| R2-B2 | a call attributed through its thread's start section counts only while that is the ONLY open section; otherwise it goes to an `ambiguous` bucket. A context that opened its own section is unaffected. | — |
| R2-B3 | an exited tracer's hook removes itself from whatever thread next calls it; every exit path resets the threading hook if it is still this tracer's | — |
| R2-D1 | a qualname step from anything but a module or class refuses | `INSTANCE_PATH` |
| R2-D2 | an unwrapped function reachable from more than one `__wrapped__` wrapper refuses, at entry and at close | `SHARED_CODE` |
| R2-D6 | a section exited in a different Context refuses | `SECTION_CONTEXT` |
| R2-D6 | `check_metrics` on a non-dict reports instead of raising | — |
| R2-D4 | an exception inside the hook body is caught and the section refuses with its own code; the PROFILER_REPLACED message names the RecursionError route | `HOOK_FAILED` |
| exam | the late-call case, non-string keys in all three places, list sections, check_metrics raise-vs-report (a raise is a crash; exam-only sentinel `[V5:REPORTED]` for the non-dict report), alias targets, C profiler kept after refusal, threading-side foreign profiler, re-entering an exited tracer, forged undeclared key, non-ASCII target, grandchild thread, thread hook released after exit, barrier timeouts | — |

Nits also taken: `gc.collect()` before counting holders; `threading:Thread.start` can be
declared; `record()` carries section-close refusals.

## The exam

Unchanged in kind from v5c: a violation passes only by refusing with its own code; a valid case
only by scoring with exactly its named counts and leaving profilers as found; the P1 retro only
exact; the differential over every pairable result; the population at least 33. v5c's 46 violation
and 14 valid cases are carried over, and round 2 adds 25 violations and 2 valid cases.

```gates
{"gates": {"G_EXAM_FROZEN": {"metric": "exam_runner_frozen", "op": ">=", "value": 1.0,
             "power_basis": "boolean identity of the runner against the sha256 frozen in this document; anything else means the cases could have been tuned to the implementation, the round-2 process finding",
             "metric_means": "1.0 iff sha256(run_protocol_v5d.py) at run time equals FROZEN_RUNNER_SHA256 in this prereg"},
           "G0_mutants_refused_for_their_reason": {"metric": "frac_violation_mutants_refused_with_expected_code", "op": ">=", "value": 1.0,
             "exercises": ["styxx.protocol:Experiment._check_coverage", "styxx.protocol:_resolve_target", "styxx.protocol:_CoverageTracer.section", "styxx.protocol:_CoverageTracer.__exit__"],
             "power_basis": "each mutant names its expected code in advance and is isolated so no other check can catch it; below 1.0 means a violation reached a verdict, crashed, or refused for another reason",
             "metric_means": "fraction of violation mutants whose outcome is a GateSpecError whose message begins with the mutant's expected [V5:CODE]"},
           "G1_valid_cases_score_with_their_property": {"metric": "frac_valid_cases_scored_with_property", "op": ">=", "value": 1.0,
             "exercises": ["styxx.protocol:Experiment._check_coverage", "styxx.protocol:_CoverageTracer.section", "styxx.protocol:_CoverageTracer.record"],
             "power_basis": "valid cases satisfy their declarations exactly and state the counts they must observe; a refusal is over-blocking and a wrong count means the property was not what passed",
             "metric_means": "fraction of valid cases that scored, recorded exactly the expected per-section counts, and left sys/threading profilers as found"},
           "G2_p1_retro_refused_as_coverage_violation": {"metric": "p1_retro_exact", "op": ">=", "value": 1.0,
             "exercises": ["run_p1:degenerate"],
             "power_basis": "unchanged from v5c: P1's audit and every previous trace state reachable() x12 and no other public function",
             "metric_means": "1.0 iff P1's G4 with a v5 declaration refuses [V5:NOT_EXERCISED], records exactly {styxx.power:reachable: 12}, and leaves exactly the other four unexercised"},
           "G3_no_v4_v5_disagreement": {"metric": "n_v4_v5_outcome_disagreements", "op": "<=", "value": 0,
             "power_basis": "v5 adds only keys no committed prereg uses; any disagreement with pinned v4 over every pairable committed result is v5 changing what a frozen document means",
             "metric_means": "count of pairable committed results whose outcome differs between pinned v4 (98a5c368) and v5"},
           "G4_population_reached": {"metric": "n_results_v5_scored", "op": ">=", "value": 33,
             "power_basis": "attempt B and v5c both measured 33; fewer means the differential's population shrank",
             "metric_means": "number of pairable committed results on which v5 returned a verdict rather than raising"}},
 "outcomes": [{"when": {"G_EXAM_FROZEN": false}, "verdict": "INVALID__exam_not_the_frozen_exam"},
              {"when": {"G_EXAM_FROZEN": true, "G3_no_v4_v5_disagreement": false}, "verdict": "DO_NOT_SHIP__v5_rewrites_frozen_history"},
              {"when": {"G_EXAM_FROZEN": true, "G3_no_v4_v5_disagreement": true, "G4_population_reached": false}, "verdict": "INVALID__differential_population_shrank"},
              {"when": {"G_EXAM_FROZEN": true, "G3_no_v4_v5_disagreement": true, "G4_population_reached": true, "G0_mutants_refused_for_their_reason": false}, "verdict": "DO_NOT_SHIP__a_violation_passed_or_refused_for_the_wrong_reason"},
              {"when": {"G_EXAM_FROZEN": true, "G3_no_v4_v5_disagreement": true, "G4_population_reached": true, "G0_mutants_refused_for_their_reason": true, "G2_p1_retro_refused_as_coverage_violation": false}, "verdict": "DO_NOT_SHIP__misses_the_real_defect_it_was_built_for"},
              {"when": {"G_EXAM_FROZEN": true, "G3_no_v4_v5_disagreement": true, "G4_population_reached": true, "G0_mutants_refused_for_their_reason": true, "G2_p1_retro_refused_as_coverage_violation": true, "G1_valid_cases_score_with_their_property": false}, "verdict": "DO_NOT_SHIP__overblocks_or_miscounts_valid_harnesses"},
              {"when": {"G_EXAM_FROZEN": true, "G3_no_v4_v5_disagreement": true, "G4_population_reached": true, "G0_mutants_refused_for_their_reason": true, "G2_p1_retro_refused_as_coverage_violation": true, "G1_valid_cases_score_with_their_property": true}, "verdict": "PROCEED_TO_RED_TEAM_ROUND_3__not_yet_shippable"}],
 "smoke_verdict": "INVALID__smoke_plumbing_only"}
```

## The rule for this round, stated before the implementation is written

If a dry run shows a case is wrong — as v5c's `profile.runcall` case was — **the runner is not
edited**. A corrected runner needs a new prereg with a new frozen hash, and the case that was
wrong is published beside it. The implementation may change freely until the scored run; the exam
may not.

## Stated limits, carried forward and extended

Everything in attempts A, B and v5c stands. Round 2 adds, and the RESULT must state:

- **Thread pools must live inside the section they serve.** A pool created outside a section, used
  by two sections in turn, or asyncio's default executor (`run_in_executor(None, ...)`,
  `asyncio.to_thread`) inside a section, refuses (`THREAD_OUTLIVES` or `NOT_EXERCISED`).
  `multiprocessing.pool.ThreadPool`'s context manager terminates without joining and refuses.
- **Rebinding a declared function's closure variables** after resolution makes its own calls read
  as impostors (refusal).
- **A runtime clone with the same globals and no closure**
  (`types.FunctionType(f.__code__, f.__globals__)`) runs the declared code in the declared
  globals and counts as a call to it, unless it is still alive at section close, in which case
  it refuses `SHARED_CODE`.
- **A RecursionError raised while CPython is entering the hook itself**, before the hook body
  runs, cannot be caught by the hook; it refuses `PROFILER_REPLACED`, whose message names that
  route. No exam case forces it, because where the limit lands is not deterministic.
- **Two sections open at once** make thread-started work ambiguous; such work counts for neither.
