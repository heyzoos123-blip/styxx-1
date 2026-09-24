# ERRATUM — six verdicts we called "hand-scored" were scored by styxx.protocol, and reproduce exactly

Fathom Lab · 2026-09-24 · receipts: `corpus_provenance_rescore.json` (written by
`corpus_provenance_rescore.py`), `corpus_provenance_audit.json`. Nothing below edits a frozen
document; this stands beside them.

## What we said

Red-team round 1 on protocol v5 audited attempt B's corpus differential and reported that of the
53 committed results both v4 and v5 refuse, six have gates blocks and are "hand-scored verdicts the
protocol cannot reproduce". We adopted that sentence without checking it. It appears in three
places we cannot edit and will not:

- the round-1 entry of `protocol_v5_redteam_audit.json` (`round_1.exam_audit.false_claim`);
- the frozen `PREREG_protocol_v5c_repair_2026_09_24.md` ("Six of them have gates blocks and are
  hand-scored verdicts the protocol cannot reproduce");
- the message of commit `adbda648`.

## What is true

All six runners import `styxx.protocol` and score through it. Each built a flat `metrics` dict,
scored it with `Experiment(...).score(metrics)`, and wrote it into the receipt nested under the key
`metrics`. Handing the whole receipt to the scorer raises, because the gate paths are top-level keys
of the nested dict. Handing it the nested dict reproduces every committed verdict exactly.

The mechanical check, run read-only against the committed receipts with the current
`styxx.protocol`: of the 7 results the v5 differential could not score, 6 reproduce from their
`metrics` sub-dict. The six are `handedness_accusations`, `handedness_v2`, `handedness_v3`,
`range_sanity_report_ab`, `efficiency_control` and `untied_control`. The seventh,
`open_set_read`, was never scored by the protocol; it has its own correction
(`papers/disjoint-worlds/CORRECTION_open_set_read_null_2026_09_24.md`).

The adjudication agrees. One auditor per result and one independent skeptic per audit, each
told to refute: 7 audits, 7 upheld. For all six the skeptic re-derived the committed verdict by
walking the frozen outcome table by hand from values in the receipt.

## What was actually wrong, smaller than what we said

The six receipts keep neither `prereg_commit` nor `gates_sha256`, so a later reader cannot tell
from the receipt alone which frozen gates block scored it. That is a provenance gap, not an
unsupported verdict. `styxx.protocol` never required a runner to store either; nothing enforced it.

## What it means for the v5 exams

Every v5 corpus differential (attempts A and B, v5c, v5d) scored whole receipts, so for these six
both v4 and v5 raised identically and **v5's gate logic never ran on them**. The differential's
effective population was 33 results; the effective population with nested metrics dicts is 39
results. The next v5 exam scores the nested `metrics` dict wherever the whole receipt raises and
the runner is shown to have scored it.

## Why this matters more than its size

DECIDE-1 named the habit on 2026-09-17: treating our own machinery's output as ground truth about
the corpus. Here the machinery was our own red team, and the habit was ours: a plausible sentence
from an auditor went into a frozen prereg without a single receipt behind it. The receipt now
exists, and it says the sentence was wrong.
