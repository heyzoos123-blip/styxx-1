# FINDING — protocol v5e: every rebuilt round 1–3 blocker held, round 4 found six new ones, and all six are in the spec

Fathom Lab · 2026-09-25

- **Preregs:** `PREREG_protocol_v5e_mint_anchor_2026_09_24.md` and `PREREG_protocol_v5e_aux_2026_09_24.md`. They were
  frozen together with the exam in `84f5391f`, a commit that precedes the implementation's first commit. A scratch
  prototype of the design existed at the freeze, as the prereg discloses.
- **Receipts:** `protocol_v5e_result.json`, `protocol_v5e_aux_result.json`, `protocol_v5_redteam_audit.json`,
  `protocol_v5e_round4_summary.json`, `protocol_v5_redteam/round4_exam_mutation/semantic_mutation_census.json`.
- **Scored by** `styxx.protocol`.

## Verdict

**v5e does not ship.** Every frozen gate passed, 25 of 25 across the two preregs. Their verdicts were
`PROCEED_TO_RED_TEAM_ROUND_4__not_yet_shippable` and `PROCEED__the_rule_holds_for_two_implementations_on_four_pythons`.
Red-team round 4 then returned **NOT SHIPPABLE**:

- 58 of 60 distinct findings were confirmed by independent verifiers.
- 6 of them are blockers. Two of these depend on the Python version, which contradicts the second verdict.
- 29 are holes in the frozen exam.
- A seventh blocker-class failure surfaced after the round: on CPython 3.13, an ordinary signal during tracer exit can
  leave the lock held.

Every earlier blocker it rebuilt held, as round 2 had reported for round 1's. Here that meant all 10 blockers from
rounds 1–3, with variants for round 1's, rebuilt alongside earlier defects: 41 of 41 cases held on each of 4 Python
versions. That did not make the classes closed. Round 4 found new failures inside both classes the redesign targeted:

- **Identity:** a stub swapped in before the trace, a shape the spec had marked closed, and a restamped cache wrapper.
- **Attribution:** a dead dispatch cut.

It also found new failures in three other places: the machinery's own exception safety, version-specific runtime
behaviour, and the power of the exam itself.

## What v5 is for

In P1, three frozen, machine-scored gates could be passed without testing what they named. v5 lets a gate declare
`"exercises": ["module:qualname"]`, and optionally a `"section"`. `score()` refuses the verdict unless each declared
function ran on the stack of an opening of that section. The refusal names its reason, for example `[V5:NOT_EXERCISED]`.

## The arc, by the frozen tables

| version | its frozen verdict | then |
|---|---|---|
| v5 attempt A | `DO_NOT_SHIP__v5_rewrites_frozen_history` | the corpus gate diff came from a filter artifact, not from v5; the same bytes were red-teamed as v5b |
| v5b | `PROCEED_TO_RED_TEAM__not_yet_shippable` | round 1: 4 module blockers, 4 module defects, 7 exam defects |
| v5c | `PROCEED_TO_RED_TEAM_ROUND_2__not_yet_shippable` | round 2: 3 module blockers, 6 module defects; 4 blocker-class exam survivors, 4 exam defects |
| v5d | `PROCEED_TO_RED_TEAM_ROUND_3__not_yet_shippable` | round 3: 3 module blockers, 6 module defects; 5 blocker-class exam survivor groups, 3 exam defects |
| v5e | `PROCEED_TO_RED_TEAM_ROUND_4__not_yet_shippable` | round 4: 6 blockers, 15 defects, 7 spec-false, 29 exam holes, 1 note |

Rounds 1–3 kept reopening **identity** (is this frame the declared function?) and **attribution** (which section does
this call belong to?) through variants the previous fix had not named. Every round also found a hook-lifecycle or
exception-safety blocker: R1-B4, R2-B3 and R3-B3. After round 3, a design panel scored three redesigns against all 10 of
those blockers. The synthesis, mint-and-anchor, reduces each targeted class to one rule:

- **Identity.** At trace entry, each declared function's code is replaced by a fresh copy of itself. A frame counts only
  if it runs that exact object with that function's globals.
- **Attribution.** A section is a call. It is credited only when its opening frame is on the live stack above the asyncio
  dispatch cut.

## How v5e was examined before the red team saw it

**The exam.** A separate author wrote it. It was frozen by sha256 together with both preregs at `84f5391f`, which git
shows is an ancestor of the first implementation commit `8b805e26`. The exam has 155 violation cases, 36 valid cases and
11 pinned residuals, and v5e met all three families exactly. v5e also passed three hazard sweeps. Two of them, H1 and H2,
were each paired with a mutant the sweep had to catch:

- 0 hangs. Blocker 5, a hook exception that skips the lock's release, is outside H1's reach. It reproduced under H2's
  pattern, whose check ignores the lock.
- 20 of 20 signal exceptions propagated.
- 5 of 5 KeyboardInterrupt cases held. This sweep had no mutant.

The corpus differential found 0 v4/v5 outcome disagreements over 86 pairable results, and scored 39 under v5.

**The mutation gate, itself a frozen gate.** Every coded emission in the implementation is deleted one at a time, and the
exam must notice each deletion. Emissions include refusals, recorded problems and notes. The mutation gate detected
57 of 57 deletions in v5e, with 0 hygiene violations.
An earlier version of the gate was run as a positive control against v5d, which was already known to be broken. That
version was tightened before the freeze and not re-run on v5d. Against v5d it caught 28 of 29 sites. The one survivor
was HOOK_FAILED, the refusal round 3 had found had no case. The 2 hygiene violations were raises built from a message
variable. A later probe measured the frozen gate's own blind spots: 8 of 9 alternative emission shapes escape both the
mutation and the hygiene check. A census of v5e found all 57 of its coded literals inside mutated sites.

**An oracle fuzzer with controls.** It generates random harness programs whose expected trace is computed by
construction. On v5e it ran 3000 programs with 0 disagreements. Its first version was blind to the dispatch cut: with
the cut removed on purpose, 0 of 300 programs disagreed. That positive control, run on the design prototype, caught the
blindness before the freeze. With the cut removed, 44 of 600 programs now disagree, both on the prototype and on v5e (aux
gate A4). The other two controls were run on the prototype only. Crediting any open section showed up in 245 of 600
programs, and removing the minted identity showed up in all 600 programs. Blockers 3 and 4 lie outside the fuzzer's
domain, so it could not have found them.

**A second implementation and four Pythons.** A second implementation was written from the frozen spec, on the freeze
tree, which never contained the first implementation. It started from the v5d code, it could run the exam and the fuzzer,
and it was written by the same model family as the first. It passed the exam, and its traces differed from the primary's
in 0 fuzz programs. Outside 3 version-keyed cases, the primary gave identical exam and fuzz outcomes on 4 CPython
versions (3.10 through 3.13).

## Round 4

Seven lenses attacked v5e:

- identity
- attribution
- hook lifecycle
- scoring
- a closure audit of every round 1–3 blocker and its variants
- exam mutation
- cross-version conformance

They produced 104 candidate findings, which came to 60 after deduplication.

**Verifying findings other than exam holes.** An independent reproducer re-ran the reporter's repro blind on all four
interpreters. For one finding that only reproduces on 3.10, the main repro ran on 3.10 and 3.11 only. The reproducer then
rebuilt the finding from the claim alone and was told to refute it. A scope judge checked it against the spec's stated
limits, its disclosed over-blocking and its pinned residuals. A finding was confirmed only if all four held:

- it reproduced;
- it was wrong per the spec;
- it was not refuted;
- it was not accurately covered by a stated limit.

**Verifying exam holes.** A verifier rebuilt the mutant independently and ran the frozen exam against it. It then wrote
its own witness program that separates the mutant from the original. A mutant with no witness was treated as equivalent
and refuted.

**Results.** 58 were confirmed. The other 2 were not, because the code matched the spec: a quadratic recursion cost the
spec never states, and a profiler list the scope judge rated SPEC_FALSE. A verifier also surfaced 1 further defect that is
recorded unverified: styxx silently replaces the yappi profiler and still gives PASS.

| class | confirmed |
|---|---|
| blocker | 6 |
| defect | 15 |
| spec sentence false | 7 |
| exam hole | 29 |
| note | 1 |

### The six blockers

1. **A stub installed before the trace by assigning `__code__` passes provenance.** The check ties a function to its
   module by `__globals__`, and `__code__` is writable. The spec's closure table had marked this shape closed.
2. **A cache wrapper stamped by `functools.wraps` credits a function the wrapper never calls.** The body was read from the
   writable `__wrapped__`, not from the wrapper's real callee.
3. **An unstarted generator is credited although its body never ran.** Throwing into it is enough on all four Pythons.
   On 3.10 and 3.11, dropping or closing it is enough.
4. **A tracer that declares `asyncio.events:Handle._run` breaks the dispatch cut for the other tracers.** Asyncio work in
   their loops, including jobs submitted by another thread, is then credited across the cut, even before the declaring
   tracer exits. The declaration is contrived, but the effect is real.
5. **An exception raised inside the hook during `_open`'s lock exit leaves the lock held, and other threads hang.** The
   hazard sweeps could not see it: H1 cannot reach it, and H2's check ignores the lock.
6. **On 3.10, an open section can revert closure writes made by other threads.** CPython 3.10 copies locals back after a
   Python-level profile callback. The traced program is corrupted, not just the verdict.

### What held, and what did not

The closure battery has 41 cases:

- 21 rebuild the 10 blockers from rounds 1–3, with variants for 4 of them.
- 20 rebuild earlier defects and design-panel attacks.

All 41 held on each of 4 interpreters (`protocol_v5e_round4_summary.json` re-runs the battery). The same lens filed the
variants that broke as findings, so the battery was always going to read 41 of 41, and it means less than that number
suggests.

The closure audit reopened two old defects, neither a blocker: resolution can still run user code, and an unhashable
trace field crashes scoring instead of being refused. Other confirmed findings break more closure rows, in new shapes:

- J1-X1, now blocker 1;
- J1-X2 / R3-B2, now blocker 4;
- R3-D3, a lock hazard, now blocker 5;
- and others the verifiers named, among them R1-B1, R1-D1 and R2-B3.

### The finding about our own method

The frozen exam detected 57 of 57 deletions of coded emissions. Round 4 then weakened rules instead of deleting them. It
narrowed a condition, shrank a bound, relaxed an exact-type check, and reordered two scoring steps. The exam detected 27 of
63 of these hand-aimed mutants, and 36 survived (`semantic_mutation_census.json`). Of the 29 exam holes confirmed with
witnesses, 9 are false-pass mutants: under them, a trace that should be refused is scored instead. **Adequacy against
deleted emissions was necessary, and nowhere near sufficient.** The exam for the repair must also be gated on
weakened-rule mutants, each paired with a witness program.

## Three measurements added after round 4 (exploratory, not preregistered)

**The blockers are in the spec, not in one implementation.** Each of the six blocker repros was run against the primary
and against the independent second implementation. So were 4 routes those repros skip. For blocker 3: throwing into
an unstarted generator, and closing one suspended at a bare yield. For blocker 4: the cut failing before the declaring
tracer exits, and another thread's job credited across the cut. All 6 blockers and all 4 routes reproduce on both
implementations, on the same Python versions
(`protocol_v5_redteam/round4/blockers_against_nversion.json`). The two implementations agreed on every exam case and
every fuzz program, and they share every blocker. As the aux prereg anticipated, this is common-mode failure: both follow
the spec, including its code sketches. Agreement tested the design against itself. The red team tested it against seven
lenses of attack.

**An exception at every opcode.** Rounds 3 and 4 found exception-safety failures one bytecode at a time.
`fault_injection_v5.py` maps those outside the profile hook along the paths of 5 scenarios. In each scenario it raises
one exception per run at each opcode it reaches in the coverage-tracer machinery: the code after the
`# -- v5: the coverage tracer` marker, outside the hook. Earlier v5 code, such as `Experiment._check_coverage`, runs in
every scenario but is not injected. It then checks the invariants on the
damaged state, before any repair, and runs one clean trace on top of it. On CPython 3.11, with an Exception subclass,
10,371 points were run:

- 3,371 are in stateless score-time validators, and all of them are clean.
- 2,505 of the 7,000 stateful points damage v5e, at 67 distinct (function, line) sites:
  - 130 hang, all at 4 `with _LOCK:` exits. On 3.11 only a callback such as the hook can raise there, and that is
    blocker 5's window.
  - 120 break the next clean trace.
  - 1,693 leave damage that a clean next trace does not clear.
  - 562 leave damage that the next clean trace clears.
- 42 more become the UNRESOLVED refusal the spec requires, with the exception chained as its cause.

A KeyboardInterrupt pass gives the same 2,505 damaging points and no conversions. On 3.10 the map shows 2,375 damaging
points. The 3.12 and 3.13 maps are partial, because settrace-driven injection behaves differently there: on 3.13 it never
reaches `_close`, and on 3.12 it injects some opcodes twice. Porting the injector to `sys.monitoring` is on the backlog. A
point is one opcode execution, so the same line recurs across scenarios. The map does not cover fork, thread races, the
hook itself, or code that no scenario runs. That last category includes the site of one confirmed round-4 defect.

**On 3.13, a real signal hangs v5e with no hook involved.** The third attack pass on this finding turned up a seventh
blocker-class failure, and `protocol_v5_redteam/round4/py313_signal_backedge.py` re-checks it on every interpreter. On
3.13.12, a SIGALRM handler that raises KeyboardInterrupt during tracer exit is delivered at `__exit__` line 949 (a
`for` loop whose body ends in an `if`, inside `with _LOCK:`). The lock stayed held against other threads in 4 of 4 trials.
It did not on 3.10, 3.11 or 3.12 in any trial. The lock is re-entrant, so the interrupted thread can still take it and
keeps tracing. Every trace on any other thread then hangs, and a single-threaded run hides the damage.

The interpreter behaviour matches the upstream CPython issue numbered #130279 in its tracker. On 3.13.12 the probe's
`finally` was skipped 5 of 5 times for a `while` condition and 5 of 5 for a `for` body ending in an `if`, and never for a
plain `for` or a `while True` loop that ends with `break`. The exception-table layout alone does not explain it: 3.12 leaves
the same closing jump outside the table and still runs `finally`. The difference is where 3.13 delivers a pending signal.
The interpreter bug is known upstream. Its consequence for a checker like v5e is new here, and the repair must not hold a
lock, or rely on `finally`, across such a loop.

**How much round 4 left unfound.** Each lens is treated as a sampling occasion over one fixed implementation, and a finding
reported by several lenses as a recapture. The incidence-based Chao2 estimator then puts the reachable total at 79.0
distinct confirmed findings (95% interval 66.59 to 109.25), against 58 found: about 73% found, and about 21 unfound
(`protocol_v5_redteam/round4/capture_recapture.json`). The pooled figure mixes implementation findings with exam holes.
For the implementation findings alone, which decide shipping, 29 were found out of an estimated 43.69, or 66%, with a
95% interval of 33.41 to 77.93 for the total. The
direction of the error is unknown. Lenses that specialise by region inflate the singletons and push the estimate up, and
wrong deduplication merges push it down. The estimate puts a rough number on "not dry". A stopping rule built on it still
has to be defined, with a threshold, and checked on rounds whose totals are known.

## Limits of this finding

- The six blockers were found against v5e. They say nothing about the repair, which does not exist yet.
- Round 4 stopped after one finder round, because that round already decided the ship question. It is recorded as
  **not dry**, and a stated limit it did not falsify is untested, not confirmed.
- The semantic-mutation census covers a hand-aimed set. Its detection rate is not the exam's power over all faults.
- Round 4 classed 7 findings SPEC_FALSE. Several of its blockers and defects also falsify spec sentences, including at
  least three stated limits. All of them are in the audit.
- The two implementations share one spec and one model family. The blocker receipt now shows that this correlation is
  real.

*Frozen before its implementation's first commit, scored by its own tables, attacked before it could be called done, and
its draft attacked four times before it was certified. It did not ship; the receipts say why.*
