"""Lifecycle / resolution: a signal-handler exception raised during __enter__'s resolution is
swallowed and replaced by a false refusal (FOREIGN_DEFINITION / NOT_A_FUNCTION / UNRESOLVED).

_resolve_target wraps user-reachable steps in `except Exception`: the import, a module's PEP 562
__getattr__, and _own_dict()'s `object.__getattribute__(obj, "__dict__")`.  A signal handler's
exception (the exam's own H2 `Timeout(Exception)`, pytest-timeout's signal method with an
Exception subclass, any SIGALRM budget) that CPython delivers inside one of those try blocks is
caught there:
  * in _own_dict it is dropped entirely -- `return None` -- and resolution carries on with a
    wrong fact: a valid `functools.wraps` wrapper from another module (spec case V11) refuses
    [V5:FOREIGN_DEFINITION] "neither it nor its __wrapped__ chain was defined in ...", a valid
    lru_cache target (V07) refuses [V5:NOT_A_FUNCTION] "body is NoneType";
  * in the import it becomes [V5:UNRESOLVED] "importing ... raised Timeout".
The harness's `except Timeout` never runs: the timeout is lost.

Spec: the hook has no try/except precisely so that "signal-handler exceptions, KeyboardInterrupt
and RecursionError" propagate (R3-B3 "hook swallows signal exceptions" CLOSED_S; H2 requires
20/20 propagated).  FOREIGN_DEFINITION is defined as "neither the object nor any link of its
own-dict __wrapped__ chain has __globals__ is module.__dict__" -- false for these targets.

The sweep varies only the SIGALRM delay; targets always resolve without a signal (checked first).

Run: PYTHONPATH=/home/user/styxx-1 python f07_resolution_swallows_signal_exception.py
"""
import collections
import importlib
import json
import random
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

from styxx.protocol import Experiment, GateSpecError, coverage_trace
import styxx.protocol as P


def make_exp(gates):
    td = Path(tempfile.mkdtemp(prefix="rt4lc_"))
    g = {k: {"metric": "m", "op": ">=", "value": 0.5, **v} for k, v in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {k: True for k in g}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True)
    return Experiment(p)


def make_mod(name, src):
    td = tempfile.mkdtemp(prefix="rt4lcmod_")
    Path(td, name + ".py").write_text(textwrap.dedent(src), encoding="utf-8")
    sys.path.insert(0, td)
    return importlib.import_module(name)


make_mod("rt4lc_f07_deco", """
    import functools
    def logged(fn):
        @functools.wraps(fn)
        def wrapper(*a, **k):
            return fn(*a, **k)
        return wrapper
""")
mod = make_mod("rt4lc_f07", """
    import functools
    from rt4lc_f07_deco import logged
    @logged
    def entry(x=0):            # spec V11: a wraps wrapper from another module
        return x + 1
    @functools.lru_cache(None)
    def cached(x=0):           # spec V07: a C cache wrapper, traced through its body
        return x * 2
""")
exp = make_exp({"G": {"exercises": ["rt4lc_f07:entry", "rt4lc_f07:cached"]}})
ORIG = {"entry": mod.entry.__code__, "cached": mod.cached.__wrapped__.__code__}


class Timeout(Exception):
    pass


ARMED = [False]


def handler(signum, frame):
    if ARMED[0]:
        raise Timeout()


def reset():
    P._THREADS.clear(); P._ANCHORS.clear(); P._MINTED.clear(); P._BY_FN.clear()
    P._ACTIVE = 0
    mod.entry.__code__ = ORIG["entry"]
    mod.cached.__wrapped__.__code__ = ORIG["cached"]
    sys.setprofile(None)


def main(budget=40.0):
    # control: without a signal both targets resolve and the gate passes
    with coverage_trace(exp) as cov:
        cov.run("G", lambda: (mod.cached.cache_clear(), mod.entry(1), mod.cached(1)))
    assert exp.score({"m": 1.0, "coverage_trace": cov.record()}).verdict == "PASS"
    signal.signal(signal.SIGALRM, handler)
    rnd = random.Random(2)
    seen = collections.Counter()
    first = {}
    end = time.monotonic() + budget
    while time.monotonic() < end:
        try:
            try:
                ARMED[0] = True
                signal.setitimer(signal.ITIMER_REAL, rnd.uniform(0.000005, 0.00008))
                with coverage_trace(exp) as cov:
                    pass
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                ARMED[0] = False
            seen["entered"] += 1
        except Timeout:
            seen["Timeout propagated"] += 1
        except GateSpecError as e:
            code = P._CODE_RE.match(str(e)).group(1)
            seen[code] += 1
            first.setdefault(code, str(e)[:170])
            if "FOREIGN_DEFINITION" in first and "NOT_A_FUNCTION" in first:
                break
        reset()
    swallowed = {k: v for k, v in seen.items() if k not in ("entered", "Timeout propagated")}
    if swallowed:
        print(f"FINDING-REPRODUCED: a SIGALRM Timeout during resolution was turned into a refusal "
              f"of targets that resolve without it: {dict(swallowed)} (propagated: "
              f"{seen['Timeout propagated']}); e.g. {first.get('FOREIGN_DEFINITION') or next(iter(first.values()))}")
    else:
        print(f"no finding: {dict(seen)}")


if __name__ == "__main__":
    main()
