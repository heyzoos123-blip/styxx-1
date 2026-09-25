"""Own repro: does stdlib `profile.Profile` refuse FOREIGN_PROFILER on 3.12+? (and cProfile?)"""
import cProfile, json, profile, subprocess, sys, tempfile, inspect
from pathlib import Path
tmp = Path(tempfile.mkdtemp(prefix="vf_prof_"))
(tmp / "vfprofmod.py").write_text("def g():\n    return 7\n")
sys.path.insert(0, str(tmp))
repo = tmp / "r"; repo.mkdir()
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["vfprofmod:g"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "S"}
(repo / "PREREG.md").write_text("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for c in (["git","init","-q"],["git","add","-A"],["git","-c","user.email=a@b","-c","user.name=a","-c","commit.gpgsign=false","commit","-qm","c"]):
    subprocess.run(c, cwd=repo, check=True)
from styxx.protocol import Experiment, GateSpecError, coverage_trace
import vfprofmod
exp = Experiment(repo / "PREREG.md")
def run_under(kind):
    seen = {}
    def body():
        seen["getprofile"] = type(sys.getprofile()).__name__
        return vfprofmod.g()
    with coverage_trace(exp) as cov:
        if kind == "none":
            try: cov.run("G", body)
            except GateSpecError as e: seen["raised"] = str(e)[:30]
        else:
            P = profile.Profile if kind == "profile" else cProfile.Profile
            p = P()
            def outer():
                seen["pre_open_getprofile"] = type(sys.getprofile()).__name__
                try: return cov.run("G", body)
                except GateSpecError as e: seen["raised"] = str(e)[:30]
            p.runcall(outer)
        sys.setprofile(None)
    try: v = exp.score({"m": 1.0, "coverage_trace": cov.record()}).verdict
    except GateSpecError as e: v = str(e)[:28]
    return v, seen
print(sys.version.split()[0], "profile.py is pure Python:", inspect.getsourcefile(profile.Profile).endswith("profile.py"),
      "| Profile.runcall uses sys.setprofile:", "sys.setprofile(self.dispatcher)" in inspect.getsource(profile.Profile.runcall))
for k in ("none", "profile", "cprofile"):
    print("  ", k, run_under(k))
print("  after: sys.getprofile() =", sys.getprofile())
