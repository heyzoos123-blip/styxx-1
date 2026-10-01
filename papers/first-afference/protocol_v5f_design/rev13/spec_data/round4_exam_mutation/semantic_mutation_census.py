"""Semantic-mutation census of the frozen v5e exam (red-team round 4).

The frozen mutation gate (``mutation_gate.py``) measures one operator: delete a coded refusal. The v5e
exam detected 57 of 57 such deletions. Round 4's exam-mutation lens asked a different question: does
the exam notice when a rule is WEAKENED rather than deleted? Examples are a condition narrowed, a bound
shrunk, two scoring steps reordered, or an exact-type check relaxed. ``mutants.py`` is that lens's
table, copied verbatim, with every mutant as a set of exact text replacements in ``styxx/protocol.py``.
This script applies each one to a private copy of the package and runs the frozen exam in the gate's
own mode (``--smoke --full-battery --mutation-mode``).

A mutant is DETECTED when the run exits non-zero, times out, or writes no result, or when any
violation, valid or residual case is not ok, the P1 retro is not exact, or any case crashes. Residual
cases are counted here, because a scored run would fail G5 on them; the frozen gate's definition omits
them. The unmutated baseline must pass, or the census is INVALID.

This is a census of a HAND-AIMED mutant set, and the mutants were chosen to probe likely weak spots.
The detection rate is therefore not an estimate of the exam's power over all possible faults. A
survivor is also not proven non-equivalent until a witness program separates it from the original.
The round-4 verifiers built those witnesses separately (``protocol_v5_redteam_audit.json``, round_4).

Writes ``semantic_mutation_census.json`` next to this file.
"""
from __future__ import annotations

import ast
import concurrent.futures as cf
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RUNNER = ROOT / "papers" / "first-afference" / "run_protocol_v5e.py"
IMPL = ROOT / "styxx" / "protocol.py"
OUT = HERE / "semantic_mutation_census.json"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _table() -> dict:
    spec = importlib.util.spec_from_file_location("mutants", HERE / "mutants.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    out = {}
    for name in sorted(k for k in vars(m) if k.startswith("MUTANTS")):
        for key, reps in getattr(m, name).items():
            assert key not in out, key
            out[key] = reps
    return out


def _run(name: str, reps: list, work: Path) -> dict:
    src = IMPL.read_text(encoding="utf-8")
    for old, new in reps:
        n = src.count(old)
        if n != 1:
            return {"mutant": name, "applied": False, "why": f"anchor found {n} times: {old[:60]!r}"}
        src = src.replace(old, new)
    ast.parse(src)
    d = work / name
    shutil.copytree(ROOT / "styxx", d / "styxx", ignore=shutil.ignore_patterns("__pycache__"))
    if reps:
        (d / "styxx" / "protocol.py").write_text(src, encoding="utf-8")
    out = d / "result.json"
    env = dict(os.environ, STYXX_V5_IMPORT_ROOT=str(d), STYXX_V5_RESULT_OUT=str(out),
               PYTHONDONTWRITEBYTECODE="1")
    try:
        p = subprocess.run([sys.executable, str(RUNNER), "--smoke", "--full-battery", "--mutation-mode"],
                           cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return {"mutant": name, "applied": True, "detected": True, "how": ["timeout"]}
    if p.returncode != 0 or not out.exists():
        return {"mutant": name, "applied": True, "detected": True,
                "how": [f"exit {p.returncode}: {p.stderr.strip()[-160:]}"]}
    r = json.loads(out.read_text(encoding="utf-8"))
    how = []
    for fam in ("violation_cases", "valid_cases", "residual_cases"):
        bad = sorted(k for k, v in (r.get(fam) or {}).items() if not v.get("ok"))
        if bad:
            how.append(f"{fam}: {bad[:10]}")
    if r.get("p1_retro_exact") != 1.0:
        how.append("p1_retro")
    if r.get("n_crashes"):
        how.append(f"{r['n_crashes']} crashes")
    return {"mutant": name, "applied": True, "detected": bool(how), "how": how}


def main() -> int:
    table = _table()
    work = Path(tempfile.mkdtemp(prefix="v5e_semmut_"))
    base = _run("__baseline__", [], work)
    jobs = int(os.environ.get("STYXX_CENSUS_JOBS", "2"))
    with cf.ThreadPoolExecutor(jobs) as ex:
        rows = list(ex.map(lambda kv: _run(kv[0], kv[1], work), sorted(table.items())))
    shutil.rmtree(work, ignore_errors=True)
    applied = [r for r in rows if r["applied"]]
    det = [r for r in applied if r["detected"]]
    res = {
        "what": "semantic-mutation census of the frozen v5e exam: a hand-aimed set of weakened-rule mutants "
                "(round-4 red team, exam-mutation lens), each run through the exam in the mutation gate's mode",
        "generator": "papers/first-afference/protocol_v5_redteam/round4_exam_mutation/semantic_mutation_census.py",
        "generator_sha256": _sha(Path(__file__)),
        "mutants_sha256": _sha(HERE / "mutants.py"),
        "runner_sha256": _sha(RUNNER),
        "impl_sha256": _sha(IMPL),
        "python": sys.version.split()[0],
        "baseline_clean": not base.get("detected", True),
        "baseline": base,
        "n_mutants": len(rows),
        "n_applied": len(applied),
        "n_detected": len(det),
        "n_survived": len(applied) - len(det),
        "frac_detected": round(len(det) / len(applied), 4) if applied else None,
        "survivors": sorted(r["mutant"] for r in applied if not r["detected"]),
        "not_applied": [r for r in rows if not r["applied"]],
        "rows": rows,
        "reading": ("Detection over a hand-aimed set, not the exam's power over all faults. A survivor is an "
                    "exam hole only once a witness program separates it from the original; see the round-4 "
                    "audit for which survivors were witnessed and which were judged equivalent."),
    }
    if not res["baseline_clean"]:
        res["verdict"] = "INVALID__baseline_not_clean"
    OUT.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(f"baseline clean {res['baseline_clean']} | {len(det)}/{len(applied)} detected, "
          f"{res['n_survived']} survived, {len(res['not_applied'])} not applied -> {OUT.name}")
    return 0 if res["baseline_clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
