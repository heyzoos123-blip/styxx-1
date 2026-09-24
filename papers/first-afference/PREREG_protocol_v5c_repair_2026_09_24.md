# PREREG — protocol v5, round 2: the red team's cases become the exam, and a refusal must give its reason

Fathom Lab · 2026-09-24 · frozen after red-team round 1 (`protocol_v5_redteam_audit.json`) and
before any repair is written.

## What round 1 found

Attempt B (`20782604` → `13ae3fed`) returned `PROCEED_TO_RED_TEAM__not_yet_shippable`. Two
adversaries were briefed with the module and the exam. Full record: `protocol_v5_redteam_audit.json`
and the scripts under `protocol_v5_redteam/`. The author re-ran the four blockers before writing
this; all four reproduced verbatim.

**The module, four blockers.** (1) Functions sharing one code object pass for each other: factory
closures, and everything behind a decorator without `functools.wraps`. (2) Calls were matched by
code-object *equality*, which ignores file and qualname: a vendored copy, two dataclasses'
generated `__init__`, and — the case that should embarrass us — **a pinned `exec`'d copy of
`styxx.protocol`, the exact pattern our own runner uses for v4**, all satisfy a declaration naming
the live function. (3) The open section was one process-wide slot, so a thread or asyncio task
started in section A credited section B. (4) Under cProfile the hook called a non-callable profiler
object and destroyed the user's profiler.

**The exam, the P1 defect latent in it.** G0 and G2 counted *any* refusal. With individual checks
deleted from the implementation, six named mutants still refused — for a later, different reason —
and with the non-empty check deleted an empty `exercises` beside a declaring gate **scored PASS**
while no mutant could see it. Misspelling one retro target made G2 pass with P1's harness never
run. Two valid cases passed with the property they name removed. The committed run was truthful
(every detail string names its intended reason); the gates did not require it to be. A gate that
can pass without testing what it names is the defect this whole version exists to catch.

**A false claim, ours.** Commit `13ae3fed` said the 53 identically-refused corpus results refuse
"because their preregs predate the gates-block format". Six of them have gates blocks and are
hand-scored verdicts the protocol cannot reproduce. The verdict is unaffected; the sentence is
wrong, and it is corrected in the RESULT, not by editing history.

## The repairs, specified before they are written

Every refusal message begins with a stable reason code `[V5:<CODE>]`. The exam matches on the code.

| finding | repair | code |
|---|---|---|
| B2 equality | match `frame.f_code` by **identity** (id-keyed, reference held, `is` checked) | — |
| B1 shared code | refuse at trace entry if a target's code object is held by more than one live function, or two targets resolve to one code object | `SHARED_CODE` |
| N2 inherited | a `Class.attr` step must find `attr` in that class's own `__dict__` | `INHERITED` |
| B3 sections | the open section lives in a `ContextVar` (asyncio tasks carry the section they were created in); a thread's section is the section open where `Thread.start` was called; a call counts only while its section is **open** | — |
| B3 outliving | a thread started in a section and still alive when the section closes refuses | `THREAD_OUTLIVES` |
| B4 C profiler | a pre-existing profiler that is not a Python function or bound method refuses at entry | `FOREIGN_PROFILER` |
| D4 blinded | a section that closes with the thread's profiler no longer this tracer's hook refuses | `PROFILER_REPLACED` |
| D1 re-entry / order | entering an active tracer refuses; an out-of-order exit refuses and never reinstalls an exited tracer's hook | `REENTRY`, `EXIT_ORDER` |
| D2 crashes | any exception from importing or unwrapping a target becomes a refusal | `UNRESOLVED` |
| D3 crashes | non-string keys anywhere in the trace refuse; `check_metrics` reports, never raises | `BAD_TRACE` |
| N2 regex | full-string match | `DECL` |

Other codes, unchanged in meaning: `NOT_EXERCISED`, `NO_TRACE`, `WRONG_TRACER`, `STALE_TRACE`,
`TARGET_SET`, `SECTION_ABSENT`, `BAD_COUNT`, `NO_CODE`, `SECTION_DECL`, `UNDECLARED_SECTION`,
`NESTED_SECTION`, `NOTHING_DECLARED`.

## The exam

**A violation mutant passes only if it refuses with its expected code.** A different code, a
verdict, or any other exception is a failure. Each mutant is isolated so that no earlier or later
check can catch it: e.g. the empty-`exercises` mutant sits beside a correctly declaring gate whose
section is opened and whose target is called. The battery is attempt B's 24 (re-isolated where the
exam audit showed a shadow) plus every round-1 red-team case: factory closure, no-wraps sibling,
wraps sibling (the unwrap case), vendored equal-code copy, pinned exec'd copy of `styxx.protocol`,
dataclass `__init__`, thread outliving its section, background thread started outside sections,
asyncio task from a closed section, pre-existing C profiler, cProfile inside a section, re-entry,
out-of-order exit, import-time `RuntimeError`, `SyntaxError`, unwrap loop, non-string trace keys (in
`score()`; and `check_metrics()` must return an unusable entry rather than raise), trailing-newline
target, inherited method, and `exercises: []` beside a declaring gate.

**A valid case passes only if it scores AND its named property is observed**: the recorded counts
equal the calls actually made (nested: the outer tracer sees the calls made inside the inner one),
and `sys`/`threading` profilers are restored to what they were. Added: asyncio task created and
awaited in one section; a thread pool created and shut down inside a section; two threads each in
their own section at the same time; a pre-existing pure-Python profiler chained and restored.

**The P1 retro-case passes only if** it refuses with `NOT_EXERCISED`, the trace shows exactly
`{reachable: 12}` in the section, and the missing set is exactly `effective_n`, `order_stat_bar`,
`false_positive_rate`, `min_detectable_bar`. G2 also declares `exercises` on P1's own
`run_p1:degenerate`, so the retro cannot pass without running P1's harness.

**The exam declares more of its own coverage** than attempt B did: the resolver, section entry and
exit, and `record`, not just the one-line factory.

**The corpus gate is attempt B's differential**, plus the effective population the exam audit asked
for: the number of results on which v5 actually reached a verdict, which attempt B measured at 33.

```gates
{"gates": {"G0_mutants_refused_for_their_reason": {"metric": "frac_violation_mutants_refused_with_expected_code", "op": ">=", "value": 1.0,
             "exercises": ["styxx.protocol:Experiment._check_coverage", "styxx.protocol:_resolve_target", "styxx.protocol:_CoverageTracer.section", "styxx.protocol:_CoverageTracer.__exit__"],
             "power_basis": "each mutant is a code path the implementation controls completely and each names its expected code in advance; below 1.0 means a violation reached a verdict, crashed, or refused for a reason other than the one it tests",
             "metric_means": "fraction of violation mutants whose outcome is a GateSpecError whose message begins with the mutant's expected [V5:CODE]"},
           "G1_valid_cases_score_with_their_property": {"metric": "frac_valid_cases_scored_with_property", "op": ">=", "value": 1.0,
             "exercises": ["styxx.protocol:Experiment._check_coverage", "styxx.protocol:_CoverageTracer.section", "styxx.protocol:_CoverageTracer.record"],
             "power_basis": "valid cases satisfy their declarations exactly and each states the counts it must observe; a refusal is over-blocking and a wrong count means the property was not what passed",
             "metric_means": "fraction of valid cases that scored, recorded exactly the expected per-section counts, and left sys/threading profilers as found"},
           "G2_p1_retro_refused_as_coverage_violation": {"metric": "p1_retro_exact", "op": ">=", "value": 1.0,
             "exercises": ["run_p1:degenerate"],
             "power_basis": "P1's committed audit and attempt B's trace both state reachable() x12 and no other public function; any other refusal reason, count, or missing set means the retro did not test what it names",
             "metric_means": "1.0 iff P1's G4 with a v5 declaration refuses [V5:NOT_EXERCISED], the section records exactly {styxx.power:reachable: 12}, and the unexercised set is exactly the other four declared functions"},
           "G3_no_v4_v5_disagreement": {"metric": "n_v4_v5_outcome_disagreements", "op": "<=", "value": 0,
             "power_basis": "v5 adds only keys no committed prereg uses; any disagreement with pinned v4 over every pairable committed result is v5 changing what a frozen document means",
             "metric_means": "count of pairable committed results whose outcome (verdict string, or exception type+message) differs between pinned v4 (98a5c368) and v5"},
           "G4_population_reached": {"metric": "n_results_v5_scored", "op": ">=", "value": 33,
             "power_basis": "attempt B's exam audit measured 33 committed results on which v5 produced a verdict; fewer means the differential's population shrank and G3 is weaker than it was",
             "metric_means": "number of pairable committed results on which v5 returned a verdict rather than raising"}},
 "outcomes": [{"when": {"G3_no_v4_v5_disagreement": false}, "verdict": "DO_NOT_SHIP__v5_rewrites_frozen_history"},
              {"when": {"G3_no_v4_v5_disagreement": true, "G4_population_reached": false}, "verdict": "INVALID__differential_population_shrank"},
              {"when": {"G3_no_v4_v5_disagreement": true, "G4_population_reached": true, "G0_mutants_refused_for_their_reason": false}, "verdict": "DO_NOT_SHIP__a_violation_passed_or_refused_for_the_wrong_reason"},
              {"when": {"G3_no_v4_v5_disagreement": true, "G4_population_reached": true, "G0_mutants_refused_for_their_reason": true, "G2_p1_retro_refused_as_coverage_violation": false}, "verdict": "DO_NOT_SHIP__misses_the_real_defect_it_was_built_for"},
              {"when": {"G3_no_v4_v5_disagreement": true, "G4_population_reached": true, "G0_mutants_refused_for_their_reason": true, "G2_p1_retro_refused_as_coverage_violation": true, "G1_valid_cases_score_with_their_property": false}, "verdict": "DO_NOT_SHIP__overblocks_or_miscounts_valid_harnesses"},
              {"when": {"G3_no_v4_v5_disagreement": true, "G4_population_reached": true, "G0_mutants_refused_for_their_reason": true, "G2_p1_retro_refused_as_coverage_violation": true, "G1_valid_cases_score_with_their_property": true}, "verdict": "PROCEED_TO_RED_TEAM_ROUND_2__not_yet_shippable"}],
 "smoke_verdict": "INVALID__smoke_plumbing_only"}
```

## Stated limits, carried forward and extended

Everything in attempt A's list stands (exercised is not tested; transitive calls count; the trace is
runner-written; declared only; hardcoded values out of scope; child processes invisible). Round 1
adds, and the RESULT must state:

- **Reserved keys.** `exercises` and `section` inside a gate were free text to v4 and are now
  parsed; a document outside the corpus that used them as notes will refuse. None in the corpus does.
- **Threads that exist before the trace**, and threads started through `_thread` rather than
  `threading.Thread.start`, are not observed; their calls read as unexercised (refusal).
- **A harness that installs its own profiler** inside a section blinds the tracer; that now refuses
  with `PROFILER_REPLACED` rather than silently, but it still cannot be traced.
- **A target shared by several functions cannot be declared at all.** That refuses; declare a
  function with its own code.
- **Round 2 of the red team is required before any shipping claim.** Passing this exam licenses
  exactly that.
