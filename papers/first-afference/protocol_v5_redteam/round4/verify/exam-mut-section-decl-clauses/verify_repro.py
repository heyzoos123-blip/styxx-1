#!/usr/bin/env python
"""Independent verifier repro for exam-mut-section-decl-clauses.

Claim: SECTION_DECL's `not sec` clause and `not sec.isascii()` clause can each be deleted and the
frozen v5e exam still passes; the original refuses `section: ""` and `section: "sección"`.

This script (never touching /home/user/styxx-1):
  1. makes three private copies of styxx/ under WORK: base (unmutated), D01 (drop isascii clause),
     D02 (drop non-empty clause);
  2. for each copy, in its own subprocess, runs an END-TO-END harness (parse -> coverage_trace ->
     cov.run -> record -> score) for section values "sección" and "", plus a control ("S");
  3. runs the frozen exam (--smoke --full-battery --mutation-mode) against each copy and judges it the
     way mutation_gate.py defines DETECTED.
Usage: python verify_repro.py [--no-exam]
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path("/home/user/styxx-1")
RUNNER = REPO / "papers/first-afference/run_protocol_v5e.py"
WORK = Path(__file__).resolve().parent / "work"
LINE = "            if not isinstance(sec, str) or not sec or not sec.isascii():"
MUTANTS = {
    "base": None,
    "D01_drop_isascii": "            if not isinstance(sec, str) or not sec:",
    "D02_drop_nonempty": "            if not isinstance(sec, str) or not sec.isascii():",
}

HARNESS = r'''
import json, subprocess, sys, tempfile
from pathlib import Path
import styxx.protocol as P
from styxx.protocol import Experiment, coverage_trace, GateSpecError
fxd = Path(tempfile.mkdtemp(prefix="vfx_")); (fxd / "vsd_fx.py").write_text("def f():\n    return 1\n")
sys.path.insert(0, str(fxd))
import vsd_fx

def prereg(section):
    spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5,
                            "exercises": ["vsd_fx:f"], "section": section}},
            "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "SMOKE"}
    d = Path(tempfile.mkdtemp(prefix="vpr_")); p = d / "PREREG_v.md"
    p.write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=v@v", "-c", "user.name=v", "-c", "commit.gpgsign=false",
               "commit", "-qm", "v"]):
        subprocess.run(c, cwd=d, check=True, capture_output=True)
    return p

out = {"impl": P.__file__}
for sec in ("S", "sección", ""):
    r = {}
    try:
        exp = Experiment(prereg(sec))
        r["parse"] = "accepted"
        r["coverage_sections"] = exp.coverage_sections
        with coverage_trace(exp) as cov:
            cov.run(sec, vsd_fx.f)
        rec = cov.record()
        r["calls"] = {s: [o["calls"] for o in v] for s, v in rec["sections"].items()}
        v = exp.score({"m": 1.0, "coverage_trace": rec})
        r["verdict"] = v.verdict
    except GateSpecError as e:
        r.setdefault("parse", "refused")
        r["refusal"] = str(e)[:90]
    out[repr(sec)] = r
print("RESULT " + json.dumps(out, ensure_ascii=True))
'''


def build(name, repl):
    root = WORK / name
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(REPO / "styxx", root / "styxx", ignore=shutil.ignore_patterns("__pycache__"))
    if repl is not None:
        p = root / "styxx/protocol.py"
        src = p.read_text(encoding="utf-8")
        assert src.count(LINE) == 1
        p.write_text(src.replace(LINE, repl), encoding="utf-8")
    return root


def harness(root):
    env = dict(os.environ, PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-c", HARNESS], cwd=str(WORK), env=env,
                       capture_output=True, text=True, timeout=60)
    ln = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
    if not ln:
        return {"crash": (p.stdout + p.stderr)[-800:]}
    r = json.loads(ln[-1][7:])
    assert r["impl"].startswith(str(root)), r["impl"]
    return r


def exam(root):
    out = root / "r.json"
    if out.exists():
        out.unlink()
    env = dict(os.environ, STYXX_V5_IMPORT_ROOT=str(root), STYXX_V5_RESULT_OUT=str(out),
               PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    try:
        p = subprocess.run([sys.executable, str(RUNNER), "--smoke", "--full-battery", "--mutation-mode"],
                           cwd=str(REPO), env=env, capture_output=True, text=True, timeout=85)
    except subprocess.TimeoutExpired:
        return "DETECTED (timeout)"
    if p.returncode != 0 or not out.exists():
        return f"DETECTED (exit {p.returncode}) {p.stderr[-200:]}"
    r = json.loads(out.read_text())
    fv = sorted(k for k, v in r.get("violation_cases", {}).items() if not v.get("ok"))
    fg = sorted(k for k, v in r.get("valid_cases", {}).items() if not v.get("ok"))
    nv, ng = len(r.get("violation_cases", {})), len(r.get("valid_cases", {}))
    if fv or fg or r.get("p1_retro_exact") != 1.0 or r.get("n_crashes", 0):
        return f"DETECTED violations={fv[:5]} valid={fg[:5]} retro={r.get('p1_retro_exact')}"
    return (f"SURVIVES ({nv} violation cases ok, {ng} valid cases ok, "
            f"residuals {r.get('frac_residuals_as_documented')}, retro {r.get('p1_retro_exact')}, "
            f"crashes {r.get('n_crashes')})")


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    print("python", sys.version.split()[0])
    for name, repl in MUTANTS.items():
        root = build(name, repl)
        h = harness(root)
        h.pop("impl", None)
        print(f"[{name}] harness: {json.dumps(h, ensure_ascii=True)}")
        if "--no-exam" not in sys.argv:
            print(f"[{name}] exam: {exam(root)}")
    shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    main()
