# ---- self-contained prelude (identical in every script of this directory) ----
import json, os, subprocess, sys, tempfile, threading, types, importlib
from pathlib import Path
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

def mkexp(**gates):
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, **extra} for n, extra in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"},
                                      {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "SMOKE"}
    td = Path(tempfile.mkdtemp(prefix="rt4ca_"))
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True, capture_output=True)
    return Experiment(p)

def fixture(name, src):
    d = Path(tempfile.mkdtemp(prefix="rt4fx_"))
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    sys.path.insert(0, str(d))
    sys.modules.pop(name, None)
    return importlib.import_module(name)

def score(e, rec, m=1.0, **extra):
    try:
        v = e.score({"m": m, "coverage_trace": rec, **extra})
        return f"PASS verdict={v.verdict} coverage={v.coverage}"
    except GateSpecError as ex:
        return f"REFUSED {str(ex)[:160]}"

def clean():
    return (not (P._MINTED or P._BY_FN or P._ANCHORS or P._THREADS) and P._ACTIVE == 0
            and sys.getprofile() is None)
# ---- end prelude ----
# F6: R1-D2 closure ("Any Exception from import or module __getattr__ becomes UNRESOLVED ... the walk
# runs no user code"; _resolve_target's docstring: "Resolution never runs user code except the import
# and a module's PEP 562 __getattr__"). For a step through an instance, _resolve_target first asks
# isinstance(obj, types.ModuleType) -- and isinstance falls back to obj.__class__, i.e. the object's
# own __getattribute__. A strict-namespace object that raises KeyError for unknown attributes (the
# spec's own "registry objects" admitted by own-__dict__ instance steps) makes __enter__ escape with a
# raw KeyError instead of a GateSpecError.
src = '''
class StrictConfig:
    """a strict namespace: unknown attributes raise KeyError naming the setting"""
    def __init__(self, **kw): object.__getattribute__(self, "__dict__").update(kw)
    def __getattribute__(self, name):
        d = object.__getattribute__(self, "__dict__")
        if name in d:
            return d[name]
        raise KeyError(f"unknown setting {name!r}")
class PlainNS:
    def __init__(self, **kw): self.__dict__.update(kw)
def handler(x=0): return x
hooks = StrictConfig(handler=handler)
plain = PlainNS(handler=handler)
'''
fx = fixture("ca_f6", src)
out = {}
for path in ("plain.handler", "hooks.handler"):
    e = mkexp(G={"exercises": [f"ca_f6:{path}"]})
    try:
        with coverage_trace(e) as cov:
            cov.run("G", fx.handler, 1)
        out[path] = score(e, cov.record())[:60]
    except GateSpecError as ex:
        out[path] = f"GateSpecError {str(ex)[:60]}"
    except Exception as ex:
        out[path] = f"ESCAPED {type(ex).__name__}: {ex}"
    print(f"{path:14s} -> {out[path]}")
print("clean:", clean())
if out["plain.handler"].startswith("PASS") and out["hooks.handler"].startswith("ESCAPED KeyError"):
    print("FINDING-REPRODUCED: resolution runs the step object's __getattribute__ (via isinstance) and a raw "
          "KeyError escapes coverage_trace().__enter__ instead of a [V5:...] GateSpecError")
else:
    print("no finding: resolution through a strict namespace refuses or passes cleanly")
