#!/usr/bin/env python
"""Independent verifier repro for wraps-over-class-wrapper-overblock.

Shape: a module's own function decorated by a functools.wraps function decorator over a
class-based functools.update_wrapper decorator. Declared as mod:fit.
Also runs control variants to locate the boundary.

Run: PYTHONPATH=<root containing styxx/> python v_repro.py
"""
import json, os, subprocess, sys, tempfile, importlib, textwrap
from pathlib import Path

import styxx.protocol as P
from styxx.protocol import Experiment, coverage_trace, GateSpecError

HERE = Path(__file__).resolve().parent
work = Path(tempfile.mkdtemp(prefix="vw_", dir=HERE / "tmp"))
sys.path.insert(0, str(work))

(work / "vdecos.py").write_text(textwrap.dedent("""
    import functools
    class memoize:                       # class-based decorator, update_wrapper on self
        def __init__(self, fn):
            functools.update_wrapper(self, fn)
            self.fn, self.cache = fn, {}
        def __call__(self, *a):
            if a not in self.cache:
                self.cache[a] = self.fn(*a)
            return self.cache[a]
    def logged(fn):                      # functools.wraps function decorator
        @functools.wraps(fn)
        def wrapper(*a, **k):
            return fn(*a, **k)
        return wrapper
"""))

VARIANTS = {
    # name: (module source, declared qualname, callable-name-to-call)
    "A_logged_over_memoize": ("""
        from vdecos import logged, memoize
        @logged
        @memoize
        def fit(x):
            return x + 1
    """, "fit", "fit"),
    "B_memoize_alone": ("""
        from vdecos import memoize
        @memoize
        def fit(x):
            return x + 1
    """, "fit", "fit"),
    "C_logged_alone": ("""
        from vdecos import logged
        @logged
        def fit(x):
            return x + 1
    """, "fit", "fit"),
    "D_logged_over_lru_cache": ("""
        import functools
        from vdecos import logged
        @logged
        @functools.lru_cache(None)
        def fit(x):
            return x + 1
    """, "fit", "fit"),
    "E_workaround_declare_raw": ("""
        from vdecos import logged, memoize
        def _fit(x):
            return x + 1
        fit = logged(memoize(_fit))
    """, "_fit", "fit"),
    "F_logged_over_local_class_wrapper": ("""
        import functools
        from vdecos import logged
        class localmemo:
            def __init__(self, fn):
                functools.update_wrapper(self, fn)
                self.fn = fn
            def __call__(self, *a):
                return self.fn(*a)
        @logged
        @localmemo
        def fit(x):
            return x + 1
    """, "fit", "fit"),
}

results = {}
for i, (vname, (src, qual, callname)) in enumerate(VARIANTS.items()):
    modname = f"vmod_{i}"
    (work / f"{modname}.py").write_text(textwrap.dedent(src))
    d = Path(tempfile.mkdtemp(prefix=f"case_{i}_", dir=work))
    spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5,
                            "exercises": [f"{modname}:{qual}"]}},
            "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "SMOKE"}
    (d / "PREREG_case.md").write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
                 "commit", "-qm", "c"]):
        subprocess.run(cmd, cwd=d, check=True, capture_output=True)
    exp = Experiment(d / "PREREG_case.md")
    mod = importlib.import_module(modname)
    try:
        with coverage_trace(exp) as cov:
            cov.run("G", getattr(mod, callname), 1)
        v = exp.score({"m": 1.0, "coverage_trace": cov.record()})
        out = v.verdict
    except GateSpecError as e:
        out = str(e)
    results[vname] = out
    print(f"{vname}: {out[:260]}")

print(f"python {sys.version.split()[0]} impl {P.__file__}")
print("A_is_FOREIGN_DEFINITION:", results["A_logged_over_memoize"].startswith("[V5:FOREIGN_DEFINITION]"))
