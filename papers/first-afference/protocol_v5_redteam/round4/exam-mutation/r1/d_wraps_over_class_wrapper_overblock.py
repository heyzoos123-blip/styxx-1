#!/usr/bin/env python
"""DEFECT (undisclosed over-block) + unpinned rule: a function defined in the declared module and
decorated by a functools.wraps decorator (from another module) over a class-based update_wrapper
decorator is refused [V5:FOREIGN_DEFINITION] ("a re-export, a stub or a mock bound at the name is not
the function the declaration names"), although it is exactly the module's decorated function and the
raw function is bound nowhere else, so there is no declarable name for it. Cause: _defined_in walks the
own-dict __wrapped__ chain "only through FunctionType and cache-wrapper links" and stops at the
class-based wrapper. The disclosed over-blocking list (#8, #9) names class-based wrappers only as
DECLARED objects and names no-wraps/factory products, not a wraps product whose chain crosses one.
Also: the exam does not pin this walk rule. The mutant that lets the walk step through any object's
own __dict__ (deleting `elif type(cur) is not _CACHE_WRAPPER: return False`) survives the frozen exam
(checked with --check-mutant).
Run: PYTHONPATH=/home/user/styxx-1 python d_wraps_over_class_wrapper_overblock.py [--check-mutant]"""
import json, os, shutil, subprocess, sys, tempfile, importlib, textwrap
from pathlib import Path
import styxx.protocol as P
from styxx.protocol import Experiment, coverage_trace, GateSpecError

d = Path(tempfile.mkdtemp(prefix="rt4em_d3_"))
sys.path.insert(0, str(d))
(d / "rt4d3_decos.py").write_text(textwrap.dedent("""
    import functools
    class memoize:                                  # a class-based decorator (update_wrapper)
        def __init__(self, fn):
            functools.update_wrapper(self, fn)
            self.fn, self.cache = fn, {}
        def __call__(self, *a):
            if a not in self.cache:
                self.cache[a] = self.fn(*a)
            return self.cache[a]
    def logged(fn):                                 # a functools.wraps function decorator
        @functools.wraps(fn)
        def wrapper(*a, **k):
            return fn(*a, **k)
        return wrapper
"""))
(d / "rt4d3_model.py").write_text(textwrap.dedent("""
    from rt4d3_decos import logged, memoize
    @logged
    @memoize
    def fit(x):
        return x + 1
"""))
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["rt4d3_model:fit"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "SMOKE"}
(d / "PREREG_case.md").write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
            ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false", "commit", "-qm", "c"]):
    subprocess.run(cmd, cwd=d, check=True, capture_output=True)
exp = Experiment(d / "PREREG_case.md")
mod = importlib.import_module("rt4d3_model")
try:
    with coverage_trace(exp) as cov:
        cov.run("G", mod.fit, 1)
    outcome = exp.score({"m": 1.0, "coverage_trace": cov.record()}).verdict
except GateSpecError as e:
    outcome = str(e)
print(f"python {sys.version.split()[0]} impl {P.__file__}")
print("outcome:", outcome[:330])
if "--check-mutant" in sys.argv:
    REPO = Path("/home/user/styxx-1")
    tmp = Path(tempfile.mkdtemp(prefix="P03_", dir="/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/exam-mutation/r1/tmp"))
    shutil.copytree(REPO / "styxx", tmp / "styxx", ignore=shutil.ignore_patterns("__pycache__"))
    src = (REPO / "styxx/protocol.py").read_text()
    old = "        elif type(cur) is not _CACHE_WRAPPER:\n            return False\n"
    assert src.count(old) == 1
    (tmp / "styxx/protocol.py").write_text(src.replace(old, ""))
    env = dict(os.environ, STYXX_V5_IMPORT_ROOT=str(tmp), STYXX_V5_RESULT_OUT=str(tmp / "r.json"), PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    p = subprocess.run([sys.executable, str(REPO / "papers/first-afference/run_protocol_v5e.py"), "--smoke",
                        "--full-battery", "--mutation-mode"], cwd=REPO, env=env, capture_output=True, text=True, timeout=45)
    r = json.loads((tmp / "r.json").read_text()) if (tmp / "r.json").exists() else {}
    bad = [k for sec in ("violation_cases", "valid_cases") for k, v in r.get(sec, {}).items() if not v.get("ok")]
    print(f"exam vs walk-anything mutant: rc={p.returncode} failed={bad} retro={r.get('p1_retro_exact')} "
          f"-> {'SURVIVES' if p.returncode == 0 and not bad and r.get('p1_retro_exact') == 1.0 else 'detected'}")
    shutil.rmtree(tmp, ignore_errors=True)
if outcome.startswith("[V5:FOREIGN_DEFINITION]"):
    print("FINDING-REPRODUCED: `@logged @memoize def fit` in the declared module (wraps decorator over a class-based "
          "decorator) is refused FOREIGN_DEFINITION with a message calling it a re-export/stub/mock; no declarable name exists")
else:
    print(f"no finding: {outcome[:100]}")
