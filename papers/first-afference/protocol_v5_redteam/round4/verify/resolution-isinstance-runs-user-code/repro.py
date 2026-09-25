# Independent verifier repro for "resolution-isinstance-runs-user-code".
# Usage: STYXX_ROOT=<dir containing styxx/> python repro.py
import json, os, subprocess, sys, tempfile, importlib
from pathlib import Path
ROOT = os.environ.get("STYXX_ROOT", "/home/user/styxx-1")
sys.path.insert(0, ROOT)
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace
assert P.__file__.startswith(ROOT), P.__file__

def exp_for(target):
    spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [target]}},
            "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "SMOKE"}
    d = Path(tempfile.mkdtemp(prefix="vfy_"))
    (d / "PREREG_x.md").write_text("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "c"]):
        subprocess.run(c, cwd=d, check=True, capture_output=True)
    return Experiment(d / "PREREG_x.md")

SRC = r'''
SIDE_EFFECTS = []
def handler(x=0): return x
class _Base:
    def __init__(self, **kw): object.__getattribute__(self, "__dict__").update(kw)
class StrictKeyError(_Base):          # registry that raises KeyError for unknown names
    def __getattribute__(self, name):
        d = object.__getattribute__(self, "__dict__")
        if name in d: return d[name]
        raise KeyError(name)
class StrictAttrError(_Base):         # same registry, raising AttributeError (control)
    def __getattribute__(self, name):
        d = object.__getattribute__(self, "__dict__")
        if name in d: return d[name]
        raise AttributeError(name)
class LazyOK(_Base):                  # lazy proxy: __class__ triggers setup (side effect only)
    @property
    def __class__(self):
        SIDE_EFFECTS.append("setup ran")
        return type(self)
class LazyUnconfigured(_Base):        # lazy proxy whose setup fails (Django-settings style)
    @property
    def __class__(self):
        raise RuntimeError("settings are not configured")
strict_ke  = StrictKeyError(handler=handler)
strict_ae  = StrictAttrError(handler=handler)
lazy_ok    = LazyOK(handler=handler)
lazy_bad   = LazyUnconfigured(handler=handler)
'''
d = Path(tempfile.mkdtemp(prefix="vfyfx_")); (d / "vfy_fx.py").write_text(SRC)
sys.path.insert(0, str(d)); fx = importlib.import_module("vfy_fx")
orig_code = fx.handler.__code__

def attempt(path):
    e = exp_for(f"vfy_fx:{path}")
    try:
        with coverage_trace(e) as cov:
            cov.run("G", fx.handler, 1)
        v = e.score({"m": 1.0, "coverage_trace": cov.record()})
        return f"PASS verdict={v.verdict}"
    except GateSpecError as ex:
        return f"REFUSED {str(ex)[:70]}"
    except Exception as ex:
        return f"ESCAPED {type(ex).__name__}: {ex}"

cases = [
    ("strict_ae.handler", "control: AttributeError registry, own-dict step (spec: resolves)"),
    ("strict_ke.handler", "CLAIM: KeyError registry, own-dict step (spec: resolves)"),
    ("lazy_ok.handler",   "lazy proxy with side effect (spec: resolves, no user code)"),
    ("lazy_bad.handler",  "lazy proxy that raises RuntimeError (spec: resolves)"),
    ("strict_ke",         "final object is the KeyError registry (spec: NOT_A_FUNCTION)"),
    ("strict_ae",         "final object is the AttributeError registry (spec: NOT_A_FUNCTION)"),
]
print(sys.version.split()[0], "styxx from", P.__file__)
for path, label in cases:
    before = len(fx.SIDE_EFFECTS)
    r = attempt(path)
    se = len(fx.SIDE_EFFECTS) - before
    print(f"  {path:20s} -> {r}   [user __class__ side effects: {se}]   # {label}")
clean = (not (P._MINTED or P._BY_FN or P._ANCHORS or P._THREADS) and P._ACTIVE == 0
         and sys.getprofile() is None and fx.handler.__code__ is orig_code)
print("  registries clean, profile None, code restored:", clean)
