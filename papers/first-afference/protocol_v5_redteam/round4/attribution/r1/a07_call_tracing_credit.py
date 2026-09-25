"""Over-blocking #14 says "Functions executed only inside profile or trace callbacks can never be
credited." A settrace callback (a debugger) that evaluates code with sys.call_tracing (pdb's
do_debug does) re-enables profiling for that call: on 3.10, 3.12 and 3.13 the hook sees it, walks
out through the trace callback into the traced section frame, and credits the section. 3.11
does not re-enable profiling there, so the SAME harness scores differently by version."""
import json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/home/user/styxx-1")
from styxx.protocol import Experiment, GateSpecError, coverage_trace
FIX = Path(tempfile.mkdtemp(prefix="a07fx_")); (FIX / "a07_fix.py").write_text("def f(): return 1\n")
sys.path.insert(0, str(FIX)); import a07_fix
td = Path(tempfile.mkdtemp(prefix="a07_"))
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["a07_fix:f"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "S"}
p = td / "PREREG_case.md"; p.write_text("# c\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for c in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=a@b", "-c",
          "user.name=a", "-c", "commit.gpgsign=false", "commit", "-qm", "c"]):
    subprocess.run(c, cwd=td, check=True)
exp = Experiment(p)
done = []

def body():                    # the section's own code never calls f
    x = 1
    x += 1
    return x

def tracer(frame, event, arg):
    if frame.f_code is body.__code__ and event == "line" and not done:
        done.append(1)
        sys.call_tracing(a07_fix.f, ())     # f runs ONLY inside the trace callback
    return tracer

with coverage_trace(exp) as cov:
    sys.settrace(tracer)
    try:
        cov.run("G", body)
    finally:
        sys.settrace(None)
try:
    v = exp.score({"m": 1.0, "coverage_trace": cov.record()})
    print(f"  {sys.version.split()[0]}: PASS {v.coverage}")
    print("FINDING-REPRODUCED: a function executed only inside a trace callback (sys.call_tracing) "
          "is credited to the section, contrary to over-blocking #14")
except GateSpecError as e:
    print(f"  {sys.version.split()[0]}: {str(e)[:80]}")
    print("no finding: code run only inside a trace callback was not credited on this version")
