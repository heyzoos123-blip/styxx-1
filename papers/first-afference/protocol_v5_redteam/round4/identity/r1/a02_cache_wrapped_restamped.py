# ---- self-contained prelude (identical in every script of this lens) ----
import json, os, subprocess, sys, tempfile, textwrap, threading, types
from pathlib import Path
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

_TMP = Path(tempfile.mkdtemp(prefix="rt4id_"))
sys.path.insert(0, str(_TMP))

def write_mod(name, src):
    (_TMP / f"{name}.py").write_text(textwrap.dedent(src), encoding="utf-8")
    sys.modules.pop(name, None)

def make_exp(**gates):
    d = Path(tempfile.mkdtemp(prefix="rt4id_repo_"))
    g = {k: {"metric": "m", "op": ">=", "value": 0.5, **v} for k, v in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {k: True for k in g}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = d / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=d, check=True)
    return Experiment(p)

def score(exp, rec, m=1.0):
    try:
        v = exp.score({"m": m, "coverage_trace": rec})
        return f"PASS verdict={v.verdict} coverage={v.coverage}"
    except GateSpecError as e:
        return f"REFUSED {str(e)[:220]}"

def leftovers():
    return dict(profile=sys.getprofile(), minted=len(P._MINTED), by_fn=len(P._BY_FN),
                anchors=len(P._ANCHORS), threads=len(P._THREADS), active=P._ACTIVE)
# ---- end prelude ----
# ATTACK 02: the resolver takes a C cache wrapper's "body" from its WRITABLE __dict__['__wrapped__'],
# not from the function the wrapper actually calls. A stacked @functools.wraps(ref) re-stamps
# __wrapped__ to `ref` (the reference implementation, kept on a class so it is not a module-level
# name). F_T becomes `ref`, which the cache wrapper never calls.
#   (a) harness calls ONLY the reference Ref.power -> gate declaring the cached `power` PASSES.
#   (b) harness calls ONLY the declared `power` -> NOT_EXERCISED (the real body is never credited).
write_mod("rt4_cachemod", """
    import functools

    class Ref:
        @staticmethod
        def power(n):
            '''exact reference implementation'''
            return sum(range(n))

    @functools.wraps(Ref.power)          # give the fast path the reference's name/doc/signature
    @functools.lru_cache(maxsize=None)
    def power(n):
        return n * (n - 1) // 2          # fast closed form: THIS is what power() runs
""")
import rt4_cachemod as cm
import gc
real_callee = [r for r in gc.get_referents(cm.power) if type(r) is types.FunctionType]
print("cache wrapper's real callee (gc.get_referents):", [f.__code__.co_firstlineno for f in real_callee],
      "| __wrapped__ claims:", cm.power.__wrapped__.__qualname__, "line",
      cm.power.__wrapped__.__code__.co_firstlineno)
exp = make_exp(G={"exercises": ["rt4_cachemod:power"]})

with coverage_trace(exp) as cov:
    cov.run("G", cm.Ref.power, 10)       # the cached `power` is never called
out_a = score(exp, cov.record())
cm.power.cache_clear()
with coverage_trace(exp) as cov:
    cov.run("G", cm.power, 10)           # the declared object IS called (a cache miss)
out_b = score(exp, cov.record())
print("(a) only Ref.power called :", out_a)
print("(b) only power called     :", out_b)
print("leftovers:", leftovers())
if out_a.startswith("PASS"):
    print("FINDING-REPRODUCED: cache wrapper re-stamped by wraps(): declared `power` never ran "
          "but the gate PASSES (credit taken from __wrapped__ = Ref.power); calling `power` "
          f"itself gives: {out_b[:60]}")
else:
    print("no finding:", out_a)

# (c) the same stacking with the reference bound at module level: refused NOT_A_FUNCTION with a
# remedy ("declare that name instead") that names a function `fast` never calls.
write_mod("rt4_cachemod_c", """
    import functools
    def reference(n):
        return sum(range(n))
    @functools.wraps(reference)
    @functools.lru_cache(maxsize=None)
    def fast(n):
        return n * (n - 1) // 2
""")
exp_c = make_exp(G={"exercises": ["rt4_cachemod_c:fast"]})
try:
    with coverage_trace(exp_c) as cov:
        pass
    print("(c) entered")
except GateSpecError as e:
    print("(c) module-level reference:", str(e)[:200])
