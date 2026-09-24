# CORRECTION — the open-set read's VOID was scored on a null that is not orthogonal, and its frozen G-O2 was never evaluated

Fathom Lab · 2026-09-24 · corrects `RESULT_open_set_read_VOID_2026_09_01.md` and the message of
commit `b5dbc494`, neither of which is edited. Receipts: `open_set_read_result.json` (committed
with the RESULT at `b5dbc494`, unchanged since), `open_set_read_null_arithmetic.json` (written by
`open_set_read_null_arithmetic.py`), `../first-afference/corpus_provenance_audit.json` (item
`open_set_read_result.json`), `../first-afference/corpus_provenance_rescore.json`. A draft of this
correction was attacked by a fact-checker and a skeptic, and the revision checked by a verifier,
before it was certified.

## What the prereg froze

G-O2 opens: "A random-orthogonal mapper, matched in shape and fit on shuffled targets, is run
through the identical pipeline. It must score `AUROC(m) <= 0.55`." The text is ambiguous. A random
QR matrix is orthogonal but drawn, not fit; a Procrustes fit on shuffled pairs (the in-arc
`TransferMap` is an orthogonal Procrustes fit) satisfies both words. In this corpus the one other
use of the phrase, in `run_causal_crossworld.py` lines 96-97, is a square QR matrix, which that
comment also calls a shuffled-map null.

## What ran

The runner's null is b34v3's pairing-shuffled null: `fit_mlp` trained on a random permutation of
the targets (`run_open_set_read.py` lines 154-155). It satisfies "matched in shape" and "fit on
shuffled targets". It is not orthogonal under either reading. It also does not go through the identical pipeline: the
real mapper is fit through `TransferMap.fit` and `assignment_from_map` (lines 147-151), and the
null replaces that assignment with a random permutation.

**The RESULT and the `b5dbc494` message both call it "a random-orthogonal mapper"**, and the RESULT
says it was "pushed through the identical pipeline". Both descriptions are wrong. The receipt's
`deviation_from_prereg` discloses the 70-concept partition and the 35/35 sizes; it does not
disclose the null.

## Other departures from the frozen design

- **G-O4 was not met.** The prereg requires the C/O split to be "committed to a hashed file before
  any mapper is fit". The runner draws it in memory; no split file was committed. The receipt does
  not say so.
- **The frozen quantity is absent for a second reason.** Every AUROC in the receipt comes from the
  runner's split of the 70 held-out concepts (35 candidates and 35 out-of-vocabulary), not the
  frozen partition of all 462 concepts. That one was disclosed.
- **The verdict was hand-coded, as prose-gate preregs then were.** The runner applies G-O1 to G-O3
  in its own code (lines 188-215) and adds a rule for combining targets the prereg does not have.
  The RESULT never claimed `styxx.protocol` scored it. But the receipt carries a hand-written
  `prereg_commit` and a hand-built `gates` dict in the protocol's own key shape, and that shape is
  what led protocol v5's attempt A to count it as protocol-produced and fail on it.

## What the receipt supports

- **G-O1 passes as reported**: all three targets reproduce b34v3's closed-set read exactly.
- **G-O5 (no receipt is regenerated) holds by git**: the source receipts and banks predate the
  prereg's commit.
- **G-O2 as frozen: UNCHECKABLE.** The prereg calls UNCHECKABLE "a first-class verdict", and it is
  the verdict against the frozen design. The quantity the gate names was never computed.
- **Under the substituted null, VOID follows, by the runner's all-targets rule**, which the prereg
  does not state: llama 0.5861 and gemma 0.5584 exceed the bar and qwen 0.5012 does not. A mean over
  the three targets, 0.5486, would have passed. `VOID__null_mapper_separates` stands as the result
  of the null that ran and the aggregation the runner chose, not of the frozen gate. The auditor
  graded this NEEDS_CORRECTION; the skeptic judged VERDICT_UNSUPPORTED arguable, because VOID is
  what let the RESULT conclude that no correction was owed.
- **Had the gate passed, the runner would have emitted a `MIXED__` verdict** (lines 211-215), because
  the three G-O3 rows fall in three different bands, one of them the CLOSED-SET ONLY band that
  carries the prereg's correction clause. Whether that clause applies per target the prereg does not
  say. The RESULT prints the G-O3 values as not licensed and forbids quoting one of them as a result
  anywhere downstream; they are not repeated here, and they are in the receipt.

## The bar itself

The RESULT reads G-O2's failure as a mechanism: "absence of a target is therefore partly
detectable from geometry alone". The bar cannot carry that. With 35 candidates against 35 out-of-vocabulary concepts, an exchangeable
null has an AUROC standard deviation of 0.0695, the 0.55 bar sits 0.7194 of those above chance, and
an honest null breaches it on one target with probability 0.2359 per target. If the three targets
were independent, at least one would breach it with probability 0.5539 over three. They share one
split, so that
figure is indicative, and it rests on the assumptions listed in the receipt. This is a false-alarm
rate: under the runner's all-targets rule, an honest null voids the run about as often as not.
Under a rule over the two targets the prereg names, or a mean over three, it would be lower; the
prereg fixed neither.

That is the b48 error again, a single-draw bar judged across several draws, in the gate the prereg
says was written "because `b48` already died on a mis-specified null in this same arc". The RESULT's
"it did its job" and "the gate was built, it ran, and it failed" do not survive it. The downstream
sentence in `../closed-model-frontier/RESULT_extraction_ceiling_REFUTED_2026_09_01.md`, that the
run is void "because its
null gate ran and failed", inherits the same qualification.

## What is owed

The frozen question cannot be settled on these data. The G-O3 values are public, so any G-O2
construction, aggregation rule or rerun chosen now is chosen with the outcome known. The honest
state is UNCHECKABLE, and a successor needs a fresh split or seed and a new prereg with a
machine-readable gates block and a `power_basis`, which fixes, before any data: the null's
construction (a QR orthogonal map, semi-orthogonal where the dimensions differ, or a Procrustes fit
on shuffled pairs, but one of them, named), its standardisation, the number of null draws, the
rule for combining targets, and a bar derived from the null's own distribution.

The VOID is not withdrawn. It stands as the result of the null that ran, and this document says
which null that was.
