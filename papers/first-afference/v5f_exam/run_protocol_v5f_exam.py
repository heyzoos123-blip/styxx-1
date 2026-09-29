# -*- coding: utf-8 -*-
"""Protocol v5f exam runner (exam author), per DESIGN_protocol_v5f_DRAFT_2026_09_25.md, "Exam cases
required" and "Exam harness rules". NOT YET FROZEN: this is the runner under construction, covered
table by table (see the receipt's "tables" and "tables_not_yet_covered").

Written from the v5f design text alone (G_INDEP). Its structure and receipt follow the committed
frozen runners in papers/first-afference/ (run_protocol_v5e.py: a docstring naming what the exam
assumes, per-case records with expected/outcome/ok/detail/leftover, a JSON receipt with the runner's
and the implementation's sha256, and a one-line VERDICT); no v5e implementation was read.

WHAT THE EXAM READS (harness rule "What the exam may read"): the public API (coverage_trace, the
facade's run/run_async/record/__enter__/__exit__, Experiment.score/check_metrics, GateSpecError),
fixture modules, _v5_state() and _v5_faultpoints(). No other private name of the implementation.

Implementation under exam: --impl PATH (a .py file, loaded under its basename as the module name;
default ref_v5f.py beside this file) or --impl-module NAME (imported, e.g. styxx.protocol).

Placements (harness rule "How cases run"): main-thread cases run first, on the main thread, before
the self-trace; fresh-subprocess cases each run in their own process of this interpreter (this
file re-executed with --child-case or --sub); every other case runs in its own thread inside the
outer self-trace as cov.run(<table's gate section>, case), with a 30 s join watchdog. The
self-trace's prereg declares, for each table's gate, the implementation's `_open` (every section
opens through it), and must itself PASS at the end.

Leftover check (revision 10, R9-6): around each case, _v5_state() must equal the "before" snapshot
except `cut`, `tool`, and `tool_ours` when the "before" `tool` is None; `cut_current` True; `guard`
"free"; every fixture function's __code__ its original; sys/threading profile and trace functions
unchanged; tool ids other than styxx's unchanged (names by identity, or == for an exact str);
gc.get_freeze_count() not higher.

Interpreters (harness rule "Interpreters"): tracing cases run on 3.12.3 and 3.13.12 only. On any
other interpreter the runner executes X37 and the scoring-only cases, which read the prebuilt /3
traces in traces_v5f/ (generated on 3.12.3 by --make-traces), and records every tracing case as
not run on this interpreter; that is a clean refusal, and its verdict says so.

Receipt: --out PATH (default: print only). Exit status 0 iff every case run passed (and, on a
verified interpreter, the self-trace passed).
"""
import argparse
import asyncio
import collections
import functools
import gc
import hashlib
import importlib
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import traceback
import types

sys.dont_write_bytecode = True
RUNNER = os.path.abspath(__file__)
HERE = os.path.dirname(RUNNER)
SPEC = os.path.join(HERE, "..", "DESIGN_protocol_v5f_DRAFT_2026_09_25.md")
TRACES = os.path.join(HERE, "traces_v5f")
VERIFIED = ((3, 12, 3), (3, 13, 12))
TRACING = tuple(sys.version_info[:3]) in VERIFIED and platform.python_implementation() == "CPython"
WATCHDOG_S = 30.0
_CODE = re.compile(r"\[V5:([A-Z_]+)\]")

_ap = argparse.ArgumentParser(add_help=True)
_ap.add_argument("--impl", default=os.path.join(HERE, "ref_v5f.py"))
_ap.add_argument("--impl-module", default=None)
_ap.add_argument("--only", default=None, help="comma-separated case ids")
_ap.add_argument("--out", default=None)
_ap.add_argument("--make-traces", action="store_true")
_ap.add_argument("--child-case", default=None)
_ap.add_argument("--sub", default=None)
ARGS = _ap.parse_args()

def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()

if ARGS.impl_module:
    P = importlib.import_module(ARGS.impl_module)
    IMPL_PATH = os.path.abspath(P.__file__)
else:
    IMPL_PATH = os.path.abspath(ARGS.impl)
    _name = os.path.splitext(os.path.basename(IMPL_PATH))[0]
    _spec = importlib.util.spec_from_file_location(_name, IMPL_PATH)
    P = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = P
    _spec.loader.exec_module(P)
IMPL_MOD = P.__name__
GateSpecError = P.GateSpecError

def _impl_args():
    return (["--impl-module", ARGS.impl_module] if ARGS.impl_module else ["--impl", IMPL_PATH])

def load_trace(name):
    with open(os.path.join(TRACES, name + ".json")) as fh:
        return json.load(fh)


# =================================================================================================
# Fixtures, preregs and cases (each case quotes its row; written from the design text)
# =================================================================================================
WORK = tempfile.mkdtemp(prefix="v5f_exam_")
FIX = os.path.join(WORK, "fixtures")
REPO = os.path.join(WORK, "repo")
os.makedirs(FIX)
os.makedirs(REPO)
sys.path.insert(0, FIX)

# -- fixture modules ------------------------------------------------------------------------------
FIXTURES = {
    "fx_v5f.py": '''
        import functools
        def f(x=0): return x + 1
        def g(x=0): return x + 2
        def t():
            raise ValueError("t raises inside its body")
        def gen():
            yield 1
            yield 2
        def gen2():
            yield 1
        def genfn():
            yield 1
        async def amain():
            await __import__("asyncio").sleep(0)
            return 7
        def other(x=0): return -1
        def make_check(th):
            def check(x): return x > th
            return check
        check_low = make_check(0)
        check_high = make_check(10)
        def fast(n): return n * 2
        class Ref:
            @staticmethod
            def power(n): return n * 2
        power = functools.wraps(Ref.power)(functools.lru_cache(None)(fast))
        @functools.lru_cache(None)
        def cached(x): return x * 3
        class Base:
            def fit(self): return 1
        class Mid(Base): pass
        class Leaf(Mid): pass
        class Weird:
            count = 0
            @property
            def __dict__(self):
                Weird.count += 1
                return {"fit": f}
        weird = Weird()
    ''',
    "fx_stub.py": '''
        def stub(): return "stub"
    ''',
    "fx_swap.py": '''
        def real(): return "real"
        alias = real
    ''',
    "fx_x59e.py": '''
        # X59e's fresh wrapper: a top-level def of its own, used by no other case (harness rules).
        import asyncio.events
        _orig_run = asyncio.events.Handle._run
        def run59(self):
            return _orig_run(self)
    ''',
    # revision 10 fixtures
    "fx_badimport.py": '''
        raise ValueError("fx_badimport: the import raises")
    ''',
    "fx_pepkey.py": '''
        def __getattr__(name):
            raise KeyError(name)
    ''',
    "fx_x14d.py": '''
        class Base:
            def fit(self): return 1
        class Sub(Base):
            pass
        Base.__module__ = 5          # set after the class statement: its own dict's '__module__' is not a str
    ''',
    "fx_x24f.py": '''
        import functools
        COUNT = {"n": 0}
        class Meta(type):
            def __getattribute__(cls, name):
                if name in ("__qualname__", "__name__"):
                    COUNT["n"] += 1
                return type.__getattribute__(cls, name)
        class Stamp(metaclass=Meta):
            pass
        cached_len = functools.lru_cache(None)(len)
        def _mk():
            def body(n): return n
            return body
        stamped = functools.lru_cache(None)(_mk())
        stamped.__wrapped__ = Stamp()
    ''',
    "fx_pep.py": '''
        def __getattr__(name):
            if name == "thing":
                def fresh(): return 1
                return fresh
            raise AttributeError(name)
    ''',
}
for fname, body in FIXTURES.items():
    with open(os.path.join(FIX, fname), "w") as fh:
        fh.write(textwrap.dedent(body))
import fx_v5f, fx_stub, fx_swap, fx_pep, fx_x59e, fx_x14d, fx_x24f   # noqa: E402

ORIG = {}
for mod in (fx_v5f, fx_stub, fx_swap):
    for k, v in vars(mod).items():
        if type(v) is types.FunctionType:
            ORIG[(mod.__name__, k)] = (v, v.__code__)
ORIG[("fx_v5f", "cached.__wrapped__")] = (fx_v5f.cached.__wrapped__, fx_v5f.cached.__wrapped__.__code__)
ORIG[("fx_v5f", "Base.fit")] = (fx_v5f.Base.fit, fx_v5f.Base.fit.__code__)

# -- preregs (all committed once, in a throwaway repo) --------------------------------------------
def gates(decl, metric_value=0.0, op=">=", sections=None, metric="m"):
    gs = {}
    for name, targets in decl.items():
        gs[name] = {"metric": metric, "op": op, "value": metric_value, "exercises": targets}
        if sections and name in sections:
            gs[name]["section"] = sections[name]
    rows = [{"when": {n: True for n in gs}, "verdict": "PASS"}]
    for n in gs:
        rows.append({"when": {n: False}, "verdict": "FAIL_" + n})
    return {"gates": gs, "outcomes": rows, "smoke_verdict": "INVALID__smoke"}

PREREGS = {
    "F": gates({"G": ["fx_v5f:f"]}),
    "FG": gates({"G": ["fx_v5f:f", "fx_v5f:g"]}),
    "GH": gates({"G": ["fx_v5f:f"], "H": ["fx_v5f:g"]}),
    "LOW": gates({"G": ["fx_v5f:check_low"]}),
    "X26B": gates({"G": ["fx_swap:real"]}),
    "X24B": gates({"G": ["fx_v5f:power"]}),
    "X13B": gates({"G": ["fx_pep:thing"]}),
    "X14C": gates({"G": ["fx_v5f:Leaf.fit"]}),
    "X17B": gates({"G": ["fx_v5f:weird.fit"]}),
    "X34": gates({"G": ["asyncio.events:Handle._run", "fx_v5f:f"]}),
    "CACHED": gates({"G": ["fx_v5f:cached"]}),
    "T": gates({"G": ["fx_v5f:t"]}),
    "CORO": gates({"G": ["fx_v5f:amain"]}),
    "GEN": gates({"G": ["fx_v5f:gen"]}),
    "GEN2": gates({"G": ["fx_v5f:gen2"]}),
    "FT": gates({"G": ["fx_v5f:f", "fx_v5f:t"]}),
    "LAZY": gates({"G": ["fx_v5f:genfn"]}),
    "X33": gates({"G": ["fx_v5f:f", "fx_v5f:nonexistent"]}),
    "X122": gates({"G": ["fx_v5f:f", "fx_v5f:g"]}, metric_value=1.0),
    "F_OTHER": gates({"G": ["fx_v5f:f"], "K": ["fx_v5f:g"]}),     # a second gates block (STALE)
    "AB": gates({"A": ["fx_v5f:f"], "B": ["fx_v5f:g"]}),
    # revision 10
    "X10C_IMP": gates({"G": ["fx_badimport:f"]}),
    "X10C_PEP": gates({"G": ["fx_pepkey:thing"]}),
    "X14D": gates({"G": ["fx_x14d:Sub.fit"]}),
    "X24F_LEN": gates({"G": ["fx_x24f:cached_len"]}),
    "X24F_STAMP": gates({"G": ["fx_x24f:stamped"]}),
    "X117E": gates({"G": ["fx_v5f:f"]}, metric="a.b"),
}
for key, spec in PREREGS.items():
    with open(os.path.join(REPO, f"PREREG_{key}.md"), "w") as fh:
        fh.write(f"# smoke prereg {key}\n\n```gates\n{json.dumps(spec, indent=1)}\n```\n")
_git = ["git", "-c", "user.name=smoke", "-c", "user.email=smoke@invalid", "-c", "commit.gpgsign=false"]
subprocess.run(["git", "init", "-q"], cwd=REPO, check=True)
subprocess.run(_git + ["add", "."], cwd=REPO, check=True)
subprocess.run(_git + ["commit", "-q", "-m", "smoke preregs"], cwd=REPO, check=True)

def EXP(key):
    return P.Experiment(os.path.join(REPO, f"PREREG_{key}.md"))

# -- outcome helpers -------------------------------------------------------------------------------
def code_of(exc):
    m = _CODE.match(str(exc))
    return m.group(1) if m else None

def score(exp, trace, m=1.0):
    """('PASS', coverage) or ('REFUSE', code, message) for the whole prereg."""
    try:
        v = exp.score({"m": m, "coverage_trace": trace})
        return ("PASS", v.coverage, v.verdict)
    except GateSpecError as e:
        return ("REFUSE", code_of(e), str(e))

def gate_outcome(exp, trace, gate):
    """Revision 9 (GAP-26): scoring cases are judged through the public score(), never through the
    private Experiment._check_coverage. `gate` names the gate the row is about; score() checks
    every declaring gate, and each caller's prereg refuses with the same code at every gate."""
    try:
        v = exp.score({"m": 1.0, "coverage_trace": trace})
        return ("PASS", v.coverage.get(gate))
    except GateSpecError as e:
        return ("REFUSE", code_of(e), str(e))

def expect(cond, why):
    if not cond:
        raise AssertionError(why)

def expect_refuse(out, code):
    expect(out[0] == "REFUSE" and out[1] == code, f"expected [V5:{code}], got {out[:2]} {out[2:][:1]}")

def expect_pass(out, counts):
    expect(out[0] == "PASS", f"expected PASS, got {out[:2]} {out[2:][:1]}")
    expect(out[1] == counts, f"expected counts {counts}, got {out[1]}")

def raises_code(fn, code):
    try:
        fn()
    except GateSpecError as e:
        expect(str(e).startswith(f"[V5:{code}]"), f"expected [V5:{code}], got {str(e)[:120]}")
        return e
    raise AssertionError(f"expected [V5:{code}], nothing raised")

# (the smoke harness's absolute leftovers() is not used: the runner applies the snapshot rule, snap()/leftover_diff())

# -- cases -----------------------------------------------------------------------------------------
CASES = []
def case(cid, family, row):
    def deco(fn):
        CASES.append((cid, family, row, fn))
        return fn
    return deco

@case("V01", "identity", "plain f -> {f:1}")
def v01():
    exp = EXP("F")
    with P.coverage_trace(exp) as cov:
        cov.run("G", fx_v5f.f)
    expect_pass(score(exp, cov.record()), {"G": {"fx_v5f:f": 1}})
    rec = cov.record()
    expect(rec["sections"]["G"] == [{"calls": {"fx_v5f:f": 1}, "ambiguous": {}, "end": "returned",
                                     "notes": []}], f"record {rec['sections']}")
    expect(rec["problems"] == [] and rec["tracer"] == "styxx.protocol.coverage_trace/3", "problems/tracer")

@case("X40", "identity", "factory sibling: declare check_low, call check_high -> NOT_EXERCISED")
def x40():
    exp = EXP("LOW")
    with P.coverage_trace(exp) as cov:
        cov.run("G", fx_v5f.check_high, 11)
    expect_refuse(score(exp, cov.record()), "NOT_EXERCISED")

@case("X55", "identity", "FunctionType(T.__code__, {})() -> CLONE_CALLED")
def x55():
    exp = EXP("F")
    with P.coverage_trace(exp) as cov:
        cov.run("G", lambda: (fx_v5f.f(), types.FunctionType(fx_v5f.f.__code__, {})(0)))
    expect_refuse(score(exp, cov.record()), "CLONE_CALLED")

@case("X59", "identity", "T called, then T.__code__ reassigned -> CODE_SWAPPED (swap left in place)")
def x59():
    exp = EXP("F")
    f = fx_v5f.f
    orig = ORIG[("fx_v5f", "f")][1]
    try:
        with P.coverage_trace(exp) as cov:
            def body():
                f()
                f.__code__ = fx_v5f.other.__code__
            cov.run("G", body)
        expect(f.__code__ is fx_v5f.other.__code__ and f() == -1, "swap left in place (X59d)")
        expect_refuse(score(exp, cov.record()), "CODE_SWAPPED")
    finally:
        f.__code__ = orig

@case("X26b", "identity", "real.__code__ = stub.__code__ before the trace; called via alias -> FOREIGN_DEFINITION")
def x26b():
    exp = EXP("X26B")
    orig = fx_swap.real.__code__
    fx_swap.real.__code__ = fx_stub.stub.__code__
    try:
        cov = P.coverage_trace(exp)
        e = raises_code(cov.__enter__, "FOREIGN_DEFINITION")
        expect(fx_swap.real.__code__ is fx_stub.stub.__code__, "nothing minted")
        cov.__exit__(None, None, None)
    finally:
        fx_swap.real.__code__ = orig

@case("X24b", "identity", "wraps(power_ref)(lru_cache(fast)) -> NOT_A_FUNCTION naming fast")
def x24b():
    cov = P.coverage_trace(EXP("X24B"))
    e = raises_code(cov.__enter__, "NOT_A_FUNCTION")
    expect("fx_v5f:fast" in str(e) and "Ref.power" not in str(e), f"message: {e}")
    cov.__exit__(None, None, None)

@case("X13b", "identity", "PEP 562 __getattr__ returning a fresh function -> UNRESOLVED with remedy")
def x13b():
    cov = P.coverage_trace(EXP("X13B"))
    e = raises_code(cov.__enter__, "UNRESOLVED")
    expect("declare the function it forwards to" in str(e), f"remedy: {e}")
    cov.__exit__(None, None, None)

@case("X14c", "identity", "Leaf(Mid(Base)).fit -> INHERITED naming the defining class")
def x14c():
    cov = P.coverage_trace(EXP("X14C"))
    e = raises_code(cov.__enter__, "INHERITED")
    expect("fx_v5f:Base" in str(e), f"defining class: {e}")
    cov.__exit__(None, None, None)

@case("X17b", "identity", "step through a Python __dict__ property -> INSTANCE_PATH, counter 0")
def x17b():
    cov = P.coverage_trace(EXP("X17B"))
    raises_code(cov.__enter__, "INSTANCE_PATH")
    expect(fx_v5f.Weird.count == 0, "the __dict__ property was called")
    cov.__exit__(None, None, None)

@case("X34", "identity", "declare asyncio.events:Handle._run and f -> RESERVED_TARGET at entry")
def x34():
    cov = P.coverage_trace(EXP("X34"))
    raises_code(cov.__enter__, "RESERVED_TARGET")
    cov.__exit__(None, None, None)

@case("V07", "identity", "cached.cache_clear(), then cached(1) twice -> {cached:1}")
def v07():
    exp = EXP("CACHED")
    fx_v5f.cached.cache_clear()
    with P.coverage_trace(exp) as cov:
        cov.run("G", lambda: (fx_v5f.cached(1), fx_v5f.cached(1)))
    expect_pass(score(exp, cov.record()), {"G": {"fx_v5f:cached": 1}})

@case("X33", "identity", "one good + one unresolvable target -> UNRESOLVED; good __code__ untouched")
def x33():
    cov = P.coverage_trace(EXP("X33"))
    raises_code(cov.__enter__, "UNRESOLVED")
    expect(fx_v5f.f.__code__ is ORIG[("fx_v5f", "f")][1], "good target minted")
    cov.__exit__(None, None, None)

@case("X73", "attribution", "cov.run(G, asyncio.run, main()) -> NOT_EXERCISED (dispatched)")
def x73():
    exp = EXP("F")
    async def main():
        fx_v5f.f()
    with P.coverage_trace(exp) as cov:
        cov.run("G", asyncio.run, main())
    out = score(exp, cov.record())
    expect_refuse(out, "NOT_EXERCISED")
    expect("dispatched {'fx_v5f:f': 1}" in out[2], f"message: {out[2][:300]}")

@case("V18", "attribution", "asyncio.run(cov.run_async(G, main)) -> {f:1, g:1}")
def v18():
    exp = EXP("FG")
    async def main():
        fx_v5f.f()
        await asyncio.sleep(0)
        fx_v5f.g()
    with P.coverage_trace(exp) as cov:
        asyncio.run(cov.run_async("G", main))
    expect_pass(score(exp, cov.record()), {"G": {"fx_v5f:f": 1, "fx_v5f:g": 1}})

@case("X76", "attribution", "same-tracer nested open, swallowed; an unrelated gate also refuses -> NESTED_SECTION")
def x76():
    exp = EXP("GH")
    with P.coverage_trace(exp) as cov:
        def body():
            fx_v5f.f()
            try:
                cov.run("G", fx_v5f.f)
            except GateSpecError as e:
                expect("on the stack of two openings of section 'G'" in str(e), f"text: {e}")
        cov.run("G", body)
        cov.run("H", fx_v5f.g)
    rec = cov.record()
    expect_refuse(gate_outcome(exp, rec, "G"), "NESTED_SECTION")
    expect_refuse(gate_outcome(exp, rec, "H"), "NESTED_SECTION")

@case("X60", "attribution", "thread started in A calls f -> NOT_EXERCISED; uncredited unattributed {f:1}")
def x60():
    exp = EXP("F")
    with P.coverage_trace(exp) as cov:
        def body():
            th = threading.Thread(target=fx_v5f.f)
            th.start()
            th.join()
        cov.run("G", body)
    rec = cov.record()
    expect_refuse(score(exp, rec), "NOT_EXERCISED")
    expect(rec["uncredited"] == {"dispatched": {}, "unattributed": {"fx_v5f:f": 1}}, f"{rec['uncredited']}")

def counting_section_class():
    """X78f's variant class (revision 10, R9-1): counts __eq__, __hash__, __repr__, __str__ and
    __format__, and its metaclass counts every read of __qualname__ and __name__."""
    calls = {"eq": 0, "hash": 0, "repr": 0, "str": 0, "format": 0, "meta": 0}
    class Meta(type):
        def __getattribute__(cls, name):
            if name in ("__qualname__", "__name__"):
                calls["meta"] += 1
            return type.__getattribute__(cls, name)
    class Sec(metaclass=Meta):
        def __eq__(self, other):
            calls["eq"] += 1
            return True
        def __hash__(self):
            calls["hash"] += 1
            return hash("G")
        def __repr__(self):
            calls["repr"] += 1
            return "'G'"
        def __str__(self):
            calls["str"] += 1
            return "G"
        def __format__(self, spec):
            calls["format"] += 1
            return "G"
    calls["meta"] = 0                   # the class statement itself may read its own names
    return Sec, calls

@case("X78f", "attribution", "cov.run(5, f) swallowed; variant (rev. 10) counting __eq__/__hash__/__repr__/__str__/__format__ and the metaclass's __qualname__/__name__ reads -> UNDECLARED_SECTION, counters 0")
def x78f():
    exp = EXP("F")
    Sec, calls = counting_section_class()
    with P.coverage_trace(exp) as cov:
        for sec in (5, Sec()):
            try:
                cov.run(sec, fx_v5f.f)
                raise AssertionError("no refusal")
            except GateSpecError as e:
                expect(code_of(e) == "UNDECLARED_SECTION", str(e))
        cov.run("G", fx_v5f.f)
    expect_refuse(score(exp, cov.record()), "UNDECLARED_SECTION")
    expect(all(v == 0 for v in calls.values()), f"section compared or formatted: {calls}")

@case("V54", "event path", "target raising inside its body, caught, 3 calls -> {t:3} (confirmed by PY_UNWIND)")
def v54():
    exp = EXP("T")
    def body():
        for _ in range(3):
            try:
                fx_v5f.t()
            except ValueError:
                pass
    with P.coverage_trace(exp) as cov:
        cov.run("G", body)
    expect_pass(score(exp, cov.record()), {"G": {"fx_v5f:t": 3}})

@case("V55", "event path", "asyncio.run(cov.run_async('G', main)), declared coroutine awaits once -> {coro:2}")
def v55():
    exp = EXP("CORO")
    with P.coverage_trace(exp) as cov:
        asyncio.run(cov.run_async("G", fx_v5f.amain))
    expect_pass(score(exp, cov.record()), {"G": {"fx_v5f:amain": 2}})

@case("V14", "event path", "generator with two yields, consumed -> {gen:3}")
def v14():
    exp = EXP("GEN")
    with P.coverage_trace(exp) as cov:
        cov.run("G", lambda: list(fx_v5f.gen()))
    expect_pass(score(exp, cov.record()), {"G": {"fx_v5f:gen": 3}})

@case("X119", "event path", "generator: dropped unstarted; close() unstarted; throw() into unstarted; primed outside, closed at a yield inside -> NOT_EXERCISED")
def x119():
    exp = EXP("GEN2")
    with P.coverage_trace(exp) as cov:
        primed = fx_v5f.gen2()
        next(primed)                                   # primed outside every section
        def body():
            g1 = fx_v5f.gen2(); del g1
            g2 = fx_v5f.gen2(); g2.close()
            g3 = fx_v5f.gen2()
            try:
                g3.throw(KeyError("x"))
            except KeyError:
                pass
            primed.close()
        cov.run("G", body)
    expect_refuse(score(exp, cov.record()), "NOT_EXERCISED")

@case("X137c", "event path", "inside G: f, then set_events(tool, 0), then t raises and is caught -> NOT_EXERCISED for t, MONITOR_LOST")
def x137c():
    exp = EXP("FT")
    with P.coverage_trace(exp) as cov:
        def body():
            fx_v5f.f()
            sys.monitoring.set_events(P._v5_state()["tool"], 0)
            try:
                fx_v5f.t()
            except ValueError:
                pass
        cov.run("G", body)
    rec = cov.record()
    out = score(exp, rec)
    expect_refuse(out, "NOT_EXERCISED")
    expect("fx_v5f:t" in out[2] and "MONITOR_LOST" in out[2], f"message: {out[2][:200]}")
    notes = rec["sections"]["G"][0]["notes"]
    expect(any(n.startswith("[V5:MONITOR_LOST]") for n in notes), f"notes {notes}")
    expect(rec["sections"]["G"][0]["calls"] == {"fx_v5f:f": 1}, f"calls {rec['sections']}")

@case("V67", "event path", "t raises 100 times outside every section -> pending == 0 before exit; leftovers clean")
def v67():
    exp = EXP("T")
    with P.coverage_trace(exp) as cov:
        for _ in range(100):
            try:
                fx_v5f.t()
            except ValueError:
                pass
        st = P._v5_state()
    expect(len(st["mints"]) == 1 and st["mints"][0]["pending"] == 0, f"mints {st['mints']}")

@case("X74d", "event path", "run(G, genfn): LAZY_RESULT note contains '...does not count (its body had not started)' -> NOT_EXERCISED")
def x74d():
    exp = EXP("LAZY")
    with P.coverage_trace(exp) as cov:
        cov.run("G", fx_v5f.genfn)
    rec = cov.record()
    expect_refuse(score(exp, rec), "NOT_EXERCISED")
    notes = rec["sections"]["G"][0]["notes"]
    expect(len(notes) == 1 and "whatever of its body runs after the section closed does not count "
           "(its body had not started)" in notes[0], f"notes {notes}")

def _genuine_trace():
    """The scoring-only cases read the prebuilt /3 trace traces_v5f/F.json (harness rule)."""
    return EXP("F"), load_trace("F")

@case("X93d", "scoring", "trace loaded with object_pairs_hook=OrderedDict -> NO_TRACE, third wording, exactly \"'coverage_trace' is a OrderedDict, not an exact dict (e.g. loaded with object_pairs_hook)\"")
def x93d():
    exp, rec = _genuine_trace()
    res = json.loads(json.dumps({"m": 1.0, "coverage_trace": rec}),
                     object_pairs_hook=collections.OrderedDict)
    try:                                          # GAP-26: X93d is judged by score()
        exp.score(res)
        raise AssertionError("no refusal")
    except GateSpecError as e:                    # GAP-15: the byte-exact text, no backticks
        expect(str(e).startswith("[V5:NO_TRACE]") and
               "'coverage_trace' is a OrderedDict, not an exact dict (e.g. loaded with "
               "object_pairs_hook)" in str(e), str(e))

@case("X96d", "scoring", "gates_sha256: 5 -> BAD_TRACE; tracer as a str subclass whose __eq__ raises -> WRONG_TRACER")
def x96d():
    exp, rec = _genuine_trace()
    r1 = dict(rec); r1["gates_sha256"] = 5
    expect_refuse(gate_outcome(exp, r1, "G"), "BAD_TRACE")
    class S(str):
        def __eq__(self, other): raise RuntimeError("the raiser ran")
        __hash__ = str.__hash__
    r2 = dict(rec); r2["tracer"] = S(rec["tracer"])
    expect_refuse(gate_outcome(exp, r2, "G"), "WRONG_TRACER")

@case("X103c", "scoring", "end = S('returned') with class S(str) -> BAD_TRACE")
def x103c():
    exp, rec = _genuine_trace()
    class S(str): pass
    r = json.loads(json.dumps(rec))
    r["sections"]["G"][0]["end"] = S("returned")
    expect_refuse(gate_outcome(exp, r, "G"), "BAD_TRACE")

@case("X112b", "scoring", "genuine recorded UNDECLARED_SECTION and one calls count set to 0 -> BAD_COUNT")
def x112b():
    exp = EXP("F")
    rec = load_trace("X112B")                     # prebuilt: G calls f, then a swallowed UNDECLARED_SECTION
    expect(rec["problems"] and rec["problems"][0].startswith("[V5:UNDECLARED_SECTION]"), "genuine problem")
    rec["sections"]["G"][0]["calls"]["fx_v5f:f"] = 0
    expect_refuse(gate_outcome(exp, rec, "G"), "BAD_COUNT")

@case("X117b", "scoring", "a 400-digit int metric -> check_metrics REPORTED ('int too large for a float'); score GateSpecError, not OverflowError")
def x117b():
    exp, rec = _genuine_trace()
    big = 10 ** 400
    cm = exp.check_metrics({"m": big, "coverage_trace": rec})
    expect(cm["G"]["usable"] is False and cm["G"]["note"] == "int too large for a float", f"{cm['G']}")
    try:
        exp.score({"m": big, "coverage_trace": rec})
        raise AssertionError("score did not refuse")
    except GateSpecError:
        pass

@case("X117c", "scoring", "smoke is an object whose __bool__ raises -> REPORTED; __bool__ never called")
def x117c():
    exp, rec = _genuine_trace()
    class B:
        def __bool__(self): raise RuntimeError("__bool__ ran")
    cm = exp.check_metrics({"m": 1.0, "smoke": B(), "coverage_trace": rec})
    expect(cm["G"]["usable"] is True, f"{cm}")
    for bad in (None, [], "s", 5):
        exp.check_metrics(bad)

@case("X95b", "scoring", "a committed v5e /2 trace -> WRONG_TRACER")
def x95b():
    exp, rec = _genuine_trace()
    r = dict(rec); r["tracer"] = "styxx.protocol.coverage_trace/2"
    expect_refuse(gate_outcome(exp, r, "G"), "WRONG_TRACER")

@case("X122", "scoring", "a declaring gate whose bar fails (m=0.0) and a harness that never calls one target -> NOT_EXERCISED (never FAIL)")
def x122():
    exp = EXP("X122")
    expect_refuse(score(exp, load_trace("X122"), m=0.0), "NOT_EXERCISED")   # prebuilt: f called, g not

@case("X109", "scoring", "trace from another gates block -> STALE_TRACE")
def x109():
    _, rec = _genuine_trace()
    exp2 = EXP("F_OTHER")
    rec["targets"] = {"fx_v5f:f": rec["targets"]["fx_v5f:f"], "fx_v5f:g": "x:1"}
    expect_refuse(gate_outcome(exp2, rec, "G"), "STALE_TRACE")

@case("X90/X91", "lifecycle", "record() inside the trace / before enter -> TRACE_ACTIVE with per-case texts")
def x90():
    exp = EXP("F")
    cov = P.coverage_trace(exp)
    e = raises_code(cov.record, "TRACE_ACTIVE")
    expect("never entered" in str(e), str(e))
    with cov:
        e = raises_code(cov.record, "TRACE_ACTIVE")
        expect("one call of __exit__() completes it" in str(e), str(e))

@case("V52", "lifecycle", "(1) explicit __exit__ plus a second in finally -> PASS {f:1}; (2) __exit__ after __enter__ raised UNRESOLVED -> TRACE_INCOMPLETE, clean")
def v52():
    b0 = snap()                                   # the mid-case leftover check is relative (revision 10 rule)
    exp = EXP("F")
    cov = P.coverage_trace(exp)
    try:
        cov.__enter__()
        cov.run("G", fx_v5f.f)
        cov.__exit__(None, None, None)
    finally:
        cov.__exit__(None, None, None)
    expect_pass(score(exp, cov.record()), {"G": {"fx_v5f:f": 1}})
    cov2 = P.coverage_trace(EXP("X33"))
    try:
        raises_code(cov2.__enter__, "UNRESOLVED")
    finally:
        cov2.__exit__(None, None, None)
    raises_code(cov2.record, "TRACE_INCOMPLETE")
    mid = leftover_diff(b0, snap())
    expect(not mid, f"leftovers after the refused enter and its exit: {mid}")
    exp3 = EXP("F")
    with P.coverage_trace(exp3) as cov3:
        cov3.run("G", fx_v5f.f)
    expect_pass(score(exp3, cov3.record()), {"G": {"fx_v5f:f": 1}})

@case("X32", "lifecycle", "tracer entered twice, second entry swallowed -> REENTRY raised and at score")
def x32():
    exp = EXP("F")
    with P.coverage_trace(exp) as cov:
        try:
            cov.__enter__()
        except GateSpecError as e:
            expect(code_of(e) == "REENTRY", str(e))
        cov.run("G", fx_v5f.f)
    expect_refuse(score(exp, cov.record()), "REENTRY")

@case("V28b", "attribution", "coroutine section B driven by send() on a worker, resumed inside A on main -> A calls {f:1} ambiguous {g:1}; B calls {g:1} ambiguous {g:1}; B returned; no notes")
def v28b():
    exp = EXP("AB")
    class Once:
        def __await__(self):
            yield
    async def bfn():
        fx_v5f.g()
        await Once()
        fx_v5f.g()
    with P.coverage_trace(exp) as cov:
        co = cov.run_async("B", bfn)
        th = threading.Thread(target=co.send, args=(None,))
        th.start(); th.join()
        def body():
            try:
                co.send(None)
            except StopIteration:
                pass
            fx_v5f.f()
        cov.run("A", body)
    rec = cov.record()
    expect(rec["sections"]["A"] == [{"calls": {"fx_v5f:f": 1}, "ambiguous": {"fx_v5f:g": 1},
                                     "end": "returned", "notes": []}], f"A {rec['sections']['A']}")
    expect(rec["sections"]["B"] == [{"calls": {"fx_v5f:g": 1}, "ambiguous": {"fx_v5f:g": 1},
                                     "end": "returned", "notes": []}], f"B {rec['sections']['B']}")
    expect_pass(score(exp, rec), {"A": {"fx_v5f:f": 1}, "B": {"fx_v5f:g": 1}})

@case("X143c", "event path", "cov.run('A', f) with a fault right after _detach's _unwind_off call (here: at _detach's return) -> Injected; global_events 0; PASS {f:1}, end returned, no MONITOR_LOST")
def x143c():
    exp = EXP("F")
    mon = sys.monitoring
    TID = 5
    class Injected(Exception):
        pass
    target = P._v5_faultpoints()["_detach"]
    fired = []
    me = threading.get_ident()
    def on_ret(code, off, val):
        if code is target and threading.get_ident() == me and not fired:
            fired.append(P._v5_state())
            raise Injected()
    mon.use_tool_id(TID, "smoke-injector")
    mon.register_callback(TID, mon.events.PY_RETURN, on_ret)
    try:
        with P.coverage_trace(exp) as cov:
            mon.set_local_events(TID, target, mon.events.PY_RETURN)
            try:
                cov.run("G", fx_v5f.f)
                raise AssertionError("no Injected")
            except Injected:
                pass
            mon.set_local_events(TID, target, 0)
            st = P._v5_state()
            expect(st["global_events"] == 0 and st["anchors"] == 0, f"after fault {st}")
    finally:
        mon.set_local_events(TID, target, 0)
        mon.register_callback(TID, mon.events.PY_RETURN, None)
        mon.free_tool_id(TID)
    rec = cov.record()
    expect(rec["sections"]["G"] == [{"calls": {"fx_v5f:f": 1}, "ambiguous": {}, "end": "returned",
                                     "notes": []}], f"record {rec['sections']}")

@case("X137-free", "event path", "inside G: f, free_tool_id(tool), g -> PASS {f:1,g:1} + MONITOR_LOST; after exit tool_ours, global_events 0, no callback for 1000 raises; 2nd trace PASS {f:1}")
def x137_free():
    exp = EXP("FG")
    with P.coverage_trace(exp) as cov:
        def body():
            fx_v5f.f()
            sys.monitoring.free_tool_id(P._v5_state()["tool"])
            fx_v5f.g()
        cov.run("G", body)
    rec = cov.record()
    expect_pass(score(exp, rec), {"G": {"fx_v5f:f": 1, "fx_v5f:g": 1}})
    notes = rec["sections"]["G"][0]["notes"]
    expect(any(n.startswith("[V5:MONITOR_LOST]") for n in notes), f"notes {notes}")
    st = P._v5_state()
    expect(st["tool_ours"] is True and st["global_events"] == 0, f"state {st}")
    for _ in range(1000):                          # the event is clear, so no styxx callback runs
        try:
            raise KeyError("x")
        except KeyError:
            pass
    exp2 = EXP("F")
    with P.coverage_trace(exp2) as cov2:
        cov2.run("G", fx_v5f.f)
    expect_pass(score(exp2, cov2.record()), {"G": {"fx_v5f:f": 1}})


# -- revision 9 cases (the exam author's gaps, "Revision 9: spec gaps from the exam author") --------
_PCODE = __import__("re").compile(r"\[V5:([A-Z_]+)\]")

def _problem_codes(rec):
    return [_PCODE.match(p).group(1) for p in rec["problems"]]

def _x59e(variant):
    exp = EXP("F")
    f = fx_v5f.f
    orig = ORIG[("fx_v5f", "f")][1]
    handle = __import__("asyncio").events.Handle
    run0 = handle.__dict__["_run"]
    keep = []
    try:
        with P.coverage_trace(exp) as cov:
            def body():
                f()
                if variant:
                    try:
                        cov.run("B", f)                    # B is undeclared: swallowed
                    except GateSpecError:
                        pass
                clone = types.FunctionType(f.__code__, {})
                clone(0)                                   # CLONE_CALLED
                keep.append(clone)                         # alive through exit: CLONE_ALIVE (a)
                f.__code__ = fx_v5f.other.__code__         # CODE_SWAPPED, left in place
                handle._run = fx_x59e.run59                # CUT_MOVED at exit
            cov.run("G", body)
        handle._run = run0
        rec = cov.record()
    finally:
        handle._run = run0
        f.__code__ = orig
        keep.clear()
        gc.collect()
    want = ["CLONE_CALLED", "CODE_SWAPPED", "CLONE_ALIVE", "CUT_MOVED"]
    if variant:
        want = ["UNDECLARED_SECTION"] + want
    expect(_problem_codes(rec) == want, f"problem codes {_problem_codes(rec)}, want {want}")
    expect_refuse(score(exp, rec), want[0])

@case("X59e", "exit order", "clone called, code swapped and left, clone alive through exit, Handle._run rebound -> problems exactly [CLONE_CALLED, CODE_SWAPPED, CLONE_ALIVE, CUT_MOVED]; score refuses CLONE_CALLED")
def x59e():
    _x59e(False)

@case("X59e-v", "exit order", "X59e plus a swallowed cov.run('B', f) with B undeclared, before the clone -> [UNDECLARED_SECTION, CLONE_CALLED, CODE_SWAPPED, CLONE_ALIVE, CUT_MOVED]; score refuses UNDECLARED_SECTION")
def x59e_v():
    _x59e(True)


# Fresh-subprocess cases: the subprocess re-runs this file with "--sub <mode>" and prints one JSON
# line; the case judges it here. The subprocess builds its own fixtures and preregs.
def run_sub(mode):
    r = subprocess.run([sys.executable, RUNNER] + _impl_args() + ["--sub", mode],
                       capture_output=True, text=True, timeout=120)
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("{")]
    expect(r.returncode == 0 and lines, f"subprocess {mode}: rc {r.returncode}\n{r.stderr[-2000:]}")
    return json.loads(lines[-1])

SUB = {}
def sub(mode):
    def deco(fn):
        SUB[mode] = fn
        return fn
    return deco

def _outcome_json(out):
    return list(out[:2]) if out[0] == "REFUSE" else ["PASS", out[1]]

@sub("state0")
def _sub_state0():
    s = P._v5_state()
    s.pop("pid")
    return {"state": s}

@case("M10-S0", "introspection", "revision 9 (GAP-05); fresh subprocess: _v5_state() before the first coverage_trace() -> mints [], anchors 0, guard free, cut 0, cut_current True, tool None, tool_ours False, global_events 0")
def m10_s0():
    got = run_sub("state0")["state"]
    want = {"mints": [], "anchors": 0, "guard": "free", "cut": 0, "cut_current": True,
            "tool": None, "tool_ours": False, "global_events": 0}
    expect(got == want, f"state {got}")

def _sub_v69b(lying):
    sm = sys.monitoring
    real = sm.get_local_events
    n = [0]
    def gle(tool, code):
        n[0] += 1
        return 0 if lying else real(tool, code)
    exp = EXP("F")
    P.coverage_trace(exp)                          # the first coverage_trace() binds _MON
    sm.get_local_events = gle
    try:
        with P.coverage_trace(exp) as cov:
            cov.run("G", fx_v5f.f)
            P._v5_state()                          # the other reader of _MON[0][6]
        rec = cov.record()
    finally:
        sm.get_local_events = real
    notes = rec["sections"]["G"][0]["notes"]
    return {"score": _outcome_json(score(exp, rec)), "calls": n[0],
            "lost": any(x.startswith("[V5:MONITOR_LOST]") for x in notes)}

@sub("V69b")
def _sub_v69b_pass():
    return _sub_v69b(False)

@sub("V69c")
def _sub_v69b_lie():
    return _sub_v69b(True)

@case("V69b", "binding", "revision 9 (GAP-03); fresh subprocess: after the first coverage_trace(), a counting pass-through on sys.monitoring.get_local_events; a trace calling f -> PASS {f:1}, no MONITOR_LOST, counter 0")
def v69b():
    r = run_sub("V69b")
    expect(r == {"score": ["PASS", {"G": {"fx_v5f:f": 1}}], "calls": 0, "lost": False}, f"{r}")

@case("V69b-v", "binding", "V69b's variant: the replacement returns 0 instead of calling through -> PASS {f:1}, no MONITOR_LOST, counter 0")
def v69c():
    r = run_sub("V69c")
    expect(r == {"score": ["PASS", {"G": {"fx_v5f:f": 1}}], "calls": 0, "lost": False}, f"{r}")

@sub("X156f")
def _sub_x156f():
    sm = sys.monitoring
    real = sm.get_local_events
    n = [0]
    def gle(tool, code):
        n[0] += 1
        return real(tool, code)
    exp = EXP("F")
    sm.get_local_events = gle
    try:
        try:
            with P.coverage_trace(exp) as cov:
                cov.run("G", fx_v5f.f)
            out = {"refused": None, "score": _outcome_json(score(exp, cov.record()))}
        except GateSpecError as e:
            out = {"refused": code_of(e)}
        # scoring works: a trace-less result is judged, and check_metrics runs
        out["scoring"] = _outcome_json(score(exp, None))[:2]
        out["check_metrics"] = sorted(exp.check_metrics({"m": 1.0}))
    finally:
        sm.get_local_events = real
    out["calls"] = n[0]
    out["tool"] = P._v5_state()["tool"]            # a refusal binds and takes nothing
    return out

@case("X156f", "binding", "revision 9 (GAP-03); fresh subprocess: before the first coverage_trace(), sys.monitoring.get_local_events replaced by a pure-Python pass-through -> coverage_trace() raises UNSUPPORTED_VERSION; scoring works")
def x156f():
    r = run_sub("X156f")
    expect(r.get("refused") == "UNSUPPORTED_VERSION", f"{r}")
    expect(r["scoring"] == ["REFUSE", "NO_TRACE"] and r["check_metrics"], f"scoring {r}")
    expect(r["calls"] == 0 and r["tool"] is None, f"{r}")

def _x65d_shape(cov):
    """X65d's shape: inside the section, a loop whose class overrides _run_once and runs its ready
    handles' callbacks directly (no Handle._run or BaseEventLoop._run_once frame) runs a coroutine
    that calls f."""
    import asyncio
    class DirectLoop(asyncio.SelectorEventLoop):
        def _run_once(self):
            while self._ready:
                h = self._ready.popleft()
                if not h._cancelled:
                    h._context.run(h._callback, *h._args)
    async def co():
        return fx_v5f.f()
    def body():
        loop = DirectLoop()
        try:
            return loop.run_until_complete(co())
        finally:
            loop.close()
    cov.run("G", body)

def _sub_x156g(patch):
    import asyncio
    real = asyncio.events._get_running_loop
    exp = EXP("F")
    if patch:
        def grl():
            return None
        asyncio.events._get_running_loop = grl
    try:
        try:
            with P.coverage_trace(exp) as cov:
                _x65d_shape(cov)
            rec = cov.record()
            out = {"refused": None, "score": _outcome_json(score(exp, rec)),
                   "uncredited": rec.get("uncredited")}
        except GateSpecError as e:
            out = {"refused": code_of(e)}
    finally:
        asyncio.events._get_running_loop = real
    return out

@sub("X156g")
def _sub_x156g_patched():
    return _sub_x156g(True)

@sub("X156g_ctl")
def _sub_x156g_ctl():
    return _sub_x156g(False)

@case("X156g", "binding", "revision 9 (GAP-02); fresh subprocess: after import and before the first coverage_trace(), asyncio.events._get_running_loop replaced by a Python function returning None; X65d's shape -> coverage_trace() raises UNSUPPORTED_VERSION")
def x156g():
    r = run_sub("X156g")
    expect(r == {"refused": "UNSUPPORTED_VERSION"}, f"{r}")

@case("X156g-ctl", "binding", "X156g unpatched: the same program -> NOT_EXERCISED with dispatched {f:1}")
def x156g_ctl():
    r = run_sub("X156g_ctl")
    expect(r.get("refused") is None and r["score"][:2] == ["REFUSE", "NOT_EXERCISED"], f"{r}")
    expect(r["uncredited"]["dispatched"] == {"fx_v5f:f": 1}, f"uncredited {r['uncredited']}")


# -- revision 10 cases ("Revision 10: verifier findings on revision 9") ------------------------------
@case("X78h", "attribution", "rev. 10 (R9-1): cov.run(Sec(), f) on a tracer never entered, and on another after its exit -> TRACE_INACTIVE both; f never runs; counters 0")
def x78h():
    exp = EXP("F")
    Sec, calls = counting_section_class()
    ran = []
    def f():
        ran.append(1)
    cov1 = P.coverage_trace(exp)                     # never entered
    raises_code(lambda: cov1.run(Sec(), f), "TRACE_INACTIVE")
    with P.coverage_trace(exp) as cov2:
        cov2.run("G", fx_v5f.f)
    raises_code(lambda: cov2.run(Sec(), f), "TRACE_INACTIVE")
    expect(not ran, "f ran")
    expect(all(v == 0 for v in calls.values()), f"section rendered: {calls}")

def _counting_meta():
    n = {"meta": 0}
    class Meta(type):
        def __getattribute__(cls, name):
            if name in ("__qualname__", "__name__"):
                n["meta"] += 1
            return type.__getattribute__(cls, name)
    return Meta, n

@case("X93e", "scoring", "rev. 10 (R9-1): NO_TRACE's first and third texts name a counting-metaclass type exactly, counter 0")
def x93e():
    exp, rec = _genuine_trace()
    Meta, n = _counting_meta()
    R = Meta("R", (), {})
    MD = Meta("MD", (dict,), {})
    n["meta"] = 0
    cm = exp.check_metrics(R())                      # GAP-26: a non-dict result is judged by check_metrics
    note = cm["G:exercises"]["note"]
    expect(note.startswith("[V5:NO_TRACE]") and "the result is a R, not a dict" in note, note)
    out = score(exp, MD(rec))
    expect(out[0] == "REFUSE" and out[1] == "NO_TRACE" and
           "'coverage_trace' is a MD, not an exact dict (e.g. loaded with object_pairs_hook)" in out[2], f"{out}")
    expect(n["meta"] == 0, f"metaclass reads: {n}")

@case("X24f", "identity", "rev. 10 (R9-1, R9-9): lru_cache(len) -> NOT_A_FUNCTION 'the wrapper calls no single Python function; ... (a builtin_function_or_method)'; a Stamp __wrapped__ -> '(a Stamp)', metaclass counter 0")
def x24f():
    cov = P.coverage_trace(EXP("X24F_LEN"))
    e = raises_code(cov.__enter__, "NOT_A_FUNCTION")
    cov.__exit__(None, None, None)
    expect("the wrapper calls no single Python function; its __wrapped__ names a different object "
           "(a builtin_function_or_method)" in str(e), str(e))
    fx_x24f.COUNT["n"] = 0
    cov = P.coverage_trace(EXP("X24F_STAMP"))
    e = raises_code(cov.__enter__, "NOT_A_FUNCTION")
    cov.__exit__(None, None, None)
    expect("its __wrapped__ names a different object (a Stamp)" in str(e), str(e))
    expect(fx_x24f.COUNT["n"] == 0, f"metaclass reads: {fx_x24f.COUNT}")

@case("X84", "attribution", "rev. 10 (R9-2), over-blocking #23: T opens G with L1 running; U opens G with None running; T opens G again with L1 running -> NESTED_SECTION; T's problems exactly that")
def x84():
    import asyncio
    ev = asyncio.events
    L1 = asyncio.new_event_loop()
    expT, expU = EXP("F"), EXP("F")
    got = []
    try:
        with P.coverage_trace(expT) as T, P.coverage_trace(expU) as U:
            def inner():                             # running loop L1 again, under U's opening
                prev = ev._get_running_loop()
                ev._set_running_loop(L1)
                try:
                    T.run("G", fx_v5f.f)
                    got.append("opened")
                except GateSpecError as e:
                    got.append(code_of(e))
                finally:
                    ev._set_running_loop(prev)
            def mid():                               # running loop None, under T's first opening
                prev = ev._get_running_loop()
                ev._set_running_loop(None)
                try:
                    U.run("G", inner)
                finally:
                    ev._set_running_loop(prev)
            ev._set_running_loop(L1)
            try:
                T.run("G", mid)
            finally:
                ev._set_running_loop(None)
        rec = T.record()
    finally:
        L1.close()
    expect(got == ["NESTED_SECTION"], f"second open of T: {got}")
    expect(_problem_codes(rec) == ["NESTED_SECTION"], f"T problems {_problem_codes(rec)}")

@case("X10c", "identity", "rev. 10 (GAP-W011, W018): import raising ValueError, PEP 562 __getattr__ raising KeyError -> UNRESOLVED, __cause__ the ValueError / the KeyError")
def x10c():
    for key, exc in (("X10C_IMP", ValueError), ("X10C_PEP", KeyError)):
        cov = P.coverage_trace(EXP(key))
        e = raises_code(cov.__enter__, "UNRESOLVED")
        cov.__exit__(None, None, None)
        expect(type(e.__cause__) is exc, f"{key}: __cause__ {type(e.__cause__).__name__}")
    sys.modules.pop("fx_badimport", None)

@case("X14d", "identity", "rev. 10 (GAP-W022): Sub.fit inherited from Base with Base.__module__ = 5 -> INHERITED 'declare the defining class ?:Base'")
def x14d():
    cov = P.coverage_trace(EXP("X14D"))
    e = raises_code(cov.__enter__, "INHERITED")
    cov.__exit__(None, None, None)
    expect("declare the defining class ?:Base" in str(e), str(e))

def _counting_dict_class():
    n = {"calls": 0}
    def counted(name):
        base = getattr(dict, name)
        def m(self, *a, **k):
            n["calls"] += 1
            return base(self, *a, **k)
        m.__name__ = name
        return m
    ns = {k: counted(k) for k in ("__getitem__", "__contains__", "get", "keys", "__iter__")}
    def __missing__(self, key):
        n["calls"] += 1
        return 0.25
    def __bool__(self):
        n["calls"] += 1
        return True
    ns["__missing__"] = __missing__
    ns["__bool__"] = __bool__
    return type("C", (dict,), ns), n

@case("X117e", "scoring", "rev. 10 (R9-5): check_metrics on counting dict subclasses, path a.b present (0.5) / b absent -> present+usable / not present; counter 0")
def x117e():
    exp = EXP("X117E")
    C, n = _counting_dict_class()
    r1 = C(a=C(b=0.5))
    r2 = C(a=C())
    n["calls"] = 0
    m1 = exp.check_metrics(r1)["G"]
    m2 = exp.check_metrics(r2)["G"]
    expect(m1["present"] is True and m1["usable"] is True, f"first {m1}")
    expect(m2["present"] is False, f"second {m2}")
    expect(n["calls"] == 0, f"user dict methods called: {n}")

@case("X117f", "scoring", "rev. 10 (R9-5): check_metrics on {m:1.0} -> NO_TRACE note 'the result has no 'coverage_trace' key'; with smoke True -> exactly 'smoke run'")
def x117f():
    exp = EXP("F")
    n1 = exp.check_metrics({"m": 1.0})["G:exercises"]["note"]
    expect(n1.startswith("[V5:NO_TRACE]") and "the result has no 'coverage_trace' key" in n1, n1)
    n2 = exp.check_metrics({"m": 1.0, "smoke": True})["G:exercises"]["note"]
    expect(n2 == "smoke run", n2)

@case("V73", "records", "rev. 10 (GAP-W183): worker's G calls f, waits; main clears f's local events and exits; worker returns an unstarted generator -> notes codes [OPEN_AT_EXIT, LAZY_RESULT, MONITOR_LOST], end open")
def v73():
    exp = EXP("F")
    entered, go = threading.Event(), threading.Event()
    def body():
        fx_v5f.f()
        entered.set()
        go.wait(30)
        return fx_v5f.genfn()
    cov = P.coverage_trace(exp)
    cov.__enter__()
    t = threading.Thread(target=lambda: cov.run("G", body))
    t.start()
    try:
        expect(entered.wait(30), "worker never entered")
        tool = P._v5_state()["tool"]
        sys.monitoring.set_local_events(tool, fx_v5f.f.__code__, 0)
        cov.__exit__(None, None, None)
    finally:
        go.set()
        t.join(30)
    rec = cov.record()
    ops = rec["sections"]["G"]
    expect(len(ops) == 1 and ops[0]["end"] == "open", f"openings {ops}")
    codes = [_PCODE.match(x).group(1) for x in ops[0]["notes"]]
    expect(codes == ["OPEN_AT_EXIT", "LAZY_RESULT", "MONITOR_LOST"], f"notes {codes}")

@sub("X156h")
def _sub_x156h():
    import asyncio
    exp = EXP("F")
    with P.coverage_trace(exp) as cov:
        cov.run("G", fx_v5f.f)
    first = _outcome_json(score(exp, cov.record()))
    real = asyncio.events._get_running_loop
    def grl():
        return None
    asyncio.events._get_running_loop = grl
    try:
        try:
            with P.coverage_trace(exp) as cov2:
                cov2.run("G", fx_v5f.f)
            second = {"refused": None, "score": _outcome_json(score(exp, cov2.record()))}
        except GateSpecError as e:
            second = {"refused": code_of(e)}
    finally:
        asyncio.events._get_running_loop = real
    return {"first": first, "second": second}

@case("X156h", "binding", "rev. 10 (R9-3); fresh subprocess: a clean trace PASS {f:1}; then _get_running_loop replaced -> the next coverage_trace() raises UNSUPPORTED_VERSION")
def x156h():
    r = run_sub("X156h")
    expect(r == {"first": ["PASS", {"G": {"fx_v5f:f": 1}}], "second": {"refused": "UNSUPPORTED_VERSION"}}, f"{r}")

@sub("X156i")
def _sub_x156i():
    import asyncio
    exp = EXP("F")
    real = asyncio.events._get_running_loop
    def grl():
        return None
    asyncio.events._get_running_loop = grl
    try:
        try:
            P.coverage_trace(exp)
            first = None
        except GateSpecError as e:
            first = code_of(e)
    finally:
        asyncio.events._get_running_loop = real
    st = P._v5_state()
    sm = sys.monitoring
    real_se = sm.set_events
    def se(*a):
        return real_se(*a)
    sm.set_events = se
    try:
        try:
            with P.coverage_trace(exp) as cov:
                cov.run("G", fx_v5f.f)
            second = {"refused": None, "score": _outcome_json(score(exp, cov.record()))}
        except GateSpecError as e:
            second = {"refused": code_of(e)}
    finally:
        sm.set_events = real_se
    return {"first": first, "state": {k: st[k] for k in ("tool", "tool_ours", "cut")}, "second": second}

@case("X156i", "binding", "rev. 10 (R9-4); fresh subprocess: a step-6 refusal at the first coverage_trace() binds nothing (tool None, tool_ours False, cut 0); a set_events wrapper installed afterwards is refused")
def x156i():
    r = run_sub("X156i")
    expect(r == {"first": "UNSUPPORTED_VERSION", "state": {"tool": None, "tool_ours": False, "cut": 0},
                 "second": {"refused": "UNSUPPORTED_VERSION"}}, f"{r}")

@sub("V72")
def _sub_v72():
    exp = EXP("F")
    cov = P.coverage_trace(exp)
    cov.__enter__()
    cov.run("G", fx_v5f.f)
    me = threading.get_ident()
    arm = {"on": True, "seen": None}
    def hook(event, args):
        if arm["on"] and event == "sys.monitoring.register_callback" and threading.get_ident() == me:
            arm["on"] = False
            arm["seen"] = P._v5_state()["guard"]
            raise RuntimeError("V72 hook")
    sys.addaudithook(hook)
    try:
        cov.__exit__(None, None, None)
        raised = None
    except RuntimeError as e:
        raised = str(e)
    after = P._v5_state()["guard"]
    exp2 = EXP("F")
    with P.coverage_trace(exp2) as cov2:
        cov2.run("G", fx_v5f.f)
    return {"seen": arm["seen"], "raised": raised, "after": after,
            "second": _outcome_json(score(exp2, cov2.record())), "final": P._v5_state()["guard"]}

@case("V72", "introspection", "rev. 10 (R9-8); fresh subprocess: an audit hook in the exit transaction's registration reads guard 'held' and raises -> RuntimeError from __exit__; guard 'dead'; a second tracer PASS {f:1}; guard 'free'")
def v72():
    r = run_sub("V72")
    expect(r == {"seen": "held", "raised": "V72 hook", "after": "dead",
                 "second": ["PASS", {"G": {"fx_v5f:f": 1}}], "final": "free"}, f"{r}")


# =================================================================================================
# The exam's case metadata: each case's table in the design and its placement (harness rules)
# =================================================================================================
X37_ROW = "X37 (3.10/3.11 only): coverage_trace() refuses UNSUPPORTED_VERSION; scoring works"

@case("X37", "version", X37_ROW)
def x37():
    raises_code(lambda: P.coverage_trace(EXP("F")), "UNSUPPORTED_VERSION")
    out = score(EXP("F"), load_trace("F"))
    expect(out[0] == "PASS" and out[1] == {"G": {"fx_v5f:f": 1}}, f"scoring {out[:2]}")

TABLE = {}
for _cid in ("X26b", "X24b", "X13b", "X14c", "X17b", "X34", "X78f", "X119", "X137c", "X74d", "X93d",
             "X96d", "X103c", "X112b", "X117b", "X117c", "X95b", "X122", "X143c", "X137-free", "X59e",
             "X59e-v", "X156f", "X156g", "X156g-ctl", "X78h", "X93e", "X24f", "X84", "X10c", "X14d",
             "X117e", "X117f", "X156h", "X156i", "X37"):
    TABLE[_cid] = "new violation cases"
for _cid in ("V54", "V55", "V67", "V52", "V28b", "V69b", "V69b-v", "V72", "V73"):
    TABLE[_cid] = "new valid cases"
for _cid in ("V01", "X40", "X55", "X59", "V07", "X33", "X73", "V18", "X76", "X60", "V14", "X109",
             "X90", "X32"):
    TABLE[_cid] = "v5e cases kept (every other v5e case keeps its id and outcome)"
TABLE["X90/X91"] = "v5e cases whose outcome changes"       # X91's row: same code, the text per case (M8)
TABLE["M10-S0"] = "M10 property (not a table row): _v5_state() before any tracer"

# Placements, from the harness rules' lists (only the cases this runner covers are listed).
MAIN = {"X137c", "X143c", "X59e", "X59e-v", "V67", "V73"}
CHILD = {"X137-free"}                                  # the whole case in a fresh subprocess
SPAWNS = {"M10-S0", "V69b", "V69b-v", "X156f", "X156g", "X156g-ctl", "X156h", "X156i", "V72"}  # the case body spawns it
SCORING = {"X93d", "X93e", "X96d", "X103c", "X112b", "X117b", "X117c", "X117e", "X117f", "X95b",
           "X122", "X109", "X37"}                      # read prebuilt traces; run on every interpreter
SELF_TARGETS = [f"{IMPL_MOD}:{q}" for q in ("Experiment._check_coverage", "_resolve_target", "_open",
                                          "_exit", "_run")]
GATE_OF = {"new violation cases": "VIOL", "new valid cases": "VALID",
           "v5e cases kept (every other v5e case keeps its id and outcome)": "V5E",
           "M10 property (not a table row): _v5_state() before any tracer": "M10",
           "v5e cases whose outcome changes": "DELTA"}

def placement(cid):
    if cid in MAIN:
        return "main"
    if cid in CHILD or cid in SPAWNS:
        return "subprocess"
    return "self-trace"

# Tables of "Exam cases required", and what this runner does not cover yet.
TABLES_ALL = ["v5e cases whose outcome changes", "new violation cases", "new valid cases",
              "new documented residuals", "exam-hole kill cases", "hazard sweeps",
              "mutation audit (SM1 witnesses)", "v5e cases kept (every other v5e case keeps its id and outcome)"]
TABLE_ROWS = {"new violation cases": 137, "new valid cases": 45, "new documented residuals": 10,
              "exam-hole kill cases": 30, "v5e cases whose outcome changes": 20}

# =================================================================================================
# Leftover snapshot (Exam harness rules, "Leftover checks after every case"; revision 10, R9-6)
# =================================================================================================
def snap():
    st = dict(P._v5_state())
    st.pop("pid", None)
    tools = {}
    if hasattr(sys, "monitoring"):
        for i in range(6):
            tools[i] = sys.monitoring.get_tool(i)
    return {"state": st,
            "codes": {k: fn.__code__ for k, (fn, code) in ORIG.items()},
            "prof": (sys.getprofile(), sys.gettrace(), threading.getprofile(), threading.gettrace()),
            "tools": tools, "freeze": gc.get_freeze_count()}

def leftover_diff(b, a):
    bad = []
    for k, v in b["state"].items():
        if k in ("cut", "tool"):
            continue
        if k == "tool_ours" and b["state"]["tool"] is None:
            continue
        if a["state"].get(k) != v:
            bad.append((k, v, a["state"].get(k)))
    if a["state"]["cut_current"] is not True:
        bad.append(("cut_current", a["state"]["cut_current"]))
    if a["state"]["guard"] != "free":
        bad.append(("guard", a["state"]["guard"]))
    for k, (fn, code) in ORIG.items():
        if a["codes"][k] is not code:
            bad.append(("fixture __code__", k))
    if any(x is not y for x, y in zip(b["prof"], a["prof"])):
        bad.append(("profile/trace functions changed",))
    ours = {b["state"]["tool"], a["state"]["tool"]}
    for i, nb in b["tools"].items():
        if i in ours:
            continue
        na = a["tools"].get(i)
        if not (na is nb or (type(nb) is str and type(na) is str and na == nb)):
            bad.append(("tool id", i, nb, na))
    if a["freeze"] > b["freeze"]:
        bad.append(("gc freeze count", b["freeze"], a["freeze"]))
    return bad

# =================================================================================================
# Running one case
# =================================================================================================
BY_ID = {cid: (fam, row, fn) for cid, fam, row, fn in CASES}

def _call(fn):
    try:
        fn()
        return True, ""
    except Exception as e:                                    # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"[:1500]

def run_main(cid):
    b = snap()
    ok, detail = _call(BY_ID[cid][2])
    left = leftover_diff(b, snap())
    return ok and not left, detail, left

def run_child(cid):
    r = subprocess.run([sys.executable, RUNNER] + _impl_args() + ["--child-case", cid],
                       capture_output=True, text=True, timeout=300)
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("{")]
    if r.returncode != 0 or not lines:
        return False, f"child rc {r.returncode}: {r.stderr[-1500:]}", []
    d = json.loads(lines[-1])
    return d["ok"], d["detail"], d["leftover"]

def run_in_self(cid, selfcov, section):
    box = {}
    def target():
        try:
            selfcov.run(section, lambda: box.setdefault("r", _call(BY_ID[cid][2])))
        except Exception as e:                                # noqa: BLE001
            box["r"] = (False, f"self-trace section raised {type(e).__name__}: {e}")
    b = snap()
    t = threading.Thread(target=target, name=f"case-{cid}", daemon=True)
    t.start()
    t.join(WATCHDOG_S)
    if t.is_alive():
        return False, f"watchdog: the case thread is still running after {WATCHDOG_S} s", ["watchdog"]
    ok, detail = box.get("r", (False, "no result"))
    left = leftover_diff(b, snap())
    return ok and not left, detail, left

# =================================================================================================
# Prebuilt traces for the scoring-only cases (harness rule "Interpreters")
# =================================================================================================
def make_traces():
    if tuple(sys.version_info[:3]) != (3, 12, 3):
        print("--make-traces runs on CPython 3.12.3 only (the harness rule)", file=sys.stderr)
        return 2
    os.makedirs(TRACES, exist_ok=True)
    out = {}
    exp = EXP("F")
    with P.coverage_trace(exp) as cov:
        cov.run("G", fx_v5f.f)
    out["F"] = cov.record()
    exp = EXP("X122")
    with P.coverage_trace(exp) as cov:
        cov.run("G", fx_v5f.f)
    out["X122"] = cov.record()
    exp = EXP("F")
    with P.coverage_trace(exp) as cov:
        cov.run("G", fx_v5f.f)
        try:
            cov.run("nope", fx_v5f.f)
        except GateSpecError:
            pass
    out["X112B"] = cov.record()
    for k, v in out.items():
        with open(os.path.join(TRACES, k + ".json"), "w") as fh:
            json.dump(v, fh, indent=1, sort_keys=True)
            fh.write("\n")
    print(f"wrote {sorted(out)} to {TRACES} (impl {IMPL_PATH}, sha256 {_sha(IMPL_PATH)[:16]})")
    return 0

# =================================================================================================
# main
# =================================================================================================
def main():
    t0 = time.monotonic()
    only = set(ARGS.only.split(",")) if ARGS.only else None
    ids = [cid for cid, _, _, _ in CASES if not only or cid in only]
    res = {}
    def record(cid, ok, detail, left, secs, note=None):
        res[cid] = {"table": TABLE.get(cid, "?"), "placement": placement(cid), "row": BY_ID[cid][1],
                    "ok": bool(ok), "detail": detail, "leftover": [list(map(str, x)) for x in left],
                    "seconds": round(secs, 3)}
        if note:
            res[cid]["note"] = note
    selfinfo = None
    if not TRACING:
        run_ids = [c for c in ids if c in SCORING]
        skipped = {c: "not run: tracing cases run only on CPython 3.12.3 and 3.13.12" for c in ids if c not in SCORING}
        mode = "scoring-only (not an exam interpreter for tracing)"
        for cid in run_ids:
            t = time.monotonic()
            ok, detail = _call(BY_ID[cid][2])
            record(cid, ok, detail, [], time.monotonic() - t)
    else:
        skipped = {c: "3.10/3.11 only" for c in ids if c == "X37"}
        mode = "full (verified interpreter)"
        ids = [c for c in ids if c != "X37"]
        for cid in [c for c in ids if placement(c) == "main"]:        # before the self-trace
            t = time.monotonic()
            record(cid, *run_main(cid), time.monotonic() - t)
        for cid in [c for c in ids if placement(c) == "subprocess"]:
            t = time.monotonic()
            if cid in CHILD:
                record(cid, *run_child(cid), time.monotonic() - t)
            else:
                ok, detail = _call(BY_ID[cid][2])
                record(cid, ok, detail, [], time.monotonic() - t, note="the case body runs its own fresh subprocess")
        selfc = [c for c in ids if placement(c) == "self-trace"]
        if selfc:
            # V34 as v5f changes it ("v5e cases whose outcome changes"): G0 declares the frozen names
            # Experiment._check_coverage, _resolve_target, _open, _exit and _run; PASS iff each has a
            # union count >= 1. Every self-placed case runs as cov.run(<G0's section>, case).
            gates_used = ["G0"]
            spec = gates({"G0": SELF_TARGETS})
            path = os.path.join(REPO, "PREREG_SELF.md")
            with open(path, "w") as fh:
                fh.write(f"# the exam's self-trace prereg\n\n```gates\n{json.dumps(spec, indent=1)}\n```\n")
            subprocess.run(_git + ["add", "."], cwd=REPO, check=True)
            subprocess.run(_git + ["commit", "-q", "-m", "self-trace prereg"], cwd=REPO, check=True)
            sexp = P.Experiment(path)
            with P.coverage_trace(sexp) as selfcov:
                for cid in selfc:
                    t = time.monotonic()
                    record(cid, *run_in_self(cid, selfcov, "G0"), time.monotonic() - t)
            srec = selfcov.record()
            sout = score(sexp, srec)
            selfinfo_debug = {"message": sout[2] if len(sout) > 2 else None, "sections": srec["sections"],
                              "uncredited": srec["uncredited"]}
            cov0 = sout[1].get("G0", {}) if sout[0] == "PASS" else {}
            selfinfo = {"case": "V34", "gates": gates_used, "targets": SELF_TARGETS, "outcome": list(sout[:2]),
                        "union": cov0, "problems": srec["problems"], "detail": selfinfo_debug,
                        "ok": sout[0] == "PASS" and all(cov0.get(t, 0) >= 1 for t in SELF_TARGETS)}
            res["V34"] = {"table": "v5e cases whose outcome changes", "placement": "self-trace",
                          "row": "V34: the self-trace; G0 declares Experiment._check_coverage, _resolve_target, "
                                 "_open, _exit and _run; PASS: each has a union count >= 1",
                          "ok": selfinfo["ok"], "detail": "" if selfinfo["ok"] else json.dumps(selfinfo_debug)[:1500],
                          "leftover": [], "seconds": 0.0}
    tables = collections.OrderedDict()
    for cid, r in res.items():
        t = tables.setdefault(r["table"], {"run": 0, "passed": 0, "ids": []})
        t["run"] += 1
        t["passed"] += r["ok"]
        t["ids"].append(cid)
    covered_new = {t: sum(1 for c in BY_ID if TABLE.get(c) == t) for t in TABLE_ROWS}
    unmapped = [c for c in BY_ID if c not in TABLE]
    if unmapped:
        raise SystemExit(f"runner bug: cases without a table: {unmapped}")
    n_ok = sum(r["ok"] for r in res.values())
    all_ok = n_ok == len(res) and (selfinfo is None or selfinfo["ok"])
    if TRACING:
        verdict = "PASS" if all_ok else "FAIL"
    else:
        verdict = ("REFUSED_TRACING_UNSUPPORTED_INTERPRETER; scoring-only cases " +
                   ("PASS" if all_ok else "FAIL"))
    receipt = {
        "runner": os.path.basename(RUNNER), "runner_sha256": _sha(RUNNER),
        "impl_path": IMPL_PATH, "impl_module": IMPL_MOD, "impl_sha256": _sha(IMPL_PATH),
        "spec_sha256": _sha(SPEC), "python": sys.version.split()[0], "build": sys.version,
        "python_build": list(platform.python_build()), "python_compiler": platform.python_compiler(),
        "mode": mode, "cases": res, "not_run": skipped, "self_trace": selfinfo,
        "tables": tables,
        "coverage_of_design_tables": {
            t: {"rows_in_design": n, "cases_in_runner": covered_new.get(t, 0)} for t, n in TABLE_ROWS.items()},
        "tables_not_yet_covered": ["new documented residuals (R05b-R22)", "exam-hole kill cases",
                                   "v5e cases whose outcome changes", "hazard sweeps (H1-H10)",
                                   "mutation audit witnesses not already in the case tables",
                                   "the rest of the new violation and valid cases",
                                   "the v5e cases kept (the v5e case tables)"],
        "n_cases_run": len(res), "n_passed": n_ok, "verdict": verdict,
        "seconds": round(time.monotonic() - t0, 2),
    }
    if ARGS.out:
        with open(ARGS.out, "w") as fh:
            json.dump(receipt, fh, indent=1, default=str)
            fh.write("\n")
    for cid, r in res.items():
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {cid:10s} [{r['placement']:10s}] {r['table'][:24]:24s} "
              f"{r['row'][:90]}" + ("" if r["ok"] else f"\n        -> {r['detail'][:300]} leftover={r['leftover']}"))
    if selfinfo:
        print(f"self-trace: {selfinfo['outcome']} problems={selfinfo['problems']}")
    print(f"CPython {receipt['python']} [{mode}]: {n_ok}/{len(res)} cases pass; {len(skipped)} not run")
    print(f"VERDICT: {verdict}", flush=True)
    return 0 if all_ok else 1


def child_case(cid):
    b = snap()
    ok, detail = _call(BY_ID[cid][2])
    left = leftover_diff(b, snap())
    print(json.dumps({"ok": ok and not left, "detail": detail, "leftover": [list(map(str, x)) for x in left]}))
    return 0


if __name__ == "__main__":
    if ARGS.sub:
        print(json.dumps(SUB[ARGS.sub]()))
        sys.exit(0)
    if ARGS.child_case:
        sys.exit(child_case(ARGS.child_case))
    if ARGS.make_traces:
        sys.exit(make_traces())
    rc = main()
    sys.stdout.flush()
    os._exit(rc)
