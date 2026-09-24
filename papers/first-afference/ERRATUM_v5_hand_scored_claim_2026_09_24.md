# ERRATUM — the 53 results the v5 corpus differential could not score, described correctly

Fathom Lab · 2026-09-24 · receipts: `corpus_provenance_rescore.json` (written by
`corpus_provenance_rescore.py`, which also records the `styxx.protocol` sha256 it ran under and
re-scores with the pinned v4), `corpus_provenance_audit.json`. Nothing below edits a frozen
document; this stands beside them. A draft of this erratum was attacked by a fact-checker and a
skeptic before it was certified. Both found two statements in it false, and both are repaired
here.

## What we said, twice

**First, in commit `13ae3fed`** (protocol v5 attempt B): the 53 committed results that v4 and v5
both refuse do so "because their preregs predate the gates-block format".

**Then, adopted from red-team round 1**: six of those 53 refused results "have gates blocks and are hand-scored
verdicts the protocol cannot reproduce". That sentence went into three places we will not edit in
place: the round-1 entry of `protocol_v5_redteam_audit.json`, the frozen
`PREREG_protocol_v5c_repair_2026_09_24.md`, and the message of commit `adbda648`. The v5c prereg
promised the correction "in the RESULT". No RESULT for protocol v5 exists yet, so it is made here.

## What the census says

The differential ranged over 86 pairable results. It scored 33 to a verdict and 53 raised: 47 at
construction because their prereg has no gates block, and 6 at score because a gate's metric path
is absent from the receipt. The first gates-block prereg in the corpus was added on 2026-08-03.

- **`13ae3fed`'s predate sentence is false for 14 of the 53 refused results.** The 6 that reach
  score have gates blocks,
  and 8 of the 47 without one were written after the format existed: seven closed-model-frontier
  batteries and `open_set_read`.
- **27 of the 47 no-gates-block results carry a committed verdict.** No version of the protocol can
  reproduce those; their gates are in prose. They were not audited here.

## The six, audited

Selection: the 6 results that have a gates block yet raise, plus `open_set_read`, audited because
it was attempt A's only corpus diff. One auditor per result, and one skeptic per audit told to
refute it: 7 audits, 7 upheld. All come from one workflow run in the lab's own session, so they
are not independent of the lab.

**"Hand-scored" was wrong.** The committed code of all six runners builds a flat `metrics` dict,
scores it with `Experiment(...).score`, and writes it into the receipt nested under the key
`metrics`. Each receipt is byte-consistent with that code; no execution log exists. Scored on its
nested dict, each reproduces its committed verdict exactly: 6 of the 7 audited results do, and the
pinned v4 agrees with v5 on all 6 nested dicts.

**"Cannot reproduce" is true of the receipts as committed.** Scored whole, all six raise, because
the gate paths are keys of the nested dict. One skeptic (on `range_sanity_report_ab`) declined to
uphold the audit's claim that the red-team sentence is false, for exactly this reason. Both halves
are now stated: the verdicts are the protocol's, and the receipts as written do not let the
protocol show it.

**The seventh, `open_set_read`, was never scored by the protocol**, and its verdict has problems of
its own: `papers/disjoint-worlds/CORRECTION_open_set_read_null_2026_09_24.md`.

## What else was wrong, which we did not say

- **Key paths.** The six receipts nest the scored dict, so the gate paths do not resolve against
  them. Nothing in `styxx.protocol` told a runner which dict to store.
- **Missing provenance fields.** The six keep no `prereg_commit`. Across the 33 results the
  protocol scores whole, 33 store `prereg_commit` and 1 stores `gates_sha256`, so the tamper check
  described in `styxx.protocol`'s own docstring cannot be run on almost any committed receipt.
  The protocol returns both fields with every verdict; nothing required a runner to keep them.
- **A defect in `styxx.protocol` itself.** `_committed_at` resolves a prereg's commit with
  `git log --follow`, which follows content similarity across files. For `handedness_v3` it
  returns the v2 prereg's commit instead of v3's. It is 1 case in the 86, it changes no verdict
  string, and it is recorded as a backlog item, not fixed here.
- The audits also found smaller defects inside some of the six results (a sentinel value the prereg
  does not define, one commit message with a wrong count). They are recorded per item in
  `corpus_provenance_audit.json` and are out of this erratum's scope.

## What it means for the v5 exams

**Attempt A never saw the six.** Its corpus filter admitted only receipts carrying both
`prereg_commit` and `gates`, and the six lack `prereg_commit`. That same key-shape filter is what
admitted `open_set_read` and failed attempt A.

**Attempts B, v5c and v5d scored whole receipts**, so for the six both v4 and v5 raised
identically. v5's gate evaluation never ran on them, and none of them declares `exercises`, so even
their nested dicts would exercise only the gate evaluation v5 shares with v4. The differential's
effective population was 33 results; the effective population with nested metrics dicts is 39,
and on those six the pinned v4 and v5 agree, so no v5b/v5c/v5d verdict changes. G4's bar of 33 in
those preregs was set on an undercounted population. The next frozen v5 prereg states a mechanical
rule for when a nested dict may stand in for a receipt; this erratum does not.

## The habit

DECIDE-1 named it on 2026-09-17: "treating our machinery's output as ground truth about the world".
Here the machinery was our red team. Its refusal count came from a committed script; its
characterisation, "hand-scored", came from nothing, went into a frozen prereg, and stood for a day.
This erratum also rests on the lab's own scorer and the lab's own agents. The receipts are
committed so that someone who trusts neither can check it.
