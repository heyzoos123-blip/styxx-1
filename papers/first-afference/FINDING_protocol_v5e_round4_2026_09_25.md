# FINDING — protocol v5e: the redesign closed every class that broke v5–v5d, and round 4 still found six blockers

Fathom Lab · 2026-09-25 · preregs: `PREREG_protocol_v5e_mint_anchor_2026_09_24.md` and
`PREREG_protocol_v5e_aux_2026_09_24.md`, frozen together with the exam before the implementation existed ·
receipts: `protocol_v5e_result.json`, `protocol_v5e_aux_result.json`, `protocol_v5_redteam_audit.json`,
`protocol_v5e_round4_summary.json`, `protocol_v5_redteam/round4_exam_mutation/semantic_mutation_census.json` ·
scored by `styxx.protocol`.

## Verdict

**v5e does not ship.** Every frozen gate passed: 25 of 25 across the two preregs. The prereg's verdict for that outcome was
`PROCEED_TO_RED_TEAM_ROUND_4__not_yet_shippable`, and red-team round 4 returned **NOT SHIPPABLE**:

- 58 of 60 distinct findings were confirmed by independent verifiers.
- 6 of the confirmed findings are blockers.
- 29 are holes in the frozen exam.

It also returned the first good news this program has had about v5's hardest problem. Every blocker class from rounds 1–3
was rebuilt against v5e with variants, and 41 of 41 cases held on each of 4 Python versions. The class-closing redesign
closed the classes it was designed to close. What round 4 found lies outside them: the machinery's own exception safety,
provenance of code installed before the trace, version-specific runtime behaviour, and the power of the exam itself.

## What v5 is for

P1 produced three frozen, machine-scored gates that were satisfiable without testing what they named. v5 lets a gate
declare `"exercises": ["module:qualname"]` and optionally a `"section"`. `score()` refuses the verdict unless each declared
function ran on the stack of an opening of that section. The refusal names the reason, for example
`[V5:NOT_EXERCISED]`.

## The arc, by the frozen tables

| version | its frozen verdict | then |
|---|---|---|
| v5 attempt A | `DO_NOT_SHIP__v5_rewrites_frozen_history` | not red-teamed; the table said no |
| v5b | `PROCEED_TO_RED_TEAM__not_yet_shippable` | round 1: 4 blockers, 4 defects |
| v5c | `PROCEED_TO_RED_TEAM_ROUND_2__not_yet_shippable` | round 2: 3 blockers, 6 defects |
| v5d | `PROCEED_TO_RED_TEAM_ROUND_3__not_yet_shippable` | round 3: 3 blockers, 6 defects |
| v5e | `PROCEED_TO_RED_TEAM_ROUND_4__not_yet_shippable` | round 4: 6 blockers, 15 defects, 29 exam holes |

Rounds 1–3 kept reopening the same two classes, **identity** (is this frame the declared function?) and **attribution**
(which section does this call belong to?), each time through a variant the previous fix had not named. After round 3 a
design panel scored three redesigns against all 10 blockers from rounds 1–3. The synthesis, mint-and-anchor, reduces
each class to one rule:

- **Identity.** At trace entry each declared function's code is replaced by a fresh copy of itself, and a frame counts only
  if it runs that exact object with that function's globals.
- **Attribution.** A section is a call, and it is credited only when its opening frame is on the live stack above the
  asyncio dispatch cut.

## How v5e was examined before the red team saw it

**The exam was frozen first.** A separate author wrote the exam, and it was frozen by sha256 together with both preregs
at `84f5391f`. That commit is an ancestor of the first implementation commit `8b805e26`, which git can show. The exam
has 155 violation cases, 36 valid cases and 11 pinned residuals, and v5e met all three families exactly. It also passed
three hazard sweeps, each paired with a mutant the sweep had to catch:

- 0 hangs;
- 20 of 20 signal exceptions propagated;
- 5 of 5 KeyboardInterrupt cases held.

The corpus differential found 0 v4/v5 outcome disagreements over 86 pairable results, with 39 results scored under v5.

**A mutation gate, itself a frozen gate.** Every coded refusal in the implementation is deleted one at a time, and the
exam must notice each deletion. v5e scored 57 of 57 with 0 hygiene violations. The gate was first run as a positive
control against v5d, which was already known to be broken. There it caught 28 of 29 sites. The one survivor was the site
round 3 had found by hand, and the 2 hygiene violations were the two refusals round 3 had shown the mutator cannot see.
A later probe measured the gate's own blind spots:

- 8 of 9 alternative emission shapes escape both the mutation and the hygiene check.
- A census of v5e found all 57 of its coded literals inside mutated sites.

**An oracle fuzzer with controls.** It generates random harness programs with the expected trace computed by
construction: 3000 programs, 0 disagreements. Its first version was blind to the dispatch cut: with the cut removed on
purpose, 0 of 300 programs disagreed. That positive control caught the blindness before the freeze. After the fix, the
same broken rule shows up in 44 of 600 programs. Crediting any open section shows up in 245 of 600, and removing the
minted identity shows up in 600 of 600 programs, every one.

**A second implementation and four Pythons.** An independent implementation was written from the frozen spec on the
freeze tree, which never contained the first implementation. It passed the exam, and its traces differed from the
primary's in 0 fuzz programs. The primary gave identical outcomes on 4 CPython versions (3.10 through 3.13). An
exploratory, non-gated run found the second implementation clean on all 4 as well.

## Round 4

Seven lenses attacked v5e:

- identity
- attribution
- hook lifecycle
- scoring
- a closure audit of every earlier finding
- exam mutation
- cross-version conformance

They produced 104 candidate findings, 60 after deduplication.

**How findings were verified.** For each finding other than an exam hole, an independent reproducer re-ran the repro
blind on all four interpreters, rebuilt it from the claim alone, and was told to refute it. A scope judge then checked the
finding against the spec's stated limits, disclosed over-blocking and pinned residuals. A finding was confirmed only if it
reproduced, was wrong per the spec, was not refuted, and was not accurately covered by a stated limit.

**How exam holes were verified.** For each claimed exam hole, a verifier rebuilt the mutant independently and ran the
frozen exam against it. It then wrote its own witness program separating the mutant from the original. A mutant with no
witness counted as equivalent and was refuted.

**Results.** 58 were confirmed and 2 were not: a cost that the spec discloses, and a wording judged disclosed.

| class | confirmed |
|---|---|
| blocker | 6 |
| defect | 15 |
| spec sentence false | 7 |
| exam hole | 29 |
| note | 1 |

### The six blockers

1. **A stub installed before the trace by assigning `__code__` passes provenance.** The check ties a function to its
   module by `__globals__`, and `__code__` is writable. The spec's own closure table marked this shape closed.
2. **A cache wrapper stamped by `functools.wraps` credits a function the wrapper never calls.** The body was read from
   the writable `__wrapped__`, not from the wrapper's real callee.
3. **An unstarted generator is credited on 3.10 and 3.11,** although its body never ran.
4. **A tracer that declares `asyncio.events:Handle._run` leaves a dead dispatch cut for the tracers still active.** Their
   later asyncio work is then credited across the cut. This needs a contrived declaration, but it is real.
5. **An exception raised inside the hook during `_open`'s lock exit leaves the lock held.** Other threads then hang.
6. **On 3.10 an open section can revert closure writes made by other threads.** CPython 3.10 copies locals back after a
   Python-level profile callback. This corrupts the traced program, not just the verdict.

### What held

The closure audit re-ran every blocker from rounds 1–3 and its variants against v5e. The cases were:

- factory products;
- shared and cloned code objects;
- threads started in one section calling into another;
- pools and asyncio tasks shared across sections;
- foreign profilers;
- a timeout signal inside the hook.

All 41 cases held on each of 4 interpreters (`protocol_v5e_round4_summary.json` re-runs the battery). Only two old defects
reopened, and neither is a blocker: resolution can still run user code, and an unhashable trace field crashes scoring
instead of being refused.

### The finding about our own method

The frozen exam detected 57 of 57 refusal deletions. Round 4 then weakened rules instead of deleting them: narrowing a
condition, shrinking a bound, relaxing an exact-type check, reordering two scoring steps. The exam detected 27 of 63 of
these hand-aimed mutants, and 36 survived (`semantic_mutation_census.json`). Of the 29 exam holes confirmed with
witnesses, 9 are mutants that would let a harness which never ran its target pass. **Refusal-deletion adequacy was
necessary and not nearly sufficient.** The repair's exam must be gated on weakened-rule mutants, each paired with a
witness program.

## Limits of this finding

- The six blockers were found against v5e. They say nothing about the repair, which does not exist yet.
- Round 4 stopped after one finder round, because that round already decided the ship question. It is recorded as
  **not dry**. More findings against v5e are likely, and the next red team will attack the repair, not v5e.
- The semantic-mutation census covers a hand-aimed set. Its detection rate is not the exam's power over all faults.
- The two implementations share one spec. Their agreement measures faithfulness to the design, not the design's
  soundness, and round 4's blockers include spec text that both implementations followed faithfully.
- The spec's stated limits stand as written wherever round 4 did not falsify them. Round 4 did falsify 7 spec
  sentences, and those are listed in the audit.

*Frozen before it existed, scored by its own table, attacked before it could be called done. It did not ship, and the
reasons are in the receipts.*
