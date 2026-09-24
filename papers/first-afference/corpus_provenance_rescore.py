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

import json
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


def main() -> int:
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
        rows.append({
            "result": f"{d}/{res_name}",
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
    out = {
        "script": "papers/first-afference/corpus_provenance_rescore.py",
        # the v5d corpus differential these seven came from, read from its committed receipt
        "v5d_committed_results_both_versions_refuse": v5d["n_v5_raised_on"],
        "v5d_effective_population_results_scored": v5d["n_results_v5_scored"],
        "n_results_the_differential_could_not_score": len(rows),
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
    (HERE / "corpus_provenance_rescore.json").write_text(json.dumps(out, indent=2) + "\n",
                                                         encoding="utf-8")
    print(f"{out['n_reproduced_from_metrics_subdict']} of {out['n_items']} reproduce from their "
          f"metrics sub-dict; not reproduced: {out['not_reproduced']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
