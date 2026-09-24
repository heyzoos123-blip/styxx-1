from rtlib import *
import fx_simple
def attempt(label, fn):
    try:
        r = fn(); print(f"{label}: returned {r!r}"[:220])
    except GateSpecError as ex:
        print(f"{label}: GateSpecError (ok)")
    except BaseException as ex:
        print(f"{label}: ESCAPED {type(ex).__name__}: {str(ex)[:120]}")

# targets whose resolution raises something other than ImportError/AttributeError
for t in ["fx_broken:f", "fx_syntax:f", "fx_cycle:f"]:
    e = exp(spec(G={"exercises": [t]}))
    attempt(f"coverage_trace({t})", lambda: coverage_trace(e))

# regex '$' admits a trailing newline
from styxx.protocol import _TARGET_RE
print("regex admits trailing newline:", bool(_TARGET_RE.match("fx_simple:f\n")))
attempt("Experiment with 'fx_simple:f\\n'", lambda: exp(spec(G={"exercises": ["fx_simple:f\n"]})).coverage)

# malformed traces fed to score() and check_metrics()
e = exp(spec(G={"exercises": ["fx_simple:f"]}))
good = None
with coverage_trace(e) as cov:
    with cov.section("G"): fx_simple.f()
good = cov.record()
import copy
def mk(mut):
    r = copy.deepcopy(good); mut(r); return r
cases = {
  "targets has int key": mk(lambda r: r["targets"].__setitem__(1, "x")),
  "targets has None key": mk(lambda r: r["targets"].__setitem__(None, "x")),
  "section key tuple": mk(lambda r: r["sections"]["G"].__setitem__(("a",), 1)),
}
for k, tr in cases.items():
    attempt(f"score[{k}]", lambda: e.score({"m": 1.0, "coverage_trace": tr}).verdict)
    attempt(f"check_metrics[{k}]", lambda: e.check_metrics({"m": 1.0, "coverage_trace": tr}))
# result that is not a dict -> check_metrics
attempt("check_metrics(list)", lambda: e.check_metrics([1]))
