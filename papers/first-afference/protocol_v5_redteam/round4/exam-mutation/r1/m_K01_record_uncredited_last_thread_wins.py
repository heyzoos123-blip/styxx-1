#!/usr/bin/env python
"""EXAM_HOLE (diagnostic only): record() sums each thread's uncredited counts. The mutant keeps
the last thread's count (disp[k] = v). No exam case books the same target as dispatched on two
threads, so the mutant survives; the NOT_EXERCISED message then under-reports the dispatched calls
it prints as evidence of where the work went.

Self-contained. Run:  PYTHONPATH=/home/user/styxx-1 python THIS_FILE.py [--no-exam]
It (1) builds the mutant in a private copy of the styxx package (the repo is never touched),
(2) runs the harness below against the UNMUTATED styxx (from /home/user/styxx-1) and against the
mutant, each in its own subprocess, (3) unless --no-exam, runs the frozen exam
(run_protocol_v5e.py --smoke --full-battery --mutation-mode) against the mutant, judged exactly as
mutation_gate.run_exam judges it, and prints one line: FINDING-REPRODUCED or no finding."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path("/home/user/styxx-1")
RUNNER = REPO / "papers/first-afference/run_protocol_v5e.py"
SCRATCH = Path("/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/exam-mutation/r1/tmp")
MUTANT_NAME = "K01_record_uncredited_last_thread_wins"
MUTATION = [('                disp[k] = disp.get(k, 0) + v', '                disp[k] = v')]

PRELUDE = r'''
import json, subprocess, sys, tempfile, textwrap, os, importlib, threading, types, functools, gc
from pathlib import Path
import styxx.protocol as P
from styxx.protocol import Experiment, coverage_trace, GateSpecError
_D = Path(tempfile.mkdtemp(prefix="rt4em_h_"))
sys.path.insert(0, str(_D))
def module(name, src):
    (_D / f"{name}.py").write_text(textwrap.dedent(src))
    return importlib.import_module(name)
def experiment(**gates):
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, **extra} for n, extra in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "SMOKE"}
    d = Path(tempfile.mkdtemp(prefix="rt4em_p_")); p = d / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
                 "commit", "-qm", "c"]):
        subprocess.run(cmd, cwd=d, check=True, capture_output=True)
    return Experiment(p)
def gate(exp, rec, name):
    try:
        return {"pass": exp._check_coverage(name, {"m": 1.0, "coverage_trace": rec})}
    except GateSpecError as e:
        return {"refused": str(e)}
def emit(**kw):
    kw["impl"] = P.__file__
    print("RESULT: " + json.dumps(kw, default=repr), flush=True)
'''

HARNESS = r'''import asyncio
mod = module("rt4k01_fx", "def f(): return 1\ndef g(): return 2\n")
exp = experiment(A={"exercises": ["rt4k01_fx:g"]}, B={"exercises": ["rt4k01_fx:f"]})
with coverage_trace(exp) as cov:
    def shard():
        def body():
            mod.f()
            loop = asyncio.new_event_loop()
            loop.call_soon(mod.g)                 # g is dispatched by a loop callback
            loop.call_soon(loop.stop)
            loop.run_forever(); loop.close()
        cov.run("B", body)
    ts = [threading.Thread(target=shard) for _ in range(2)]
    for t in ts: t.start()
    for t in ts: t.join()
    cov.run("A", lambda: None)
rec = cov.record()
emit(dispatched=rec["uncredited"]["dispatched"])'''


def judge(orig, mut):
    ok = orig["dispatched"].get("rt4k01_fx:g") == 2 and mut["dispatched"].get("rt4k01_fx:g") == 1
    return ok, ("two threads each dispatch g once: the original records dispatched g=2, the mutant 1"
                if ok else "no difference")


def build_mutant(root: Path) -> None:
    shutil.copytree(REPO / "styxx", root / "styxx", ignore=shutil.ignore_patterns("__pycache__"))
    src = (REPO / "styxx/protocol.py").read_text(encoding="utf-8")
    for old, new in MUTATION:
        assert src.count(old) == 1, f"mutation anchor not unique/present: {old[:70]!r}"
        src = src.replace(old, new)
    (root / "styxx/protocol.py").write_text(src, encoding="utf-8")


def run_harness(import_root: Path, cwd: Path) -> dict:
    env = dict(os.environ, PYTHONPATH=str(import_root), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-c", PRELUDE + HARNESS], cwd=cwd, env=env,
                       capture_output=True, text=True, timeout=40)
    lines = [ln for ln in p.stdout.splitlines() if ln.startswith("RESULT: ")]
    if not lines:
        return {"crash": (p.stdout + p.stderr)[-600:], "rc": p.returncode}
    r = json.loads(lines[-1][len("RESULT: "):])
    assert r["impl"].startswith(str(import_root)), (r["impl"], import_root)
    return r


def run_exam(import_root: Path) -> tuple:
    out = import_root / "exam_result.json"
    env = dict(os.environ, STYXX_V5_IMPORT_ROOT=str(import_root), STYXX_V5_RESULT_OUT=str(out),
               PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    try:
        p = subprocess.run([sys.executable, str(RUNNER), "--smoke", "--full-battery", "--mutation-mode"],
                           cwd=REPO, env=env, capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        return False, "exam timed out (a timeout counts as DETECTED)"
    if p.returncode != 0 or not out.exists():
        return False, f"exam exit {p.returncode} (DETECTED): {p.stderr.strip()[-200:]}"
    r = json.loads(out.read_text())
    fv = sorted(k for k, v in r.get("violation_cases", {}).items() if not v.get("ok"))
    fg = sorted(k for k, v in r.get("valid_cases", {}).items() if not v.get("ok"))
    if fv or fg or r.get("p1_retro_exact") != 1.0 or r.get("n_crashes", 0):
        return False, f"exam DETECTED the mutant: violations {fv[:6]} valid {fg[:6]}"
    return True, (f"exam passes the mutant: violation {r['frac_violation_cases_refused_with_expected_code']}, "
                  f"valid {r['frac_valid_cases_exact']}, residuals {r['frac_residuals_as_documented']}, "
                  f"retro {r['p1_retro_exact']}, crashes {r['n_crashes']}")


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f"{MUTANT_NAME}_", dir=str(SCRATCH)))
    try:
        mroot = tmp / "mutant"
        mroot.mkdir()
        build_mutant(mroot)
        cwd = tmp / "cwd"
        cwd.mkdir()
        orig = run_harness(REPO, cwd)
        mut = run_harness(mroot, cwd)
        print(f"python {sys.version.split()[0]}")
        print(f"original: {json.dumps(orig)[:900]}")
        print(f"mutant:   {json.dumps(mut)[:900]}")
        ok, why = judge(orig, mut)
        print(f"harness: {why}")
        survived, how = (True, "exam skipped (--no-exam)") if "--no-exam" in sys.argv else run_exam(mroot)
        print(f"exam: {how}")
        if ok and survived:
            print(f"FINDING-REPRODUCED: mutant {MUTANT_NAME} survives the frozen v5e exam and {why}")
        else:
            print(f"no finding: mutant {MUTANT_NAME}: harness ok={ok}, exam-survived={survived}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
