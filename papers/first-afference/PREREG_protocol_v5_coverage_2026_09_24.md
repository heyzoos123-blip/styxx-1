# PREREG — protocol v5: can a gate declare what its harness must exercise, and be refused when it did not?

Fathom Lab · 2026-09-24 · frozen before the implementation exists.

## Why

P1 (cycle 158) produced the defect this version is for, and named it: **three of five frozen,
machine-scored gates were satisfiable without testing what they named.**
`p1_redteam_audit.json` records them verbatim:

- `G4_refuses_degenerate` — "scored 1.0 but the harness exercises only reachable(); 3 of 5 public
  entry points return verdicts on a zero-variance null".
- `G1_historical_in_sample` — "satisfied without exercising the order-statistic machinery at all".
- `G3_beats_constant` — "baseline hardcoded to 0.5 rather than scored".

`power_basis` and `metric_means` were present on every one of them and caught none. The cycle-158
log states the missing artifact: *a declaration of what the HARNESS must exercise, checkable
against what it did.* Cycle 160 shipped v4 (gate composition) and carried this forward as "the
open successor from P1 — v4 checks gate composition, not harness coverage". It has been open for
46 days.

## The mechanic

A gate may declare, in the frozen gates block:

- `exercises` — a non-empty list of `"module:qualname"` strings naming Python functions the code
  that produced this gate's metric must actually have executed;
- `section` — optionally, the name of the trace section that code ran in (default: the gate name).

A new context manager, `styxx.protocol.coverage_trace(experiment)`, reads the declared targets
**from the frozen document** (not from the caller), resolves each to its code object before any
work runs (refusing at entry on a target that does not resolve or has no Python code), and records
every call to a declared target's code object — direct or transitive, in the calling thread and in
threads started while tracing — attributed to the currently open `section(name)`. The trace is
written into the result under the key `coverage_trace`, stamped with the gates block's sha256 and
the set of declared targets.

At scoring time, for every gate that declares `exercises`, `score()` **refuses** unless:
the trace exists; was taken against this gates block's sha256 and exactly this declared target
set; contains the gate's section; and records at least one call to every declared target inside
that section. Everything ill-formed refuses. A gate that declares nothing is untouched.

## The exam

**Violation mutants** (each must refuse, never return a verdict): a declared target never called;
called only in a *different* section; called only outside any section; no trace at all; the gate's
section absent from the trace; a trace stamped with a different gates sha256 (stale); a trace whose
target set differs from the declaration; a target that does not resolve; a target with no Python
code object (a builtin); `exercises` empty, not a list, or containing a non-string or a string
without `module:qualname` form; a non-string `section`; a count that is not a positive integer
(bool, float, negative) in a hand-edited trace; a target called only in a child **process** (which
the tracer cannot see — the refusal is the fail-safe direction).

**Valid cases** (each must score): a direct call; a transitive call through an undeclared helper;
a `functools.wraps`-decorated target; a method named `Class.method`; a call made in a thread
started inside the section; two gates sharing one declared section; a gate that declares
`exercises` beside one that does not; a trace taken inside another `coverage_trace` (nesting must
not blind either tracer).

**The P1 retro-case** — the one case drawn from a real defect rather than constructed. The
quarantined module (`styxx/power_QUARANTINED.py.txt`) is loaded as `styxx.power`, P1's own
`degenerate()` battery from the committed `run_p1.py` is re-run unmodified inside a trace section,
and P1's own G4 — rewritten with a v5 declaration naming the module's public functions that take a
null or a series (`effective_n`, `order_stat_bar`, `false_positive_rate`, `min_detectable_bar`,
`reachable`) — is scored against the result. **It must refuse.**

Reported but **not gated**, because the author does not know the answer and a gate on it would be
a guess: whether P1's G1 re-run under a declaration naming `order_stat_bar` refuses. The audit
says it would; `reachable()` may reach `order_stat_bar` transitively when `n_draws > 1`, in which
case the transitive semantics above would pass it. Whichever happens is published.

**The exam declares its own coverage.** This prereg's G0 and G1 declare `exercises` on the v5
machinery, and the runner produces its result inside `coverage_trace`. An exam of a coverage
check that did not itself exercise the coverage check is the P1 defect again.

**Backward compatibility is the hard constraint.** Every committed result produced by
`styxx.protocol` is re-scored; any drift in any verdict string fails this exam regardless of the
other gates.

```gates
{"gates": {"G0_mutants_refused": {"metric": "frac_violation_mutants_refused", "op": ">=", "value": 1.0,
             "exercises": ["styxx.protocol:Experiment._check_coverage", "styxx.protocol:coverage_trace"],
             "power_basis": "each mutant is a code path the implementation controls completely; anything below 1.0 means an undeclared-coverage violation reached a verdict, which is the defect this version exists to prevent",
             "metric_means": "fraction of constructed violation mutants on which the machinery raised (at trace entry, construction, or score) rather than returned a verdict"},
           "G1_valid_still_scores": {"metric": "frac_valid_cases_scored", "op": ">=", "value": 1.0,
             "exercises": ["styxx.protocol:Experiment._check_coverage", "styxx.protocol:coverage_trace"],
             "power_basis": "the valid cases are constructed to satisfy their declarations exactly, so a correct implementation scores all of them; a refusal here is over-blocking, which kills adoption of the mechanic",
             "metric_means": "fraction of correct-declaration cases that scored without refusal"},
           "G2_p1_retro_refused": {"metric": "p1_retro_case_refused", "op": ">=", "value": 1.0,
             "power_basis": "boolean; P1's committed audit states its harness exercised only reachable(), so a v5 declaration naming the other public functions must refuse against an unmodified re-run of the committed harness -- the one case drawn from a real defect",
             "metric_means": "1.0 if P1's G4, rewritten with a v5 exercises declaration, refuses against a traced re-run of run_p1.degenerate() on the quarantined module"},
           "G3_corpus_byte_identical": {"metric": "n_corpus_verdict_diffs", "op": "<=", "value": 0,
             "power_basis": "v2, v3 and v4 each shipped against this same bar (0 diffs across all committed scoring events), so it is known achievable; any nonzero count means v5 changed the meaning of a frozen document",
             "metric_means": "count of committed protocol-produced results whose verdict string differs when re-scored under v5"}},
 "outcomes": [{"when": {"G3_corpus_byte_identical": false}, "verdict": "DO_NOT_SHIP__v5_rewrites_frozen_history"},
              {"when": {"G3_corpus_byte_identical": true, "G0_mutants_refused": false}, "verdict": "DO_NOT_SHIP__an_unexercised_gate_reached_a_verdict"},
              {"when": {"G3_corpus_byte_identical": true, "G0_mutants_refused": true, "G2_p1_retro_refused": false}, "verdict": "DO_NOT_SHIP__misses_the_real_defect_it_was_built_for"},
              {"when": {"G3_corpus_byte_identical": true, "G0_mutants_refused": true, "G2_p1_retro_refused": true, "G1_valid_still_scores": false}, "verdict": "DO_NOT_SHIP__overblocks_valid_declarations"},
              {"when": {"G3_corpus_byte_identical": true, "G0_mutants_refused": true, "G2_p1_retro_refused": true, "G1_valid_still_scores": true}, "verdict": "PROCEED_TO_RED_TEAM__not_yet_shippable"}],
 "smoke_verdict": "INVALID__smoke_plumbing_only"}
```

## What the winning branch does NOT license

`PROCEED_TO_RED_TEAM__not_yet_shippable` is not a release, and this session cuts none (version
bumps, tags and PyPI are operator-gated). The battery is written by the implementer except for one
case. **No shipping claim is made unless an adversary, briefed with the module AND this exam,
tries to break v5 and fails.** Every red-team finding is published with its repair or its
refusal-to-repair.

## Stated limits, in advance

- **Exercised is not tested.** A declared target that was called once, on one input, with its
  return value discarded, satisfies the declaration. v5 converts "the harness never touched it"
  from a silent pass into a refusal; it says nothing about whether the touch checked anything.
  P1's G4 would be caught; a harness that calls every entry point and asserts nothing would not.
- **Transitive counts.** A target reached through another declared target counts as exercised.
  A declaration that wants a *direct* call cannot say so in v5.
- **The trace is written by the runner.** Like every metric in a result dict, it can be forged by
  a runner that wants to forge it. v5 defends against omission, not against an adversarial author;
  that residual is the same one every layer of this programme has.
- **Declared only.** A prereg that declares nothing gets no check. P1's author would have had to
  write `exercises` for P1 to be caught — the same ratchet-not-proof residual v4 stated.
- **G3's defect is out of scope.** A hardcoded baseline is a value, not a missing call; no coverage
  declaration catches it, and this prereg does not claim to.
- **Other processes are invisible.** Work done in a subprocess or process pool is not traced and
  its targets read as unexercised. That refuses, which is the safe direction, and is disclosed so
  that a multiprocess harness is not surprised by it.
