"""Verifier's own repro. Over-blocking #14 of the v5e spec: "Functions executed only inside profile
or trace callbacks can never be credited." A settrace callback runs the declared target ONLY
through sys.call_tracing (as pdb's `debug` command does). Two arms:
  CT   : tracer calls sys.call_tracing(target, ())
  PLAIN: tracer calls target() directly (control; should never be credited on any version)
The section's own code never calls the target in either arm."""
import json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/home/user/styxx-1")
from styxx.protocol import Experiment, GateSpecError, coverage_trace

mod_dir = Path(tempfile.mkdtemp(prefix="vct_mod_"))
(mod_dir / "vct_target.py").write_text("def target(n):\n    return n * 2\n")
sys.path.insert(0, str(mod_dir))
import vct_target

repo = Path(tempfile.mkdtemp(prefix="vct_repo_"))
gates = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0,
                         "exercises": ["vct_target:target"], "section": "S"}},
         "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
         "smoke_verdict": "SMOKE"}
pre = repo / "PREREG_vct.md"
pre.write_text("# vct\n\n```gates\n" + json.dumps(gates) + "\n```\n")
for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
            ["git", "-c", "user.email=v@v", "-c", "user.name=v", "-c", "commit.gpgsign=false",
             "commit", "-qm", "p"]):
    subprocess.run(cmd, cwd=repo, check=True)
exp = Experiment(pre)

def section_body(k):
    # never references vct_target
    total = 0
    for i in range(k):
        total += i
    return total

def run_arm(use_call_tracing):
    fired = []
    def tr(frame, event, arg):
        if event == "call" and frame.f_code is section_body.__code__ and not fired:
            fired.append(1)
            if use_call_tracing:
                sys.call_tracing(vct_target.target, (3,))
            else:
                vct_target.target(3)
        return None
    with coverage_trace(exp) as cov:
        old = sys.gettrace()
        sys.settrace(tr)
        try:
            cov.run("S", section_body, 4)
        finally:
            sys.settrace(old)
    rec = cov.record()
    assert fired == [1]
    try:
        v = exp.score({"m": 1, "coverage_trace": rec})
        out = f"verdict={v.verdict} coverage={v.coverage}"
    except GateSpecError as e:
        out = str(e)[:60]
    return out, rec["sections"], rec["uncredited"]

ver = sys.version.split()[0]
for arm, flag in (("CT", True), ("PLAIN", False)):
    out, secs, unc = run_arm(flag)
    print(f"{ver} {arm:5s}: {out} | sections={secs} uncredited={unc}")
print(f"{ver} leftover getprofile={sys.getprofile()!r}, code restored="
      f"{vct_target.target.__code__.co_name == 'target'}")
