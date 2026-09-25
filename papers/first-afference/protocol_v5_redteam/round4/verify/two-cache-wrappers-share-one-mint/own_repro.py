"""Independent repro: two C lru_cache wrappers of one unnamed body share one mint."""
import json, os, subprocess, sys, tempfile, textwrap
from pathlib import Path
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

TMP = Path(tempfile.mkdtemp(prefix="v2c_")); sys.path.insert(0, str(TMP))

def mod(name, src):
    (TMP / f"{name}.py").write_text(textwrap.dedent(src)); sys.modules.pop(name, None)
    return __import__(name)

def exp_for(gates):
    d = Path(tempfile.mkdtemp(prefix="v2c_repo_"))
    g = {k: {"metric": "m", "op": ">=", "value": 0.5, "exercises": v[0], "section": v[1]}
         for k, v in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {k: True for k in g}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = d / "PREREG_x.md"; p.write_text("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=d, check=True)
    return Experiment(p)

def score(exp, rec):
    try:
        v = exp.score({"m": 1.0, "coverage_trace": rec}); return f"PASS {v.verdict}"
    except GateSpecError as e:
        return "REFUSED " + str(e)[:120]

SRC_CACHE = """
    import functools
    def _mk(fn, order):
        a = functools.lru_cache(maxsize=None)(fn); b = functools.lru_cache(maxsize=4)(fn)
        return (a, b) if order == 0 else (b, a)
    def _body(x):
        return x + 1
    ORDER = {order}
    if ORDER == 0:
        big, small = _mk(_body, 0)
    else:
        small, big = _mk(_body, 1)
    del _body
"""
# (1) one gate declares ONLY `small`; the section calls ONLY `big` (no alias rule involved)
for order in (0, 1):
    m = mod(f"v2c_c{order}", SRC_CACHE.format(order=order))
    e = exp_for({"G": ([f"v2c_c{order}:small"], "S")})
    with coverage_trace(e) as cov:
        cov.run("S", m.big, 7)
    rec = cov.record()
    print(f"[cache, order={order}, declare small only, call big] calls={rec['sections']['S'][0]['calls']}"
          f" score={score(e, rec)} small.cache_info={m.small.cache_info()}")

# (2) both declared in different sections; section S calls only `big`
m = mod("v2c_both", SRC_CACHE.format(order=0))
e = exp_for({"GB": (["v2c_both:big"], "B"), "GS": (["v2c_both:small"], "S")})
with coverage_trace(e) as cov:
    cov.run("B", m.big, 1); cov.run("S", m.big, 2)
rec = cov.record()
print(f"[cache, both declared] S calls={rec['sections']['S'][0]['calls']} score={score(e, rec)}"
      f" small.cache_info={m.small.cache_info()}")

# (3) control: a cache HIT on big in S credits nothing (hits do not count)
m = mod("v2c_hit", SRC_CACHE.format(order=0))
m.big(3)
e = exp_for({"G": (["v2c_hit:small"], "S")})
with coverage_trace(e) as cov:
    cov.run("S", m.big, 3)
rec = cov.record()
print(f"[cache hit on big] S calls={rec['sections']['S'][0]['calls']} score={score(e, rec)}")

# (4) contrast: two FunctionType wraps-wrappers of one body -> separate mints, no cross credit
m = mod("v2c_wraps", """
    import functools
    def _mk(fn):
        @functools.wraps(fn)
        def w1(*a): return fn(*a)
        @functools.wraps(fn)
        def w2(*a): return fn(*a)
        return w1, w2
    def _body(x):
        return x + 1
    big, small = _mk(_body)
    del _body
""")
e = exp_for({"G": (["v2c_wraps:small"], "S")})
with coverage_trace(e) as cov:
    cov.run("S", m.big, 1)
rec = cov.record()
print(f"[wraps FunctionType contrast] S calls={rec['sections']['S'][0]['calls']} score={score(e, rec)}")
print("leftovers:", sys.getprofile(), len(P._MINTED), len(P._BY_FN), len(P._ANCHORS), len(P._THREADS), P._ACTIVE)
