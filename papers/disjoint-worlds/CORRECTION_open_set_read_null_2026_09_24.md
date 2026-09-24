# CORRECTION — the open-set read's VOID was scored on a null the prereg did not name

Fathom Lab · 2026-09-24 · corrects `RESULT_open_set_read_VOID_2026_09_01.md`, which is not edited.
Receipts: `open_set_read_result.json` (committed with the RESULT at `b5dbc494`, unchanged since),
`../first-afference/corpus_provenance_audit.json` (item `open_set_read_result.json`: one auditor,
one skeptic told to refute, audit upheld), `../first-afference/corpus_provenance_rescore.json`.

## What the RESULT says

"A random-orthogonal mapper, fit on shuffled targets and pushed through the identical pipeline, was
required to score `AUROC(margin) <= 0.55`." It then reports that mapper at 0.5861 (llama) and 0.5584
(gemma) and declares the run `VOID__null_mapper_separates`.

## What ran

The prereg's G-O2 names a **random-orthogonal mapper**. The runner did not build one. Its null is
`fit_mlp` trained on a random pairing (`run_open_set_read.py`, the `null_fn` lines), which is b34v3's
pairing-shuffled MLP null, not an orthogonal map; in this corpus "random orthogonal map" is a QR
matrix. The receipt's `deviation_from_prereg` discloses the 70-concept partition and the 35/35 split
sizes. It does not disclose the substitution of the null.

The verdict was also not produced by `styxx.protocol`. The prereg states its gates in prose, not in
a gates block, and the runner applies them in hand-written code; the scorer refuses the prereg
outright.

## What the receipt supports

- **G-O1 (closed-set reconciliation) passes as reported.** All three targets reproduce b34v3's
  closed-set read exactly.
- **G-O2 as frozen cannot be evaluated from the receipt.** The quantity it names was never computed.
- **Under the substituted null, VOID follows.** llama 0.5861 and gemma 0.5584 both exceed the 0.55
  bar; qwen 0.5012 does not. So the committed verdict is what the runner's own null gives. It is not
  what the frozen gate was shown to give.
- **Had G-O2 passed, the outcome would not have been VOID.** The G-O3 rows are llama 0.7665
  (open-set signal), gemma 0.6033 (indeterminate) and qwen 0.5061 (closed-set only), and the prereg
  has no rule for combining targets. The RESULT's "no correction is owed" depends on the VOID.
- **The bar sits inside sampling noise.** Every AUROC here compares 35 candidates (n_candidates)
  against 35 out-of-vocabulary concepts (n_oov). Under a pure null the auditor computed a standard
  deviation of about 0.069 and roughly even odds that at least one of three null targets exceeds
  0.55 by chance. G-O2 as written had little power to separate a leaking null from an honest one.

## What is owed

1. The literal G-O2: the same pipeline under a random orthogonal (QR) null map, into a new dated
   receipt. If it passes the bar, the run moves to G-O3, and the prereg's missing rule for combining
   targets has to be settled by a new prereg before any row is read.
2. Any successor to this experiment freezes a machine-readable gates block with a `power_basis`.

The VOID is not withdrawn. It stands as the verdict of the null that ran, and this document says
which null that was.
