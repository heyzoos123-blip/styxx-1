"""F05: the stdlib `profile` module refuses FOREIGN_PROFILER on 3.12 and 3.13 too, not only on <= 3.11.

Spec, Over-blocking #6: "Any pre-existing sys.setprofile profiler on the opening thread refuses
FOREIGN_PROFILER: pure-Python profilers on every version; cProfile, profile, yappi and pyinstrument
on <=3.11." and Versions: "On 3.12 and later, cProfile uses sys.monitoring and coexists with the
tracer." -- `profile` is listed with the <=3.11-only group, but profile.Profile installs itself with
sys.setprofile on every version, so a harness profiled with `profile` refuses on 3.12+ as well.
Run: PYTHONPATH=/home/user/styxx-1 python f05_profile_module_refuses_on_312.py
"""
import cProfile, json, profile, subprocess, sys, tempfile
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="rt4xv_f05_"))
modname = "_rt4xv_f05_mod"
(tmp / f"{modname}.py").write_text("def f(x=0):\n    return x\n")
sys.path.insert(0, str(tmp))
repo = tmp / "repo"; repo.mkdir()
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [f"{modname}:f"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "S"}
p = repo / "PREREG_f05.md"
p.write_text("# f05\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", "commit", "-qm", "c"]):
    subprocess.run(cmd, cwd=repo, check=True)

from styxx.protocol import Experiment, GateSpecError, coverage_trace
import importlib
mod = importlib.import_module(modname)
exp = Experiment(p)

def outcome(profiler_cls):
    with coverage_trace(exp) as cov:
        prof = profiler_cls()
        try:
            prof.runcall(cov.run, "G", mod.f, 1)
        except GateSpecError:
            pass
        finally:
            sys.setprofile(None)
    try:
        return exp.score({"m": 1.0, "coverage_trace": cov.record()}).verdict
    except GateSpecError as e:
        return str(e)[:40]
ver = sys.version.split()[0]
r_profile, r_cprofile = outcome(profile.Profile), outcome(cProfile.Profile)
print(f"[{ver}] profile.Profile: {r_profile}; cProfile.Profile: {r_cprofile}")
if sys.version_info >= (3, 12) and r_profile.startswith("[V5:FOREIGN_PROFILER]"):
    print(f"FINDING-REPRODUCED: on {ver} `profile` refuses FOREIGN_PROFILER although the spec lists it "
          f"among the profilers that refuse only on <=3.11 (cProfile: {r_cprofile})")
else:
    print(f"no finding: on {ver} the `profile` outcome matches the spec's version claim")
