"""Re-score the seven committed results the v5 differential could not score, the right way.

The v5 exams (attempts A/B, v5c, v5d) re-scored every committed result by handing the WHOLE
receipt to ``Experiment(prereg).score``. Seven raise. The provenance audit
(``corpus_provenance_audit.json``) found that six of them were scored by ``styxx.protocol`` when
they ran -- on a flat ``metrics`` dict that the runner then nested under ``"metrics"`` in the
receipt -- and one (open_set_read) never was. This script checks that finding mechanically and
read-only: it never runs a runner, never writes anywhere but its own receipt.

Writes ``corpus_provenance_rescore.json``.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from styxx.protocol import Experiment, GateSpecError  # noqa: E402

ITEMS = [
    ("closed-model-frontier", "handedness_accusations_result.json",
     "handedness_accusations.py"),
    ("closed-model-frontier", "handedness_v2_result.json", "handedness_accusations_v2.py"),
    ("closed-model-frontier", "handedness_v3_result.json", "handedness_accusations_v3.py"),
    ("closed-model-frontier", "range_sanity_report_ab_result.json", "range_sanity_report_ab.py"),
    ("frequency-resonance", "efficiency_control_result.json", "run_efficiency_control.py"),
    ("rhythm-rescue", "untied_control_result.json", "run_untied_control.py"),
    ("disjoint-worlds", "open_set_read_result.json", "run_open_set_read.py"),
]


def _outcome(fn):
    try:
        return fn().verdict
    except GateSpecError as e:
        return f"RAISED:GateSpecError:{e}"


def _first_commit(path: Path, follow: bool):
    """(sha, iso date) of the commit that added *path*; with follow, the way styxx.protocol's
    _committed_at resolves it (git log --follow, run from the file's directory)."""
    cmd = ["git", "log", "--diff-filter=A", "--format=%H %aI"]
    if follow:
        cmd += ["--follow", "--", path.name]
        cwd = path.parent
    else:
        cmd += ["--", str(path.relative_to(ROOT))]
        cwd = ROOT
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    lines = [x for x in r.stdout.split("\n") if x]
    return tuple(lines[-1].split()) if lines else (None, None)


def census(v4) -> dict:
    """The whole population the v5 differential ranged over (every committed *_result.json whose
    prereg exists beside it, minus the v5 exams' own), measured, not quoted."""
    own = {"PREREG_protocol_v5_coverage_2026_09_24.md", "PREREG_protocol_v5b_coverage_2026_09_24.md",
           "PREREG_protocol_v5c_repair_2026_09_24.md", "PREREG_protocol_v5d_repair_2026_09_24.md"}
    first_gates = min(
        (_first_commit(p, False)[1], str(p.relative_to(ROOT)))
        for p in ROOT.glob("papers/*/PREREG_*.md")
        if "\n```gates\n" in p.read_text(encoding="utf-8") and _first_commit(p, False)[1])
    rows = []
    for res_file in sorted(ROOT.glob("papers/*/*_result.json")):
        try:
            rec = json.loads(res_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(rec, dict) or not isinstance(rec.get("prereg"), str):
            continue
        prereg = res_file.parent / rec["prereg"]
        if not prereg.is_file() or prereg.name in own:
            continue
        try:
            outcome = Experiment(prereg).score(rec, smoke=bool(rec.get("smoke"))).verdict
            stage = "verdict"
        except GateSpecError as e:
            outcome = f"RAISED:GateSpecError:{e}"
            stage = "construction" if "gates block" in str(e) else "score"
        added = _first_commit(prereg, False)
        followed = _first_commit(prereg, True)
        rows.append({
            "result": str(res_file.relative_to(ROOT / "papers")),
            "stage": stage,
            "has_committed_verdict": isinstance(rec.get("verdict"), str),
            "prereg_added": added[1],
            "prereg_postdates_first_gates_block": bool(added[1] and added[1] > first_gates[0]),
            "stores_prereg_commit": "prereg_commit" in rec,
            "stores_gates_sha256": "gates_sha256" in rec,
            "prereg_commit_by_follow_matches_by_path": followed[0] == added[0],
            "prereg_commit_by_path": added[0], "prereg_commit_by_follow": followed[0],
            "outcome": outcome[:200],
        })
    raised = [r for r in rows if r["stage"] != "verdict"]
    scored = [r for r in rows if r["stage"] == "verdict"]
    constr = [r for r in raised if r["stage"] == "construction"]
    return {
        "first_gates_block_prereg": {"added": first_gates[0], "path": first_gates[1]},
        "n_pairable": len(rows),
        "n_scored_to_a_verdict": len(scored),
        "n_raised": len(raised),
        "n_raised_at_construction_no_gates_block": len(constr),
        "n_raised_at_score": len(raised) - len(constr),
        "n_no_gates_block_with_committed_verdict": sum(r["has_committed_verdict"] for r in constr),
        "n_no_gates_block_prereg_postdates_first_gates_block": sum(
            r["prereg_postdates_first_gates_block"] for r in constr),
        # 13ae3fed said all the raised results "predate the gates-block format": false for every
        # one that has a gates block (raised at score) and every no-gates-block prereg written
        # after the format existed
        "predate_sentence_false_for_n_refused": (len(raised) - len(constr)) + sum(
            r["prereg_postdates_first_gates_block"] for r in constr),
        "no_gates_block_postdating_the_format": [r["result"] for r in constr
                                                  if r["prereg_postdates_first_gates_block"]],
        "n_scored_storing_prereg_commit": sum(r["stores_prereg_commit"] for r in scored),
        "n_scored_storing_gates_sha256": sum(r["stores_gates_sha256"] for r in scored),
        "n_follow_resolves_a_different_prereg_commit": sum(
            not r["prereg_commit_by_follow_matches_by_path"] for r in rows),
        "follow_mismatches": [{"result": r["result"], "by_path": r["prereg_commit_by_path"],
                               "by_follow": r["prereg_commit_by_follow"]}
                              for r in rows if not r["prereg_commit_by_follow_matches_by_path"]],
        "rows": rows,
    }


def main() -> int:
    sys.path.insert(0, str(HERE))
    import run_protocol_v5 as attempt_b          # the committed, hash-checked v4 pin
    v4 = attempt_b._pinned_v4()
    rows = []
    for d, res_name, runner in ITEMS:
        res_path = ROOT / "papers" / d / res_name
        rec = json.loads(res_path.read_text(encoding="utf-8"))
        prereg = ROOT / "papers" / d / rec["prereg"]
        runner_src = (ROOT / "papers" / d / runner).read_text(encoding="utf-8")
        exp = None
        try:
            exp = Experiment(prereg)
        except GateSpecError as e:
            construct = f"RAISED:GateSpecError:{e}"
        else:
            construct = "ok"
        whole = _outcome(lambda: exp.score(rec)) if exp else construct
        nested = rec.get("metrics")
        sub = (_outcome(lambda: exp.score(nested)) if exp and isinstance(nested, dict)
               else "no metrics sub-dict" if exp else construct)
        sub_v4 = (_outcome(lambda: v4.Experiment(prereg).score(nested))
                  if exp and isinstance(nested, dict) else None)
        rows.append({
            "result": f"{d}/{res_name}",
            "score_metrics_subdict_pinned_v4": sub_v4,
            "committed_verdict": rec.get("verdict"),
            "runner": f"{d}/{runner}",
            "runner_imports_styxx_protocol": "from styxx.protocol import Experiment" in runner_src,
            "runner_calls_score": ".score(" in runner_src,
            "receipt_keeps_prereg_commit": "prereg_commit" in rec,
            "receipt_keeps_gates_sha256": "gates_sha256" in rec,
            "score_whole_receipt": whole,
            "score_metrics_subdict": sub,
            "metrics_subdict_reproduces_committed": sub == rec.get("verdict"),
        })
    reproduced = [r["result"] for r in rows if r["metrics_subdict_reproduces_committed"]]
    v5d = json.loads((HERE / "protocol_v5d_result.json").read_text(encoding="utf-8"))
    cen = census(v4)
    out = {
        "script": "papers/first-afference/corpus_provenance_rescore.py",
        "styxx_protocol_sha256": hashlib.sha256(
            (ROOT / "styxx" / "protocol.py").read_bytes()).hexdigest(),
        "v4_pin": {"commit": attempt_b.V4_COMMIT, "sha256": attempt_b.V4_SHA},
        "selection_rule": ("the 6 results whose preregs have a gates block yet raise when the whole "
                           "receipt is scored, plus open_set_read, audited because it was attempt "
                           "A's only corpus diff; the other no-gates-block results were not audited"),
        "n_items_audited": len(rows),
        "n_nested_dicts_where_pinned_v4_agrees_with_v5": sum(
            r["score_metrics_subdict_pinned_v4"] == r["score_metrics_subdict"]
            for r in rows if r["score_metrics_subdict_pinned_v4"] is not None),
        # the v5d corpus differential these seven came from, read from its committed receipt
        "v5d_committed_results_both_versions_refuse": v5d["n_v5_raised_on"],
        "v5d_effective_population_results_scored": v5d["n_results_v5_scored"],
        "census": {k: v for k, v in cen.items() if k != "rows"},
        "effective_population_with_nested_metrics_dicts": (
            v5d["n_results_v5_scored"] + len(reproduced)),
        "what": ("each committed result that raises when its WHOLE receipt is scored, re-scored "
                 "on its nested 'metrics' dict with the current styxx.protocol"),
        "n_items": len(rows),
        "n_protocol_scored_runners": sum(r["runner_imports_styxx_protocol"]
                                         and r["runner_calls_score"] for r in rows),
        "n_reproduced_from_metrics_subdict": len(reproduced),
        "reproduced": reproduced,
        "not_reproduced": [r["result"] for r in rows
                           if not r["metrics_subdict_reproduces_committed"]],
        "rows": rows,
    }
    out["census_rows"] = cen["rows"]
    (HERE / "corpus_provenance_rescore.json").write_text(json.dumps(out, indent=2) + "\n",
                                                         encoding="utf-8")
    print(f"{out['n_reproduced_from_metrics_subdict']} of {out['n_items']} reproduce from their "
          f"metrics sub-dict; not reproduced: {out['not_reproduced']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
