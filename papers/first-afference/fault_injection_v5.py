"""Exhaustive fault injection for the v5 coverage tracer: an exception at EVERY opcode of its machinery.

Most lifecycle blockers from red-team rounds 3 and 4 share one shape: an exception (a signal handler's
Timeout, KeyboardInterrupt, a RecursionError) lands at some bytecode inside the tracer's own machinery,
and the machinery is left half-transitioned. Examples are a lock held for good, a thread count that
never returns to zero, or a minted code object that is never restored. A red team finds such points by
luck. This script finds all of them, for the scenarios it runs.

Method. The script traces the machinery's own code objects (every function of the v5 region: the
tracer's methods, target resolution and provenance) with ``sys.settrace`` and per-opcode events. For
each scenario it first runs the scenario twice without injecting: on 3.12+ settrace misses opcode
events on a code object's first calls in a process, so the first run only warms the instrumentation.
Then for k = 1, 2, ... it runs the scenario again and raises the injected exception at the k-th
machinery opcode, and it stops at the first k that the run never reaches. Because the interpreter
removes a trace function that raises, each injected run is preceded by one more warm-up run. The fault space is
therefore enumerated by the runs themselves, not sized from one clean run.
The profile hook itself is out of reach: CPython suspends tracing inside a profile callback. Its
failure modes are the H1/H2 hazard sweeps' business.

After each faulted run the invariants are checked, all before any repair:

* PROPAGATED: the injected exception reached the harness. If the scenario completed normally, the
  exception was SWALLOWED somewhere.
* CLEAN STATE: no profile function is installed; the module registries (``_MINTED``, ``_BY_FN``,
  ``_ANCHORS``, ``_THREADS``) are empty; ``_ACTIVE == 0``; ``_STOP is None``; the fixture functions' code
  is their original code; another thread can take ``_LOCK`` within 2 s.
* NEXT TRACE: a fresh, clean trace of the same target, run on the damaged state without a reset, must
  score PASS with the exact count. Afterwards the state is checked again.

Each point gets the worst class that applies, in this order:

  HANG        another thread cannot take ``_LOCK`` within 2 s
  BREAKS_NEXT the next clean trace raises or scores anything but PASS with the exact count
  PERSISTS    state was left behind and is still there after a clean next trace
  CLEARED     state was left behind, and the next clean trace cleared it
  CONVERTED   state is clean, but the exception reached the harness as something else, e.g. as a
              coded refusal (``chained`` records whether the injected exception is its ``__cause__``)
  CLEAN       the exception propagated as itself, the state is clean, and the next trace is exact

Scope, stated so no one reads more into the map than it holds. It is exhaustive only for the
exception class it raises (``--exc``: an ``Exception`` subclass, or ``KeyboardInterrupt``), at every
opcode that these scenarios execute, on the interpreter it runs on. Opcode streams differ by CPython
version. A point is a dynamic opcode execution, so the same source line recurs across scenarios; the
receipt also counts distinct (function, line) sites. It also tags each point as ``stateful`` (the
tracer's lifecycle and target resolution) or ``stateless`` (score-time trace validation), because
stateless code cannot leave state behind. It cannot see which opcodes a real exception source can
reach: a signal handler runs only at the interpreter's eval-breaker checks, so points such as a
``LOAD_CONST`` are reachable in practice only through a callback, such as the profile hook.

A fault point is CLEAN only if the exception propagated, the state is clean and the next trace is OK.
Between points the state is forcibly reset, so each point is judged on its own.

Usage: ``python fault_injection_v5.py [--scenario NAME] [--out PATH]``. Set ``STYXX_V5_IMPORT_ROOT`` to
fault-inject another implementation, the same way the frozen exam does. Writes
``fault_injection_v5_result.json`` by default.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
if os.environ.get("STYXX_V5_IMPORT_ROOT"):
    sys.path.insert(0, os.environ["STYXX_V5_IMPORT_ROOT"])
else:
    sys.path.insert(0, str(ROOT))
import styxx.protocol as P  # noqa: E402
from styxx.protocol import Experiment, coverage_trace  # noqa: E402

MARKER = "# -- v5: the coverage tracer"
FIX = "_v5fi_fix"
FIXTURE = "def f(x=0):\n    return x + 1\n\n\ndef g(x=0):\n    return x + 2\n"


class Injected(Exception):
    pass


class InjectedInterrupt(KeyboardInterrupt):
    pass


EXC = {"exception": Injected, "keyboardinterrupt": InjectedInterrupt}
CLASSES = ("CLEAN", "CONVERTED", "CLEARED", "PERSISTS", "BREAKS_NEXT", "HANG")
# A trace function that raises is removed by the interpreter. On 3.12+ a re-installed one then misses
# opcode events on each code object's first calls again, so every injected run is preceded by one
# traced, uninjected run of the same scenario. On 3.10/3.11 this changes nothing but the runtime.
WARM_EACH = True


# -- the machinery's code objects -------------------------------------------------------------

def machinery_codes() -> set:
    src = Path(P.__file__).read_text(encoding="utf-8").split("\n")
    marker = next(i + 1 for i, ln in enumerate(src) if ln.startswith(MARKER))
    codes = set()

    def add(fn):
        fn = getattr(fn, "__func__", fn)
        if isinstance(fn, types.FunctionType) and fn.__code__.co_filename == P.__file__ \
                and fn.__code__.co_firstlineno > marker and fn.__name__ != "_hook":
            codes.add(fn.__code__)
            for c in fn.__code__.co_consts:        # nested functions and comprehensions
                if isinstance(c, types.CodeType):
                    codes.add(c)
    for v in vars(P).values():
        if isinstance(v, type) and v.__module__ == P.__name__:
            for m in vars(v).values():
                add(m)
        else:
            add(v)
    return codes


# -- fixture: a module to declare, and preregs to score against --------------------------------

class Env:
    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="v5fi_"))
        (self.tmp / f"{FIX}.py").write_text(FIXTURE, encoding="utf-8")
        sys.path.insert(0, str(self.tmp))
        self.mod = __import__(FIX)
        self.orig = {n: getattr(self.mod, n).__code__ for n in ("f", "g")}
        self.n = 0
        self.exps = {}

    def exp(self, **gates) -> Experiment:
        key = json.dumps(gates, sort_keys=True)
        if key in self.exps:
            return self.exps[key]
        self.n += 1
        repo = self.tmp / f"repo{self.n}"
        repo.mkdir()
        g = {k: {"metric": "m", "op": ">=", "value": 0.5, **v} for k, v in gates.items()}
        spec = {"gates": g, "outcomes": [{"when": {k: True for k in g}, "verdict": "PASS"},
                                         {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
        p = repo / "PREREG_fi.md"
        p.write_text("# fi\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
        for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                    ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false",
                     "commit", "-qm", "c"]):
            subprocess.run(cmd, cwd=repo, check=True)
        self.exps[key] = Experiment(p)
        return self.exps[key]


def T(n):
    return f"{FIX}:{n}"


# -- scenarios: each returns (verdict, coverage) and must be deterministic ---------------------

def s_sync(env):
    exp = env.exp(G={"exercises": [T("f")]})
    with coverage_trace(exp) as cov:
        cov.run("G", env.mod.f, 1)
    v = exp.score({"m": 1.0, "coverage_trace": cov.record()})
    return v.verdict, getattr(v, "coverage", None)


def s_two_sections(env):
    exp = env.exp(A={"exercises": [T("f")]}, B={"exercises": [T("g")]})
    with coverage_trace(exp) as cov:
        cov.run("A", env.mod.f, 1)
        cov.run("B", env.mod.g, 1)
    v = exp.score({"m": 1.0, "coverage_trace": cov.record()})
    return v.verdict, getattr(v, "coverage", None)


def s_raising_section(env):
    exp = env.exp(G={"exercises": [T("f")]})

    def body():
        env.mod.f(1)
        raise KeyError("harness error")
    with coverage_trace(exp) as cov:
        try:
            cov.run("G", body)
        except KeyError:
            pass
    v = exp.score({"m": 1.0, "coverage_trace": cov.record()})
    return v.verdict, getattr(v, "coverage", None)


def s_nested_tracers(env):
    outer = env.exp(G={"exercises": [T("f")]})
    inner = env.exp(H={"exercises": [T("f")]})
    with coverage_trace(outer) as co:
        with coverage_trace(inner) as ci:
            ci.run("H", env.mod.f, 1)
        co.run("G", env.mod.f, 1)
    vo = outer.score({"m": 1.0, "coverage_trace": co.record()})
    vi = inner.score({"m": 1.0, "coverage_trace": ci.record()})
    return (vo.verdict, vi.verdict), (getattr(vo, "coverage", None), getattr(vi, "coverage", None))


def s_async(env):
    exp = env.exp(G={"exercises": [T("f")]})

    async def job():
        return env.mod.f(1)

    async def main(cov):
        return await cov.run_async("G", job)
    with coverage_trace(exp) as cov:
        asyncio.run(main(cov))
    v = exp.score({"m": 1.0, "coverage_trace": cov.record()})
    return v.verdict, getattr(v, "coverage", None)


SCENARIOS = {"sync": s_sync, "two_sections": s_two_sections, "raising_section": s_raising_section,
             "nested_tracers": s_nested_tracers, "async": s_async}


# -- injection ----------------------------------------------------------------------------------

class Injector:
    def __init__(self, codes, fire_at=None, exc=Injected):
        self.codes, self.fire_at, self.count, self.fired_where, self.exc = codes, fire_at, 0, None, exc

    def global_trace(self, frame, event, arg):
        if event == "call" and frame.f_code in self.codes:
            frame.f_trace_opcodes = True
            return self.local_trace
        return None

    def local_trace(self, frame, event, arg):
        if event == "opcode":
            self.count += 1
            if self.fire_at is not None and self.count == self.fire_at:
                self.fired_where = (frame.f_code.co_qualname if hasattr(frame.f_code, "co_qualname")
                                    else frame.f_code.co_name, frame.f_lineno, frame.f_lasti)
                raise self.exc(f"fault point {self.fire_at}")
        return self.local_trace


def run_injected(fn, env, codes, fire_at, exc=Injected):
    inj = Injector(codes, fire_at, exc)
    sys.settrace(inj.global_trace)
    try:
        out = fn(env)
        exc = None
    except BaseException as e:            # noqa: BLE001 -- we classify whatever escapes
        out, exc = None, e
    finally:
        sys.settrace(None)
    return inj, out, exc


def lock_free(timeout=2.0) -> bool:
    got = []

    def take():
        ok = P._LOCK.acquire(timeout=timeout)
        got.append(ok)
        if ok:
            P._LOCK.release()
    t = threading.Thread(target=take, daemon=True)
    t.start()
    t.join(timeout + 1.0)
    return bool(got and got[0])


def state_problems(env) -> list:
    bad = []
    if sys.getprofile() is not None:
        bad.append(f"profile installed: {sys.getprofile()!r}"[:120])
    for name in ("_MINTED", "_BY_FN", "_ANCHORS", "_THREADS"):
        reg = getattr(P, name, None)
        if reg:
            bad.append(f"{name} holds {len(reg)}")
    if getattr(P, "_ACTIVE", 0) != 0:
        bad.append(f"_ACTIVE == {P._ACTIVE}")
    if getattr(P, "_STOP", None) is not None:
        bad.append("_STOP not None")
    for n, c in env.orig.items():
        if getattr(env.mod, n).__code__ is not c:
            bad.append(f"{n}.__code__ not original")
    if not lock_free():
        bad.append("_LOCK not free (another thread could not take it in 2 s)")
    return bad


def force_reset(env):
    sys.setprofile(None)
    threading.setprofile(None)
    for name in ("_MINTED", "_BY_FN", "_ANCHORS", "_THREADS"):
        getattr(P, name).clear()
    P._ACTIVE = 0
    P._STOP = None
    for n, c in env.orig.items():
        getattr(env.mod, n).__code__ = c
    # an RLock held by THIS thread can be released; one held by a dead frame on this thread too
    while True:
        try:
            P._LOCK.release()
        except RuntimeError:
            break


def next_trace_ok(env) -> str | None:
    try:
        v, cov = s_sync(env)
    except BaseException as e:            # noqa: BLE001
        return f"next trace raised {type(e).__name__}: {str(e)[:160]}"
    if v != "PASS" or cov != {"G": {T("f"): 1}}:
        return f"next trace scored {v} {cov}"
    p = state_problems(env)
    return f"next trace left state: {p}" if p else None


STATELESS = {"_check_trace_shape", "_count_dicts", "Experiment._check_coverage", "Experiment.check_metrics",
             "_check_coverage", "check_metrics"}


def stateful(where) -> bool:
    return bool(where) and where[0] not in STATELESS and not where[0].startswith(tuple(s + "." for s in STATELESS))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", action="append", default=[])
    ap.add_argument("--out", default=str(HERE / "fault_injection_v5_result.json"))
    ap.add_argument("--max-points", type=int, default=0, help="0 = every point")
    ap.add_argument("--exc", choices=sorted(EXC), default="exception")
    a = ap.parse_args()
    exc_cls = EXC[a.exc]
    env = Env()
    codes = machinery_codes()
    names = a.scenario or list(SCENARIOS)
    t0 = time.time()
    results = {}
    for name in names:
        fn = SCENARIOS[name]
        force_reset(env)
        run_injected(fn, env, codes, None, exc_cls)          # warm-up: instruments code objects on 3.12+
        force_reset(env)
        inj, clean_out, exc = run_injected(fn, env, codes, None, exc_cls)
        base_bad = state_problems(env)
        n = inj.count
        rows, tally = [], {k: 0 for k in CLASSES}
        split = {"stateful": {k: 0 for k in CLASSES}, "stateless": {k: 0 for k in CLASSES}}
        k, n_run = 0, 0
        while True:
            k += 1
            if a.max_points and k > a.max_points:
                break
            force_reset(env)
            if WARM_EACH:
                run_injected(fn, env, codes, None, exc_cls)      # re-warm: see the docstring
                force_reset(env)
            inj, out, exc = run_injected(fn, env, codes, k, exc_cls)
            if inj.fired_where is None:                          # the run never reached point k: done
                break
            n_run += 1
            propagated = isinstance(exc, exc_cls)
            other_exc = exc is not None and not propagated
            bad = state_problems(env)
            hang = any("_LOCK" in b for b in bad)
            nxt = None
            if not hang:
                nxt = next_trace_ok(env)
            if hang:
                kind = "HANG"
            elif nxt and not nxt.startswith("next trace left state"):
                kind = "BREAKS_NEXT"       # the next clean trace raised or mis-scored
            elif nxt:
                kind = "PERSISTS"          # the next trace was exact, but the damage outlived it
            elif bad:
                kind = "CLEARED"           # damage the next clean trace repaired
            elif not propagated:
                kind = "CONVERTED"
            else:
                kind = "CLEAN"
            tally[kind] += 1
            split["stateful" if stateful(inj.fired_where) else "stateless"][kind] += 1
            if kind != "CLEAN":
                rows.append({"k": k, "kind": kind, "where": inj.fired_where,
                             "stateful": stateful(inj.fired_where),
                             "chained": bool(exc is not None and isinstance(exc.__cause__, exc_cls)),
                             "escaped": None if exc is None else f"{type(exc).__name__}: {str(exc)[:120]}",
                             "state": bad, "next": nxt, "other_exception": other_exc,
                             "completed_normally": exc is None, "result_if_completed": repr(out)[:160]})
            if hang:
                force_reset(env)
                if not lock_free(0.5):
                    rows[-1]["aborted"] = "the lock is held by another thread; later points in this scenario were not run"
                    break
        where = {}
        for r in rows:
            w = r["where"]
            key = f"{w[0]}:{w[1]}" if w else "?"
            where.setdefault(key, {}).setdefault(r["kind"], 0)
            where[key][r["kind"]] += 1
        results[name] = {"clean_run": {"out": repr(clean_out)[:200], "raised": repr(exc)[:200] if exc else None,
                                       "state_after": base_bad},
                         "n_opcodes_clean_run": n, "n_fault_points": n_run, "n_run": n_run,
                         "tally": tally, "by_region": split,
                         "n_not_clean": sum(v for k, v in tally.items() if k != "CLEAN"),
                         "by_source_line": dict(sorted(where.items())), "not_clean": rows}
        print(f"{name:16s} points {n_run:5d} (clean run {n})  " + "  ".join(f"{c} {v}" for c, v in tally.items()), flush=True)
    force_reset(env)
    tot = {k: sum(r["tally"][k] for r in results.values()) for k in CLASSES}
    region = {reg: {k: sum(r["by_region"][reg][k] for r in results.values()) for k in CLASSES}
              for reg in ("stateful", "stateless")}
    sites = {}
    for r in results.values():
        for row in r["not_clean"]:
            w = row["where"]
            sites.setdefault(row["kind"], set()).add(f"{w[0]}:{w[1]}" if w else "?")
    n_sites_all = len(set().union(*sites.values())) if sites else 0
    res = {
        "what": "exhaustive fault injection: an Injected exception at every opcode the v5 tracer's machinery "
                "executes (outside the profile hook), one point per run, with state invariants and a follow-up "
                "trace checked after each",
        "generator": "papers/first-afference/fault_injection_v5.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "impl_path": P.__file__,
        "impl_sha256": hashlib.sha256(Path(P.__file__).read_bytes()).hexdigest(),
        "python": sys.version.split()[0],
        "exception_class": exc_cls.__mro__[1].__name__ + " subclass",
        "n_machinery_code_objects": len(codes),
        "scenarios": results,
        "n_fault_points": sum(r["n_run"] for r in results.values()),
        "totals": tot,
        "totals_by_region": region,
        "n_not_clean": sum(v for k, v in tot.items() if k != "CLEAN"),
        "n_damaging": sum(tot[k] for k in ("HANG", "BREAKS_NEXT", "PERSISTS", "CLEARED")),
        "n_stateful_points": sum(region["stateful"].values()),
        "n_stateful_damaging": sum(region["stateful"][k] for k in ("HANG", "BREAKS_NEXT", "PERSISTS", "CLEARED")),
        "distinct_sites_by_class": {k: len(v) for k, v in sorted(sites.items())},
        "n_distinct_not_clean_sites": n_sites_all,
        "seconds": round(time.time() - t0, 1),
    }
    Path(a.out).write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"TOTAL points {res['n_fault_points']}  " + "  ".join(f"{k} {v}" for k, v in tot.items())
          + f"  ({res['seconds']} s) -> {Path(a.out).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
