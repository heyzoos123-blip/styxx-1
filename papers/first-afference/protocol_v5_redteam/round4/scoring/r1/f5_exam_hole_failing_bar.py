"""F5 (EXAM_HOLE): every scored exam case gives the declaring gate a PASSING bar (the exam's _res()
always writes m=1.0 against ">= 0.5"; X118's metric is 1.0), so a score() mutant that checks
coverage only for gates whose bar passed survives the frozen exam:

  MF: in score(), `if name in self.coverage:` -> `if name in self.coverage and fired[name]:`
      (fired computed first)

Paired harness: gate G {exercises [f, g], metric m >= 0.5}; the harness calls f only and measures
m = 0.0. Per spec ("score() for a declaring gate, in this order ... NOT_EXERCISED"; "Every entry in
problems ... refuses every declaring gate scored against the trace") the original refuses
[V5:NOT_EXERCISED]; the mutant returns the frozen table's FAIL row as a sealed verdict from a
harness that never ran g -- the P1 defect with the sign flipped (a negative result for code the
harness never executed). Same for a swallowed NESTED_SECTION.

Run: PYTHONPATH=/home/user/styxx-1 python f5_exam_hole_failing_bar.py
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
WORK = Path(tempfile.mkdtemp(prefix=f"f5_py{sys.version_info[0]}{sys.version_info[1]}_", dir=HERE))

OLD = ("            if name in self.coverage:\n"
       "                covered[name] = self._check_coverage(name, result)\n"
       "            fired[name] = bool(op(_v, g[\"value\"]))")
NEW = ("            fired[name] = bool(op(_v, g[\"value\"]))\n"
       "            if name in self.coverage and fired[name]:\n"
       "                covered[name] = self._check_coverage(name, result)")

HARNESS = r'''
import json, subprocess, sys, tempfile, uuid
from pathlib import Path
from styxx.protocol import Experiment, GateSpecError, coverage_trace
tmp = Path(tempfile.mkdtemp(prefix="rt4sc_f5h_"))
mn = "rt4sc_fx_" + uuid.uuid4().hex[:8]
(tmp / f"{mn}.py").write_text("def f():\n    return 1\n\ndef g():\n    return 2\n")
sys.path.insert(0, str(tmp))
mod = __import__(mn)
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5,
                        "exercises": [f"{mn}:f", f"{mn}:g"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {"G": False}, "verdict": "FAIL"}],
        "smoke_verdict": "SMOKE"}
d = tmp / "r"; d.mkdir()
(d / "PREREG_x.md").write_text("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=a@b",
            "-c", "user.name=a", "-c", "commit.gpgsign=false", "commit", "-qm", "x"]):
    subprocess.run(cmd, cwd=d, check=True, capture_output=True)
exp = Experiment(d / "PREREG_x.md")
def outcome(harness, m):
    with coverage_trace(exp) as cov:
        harness(cov)
    try:
        return exp.score({"m": m, "coverage_trace": cov.record()}).verdict
    except GateSpecError as e:
        return str(e)[:40]
def nested(cov):
    def inner():
        try:
            cov.run("G", mod.g)
        except GateSpecError:
            pass
        mod.f()
    cov.run("G", inner)
out = {"not_exercised_bar_fails": outcome(lambda cov: cov.run("G", mod.f), 0.0),
       "swallowed_nested_bar_fails": outcome(nested, 0.0),
       "not_exercised_bar_passes": outcome(lambda cov: cov.run("G", mod.f), 1.0)}
print(json.dumps(out))
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
    return (f"SURVIVED ({len(r['violation_cases'])} violation, {len(r['valid_cases'])} valid, "
            f"{len(r['residual_cases'])} residual cases all ok)")


def harness(root):
    hp = WORK / "harness.py"
    hp.write_text(HARNESS)
    env = dict(os.environ, PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, str(hp)], env=env, capture_output=True, text=True, timeout=60)
    return json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else {"err": p.stderr[-300:]}


print(f"python {sys.version.split()[0]}")
try:
    root = WORK / "MF"
    shutil.copytree(REPO / "styxx", root / "styxx", ignore=shutil.ignore_patterns("__pycache__"))
    pp = root / "styxx" / "protocol.py"
    src = pp.read_text(encoding="utf-8")
    assert src.count(OLD) == 1
    pp.write_text(src.replace(OLD, NEW), encoding="utf-8")
    orig = harness(REPO)
    mut = harness(root)
    ex = exam(root)
finally:
    shutil.rmtree(WORK, ignore_errors=True)
print(f"  original harness: {orig}")
print(f"  mutant   harness: {mut}")
print(f"  mutant   exam:    {ex}")
if ex.startswith("SURVIVED") and orig["not_exercised_bar_fails"].startswith("[V5:NOT_EXERCISED]") \
        and mut["not_exercised_bar_fails"] == "FAIL":
    print("FINDING-REPRODUCED: the mutant that checks coverage only for gates whose bar passed "
          "survives the frozen exam; on a failing bar it seals FAIL where the original refuses "
          "[V5:NOT_EXERCISED] / [V5:NESTED_SECTION]")
else:
    print("no finding: the bar-conditioned coverage mutant is detected or behaves identically")
