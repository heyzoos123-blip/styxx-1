"""Independent verification of 'resolution-swallows-signal-exception'.

Claim: _own_dict wraps object.__getattribute__(obj, "__dict__") in `except Exception: return None`.
A signal handler's Exception delivered inside that try is dropped, and resolution then refuses a
valid target with a false FOREIGN_DEFINITION (wraps wrapper from another module, spec V11) or a false
NOT_A_FUNCTION (lru_cache target, spec V07).

Part A (deterministic): a line tracer, local to _own_dict only, raises SIGALRM with
signal.raise_signal() on the try-body line, so the Python-level handler runs exactly there (this is
where CPython would run it if the signal arrived there). The tracer is one-shot: CPython drops a
trace function that raises. Nothing in styxx is patched.

Part B (real timing, no tracer, public API only): SIGALRM with a random microsecond delay around
`with coverage_trace(exp): pass`; count what the harness sees. No private state is reset between
trials: FOREIGN_DEFINITION / NOT_A_FUNCTION are decided by resolution, which reads no module state.
"""
import collections
import dis
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

import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace


def mk_exp(target):
    td = Path(tempfile.mkdtemp(prefix="vrsig_"))
    spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [target]}},
            "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "S"}
    p = td / "PREREG_v.md"
    p.write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True)
    return Experiment(p)


def mk_mod(name, src):
    td = tempfile.mkdtemp(prefix="vrsigmod_")
    Path(td, name + ".py").write_text(textwrap.dedent(src), encoding="utf-8")
    sys.path.insert(0, td)
    return importlib.import_module(name)


mk_mod("vrsig_deco", """
    import functools
    def logged(fn):
        @functools.wraps(fn)
        def wrapper(*a, **k):
            return fn(*a, **k)
        return wrapper
""")
mod = mk_mod("vrsig_tgt", """
    import functools
    from vrsig_deco import logged
    @logged
    def entry(x=0):
        return x + 1
    @functools.lru_cache(None)
    def cached(x=0):
        return x * 2
""")
EXP = {t: mk_exp(t) for t in ("vrsig_tgt:entry", "vrsig_tgt:cached")}


class Timeout(Exception):
    pass


def handler(signum, frame):
    raise Timeout("SIGALRM budget")


# the try-body line of _own_dict: the line holding `object.__getattribute__`
OD = P._own_dict.__code__
src_lines = Path(OD.co_filename).read_text().splitlines()
TRY_LINE = next(ln for _, ln in dis.findlinestarts(OD)
                if ln and "object.__getattribute__" in src_lines[ln - 1])


def control(target):
    exp = EXP[target]
    with coverage_trace(exp) as cov:
        cov.run("G", lambda: (mod.cached.cache_clear(), mod.entry(1), mod.cached(1)))
    return exp.score({"m": 1.0, "coverage_trace": cov.record()}).verdict


def part_a(target, nth):
    """Deliver the signal on the nth execution of _own_dict's try-body line during __enter__."""
    seen = [0]

    def local(frame, event, arg):
        if event == "line" and frame.f_lineno == TRY_LINE:
            seen[0] += 1
            if seen[0] == nth:
                signal.raise_signal(signal.SIGALRM)   # the handler runs here and raises Timeout
        return local

    def glob(frame, event, arg):
        return local if frame.f_code is OD else None

    out = {"target": target, "nth": nth}
    try:
        sys.settrace(glob)
        try:
            with coverage_trace(EXP[target]):
                pass
        finally:
            sys.settrace(None)
        out["outcome"] = "entered normally (signal never delivered)" if seen[0] < nth else \
            "entered normally although the handler raised"
    except Timeout:
        out["outcome"] = "Timeout propagated"
    except GateSpecError as e:
        chain, x = [], e
        while x is not None:
            chain.append(type(x).__name__)
            x = x.__cause__ or x.__context__
        out["outcome"] = "GateSpecError"
        out["msg"] = str(e)[:200]
        out["exception_chain"] = chain
    out["own_dict_line_hits"] = seen[0]
    return out


def part_b(target, budget):
    rnd = random.Random(7)
    seen = collections.Counter()
    ex = {}
    end = time.monotonic() + budget
    while time.monotonic() < end:
        try:
            try:
                signal.setitimer(signal.ITIMER_REAL, rnd.uniform(0.000003, 0.00008))
                with coverage_trace(EXP[target]):
                    pass
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            seen["no signal inside"] += 1
        except Timeout:
            seen["Timeout propagated"] += 1
        except GateSpecError as e:
            code = P._CODE_RE.match(str(e)).group(1)
            has_timeout = False
            x = e
            while x is not None:
                has_timeout |= isinstance(x, Timeout)
                x = x.__cause__ or x.__context__
            k = f"{code} ({'Timeout chained' if has_timeout else 'Timeout LOST'})"
            seen[k] += 1
            ex.setdefault(k, str(e)[:160])
    return dict(seen), ex


if __name__ == "__main__":
    print(sys.version.split()[0], "try-body line", TRY_LINE)
    for t in EXP:
        print("control", t, control(t))
    signal.signal(signal.SIGALRM, handler)
    print("PART A (deterministic delivery inside _own_dict's try)")
    for t, nth in (("vrsig_tgt:entry", 1), ("vrsig_tgt:cached", 1), ("vrsig_tgt:cached", 2)):
        print(" ", json.dumps(part_a(t, nth)))
    for t in EXP:
        print("control after part A", t, control(t))
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    print(f"PART B (real SIGALRM timing, {budget:.0f}s per target)")
    for t in EXP:
        counts, ex = part_b(t, budget)
        print(" ", t, counts)
        for k, v in ex.items():
            print("    e.g.", k, "->", v)
