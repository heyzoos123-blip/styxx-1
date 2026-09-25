"""Protocol v5e (minted identity, stack-anchor attribution) regression tests.

The frozen exam (papers/first-afference/run_protocol_v5e.py) is the full battery; this pins the
properties the three red-team rounds broke, each matched on its reason code, plus the P1 retro-case
against the committed harness. v5c/v5d's `with cov.section(...)` API is retired: sections are calls.
"""
import asyncio
import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import threading
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import styxx.protocol as P  # noqa: E402
from styxx.protocol import (Experiment, GateSpecError, _select_gates_block,  # noqa: E402
                            coverage_trace)

FIX = "_v5e_testfix"
FIXTURE = '''
import functools
import types
def f(x=0): return x
def g(x=0): return x
alias_f = f
def _mk(k):
    def prod(x=0): return x + k
    return prod
double = _mk(2)
triple = _mk(3)
def _inner(x=0): return x
@functools.wraps(_inner)
def run_fast(x=0): return _inner(x)
@functools.wraps(_inner)
def run_safe(x=0): return _inner(x)
f_preclone = types.FunctionType(f.__code__, globals(), "f_preclone", f.__defaults__)
'''
STUB = "def f(x=0): return 'stub'\n"


def T(n):
    return f"{FIX}:{n}"


@pytest.fixture()
def fx(tmp_path, monkeypatch):
    d = tmp_path / "fixmod"
    d.mkdir()
    (d / f"{FIX}.py").write_text(FIXTURE, encoding="utf-8")
    (d / "_v5e_teststub.py").write_text(STUB, encoding="utf-8")
    monkeypatch.syspath_prepend(str(d))
    for m in (FIX, "_v5e_teststub"):
        sys.modules.pop(m, None)
    mod = __import__(FIX)
    originals = {n: getattr(mod, n).__code__ for n in ("f", "g", "double", "run_fast")}
    yield mod
    for n, c in originals.items():
        assert getattr(mod, n).__code__ is c, f"{n}.__code__ not restored"
    assert sys.getprofile() is None
    assert not (P._MINTED or P._BY_FN or P._ANCHORS or P._THREADS) and P._ACTIVE == 0
    for m in (FIX, "_v5e_teststub"):
        sys.modules.pop(m, None)


@pytest.fixture()
def mk(tmp_path):
    n = [0]

    def _mk(**gates):
        n[0] += 1
        repo = tmp_path / f"repo{n[0]}"
        repo.mkdir()
        g = {k: {"metric": "m", "op": ">=", "value": 0.5, **v} for k, v in gates.items()}
        spec = {"gates": g, "outcomes": [{"when": {k: True for k in g}, "verdict": "PASS"},
                                         {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
        p = repo / "PREREG_case.md"
        p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
        for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                    ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false",
                     "commit", "-qm", "c"]):
            subprocess.run(cmd, cwd=repo, check=True)
        return Experiment(p)
    return _mk


def _trace(exp, body):
    with coverage_trace(exp) as cov:
        body(cov)
    return {"m": 1.0, "coverage_trace": cov.record()}


# -- identity: minting ------------------------------------------------------------------------

@pytest.mark.parametrize("declared, call", [
    ("double", lambda fx: fx._mk(2)(1)),           # a factory sibling, even with the same argument
    ("double", lambda fx: fx.triple(1)),
    ("run_fast", lambda fx: fx.run_safe(1)),       # a wraps sibling of the same inner
    ("run_fast", lambda fx: fx._inner(1)),         # the wrapped inner, called directly
    ("f", lambda fx: fx.f_preclone(1)),            # a clone made before the trace
])
def test_code_sharing_functions_are_never_credited(mk, fx, declared, call):
    exp = mk(G={"exercises": [T(declared)]})
    with pytest.raises(GateSpecError, match=r"^\[V5:NOT_EXERCISED\]"):
        exp.score(_trace(exp, lambda cov: cov.run("G", call, fx)))


def test_declared_product_wrapper_and_alias_are_credited(mk, fx):
    exp = mk(G={"exercises": [T("double"), T("run_fast"), T("f"), T("alias_f")]})
    res = _trace(exp, lambda cov: cov.run("G", lambda: (fx.double(1), fx.run_fast(1), fx.f(1))))
    v = exp.score(res)
    assert v.verdict == "PASS"
    assert v.coverage["G"] == {T("double"): 1, T("run_fast"): 1, T("f"): 1, T("alias_f"): 1}


def test_clone_under_other_globals_is_a_tripwire(mk, fx):
    exp = mk(G={"exercises": [T("f")]})
    res = _trace(exp, lambda cov: cov.run("G", lambda: (
        fx.f(), types.FunctionType(fx.f.__code__, {"__builtins__": {}})(1))))
    with pytest.raises(GateSpecError, match=r"^\[V5:CLONE_CALLED\]"):
        exp.score(res)


def test_swapped_code_is_a_tripwire(mk, fx):
    exp = mk(G={"exercises": [T("f")]})
    original = fx.f.__code__

    def body():
        fx.f()
        fx.f.__code__ = fx.g.__code__               # swapped during the trace, left in place
    res = _trace(exp, lambda cov: cov.run("G", body))
    fx.f.__code__ = original                        # the trace does not restore a swapped function
    with pytest.raises(GateSpecError, match=r"^\[V5:CODE_SWAPPED\]"):
        exp.score(res)


def test_stub_from_another_module_is_foreign(mk, fx):
    import _v5e_teststub
    real = fx.f
    fx.f = _v5e_teststub.f                          # a stub bound at the name before the trace
    try:
        with pytest.raises(GateSpecError, match=r"^\[V5:FOREIGN_DEFINITION\]"):
            coverage_trace(mk(G={"exercises": [T("f")]})).__enter__()
    finally:
        fx.f = real


# -- attribution: the stack anchor ------------------------------------------------------------

def test_thread_calls_count_only_in_the_threads_own_section(mk, fx):
    exp = mk(G={"exercises": [T("f")]}, H={"exercises": [T("g")]})

    def spawn(cov):
        th = threading.Thread(target=fx.f)             # no section of its own: not credited
        th.start()
        th.join()
        th = threading.Thread(target=cov.run, args=("H", fx.g))
        th.start()
        th.join()
    res = _trace(exp, lambda cov: cov.run("G", spawn, cov))
    with pytest.raises(GateSpecError, match=r"gate 'G': COVERAGE VIOLATION"):
        exp.score(res)
    assert exp._check_coverage("H", res) == {T("g"): 1}


def test_tasks_are_cut_at_dispatch_and_run_async_is_the_remedy(mk, fx):
    exp = mk(G={"exercises": [T("f")]}, H={"exercises": [T("g")]})

    async def call(fn):
        fn()

    async def main(cov):
        await asyncio.get_running_loop().create_task(call(fx.f))   # a task: cut, not credited
        await asyncio.gather(cov.run_async("H", call, fx.g))       # its own opening: credited
    res = _trace(exp, lambda cov: asyncio.run(cov.run_async("G", main, cov)))
    with pytest.raises(GateSpecError, match=r"gate 'G': COVERAGE VIOLATION"):
        exp._check_coverage("G", res)
    assert exp._check_coverage("H", res) == {T("g"): 1}


def test_a_loop_inside_a_section_is_cut(mk, fx):
    exp = mk(G={"exercises": [T("f")]})

    async def main():
        fx.f()
    res = _trace(exp, lambda cov: cov.run("G", asyncio.run, main()))
    with pytest.raises(GateSpecError, match=r"not executed on the stack of any opening"):
        exp.score(res)
    assert res["coverage_trace"]["uncredited"]["dispatched"] == {T("f"): 1}


def test_swallowed_nested_section_still_refuses_at_score(mk, fx):
    exp = mk(G={"exercises": [T("f")]}, H={"exercises": [T("g")]})

    def outer(cov):
        fx.f()
        try:
            cov.run("H", fx.g)
        except GateSpecError:
            pass
    res = _trace(exp, lambda cov: cov.run("G", outer, cov))
    with pytest.raises(GateSpecError, match=r"^\[V5:NESTED_SECTION\]"):
        exp.score(res)


def test_a_raising_section_keeps_its_counts(mk, fx):
    exp = mk(G={"exercises": [T("f")]})

    def body():
        fx.f()
        raise ValueError("boom")

    def harness(cov):
        with pytest.raises(ValueError):
            cov.run("G", body)
    res = _trace(exp, harness)
    assert exp.score(res).coverage["G"] == {T("f"): 1}
    assert res["coverage_trace"]["sections"]["G"][0]["end"] == "raised"


# -- the trace ---------------------------------------------------------------------------------

def test_every_type_check_is_exact(mk, fx):
    class D(dict):
        pass
    exp = mk(G={"exercises": [T("f")]})
    res = _trace(exp, lambda cov: cov.run("G", fx.f))
    res["coverage_trace"]["targets"] = D(res["coverage_trace"]["targets"])
    with pytest.raises(GateSpecError, match=r"^\[V5:BAD_TRACE\]"):
        exp.score(res)


def test_record_refuses_inside_the_trace(mk, fx):
    exp = mk(G={"exercises": [T("f")]})
    with coverage_trace(exp) as cov:
        with pytest.raises(GateSpecError, match=r"^\[V5:TRACE_ACTIVE\]"):
            cov.record()


def test_v5d_traces_refuse_as_wrong_tracer(mk, fx):
    exp = mk(G={"exercises": [T("f")]})
    res = _trace(exp, lambda cov: cov.run("G", fx.f))
    res["coverage_trace"]["tracer"] = "styxx.protocol.coverage_trace/1"
    with pytest.raises(GateSpecError, match=r"^\[V5:WRONG_TRACER\]"):
        exp.score(res)


# -- the P1 retro-case, against the committed harness -----------------------------------------

def test_p1_g4_refuses_against_its_own_harness(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    fa = ROOT / "papers" / "first-afference"
    loader = importlib.machinery.SourceFileLoader(
        "styxx.power", str(ROOT / "styxx" / "power_QUARANTINED.py.txt"))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("styxx.power", loader))
    monkeypatch.setitem(sys.modules, "styxx.power", mod)
    loader.exec_module(mod)
    spec = importlib.util.spec_from_file_location("run_p1_v5etest", fa / "run_p1.py")
    run_p1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_p1)
    gates = json.loads(_select_gates_block(
        (fa / "PREREG_p1_power_refusal_2026_08_08.md").read_text(encoding="utf-8")))
    gates["gates"]["G4_refuses_degenerate"]["exercises"] = [
        f"styxx.power:{n}" for n in ("effective_n", "order_stat_bar", "false_positive_rate",
                                     "min_detectable_bar", "reachable")]
    p = tmp_path / "PREREG_p1_retro.md"
    p.write_text("# retro\n\n```gates\n" + json.dumps(gates) + "\n```\n", encoding="utf-8")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false",
                 "commit", "-qm", "r"]):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    exp = Experiment(p)
    res = json.loads((fa / "p1_result.json").read_text(encoding="utf-8"))
    with coverage_trace(exp) as cov:
        cov.run("G4_refuses_degenerate", run_p1.degenerate, np.random.default_rng(run_p1.SEED))
    res["coverage_trace"] = cov.record()
    assert res["coverage_trace"]["sections"]["G4_refuses_degenerate"][0]["calls"] == \
        {"styxx.power:reachable": 12}
    with pytest.raises(GateSpecError, match=r"^\[V5:NOT_EXERCISED\].*order_stat_bar"):
        exp.score(res)
