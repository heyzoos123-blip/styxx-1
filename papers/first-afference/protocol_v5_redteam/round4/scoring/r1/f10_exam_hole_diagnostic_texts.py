"""F10 (EXAM_HOLE): the diagnostic outputs that the spec's closures rest on are not pinned by the
frozen exam, so three mutants that make them lie pass it:

  MS  _check_coverage's NOT_EXERCISED message prints the two uncredited buckets under each other's
      labels ("dispatched {unat}, unattributed {disp}"). X72/X73's msg_lists_diagnostics only checks
      that a changed COUNT shows up somewhere in the text, never under which label -- yet the
      closure row "J2: message says 'never executed' misleadingly | CLOSED_P | ... dispatched/
      unattributed counts ... (X72, X73, which check the message text)" rests on it. The label is
      the remedy: dispatched = cut at Handle._run (open run_async in the task), unattributed = off
      the section's stack (open a section on that thread).
  MU  check_metrics reports a NOT_EXERCISED coverage refusal as usable: True (the pre-run safety
      tool gives an all-clear for a harness that never calls a declared target). X117 checks only
      usable False for None/[]/'s'/5 (all NO_TRACE).
  MN  check_metrics drops the refusal text (note None) -- the spec: "reports usable: False with the
      refusal text".

Paired harness: gate G [f]; asyncio.run(cov.run_async("G", main)) where main gathers two children
that call f (the X72 shape). Original: message "dispatched {f: 2}, unattributed {}", check_metrics
usable False with the NOT_EXERCISED text. Each mutant changes exactly its output.

Run: PYTHONPATH=/home/user/styxx-1 python f10_exam_hole_diagnostic_texts.py
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
WORK = Path(tempfile.mkdtemp(prefix=f"f10_py{sys.version_info[0]}{sys.version_info[1]}_", dir=HERE))

CM = "\"usable\": False, \"note\": \"smoke run\" if smoke else str(e)}"
MUTANTS = {
    "MS": ("f\"dispatched {disp}, unattributed {unat}; openings' non-returned ends {ends}; \"",
           "f\"dispatched {unat}, unattributed {disp}; openings' non-returned ends {ends}; \""),
    "MU": (CM, "\"usable\": str(e).startswith(\"[V5:NOT_EXERCISED]\"), \"note\": str(e)}"),
    "MN": (CM, "\"usable\": False, \"note\": None}"),
}

HARNESS = r'''
import asyncio, json, re, subprocess, sys, tempfile, uuid
from pathlib import Path
from styxx.protocol import Experiment, GateSpecError, coverage_trace
tmp = Path(tempfile.mkdtemp(prefix="rt4sc_f10h_"))
mn = "rt4sc_fx_" + uuid.uuid4().hex[:8]
(tmp / f"{mn}.py").write_text("def f():\n    return 1\n")
sys.path.insert(0, str(tmp))
mod = __import__(mn)
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [f"{mn}:f"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "SMOKE"}
d = tmp / "r"; d.mkdir()
(d / "PREREG_x.md").write_text("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=a@b",
            "-c", "user.name=a", "-c", "commit.gpgsign=false", "commit", "-qm", "x"]):
    subprocess.run(cmd, cwd=d, check=True, capture_output=True)
exp = Experiment(d / "PREREG_x.md")
async def main():
    async def child():
        mod.f()
    await asyncio.gather(child(), child())
with coverage_trace(exp) as cov:
    asyncio.run(cov.run_async("G", main))
res = {"m": 1.0, "coverage_trace": cov.record()}
try:
    exp.score(res); msg = "PASS"
except GateSpecError as e:
    msg = str(e)
lab = re.search(r"dispatched (\{.*?\}), unattributed (\{.*?\})", msg)
cm = exp.check_metrics(res)["G:exercises"]
print(json.dumps({"trace_uncredited": res["coverage_trace"]["uncredited"],
                  "msg_labels": lab.groups() if lab else None,
                  "cm_usable": cm["usable"], "cm_note": (cm["note"] or "")[:30] or None}).replace(mn, "fx"))
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
    return "SURVIVED"


def harness(root):
    hp = WORK / "harness.py"
    hp.write_text(HARNESS)
    env = dict(os.environ, PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, str(hp)], env=env, capture_output=True, text=True, timeout=60)
    return json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else {"err": p.stderr[-300:]}


print(f"python {sys.version.split()[0]}")
orig = harness(REPO)
print(f"  original: {orig}")
surv = []
try:
    for tag, (old, new) in MUTANTS.items():
        root = WORK / tag
        shutil.copytree(REPO / "styxx", root / "styxx", ignore=shutil.ignore_patterns("__pycache__"))
        pp = root / "styxx" / "protocol.py"
        src = pp.read_text(encoding="utf-8")
        assert src.count(old) == 1, (tag, old)
        pp.write_text(src.replace(old, new), encoding="utf-8")
        h = harness(root)
        ex = exam(root)
        print(f"  {tag}: exam {ex}; harness {h}")
        if ex == "SURVIVED" and h != orig:
            surv.append(tag)
finally:
    shutil.rmtree(WORK, ignore_errors=True)
if surv:
    print(f"FINDING-REPRODUCED: diagnostic-text mutants {surv} pass the frozen exam while their "
          f"NOT_EXERCISED labels / check_metrics verdicts differ from the original's")
else:
    print("no finding: the diagnostic-text mutants are detected")
