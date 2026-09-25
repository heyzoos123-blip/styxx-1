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
# ATTACK 03: two distinct C cache wrappers around ONE body (e.g. an unbounded and a bounded cache
# of the same computation; the body is not bound by name, e.g. built by a helper). Both declared
# names resolve to the same F_T and share one mint, so calling ONLY `cached_all` credits
# `cached_small` too. A gate declaring `cached_small` PASSES although `cached_small` -- the
# declared callable -- was never called. The spec says "no two distinct callables ever map to
# one observed code object".
write_mod("rt4_twocache", """
    import functools
    def _two_caches(fn):
        return functools.lru_cache(maxsize=None)(fn), functools.lru_cache(maxsize=16)(fn)

    def _score(x):
        return x * 2
    cached_all, cached_small = _two_caches(_score)
    del _score
""")
import rt4_twocache as tc
exp = make_exp(G_ALL={"exercises": ["rt4_twocache:cached_all"], "section": "A"},
               G_SMALL={"exercises": ["rt4_twocache:cached_small"], "section": "S"})
with coverage_trace(exp) as cov:
    cov.run("A", tc.cached_all, 1)
    cov.run("S", tc.cached_all, 2)     # section S only ever calls cached_all
rec = cov.record()
print("sections:", rec["sections"])
out = score(exp, rec)
print("score:", out)
print("cached_small.cache_info():", tc.cached_small.cache_info())
if out.startswith("PASS") and tc.cached_small.cache_info().misses == 0:
    print("FINDING-REPRODUCED: gate declaring cached_small PASSES; cached_small was never called "
          "(cache_info misses=0 hits=0); two distinct cache wrappers share one mint")
else:
    print("no finding:", out)
