"""F6 (EXAM_HOLE): the frozen exam does not pin two boundaries of score()'s stated step order, so
two reorder mutants of Experiment._check_coverage pass it:

  MD  step 7 (recorded problem) moved AFTER step 8 (SECTION_ABSENT). X78c pins problems before
      NOT_EXERCISED only; no case has a problem AND an absent section.
  ME  step 4 (STALE_TRACE) moved BEFORE step 3 (BAD_TRACE). Every BAD_TRACE case edits a trace of
      the SAME gates block, so a malformed trace never reaches STALE first.

Paired harnesses:
  HD  gates G [f], H [g]; the harness runs its cases under a per-case try/except (a common shape)
      and typos G's section: cov.run("G_typo", f) is refused and swallowed; cov.run("H", g).
      Spec: step 7 -> every declaring gate refuses [V5:UNDECLARED_SECTION] (the actual cause, which
      names the typo). MD: gate G refuses [V5:SECTION_ABSENT] and the recorded cause is hidden.
  HE  the tracer's own trace with its "gates_sha256" key missing (a truncated/hand-edited trace).
      Spec: step 3 "BAD_TRACE, in one pass before anything is read" -> [V5:BAD_TRACE].
      ME: KeyError out of score() and check_metrics() (a crash, not a refusal).

Run: PYTHONPATH=/home/user/styxx-1 python f6_exam_hole_step_order.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path("/home/user/styxx-1")
RUNNER = REPO / "papers/first-afference/run_protocol_v5e.py"
HERE = Path(__file__).resolve().parent
WORK = Path(tempfile.mkdtemp(prefix=f"f6_py{sys.version_info[0]}{sys.version_info[1]}_", dir=HERE))

MUTANTS = {
    "MD": [("        problems = tr[\"problems\"]\n        if problems:",
            "        problems = tr[\"problems\"]\n"
            "        if tr[\"sections\"].get(c[\"section\"]) is None:\n"
            "            raise GateSpecError(\n"
            "                f\"[V5:SECTION_ABSENT] gate {name!r}: section {c['section']!r} was never opened\")\n"
            "        if problems:")],
    "ME": [("        _check_trace_shape(name, tr)\n        if tr[\"gates_sha256\"] != self.gates_sha256:",
            "        if tr[\"gates_sha256\"] != self.gates_sha256:"),
           ("        if sorted(tr[\"targets\"]) != self.coverage_targets:",
            "        _check_trace_shape(name, tr)\n        if sorted(tr[\"targets\"]) != self.coverage_targets:")],
}

HARNESS = r'''
import json, subprocess, sys, tempfile, uuid
from pathlib import Path
from styxx.protocol import Experiment, GateSpecError, coverage_trace
tmp = Path(tempfile.mkdtemp(prefix="rt4sc_f6h_"))
mn = "rt4sc_fx_" + uuid.uuid4().hex[:8]
(tmp / f"{mn}.py").write_text("def f():\n    return 1\n\ndef g():\n    return 2\n")
sys.path.insert(0, str(tmp))
mod = __import__(mn)
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [f"{mn}:f"]},
                  "H": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [f"{mn}:g"]}},
        "outcomes": [{"when": {"G": True, "H": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "SMOKE"}
d = tmp / "r"; d.mkdir()
(d / "PREREG_x.md").write_text("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=a@b",
            "-c", "user.name=a", "-c", "commit.gpgsign=false", "commit", "-qm", "x"]):
    subprocess.run(cmd, cwd=d, check=True, capture_output=True)
exp = Experiment(d / "PREREG_x.md")
def score(rec):
    try:
        return exp.score({"m": 1.0, "coverage_trace": rec}).verdict
    except GateSpecError as e:
        return str(e)[:34]
    except Exception as e:
        return f"CRASH {type(e).__name__}: {e}"
with coverage_trace(exp) as cov:
    for sec, fn in (("G_typo", mod.f), ("H", mod.g)):     # per-case isolation, as harnesses do
        try:
            cov.run(sec, fn)
        except GateSpecError:
            pass
hd = score(cov.record())
with coverage_trace(exp) as cov:
    cov.run("G", mod.f); cov.run("H", mod.g)
rec = cov.record(); rec.pop("gates_sha256")
he = score(rec)
print(json.dumps({"HD": hd, "HE": he}))
'''


def exam(root):
    env = dict(os.environ, STYXX_V5_IMPORT_ROOT=str(root), PYTHONDONTWRITEBYTECODE="1",
               STYXX_V5_RESULT_OUT=str(root / "result.json"))
    p = subprocess.run([sys.executable, str(RUNNER), "--smoke", "--full-battery", "--mutation-mode"],
                       cwd=REPO, env=env, capture_output=True, text=True, timeout=240)
    if p.returncode != 0 or not (root / "result.json").exists():
        return f"DETECTED (exit {p.returncode})"
    r = json.loads((root / "result.json").read_text(encoding="utf-8"))
    fv = sorted(k for k, v in r.get("violation_cases", {}).items() if not v.get("ok"))
    fg = sorted(k for k, v in r.get("valid_cases", {}).items() if not v.get("ok"))
    if fv or fg or r.get("p1_retro_exact") != 1.0 or r.get("n_crashes", 0):
        return f"DETECTED {fv[:4]} {fg[:4]}"
    return "SURVIVED (all violation, valid and residual cases ok)"


def harness(root):
    hp = WORK / "harness.py"
    hp.write_text(HARNESS)
    env = dict(os.environ, PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, str(hp)], env=env, capture_output=True, text=True, timeout=60)
    return json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else {"err": p.stderr[-300:]}


print(f"python {sys.version.split()[0]}")
orig = harness(REPO)
print(f"  original harness: {orig}")
surv = []
try:
    for tag, reps in MUTANTS.items():
        root = WORK / tag
        shutil.copytree(REPO / "styxx", root / "styxx", ignore=shutil.ignore_patterns("__pycache__"))
        pp = root / "styxx" / "protocol.py"
        src = pp.read_text(encoding="utf-8")
        for old, new in reps:
            assert src.count(old) == 1, (tag, old)
            src = src.replace(old, new)
        pp.write_text(src, encoding="utf-8")
        h = harness(root)
        ex = exam(root)
        key = "HD" if tag == "MD" else "HE"
        print(f"  {tag} harness: {h}")
        print(f"  {tag} exam: {ex}")
        if ex.startswith("SURVIVED") and h.get(key) != orig.get(key):
            surv.append(tag)
finally:
    shutil.rmtree(WORK, ignore_errors=True)
if surv:
    print(f"FINDING-REPRODUCED: step-order mutants {surv} pass the frozen exam; MD hides the recorded "
          f"UNDECLARED_SECTION behind SECTION_ABSENT, ME crashes with KeyError on a trace missing "
          f"gates_sha256 where the original refuses BAD_TRACE")
else:
    print("no finding: the step-order mutants are detected")
