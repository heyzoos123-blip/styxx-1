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
_ap.add_argument("--pre-import-patch", default=None, help="chain|deque: replaced before the implementation is imported (X156b, X156d)")
_ap.add_argument("--greenlet-path", default=os.environ.get("V5F_GREENLET_PATH"),
                 help="a directory holding the pinned greenlet 3.5.6 (X137f, X158d)")
ARGS = _ap.parse_args()

def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()

if ARGS.pre_import_patch == "chain":           # X156b: before import, itertools.chain is a Python subclass
    import itertools as _it
    class _Chain(_it.chain):
        pass
    _it.chain = _Chain
elif ARGS.pre_import_patch == "deque":         # X156d: before import, collections.deque is a Python subclass
    import collections as _co                  # named deque whose __init__ drops maxlen
    _RealDeque = _co.deque
    class deque(_RealDeque):                   # noqa: N801
        def __init__(self, iterable=(), maxlen=None):
            _RealDeque.__init__(self, iterable)
    _co.deque = deque
if ARGS.greenlet_path:
    sys.path.insert(0, ARGS.greenlet_path)

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
    a = (["--impl-module", ARGS.impl_module] if ARGS.impl_module else ["--impl", IMPL_PATH])
    if ARGS.greenlet_path:
        a += ["--greenlet-path", ARGS.greenlet_path]
    return a

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
    # batch-1 violation fixtures
    "fx_b1.py": '''
        import abc, functools, types
        def f59(): return 59
        def u59(): return -59
        class ABase(abc.ABC):
            def fit(self): return 1
        class ALeaf(ABase):
            pass
        def t135(box):
            box.append(1)
            return 1
        def clonebox(): return 0            # X34b binds its clone here, inside the case
        def h137(): return 137
    ''',
    "fx_x16b_pkg/__init__.py": '''
    ''',
    "fx_x16b_pkg/sub.py": '''
        import sys, types
        def fit(): return 1
        class _M(types.ModuleType):
            pass
        sys.modules[__name__].__class__ = _M
    ''',
    "fx_x24c.py": '''
        import functools
        def fast(n): return n * 2
        class Ref:
            @staticmethod
            def power_ref(n): return n * 2
        power_ref = Ref.power_ref
        power = functools.wraps(power_ref)(functools.lru_cache(None)(fast))
    ''',
    "fx_x24d.py": '''
        import functools
        def _mk():
            def body(x): return x + 24
            return body
        w1 = functools.lru_cache(None)(_mk())
        w2 = functools.lru_cache(None)(w1.__wrapped__)
    ''',
    "fx_x24e.py": '''
        import functools
        def _mk():
            def body(x): return x + 25
            return body
        w1 = functools.lru_cache(None)(_mk())
        sibling = functools.lru_cache(None)(w1.__wrapped__)
    ''',
    "fx_x25c.py": '''
        import functools
        def _impl(x): return x
        class Scorer:
            fast = functools.lru_cache(None)(_impl)
        class ScorerS:
            fast = staticmethod(functools.lru_cache(None)(_impl))
    ''',
    "fx_x25d.py": '''
        import functools
        def _impl(x): return x
        def _mk_ga():
            W = functools.lru_cache(None)(_impl)
            def __getattr__(name):
                if name == "fast":
                    return W
                raise AttributeError(name)
            return __getattr__
        __getattr__ = _mk_ga()
    ''',
    "fx_x26c.py": '''
        def real(): return "real"
    ''',
    "fx_x26dlib.py": '''
        import functools
        def deco(fn):
            @functools.wraps(fn)
            def wrapper(*a, **k):
                return fn(*a, **k)
            return wrapper
    ''',
    "fx_x26dstub.py": '''
        # X26d's test stub: a closure with one free variable, like the wrapper whose code it replaces
        def make():
            fn = None
            def stub(*a, **k):
                return fn
            return stub
    ''',
    "fx_x26d.py": '''
        import fx_x26dlib
        def _impl(): return 1
        real = fx_x26dlib.deco(_impl)
    ''',
    "fx_x26f_src.py": '''
        def f(): return 26
    ''',
    "fx_x29b_def.py": '''
        def thing(): return 29
    ''',
    "fx_x29b.py": '''
        import functools
        @functools.lru_cache(None)
        def __getattr__(name):
            if name == "thing":
                import fx_x29b_def
                return fx_x29b_def.thing
            raise AttributeError(name)
    ''',
    "fx_x30dlib.py": '''
        def helper30(): return 30
    ''',
    "fx_x30d.py": '''
        import fx_x30dlib
        class W:
            count = 0
            @property
            def __dict__(self):
                W.count += 1
                return {}
        fx_x30dlib.helper30.__wrapped__ = W()
        real = fx_x30dlib.helper30
    ''',
    "fx_x35b.py": '''
        def logged(fn):
            def inner(*a, **k):
                return fn(*a, **k)
            return inner
        @logged
        def helper():
            import fx_v5f
            return fx_v5f.f()
    ''',
    "fx_x35c.py": '''
        import types
        def w35(self):
            return None
        _twin = types.FunctionType(w35.__code__, {})    # the fixture holds a same-code function alive
    ''',
    "fx_cutw.py": '''
        # fresh wrappers, one per case (harness rules): each a top-level def used by no other case
        import asyncio.events, asyncio.base_events
        ORIG_RUN = asyncio.events.Handle._run
        ORIG_RUN_ONCE = asyncio.base_events.BaseEventLoop._run_once
        def timer_run_65e(self):                       # X65e: TimerHandle._run reimplementation
            self._context.run(self._callback, *self._args)
        def handle_run_65f(self):                      # X65f: the subclass's own _run
            self._context.run(self._callback, *self._args)
        def w65g(self):                                # X65g: restores, then runs the job
            asyncio.events.Handle._run = ORIG_RUN
            self._context.run(self._callback, *self._args)
        def w141(self):                                # X141: a wrapper
            return ORIG_RUN(self)
        def w141b(self):                               # X141b: a reimplementation
            self._context.run(self._callback, *self._args)
        def w141c(self):                               # X141c: runs ready callbacks, no restore
            for _ in range(len(self._ready)):
                h = self._ready.popleft()
                if not h._cancelled:
                    h._context.run(h._callback, *h._args)
    ''',
    # residual fixtures
    "fx_r05b.py": '''
        def real(): return "real"
    ''',
    "fx_r13a.py": '''
        import functools
        def _mk():
            def body(x): return x + 13
            return body
        cached = functools.lru_cache(None)(_mk())
    ''',
    "fx_r13b.py": '''
        import functools, fx_r13a
        sibling = functools.lru_cache(None)(fx_r13a.cached.__wrapped__)   # a sibling in another module
    ''',
    "fx_r18.py": '''
        # R18 (b)'s fresh wrapper: a top-level def of its own, used by no other case (harness rules)
        import asyncio.base_events
        ORIG_RUN_ONCE = asyncio.base_events.BaseEventLoop._run_once
        def w18(self):
            asyncio.base_events.BaseEventLoop._run_once = ORIG_RUN_ONCE     # first restore the binding
            for _ in range(len(self._ready)):                                # then run the ready callbacks
                h = self._ready.popleft()
                if not h._cancelled:
                    h._context.run(h._callback, *h._args)
    ''',
    "fx_r20.py": '''
        # R20's fresh wrapper W (harness rules): its body calls its argument
        def w20(x):
            return x()
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
    os.makedirs(os.path.dirname(os.path.join(FIX, fname)), exist_ok=True)
    with open(os.path.join(FIX, fname), "w") as fh:
        fh.write(textwrap.dedent(body))
# X26f: a sourceless module (a .pyc beside no source; SourcelessFileLoader)
import py_compile as _pyc                                                  # noqa: E402
_pyc.compile(os.path.join(FIX, "fx_x26f_src.py"), cfile=os.path.join(FIX, "fx_x26f.pyc"), doraise=True)
os.remove(os.path.join(FIX, "fx_x26f_src.py"))
import fx_v5f, fx_stub, fx_swap, fx_pep, fx_x59e, fx_x14d, fx_x24f   # noqa: E402
import fx_r05b, fx_r13a, fx_r13b, fx_r18, fx_r20                   # noqa: E402
import fx_b1, fx_x26c, fx_x26d, fx_x30d, fx_x30dlib, fx_x35b, fx_x35c, fx_cutw   # noqa: E402

ORIG = {}
for mod in (fx_v5f, fx_stub, fx_swap):
    for k, v in vars(mod).items():
        if type(v) is types.FunctionType:
            ORIG[(mod.__name__, k)] = (v, v.__code__)
ORIG[("fx_v5f", "cached.__wrapped__")] = (fx_v5f.cached.__wrapped__, fx_v5f.cached.__wrapped__.__code__)
ORIG[("fx_v5f", "Base.fit")] = (fx_v5f.Base.fit, fx_v5f.Base.fit.__code__)
ORIG[("fx_b1", "f59")] = (fx_b1.f59, fx_b1.f59.__code__)

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
    # residuals
    "A_F": gates({"A": ["fx_v5f:f"]}),
    # batch-1 violation preregs
    "X07B": gates({"G": ["fx_v5f:f"]}, sections={"G": ""}),
    "X07C": gates({"G": ["fx_v5f:f"]}, sections={"G": "s\u0435ction"}),
    "X14B": gates({"G": ["fx_b1:ALeaf.fit"]}),
    "X16B": gates({"G": ["fx_x16b_pkg:sub.fit"]}),
    "X24C": gates({"G": ["fx_x24c:power"]}),
    "X24D": gates({"G": ["fx_x24d:w1", "fx_x24d:w2"]}),
    "X24E": gates({"G": ["fx_x24e:w1"]}),
    "X25C": gates({"G": ["fx_x25c:Scorer.fast"]}),
    "X25C_S": gates({"G": ["fx_x25c:ScorerS.fast"]}),
    "X25D": gates({"G": ["fx_x25d:fast"]}),
    "X26C": gates({"G": ["fx_x26c:real"]}),
    "X26D": gates({"G": ["fx_x26d:real"]}),
    "X26E": gates({"G": ["fx_x26e_mod:f"]}),
    "X26F": gates({"G": ["fx_x26f:f"]}),
    "X29B": gates({"G": ["fx_x29b:thing"]}),
    "X30D": gates({"G": ["fx_x30d:real"]}),
    "X34B": gates({"G": ["fx_b1:clonebox"]}),
    "X34C": gates({"G": ["asyncio.base_events:BaseEventLoop._run_once", "fx_v5f:f"]}),
    "X59D": gates({"G": ["fx_b1:f59"]}),
    "X78G": gates({"G": ["fx_v5f:f"]}, sections={"G": "harness"}),
    "X120": gates({"A": ["fx_v5f:f"], "B": ["fx_v5f:g"]}),
    "X121": gates({"X": ["fx_v5f:f"], "Y": ["fx_v5f:g"]}, sections={"X": "Y", "Y": "X"}),
    "A_Gdecl": gates({"A": ["fx_v5f:g"]}),
    "T135": gates({"G": ["fx_b1:t135"]}),
    "A_T": gates({"A": ["fx_v5f:t"]}),
    "B_G": gates({"B": ["fx_v5f:g"]}),
    "B_H": gates({"B": ["fx_b1:h137"]}),
    "A_G": gates({"A": ["fx_v5f:g"]}),
    "R05B": gates({"G": ["fx_r05b:real"]}),
    "R13": gates({"G": ["fx_r13a:cached"]}),
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


# -- New documented residuals (pinned outcome) --------------------------------------------------------
def _resid_score(exp, rec):
    return score(exp, rec)

@case("R05b", "residual", "a '<stub>'-compiled stub exec'd into the declared module and bound before the trace; variant: co_filename forged to mod.__file__ -> PASS (deliberate only)")
def r05b():
    mod = fx_r05b
    real = mod.real
    try:
        for forged in (False, True):
            code = compile("def real():\n    return 'stub'\n", "<stub>", "exec")
            if not forged:
                exec(code, mod.__dict__)                 # binds mod.real to the stub
            else:
                fcode = [c for c in code.co_consts if isinstance(c, types.CodeType)][0]
                mod.real = types.FunctionType(fcode.replace(co_filename=mod.__file__), mod.__dict__, "real")
            exp = EXP("R05B")
            with P.coverage_trace(exp) as cov:
                cov.run("G", mod.real)
            expect_pass(score(exp, cov.record()), {"G": {"fx_r05b:real": 1}})
    finally:
        mod.real = real

@case("R12", "residual", "a settrace callback runs T on a section's stack through sys.call_tracing -> PASS, credited; calling T directly in the callback -> NOT_EXERCISED")
def r12():
    for via in ("call_tracing", "direct"):
        exp = EXP("F")
        def marker():
            return 0
        def tracer(frame, event, arg):
            if event == "call" and frame.f_code is marker.__code__:
                if via == "call_tracing":
                    sys.call_tracing(fx_v5f.f, ())
                else:
                    fx_v5f.f()
            return None
        prev = sys.gettrace()
        with P.coverage_trace(exp) as cov:
            def body():
                sys.settrace(tracer)
                try:
                    marker()
                finally:
                    sys.settrace(prev)
            cov.run("G", body)
        out = score(exp, cov.record())
        if via == "call_tracing":
            expect_pass(out, {"G": {"fx_v5f:f": 1}})
        else:
            expect_refuse(out, "NOT_EXERCISED")

@case("R13", "residual", "a sibling cache wrapper of the declared wrapper's body, held in another module, is called; the declared wrapper never -> PASS")
def r13():
    exp = EXP("R13")
    with P.coverage_trace(exp) as cov:
        cov.run("G", fx_r13b.sibling, 1)
    expect_pass(score(exp, cov.record()), {"G": {"fx_r13a:cached": 1}})

@case("R14", "residual", "a generator object of the declared generator function created before the trace, resumed inside a section -> NOT_EXERCISED")
def r14():
    exp = EXP("GEN")
    g = fx_v5f.gen()
    try:
        with P.coverage_trace(exp) as cov:
            cov.run("G", next, g)
        expect_refuse(score(exp, cov.record()), "NOT_EXERCISED")
    finally:
        g.close()

@case("R16", "residual", "the id-3 tool raises at the target's PY_RETURN -> the caller sees it; the call is counted {f:1} (L-DELIVERY)")
def r16():
    mon = sys.monitoring
    class Boom(Exception):
        pass
    exp = EXP("F")
    seen = []
    mon.use_tool_id(3, "exam-fault-tool")
    try:
        with P.coverage_trace(exp) as cov:
            code = fx_v5f.f.__code__
            def on_ret(c, off, val):
                if c is code:
                    raise Boom()
            mon.register_callback(3, mon.events.PY_RETURN, on_ret)
            mon.set_local_events(3, code, mon.events.PY_RETURN)
            def body():
                try:
                    fx_v5f.f()
                except Boom:
                    seen.append("Boom")
            try:
                cov.run("G", body)
            finally:
                mon.set_local_events(3, code, 0)
    finally:
        mon.register_callback(3, mon.events.PY_RETURN, None)
        mon.free_tool_id(3)
    expect(seen == ["Boom"], f"the caller saw {seen}")
    expect_pass(score(exp, cov.record()), {"G": {"fx_v5f:f": 1}})

def _r18(variant):
    import asyncio, operator
    exp = EXP("A_F")
    class L(asyncio.SelectorEventLoop):
        def _run_once(self):                      # X65d's loop: ready callbacks through map(operator.call, ...)
            hs = [self._ready.popleft() for _ in range(len(self._ready))]
            list(map(operator.call, [functools.partial(h._context.run, h._callback, *h._args)
                                     for h in hs if not h._cancelled]))
    loop = L() if variant == "a" else asyncio.new_event_loop()
    try:
        with P.coverage_trace(exp) as cov:
            async def other():
                loop.call_soon(fx_v5f.f)
            async def main():
                t = asyncio.ensure_future(other())
                await asyncio.sleep(0)
                if variant == "b":
                    asyncio.base_events.BaseEventLoop._run_once = fx_r18.w18
                try:
                    cov.run("A", loop._run_once)
                finally:
                    asyncio.base_events.BaseEventLoop._run_once = fx_r18.ORIG_RUN_ONCE
                await t
            loop.run_until_complete(main())
        rec = cov.record()
    finally:
        asyncio.base_events.BaseEventLoop._run_once = fx_r18.ORIG_RUN_ONCE
        loop.close()
    expect_pass(score(exp, rec), {"A": {"fx_v5f:f": 1}})

@case("R18a", "residual", "(a) X65d's loop (map(operator.call, ...)); in a task, section A calls loop._run_once(), which runs a job another task scheduled with call_soon(f) -> PASS, credited to A")
def r18a():
    _r18("a")

@case("R18b", "residual", "(b) the stdlib loop; after __enter__ BaseEventLoop._run_once is rebound to W, which restores the binding and runs the ready callbacks without Handle._run -> PASS, credited to A")
def r18b():
    _r18("b")

@case("R20", "residual", "W bound as Handle._run across one coverage_trace() and __enter__, then restored; FunctionType(W.__code__, g) runs f in section A -> NOT_EXERCISED, dispatched {f:1}")
def r20():
    import asyncio
    H = asyncio.events.Handle
    run0 = H.__dict__["_run"]
    try:
        H._run = fx_r20.w20
        cov0 = P.coverage_trace(EXP("A_G"))
        cov0.__enter__()
        cov0.__exit__(None, None, None)
    finally:
        H._run = run0
    clone = types.FunctionType(fx_r20.w20.__code__, vars(fx_v5f))
    try:
        exp = EXP("A_F")
        with P.coverage_trace(exp) as cov:
            cov.run("A", clone, fx_v5f.f)
        rec = cov.record()
    finally:
        del clone
        gc.collect()
    out = score(exp, rec)
    expect_refuse(out, "NOT_EXERCISED")
    expect(rec["uncredited"]["dispatched"] == {"fx_v5f:f": 1}, f"uncredited {rec['uncredited']}")

@sub("R21")
def _sub_r21():
    mon = sys.monitoring
    exp = EXP("A_F")
    with P.coverage_trace(exp) as cov:
        cov.run("A", fx_v5f.f)
        t = P._v5_state()["tool"]
        name = mon.get_tool(t)
        mon.free_tool_id(t)
        mon.use_tool_id(t, name)                  # the hostile tool re-takes it with styxx's own name object
        cov.run("A", fx_v5f.f)
    rec = cov.record()
    notes = [n for o in rec["sections"]["A"] for n in o["notes"]]
    return {"score": _outcome_json(score(exp, rec)), "lost": any(n.startswith("[V5:MONITOR_LOST]") for n in notes)}

@case("R21", "residual", "fresh subprocess: after one run, another tool frees styxx's id and re-takes it with styxx's name object; a second run -> PASS {f:2}, no MONITOR_LOST")
def r21():
    r = run_sub("R21")
    expect(r == {"score": ["PASS", {"A": {"fx_v5f:f": 2}}], "lost": False}, f"{r}")

@case("R22", "residual", "FunctionType(f.__code__.replace(), f.__globals__) called inside section A -> NOT_EXERCISED; the copy in no bucket; no problem")
def r22():
    exp = EXP("A_F")
    with P.coverage_trace(exp) as cov:
        def body():
            types.FunctionType(fx_v5f.f.__code__.replace(), fx_v5f.f.__globals__)(0)   # no defaults on the copy
        cov.run("A", body)
    rec = cov.record()
    expect_refuse(score(exp, rec), "NOT_EXERCISED")
    expect(rec["uncredited"] == {"dispatched": {}, "unattributed": {}} and rec["problems"] == [],
           f"uncredited {rec['uncredited']} problems {rec['problems']}")

def _denied_hook(nth):
    class Denied(Exception):
        pass
    me = threading.get_ident()
    st = {"n": 0, "armed": True}
    def hook(event, args):
        if st["armed"] and event == "sys.monitoring.register_callback" and threading.get_ident() == me:
            st["n"] += 1
            if st["n"] == nth:
                st["armed"] = False
                raise Denied("denied")
    sys.addaudithook(hook)
    return Denied

@sub("X157")
def _sub_x157():
    exp = EXP("A_F")
    cov = P.coverage_trace(exp)
    cov.__enter__()
    cov.run("A", fx_v5f.f)
    Denied = _denied_hook(2)
    try:
        cov.__exit__(None, None, None)
        raised = None
    except Denied:
        raised = "Denied"
    try:
        cov.record()
        rec = None
    except GateSpecError as e:
        rec = code_of(e)
    guard = P._v5_state()["guard"]
    exp2 = EXP("A_G")
    with P.coverage_trace(exp2) as cov2:
        cov2.run("A", fx_v5f.g)
    rec2 = cov2.record()
    st = P._v5_state()
    return {"raised": raised, "record": rec, "guard": guard, "second": _outcome_json(score(exp2, rec2)),
            "lost": any(n.startswith("[V5:MONITOR_LOST]") for o in rec2["sections"]["A"] for n in o["notes"]),
            "after": [st["guard"], st["anchors"], st["global_events"]]}

@case("X157", "residual", "fresh subprocess: an audit hook raises Denied at the 2nd register_callback of the exit -> Denied from __exit__; record TRACE_INCOMPLETE; guard dead; a tracer on g PASS {g:1}, no MONITOR_LOST; then guard free, anchors 0, global_events 0")
def x157():
    r = run_sub("X157")
    expect(r == {"raised": "Denied", "record": "TRACE_INCOMPLETE", "guard": "dead",
                 "second": ["PASS", {"A": {"fx_v5f:g": 1}}], "lost": False, "after": ["free", 0, 0]}, f"{r}")

@sub("X157b")
def _sub_x157b():
    mon = sys.monitoring
    expP = EXP("A_F")
    covP = P.coverage_trace(expP)
    covP.__enter__()
    covP.run("A", fx_v5f.f)
    mon.free_tool_id(P._v5_state()["tool"])       # an outside party frees styxx's id; nobody takes it
    Denied = _denied_hook(2)
    covQ = P.coverage_trace(EXP("A_G"))
    try:
        covQ.__enter__()
        q = None
    except Denied:
        q = "Denied"
    try:
        covQ.record()
        qrec = None
    except GateSpecError as e:
        qrec = code_of(e)
    st = P._v5_state()
    mid = [st["tool_ours"], st["guard"]]
    covP.__exit__(None, None, None)
    recP = covP.record()
    expR = EXP("A_G")
    with P.coverage_trace(expR) as covR:
        covR.run("A", fx_v5f.g)
    recR = covR.record()
    st = P._v5_state()
    lost = lambda rec: any(n.startswith("[V5:MONITOR_LOST]") for o in rec["sections"]["A"] for n in o["notes"])
    return {"q": q, "qrec": qrec, "mid": mid, "P": _outcome_json(score(expP, recP)), "P_lost": lost(recP),
            "R": _outcome_json(score(expR, recR)), "R_lost": lost(recR),
            "after": [st["guard"], st["anchors"], st["global_events"]]}

@case("X157b", "residual", "fresh subprocess: styxx's id freed; an audit hook raises at the 2nd register_callback of Q's enter -> Denied from Q's __enter__, Q TRACE_INCOMPLETE; tool_ours True, guard dead; P PASS {f:1} no MONITOR_LOST; R on g PASS {g:1}; then guard free, anchors 0, global_events 0")
def x157b():
    r = run_sub("X157b")
    expect(r == {"q": "Denied", "qrec": "TRACE_INCOMPLETE", "mid": [True, "dead"],
                 "P": ["PASS", {"A": {"fx_v5f:f": 1}}], "P_lost": False,
                 "R": ["PASS", {"A": {"fx_v5f:g": 1}}], "R_lost": False, "after": ["free", 0, 0]}, f"{r}")


# -- v5e cases whose outcome changes (the delta table) -------------------------------------------------
@case("V48", "valid", "a pure-Python setprofile profiler installed before open (replaces X80) -> {f:1}; the profiler still installed; it saw the call")
def v48():
    exp = EXP("F")
    saw = []
    def prof(frame, event, arg):
        if event == "call" and frame.f_code is fx_v5f.f.__code__:
            saw.append(1)
    prev = sys.getprofile()
    sys.setprofile(prof)
    try:
        with P.coverage_trace(exp) as cov:
            cov.run("G", fx_v5f.f)
        still = sys.getprofile() is prof
    finally:
        sys.setprofile(prev)
    expect_pass(score(exp, cov.record()), {"G": {"fx_v5f:f": 1}})
    expect(still and saw, f"profiler installed {still}, saw {len(saw)} call(s)")

@case("V49", "valid", "the harness calls sys.setprofile(None) and sys.settrace(None) before the target (replaces X75) -> {f:1}, no note")
def v49():
    exp = EXP("F")
    prev = (sys.getprofile(), sys.gettrace())
    try:
        with P.coverage_trace(exp) as cov:
            def body():
                sys.setprofile(None)
                sys.settrace(None)
                return fx_v5f.f()
            cov.run("G", body)
    finally:
        sys.setprofile(prev[0])
        sys.settrace(prev[1])
    rec = cov.record()
    expect_pass(score(exp, rec), {"G": {"fx_v5f:f": 1}})
    expect(rec["sections"]["G"][0]["notes"] == [], f"notes {rec['sections']['G'][0]['notes']}")

@case("X95", "scoring", "a /1 trace -> WRONG_TRACER (the delta table: same as v5e; X95b adds /2)")
def x95():
    exp, rec = _genuine_trace()
    r = dict(rec); r["tracer"] = "styxx.protocol.coverage_trace/1"
    expect_refuse(gate_outcome(exp, r, "G"), "WRONG_TRACER")


# -- New violation cases, batch 1 (rows that need no instruction sweep or id-5 injector) ---------------
MON = getattr(sys, "monitoring", None)

class FaultTool:
    """The exam's id-3 fault tool (harness rules, "Fault tools"): it takes its id only for the case, and
    before freeing it sets every local and global event it set to 0 and registers None for every
    event it registered a callback for."""
    def __init__(self, tid=3, name="exam-fault-tool"):
        self.t = tid
        MON.use_tool_id(tid, name)
        self.codes, self.evs = set(), set()
    def on(self, code, event, cb):
        MON.register_callback(self.t, event, cb)
        MON.set_local_events(self.t, code, MON.get_local_events(self.t, code) | event)
        self.codes.add(code)
        self.evs.add(event)
    def off(self, code):
        MON.set_local_events(self.t, code, 0)
    def close(self):
        for c in self.codes:
            MON.set_local_events(self.t, c, 0)
        MON.set_events(self.t, 0)
        for e in self.evs:
            MON.register_callback(self.t, e, None)
        MON.free_tool_id(self.t)

def enter_refuses(key, code):
    cov = P.coverage_trace(EXP(key))
    try:
        return raises_code(cov.__enter__, code)
    finally:
        cov.__exit__(None, None, None)

def decl_refuses(key, code):
    """A parse refusal: raised when the prereg's gates block is read (Experiment) or at coverage_trace."""
    try:
        exp = EXP(key)
        P.coverage_trace(exp)
    except GateSpecError as e:
        expect(str(e).startswith(f"[V5:{code}]"), f"expected [V5:{code}], got {str(e)[:150]}")
        return e
    raise AssertionError(f"expected [V5:{code}], nothing raised")

@case("X07b / X07c", "declaration", "section '' / 'sеction' (Cyrillic е) -> SECTION_DECL")
def x07b_c():
    decl_refuses("X07B", "SECTION_DECL")
    decl_refuses("X07C", "SECTION_DECL")

@case("X14b", "identity", "an inherited method of an abc.ABC subclass -> INHERITED")
def x14b():
    enter_refuses("X14B", "INHERITED")

@case("X16b", "identity", "a submodule whose __class__ is a ModuleType subclass, reached after the colon -> INSTANCE_PATH")
def x16b():
    importlib.import_module("fx_x16b_pkg.sub")
    enter_refuses("X16B", "INSTANCE_PATH")

@case("X24c", "identity", "X24b with power_ref also bound at module level -> NOT_A_FUNCTION naming fast, never power_ref")
def x24c():
    e = enter_refuses("X24C", "NOT_A_FUNCTION")
    expect("fx_x24c:fast" in str(e) and "power_ref" not in str(e), str(e))

@case("X24d", "identity", "both of two cache wrappers of one body declared -> NOT_A_FUNCTION")
def x24d():
    enter_refuses("X24D", "NOT_A_FUNCTION")

@case("X24e", "identity", "the declared wrapper's body also wrapped by a sibling cache wrapper in the same module -> NOT_A_FUNCTION containing .__wrapped__")
def x24e():
    e = enter_refuses("X24E", "NOT_A_FUNCTION")
    expect(".__wrapped__" in str(e), str(e))

@case("X25c", "identity", "Scorer.fast = lru_cache(None)(_impl), bare and as a staticmethod, _impl bound at module level -> NOT_A_FUNCTION")
def x25c():
    enter_refuses("X25C", "NOT_A_FUNCTION")
    enter_refuses("X25C_S", "NOT_A_FUNCTION")

@case("X25d", "identity", "a cache wrapper served only through PEP 562 (holder None) whose body is bound at module level -> NOT_A_FUNCTION")
def x25d():
    enter_refuses("X25D", "NOT_A_FUNCTION")

@case("X26c", "identity", "FunctionType(stub.__code__, vars(mod)) bound at the name -> FOREIGN_DEFINITION")
def x26c():
    real = fx_x26c.real
    try:
        fx_x26c.real = types.FunctionType(fx_stub.stub.__code__, vars(fx_x26c))
        enter_refuses("X26C", "FOREIGN_DEFINITION")
    finally:
        fx_x26c.real = real

@case("X26d", "identity", "a foreign functools.wraps wrapper bound at the name, its own __code__ swapped to a test stub before the trace -> FOREIGN_DEFINITION")
def x26d():
    w = fx_x26d.real
    code = w.__code__
    try:
        w.__code__ = importlib.import_module("fx_x26dstub").make().__code__
        enter_refuses("X26D", "FOREIGN_DEFINITION")
    finally:
        w.__code__ = code

@case("X26e", "identity", "a declared module built with types.ModuleType, no __file__, in sys.modules, whose function has a '<m>' filename -> FOREIGN_DEFINITION")
def x26e():
    m = types.ModuleType("fx_x26e_mod")
    exec(compile("def f():\n    return 1\n", "<m>", "exec"), m.__dict__)
    sys.modules["fx_x26e_mod"] = m
    try:
        enter_refuses("X26E", "FOREIGN_DEFINITION")
    finally:
        sys.modules.pop("fx_x26e_mod", None)

@case("X26f", "identity", "a sourceless module (__file__ ends .pyc, SourcelessFileLoader) -> FOREIGN_DEFINITION")
def x26f():
    m = importlib.import_module("fx_x26f")
    expect(m.__file__.endswith(".pyc") and type(m.__loader__).__name__ == "SourcelessFileLoader",
           f"fixture: {m.__file__} {type(m.__loader__).__name__}")
    enter_refuses("X26F", "FOREIGN_DEFINITION")

@case("X29b", "identity", "a re-export through a decorated PEP 562 lazy attribute -> FOREIGN_DEFINITION naming the defining module:qualname")
def x29b():
    e = enter_refuses("X29B", "FOREIGN_DEFINITION")
    expect("fx_x29b_def:thing" in str(e), str(e))

@case("X30d", "identity", "a __wrapped__ link whose class defines a Python __dict__ property, no accepting link before it -> FOREIGN_DEFINITION; the property counter 0")
def x30d():
    fx_x30d.W.count = 0
    enter_refuses("X30D", "FOREIGN_DEFINITION")
    expect(fx_x30d.W.count == 0, f"the __dict__ property ran {fx_x30d.W.count} time(s)")

@case("X32d", "lifecycle", "two barrier-synchronised threads enter one tracer, 50 repetitions -> REENTRY at score; exactly one entry each time; counts exact")
def x32d():
    for rep in range(50):
        exp = EXP("F")
        cov = P.coverage_trace(exp)
        bar = threading.Barrier(2)
        got = []
        def enter():
            bar.wait()
            try:
                cov.__enter__()
                got.append("entered")
            except GateSpecError as e:
                got.append(code_of(e))
        ts = [threading.Thread(target=enter) for _ in range(2)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(30)
        cov.run("G", fx_v5f.f)
        cov.__exit__(None, None, None)
        expect(sorted(got) == ["REENTRY", "entered"], f"repetition {rep}: {got}")
        rec = cov.record()
        expect(rec["sections"]["G"][0]["calls"] == {"fx_v5f:f": 1}, f"repetition {rep}: {rec['sections']}")
        expect_refuse(score(exp, rec), "REENTRY")

@case("X34b", "cut", "a fixture function built as FunctionType(Handle._run.__code__, vars(fx)) inside the case and declared -> RESERVED_TARGET")
def x34b():
    import asyncio
    orig = fx_b1.clonebox
    fx_b1.clonebox = types.FunctionType(asyncio.events.Handle._run.__code__, vars(fx_b1))
    try:
        enter_refuses("X34B", "RESERVED_TARGET")
    finally:
        fx_b1.clonebox = orig
        gc.collect()

@case("X34c", "cut", "declare asyncio.base_events:BaseEventLoop._run_once and f -> RESERVED_TARGET at entry")
def x34c():
    enter_refuses("X34C", "RESERVED_TARGET")

@case("X35", "cut", "Handle._run replaced by a MagicMock around __enter__; nothing minted afterwards -> CUT_UNAVAILABLE")
def x35():
    import asyncio
    from unittest import mock
    H = asyncio.events.Handle
    run0 = H.__dict__["_run"]
    before = P._v5_state()["mints"]
    cov = P.coverage_trace(EXP("F"))
    H._run = mock.MagicMock(name="Handle._run")
    try:
        raises_code(cov.__enter__, "CUT_UNAVAILABLE")
        expect(P._v5_state()["mints"] == before, "something was minted")
    finally:
        H._run = run0
        cov.__exit__(None, None, None)

@case("X35b", "cut", "Handle._run = logged(orig) (logged.<locals>.inner) before __enter__ -> CUT_UNAVAILABLE naming logged.<locals>.inner; a later trace of a logged helper calling f PASS {f:1}")
def x35b():
    import asyncio
    H = asyncio.events.Handle
    run0 = H.__dict__["_run"]
    cov = P.coverage_trace(EXP("F"))
    H._run = fx_x35b.logged(run0)
    try:
        e = raises_code(cov.__enter__, "CUT_UNAVAILABLE")
        expect("logged.<locals>.inner" in str(e), str(e))
    finally:
        H._run = run0
        cov.__exit__(None, None, None)
    exp = EXP("F")
    with P.coverage_trace(exp) as cov2:
        cov2.run("G", fx_x35b.helper)
    expect_pass(score(exp, cov2.record()), {"G": {"fx_v5f:f": 1}})

@case("X35c", "cut", "a module-level W bound as Handle._run while the fixture holds FunctionType(W.__code__, g) alive -> CUT_UNAVAILABLE")
def x35c():
    import asyncio
    H = asyncio.events.Handle
    run0 = H.__dict__["_run"]
    H._run = fx_x35c.w35
    try:
        try:
            cov = P.coverage_trace(EXP("F"))
        except GateSpecError as e:              # construction runs E2 too (M0 step 9)
            expect(str(e).startswith("[V5:CUT_UNAVAILABLE]"), str(e))
            return
        try:
            raises_code(cov.__enter__, "CUT_UNAVAILABLE")
        finally:
            cov.__exit__(None, None, None)
    finally:
        H._run = run0

@sub("X36")
def _sub_x36():
    MON.use_tool_id(4, "other4")
    MON.use_tool_id(3, "other3")
    cov = P.coverage_trace(EXP("F"))
    try:
        cov.__enter__()
        out = None
    except GateSpecError as e:
        out = code_of(e)
    return {"code": out, "mints": P._v5_state()["mints"]}

@case("X36", "monitoring", "fresh subprocess: tool ids 3 and 4 taken by two other tools before any tracer is entered -> MONITOR_BUSY; nothing minted")
def x36():
    r = run_sub("X36")
    expect(r == {"code": "MONITOR_BUSY", "mints": []}, f"{r}")

@case("X55d", "identity", "nested tracers on f; FunctionType(f.__code__, {})() while both hold the mint -> CLONE_CALLED for both")
def x55d():
    e1, e2 = EXP("F"), EXP("F")
    with P.coverage_trace(e1) as c1:
        with P.coverage_trace(e2) as c2:
            def body():
                fx_v5f.f()
                types.FunctionType(fx_v5f.f.__code__, {})(0)
            c1.run("G", lambda: c2.run("G", body))
    expect_refuse(score(e1, c1.record()), "CLONE_CALLED")
    expect_refuse(score(e2, c2.record()), "CLONE_CALLED")

@case("X57b", "identity", "a same-globals clone of M_T made in the trace, then gc.freeze(), kept alive through exit -> CLONE_ALIVE")
def x57b():
    exp = EXP("F")
    keep = []
    try:
        with P.coverage_trace(exp) as cov:
            cov.run("G", fx_v5f.f)
            keep.append(types.FunctionType(fx_v5f.f.__code__, fx_v5f.f.__globals__))
            gc.freeze()
        rec = cov.record()
    finally:
        gc.unfreeze()
        keep.clear()
        gc.collect()        # after unfreeze: 3.12.3 restores its boot count at a full collection (GAP-39)
    expect_refuse(score(exp, rec), "CLONE_ALIVE")

@case("X57c", "identity", "nested tracers on f; the inner section calls only a same-globals clone, kept alive past the inner exit, dropped before the outer exit -> inner: CLONE_ALIVE")
def x57c():
    eo, ei = EXP("F"), EXP("F")
    keep = []
    with P.coverage_trace(eo) as co:
        co.run("G", fx_v5f.f)
        with P.coverage_trace(ei) as ci:
            def body():
                keep.append(types.FunctionType(fx_v5f.f.__code__, fx_v5f.f.__globals__))
                keep[0](0)
            ci.run("G", body)
        keep.clear()
        gc.collect()
    expect_refuse(score(ei, ci.record()), "CLONE_ALIVE")

@case("X58b", "identity", "U.__code__ = T.__code__, U kept, then gc.freeze() -> CLONE_ALIVE")
def x58b():
    exp = EXP("F")
    u = fx_v5f.other
    ucode = u.__code__
    try:
        with P.coverage_trace(exp) as cov:
            cov.run("G", fx_v5f.f)
            u.__code__ = fx_v5f.f.__code__
            gc.freeze()
        rec = cov.record()
    finally:
        gc.unfreeze()
        u.__code__ = ucode
        gc.collect()        # after unfreeze: 3.12.3 restores its boot count at a full collection (GAP-39)
    expect_refuse(score(exp, rec), "CLONE_ALIVE")

@case("X59c", "identity", "nested tracers; the inner section calls f, then swaps f.__code__ and leaves it through the inner exit, restoring before the outer exit -> inner: CODE_SWAPPED")
def x59c():
    eo, ei = EXP("F"), EXP("F")
    f = fx_v5f.f
    orig = ORIG[("fx_v5f", "f")][1]
    try:
        with P.coverage_trace(eo) as co:
            co.run("G", f)
            minted = f.__code__
            with P.coverage_trace(ei) as ci:
                def body():
                    f()
                    f.__code__ = fx_v5f.other.__code__
                ci.run("G", body)
            f.__code__ = minted
        expect_refuse(score(ei, ci.record()), "CODE_SWAPPED")
    finally:
        f.__code__ = orig

@case("X59d", "identity", "X59 plus a check after exit and before the case's own restore that f59.__code__ is u59.__code__ and f59() == -59 -> CODE_SWAPPED; swap left in place")
def x59d():
    exp = EXP("X59D")
    f59, u59 = fx_b1.f59, fx_b1.u59
    orig = f59.__code__
    try:
        with P.coverage_trace(exp) as cov:
            def body():
                f59()
                f59.__code__ = u59.__code__
            cov.run("G", body)
        expect(f59.__code__ is u59.__code__ and f59() == -59, "the swap was not left in place")
        expect_refuse(score(exp, cov.record()), "CODE_SWAPPED")
    finally:
        f59.__code__ = orig

def _loop_job_case(exp, section_fn_factory, loop=None):
    """In a task of a running loop L, section A runs section_fn (built by the factory from L and the
    job's scheduling); the case returns the record."""
    import asyncio
    L = loop or asyncio.new_event_loop()
    try:
        with P.coverage_trace(exp) as cov:
            L.run_until_complete(section_fn_factory(L, cov))
        return cov.record()
    finally:
        L.close()

@case("X65c", "cut", "in a task of a running loop L, cov.run('A', section) calls L._run_once(), which runs a callback another task scheduled; it calls f -> A: NOT_EXERCISED, dispatched {f:1}")
def x65c():
    import asyncio
    exp = EXP("A_F")
    def factory(L, cov):
        async def other():
            L.call_soon(fx_v5f.f)
        async def main():
            t = asyncio.ensure_future(other())
            await asyncio.sleep(0)
            cov.run("A", L._run_once)
            await t
        return main()
    rec = _loop_job_case(exp, factory)
    expect_refuse(score(exp, rec), "NOT_EXERCISED")
    expect(rec["uncredited"]["dispatched"] == {"fx_v5f:f": 1}, f"uncredited {rec['uncredited']}")

@case("X65d", "attribution", "a SelectorEventLoop subclass whose _run_once runs ready callbacks through map(operator.call, ...), run inside section A, serving another thread's call_soon_threadsafe job that calls f -> A: NOT_EXERCISED, dispatched {f:1}")
def x65d():
    import asyncio, operator
    exp = EXP("A_F")
    class L(asyncio.SelectorEventLoop):
        def _run_once(self):
            hs = [self._ready.popleft() for _ in range(len(self._ready))]
            if not hs:
                time.sleep(0.001)
            list(map(operator.call, [functools.partial(h._context.run, h._callback, *h._args)
                                     for h in hs if not h._cancelled]))
    loop = L()
    try:
        with P.coverage_trace(exp) as cov:
            async def main():
                fut = loop.create_future()
                def job():
                    fx_v5f.f()
                    fut.set_result(1)
                th = threading.Thread(target=lambda: loop.call_soon_threadsafe(job))
                th.start()
                await fut
                th.join()
            cov.run("A", loop.run_until_complete, main())
        rec = cov.record()
    finally:
        loop.close()
    expect_refuse(score(exp, rec), "NOT_EXERCISED")
    expect(rec["uncredited"]["dispatched"] == {"fx_v5f:f": 1}, f"uncredited {rec['uncredited']}")

@case("X65e", "cut", "X65c with TimerHandle._run set to a reimplementation after __enter__ and before the section, the job scheduled with call_later(0, f); the override deleted after exit -> dispatched {f:1}; no CUT_MOVED")
def x65e():
    import asyncio
    exp = EXP("A_F")
    TH = asyncio.TimerHandle
    had = "_run" in TH.__dict__
    L = asyncio.new_event_loop()
    try:
        with P.coverage_trace(exp) as cov:
            TH._run = fx_cutw.timer_run_65e
            async def other():
                L.call_later(0, fx_v5f.f)
            async def main():
                t = asyncio.ensure_future(other())
                await asyncio.sleep(0)
                cov.run("A", L._run_once)
                await t
            L.run_until_complete(main())
        rec = cov.record()
    finally:
        if not had and "_run" in TH.__dict__:
            del TH._run
        L.close()
    expect_refuse(score(exp, rec), "NOT_EXERCISED")
    expect(rec["uncredited"]["dispatched"] == {"fx_v5f:f": 1}, f"uncredited {rec['uncredited']}")
    expect(not any(p.startswith("[V5:CUT_MOVED]") for p in rec["problems"]), f"problems {rec['problems']}")

@case("X65f", "cut", "X65c with asyncio.events.Handle rebound to a subclass with its own _run after __enter__ and before call_soon(f); restored before exit -> dispatched {f:1}")
def x65f():
    import asyncio
    exp = EXP("A_F")
    H = asyncio.events.Handle
    Sub = type("Handle65f", (H,), {"_run": fx_cutw.handle_run_65f})
    L = asyncio.new_event_loop()
    try:
        with P.coverage_trace(exp) as cov:
            async def other():
                L.call_soon(fx_v5f.f)
            async def main():
                asyncio.events.Handle = Sub
                try:
                    t = asyncio.ensure_future(other())
                    await asyncio.sleep(0)
                    cov.run("A", L._run_once)
                    await t
                finally:
                    asyncio.events.Handle = H
            L.run_until_complete(main())
        rec = cov.record()
    finally:
        asyncio.events.Handle = H
        L.close()
    expect_refuse(score(exp, rec), "NOT_EXERCISED")
    expect(rec["uncredited"]["dispatched"] == {"fx_v5f:f": 1}, f"uncredited {rec['uncredited']}")

@case("X65g", "cut", "after __enter__, inside the running task and immediately before section A, Handle._run is rebound to W (restores, then runs the job); L._ready holds exactly the job; A calls L._run_once() -> dispatched {f:1}; no CUT_MOVED")
def x65g():
    import asyncio
    exp = EXP("A_F")
    H = asyncio.events.Handle
    L = asyncio.new_event_loop()
    seen = {}
    try:
        with P.coverage_trace(exp) as cov:
            async def other():
                L.call_soon(fx_v5f.f)
            async def main():
                t = asyncio.ensure_future(other())
                await asyncio.sleep(0)
                seen["ready"] = [h._callback for h in L._ready]
                H._run = fx_cutw.w65g
                try:
                    cov.run("A", L._run_once)
                finally:
                    H._run = fx_cutw.ORIG_RUN
                await t
            L.run_until_complete(main())
        rec = cov.record()
    finally:
        H._run = fx_cutw.ORIG_RUN
        L.close()
    expect(seen.get("ready") == [fx_v5f.f], f"L._ready at the rebinding: {seen.get('ready')}")
    expect_refuse(score(exp, rec), "NOT_EXERCISED")
    expect(rec["uncredited"]["dispatched"] == {"fx_v5f:f": 1}, f"uncredited {rec['uncredited']}")
    expect(not any(p.startswith("[V5:CUT_MOVED]") for p in rec["problems"]), f"problems {rec['problems']}")

@case("X76b", "attribution", "a nested open of the same section, and a variant on two sections -> NESTED_SECTION with the two spec-fixed texts")
def x76b():
    exp = EXP("GH")
    texts = []
    with P.coverage_trace(exp) as cov:
        def body():
            fx_v5f.f()
            for sec, fn in (("G", fx_v5f.f), ("H", fx_v5f.g)):
                try:
                    cov.run(sec, fn)
                except GateSpecError as e:
                    texts.append(str(e))
        cov.run("G", body)
        cov.run("H", fx_v5f.g)
    expect(len(texts) == 2 and texts[0].startswith("[V5:NESTED_SECTION]") and texts[1].startswith("[V5:NESTED_SECTION]"), f"{texts}")
    expect("a call there would be on the stack of two openings of section 'G'" in texts[0], texts[0])
    expect("one call would count for both sections 'G' and 'H'" in texts[1], texts[1])
    expect_refuse(score(exp, cov.record()), "NESTED_SECTION")

@case("X78e", "sections", "the harness swallows cov.run('G_typo', f) and never opens G's section -> UNDECLARED_SECTION (not SECTION_ABSENT)")
def x78e():
    exp = EXP("F")
    with P.coverage_trace(exp) as cov:
        try:
            cov.run("G_typo", fx_v5f.f)
        except GateSpecError:
            pass
    expect_refuse(score(exp, cov.record()), "UNDECLARED_SECTION")

@case("X78g", "sections", "a gate whose declared section is 'harness', opened by its gate name -> UNDECLARED_SECTION")
def x78g():
    exp = EXP("X78G")
    with P.coverage_trace(exp) as cov:
        try:
            cov.run("G", fx_v5f.f)
        except GateSpecError:
            pass
    expect_refuse(score(exp, cov.record()), "UNDECLARED_SECTION")

@case("X83", "attribution", "an eager child task created inside run_async('A') calls cov.run_async('B', ...) in its first step -> NESTED_SECTION")
def x83():
    import asyncio
    exp = EXP("AB")
    got = []
    with P.coverage_trace(exp) as cov:
        async def gbody():
            return fx_v5f.g()
        async def child():
            try:
                await cov.run_async("B", gbody)
            except GateSpecError as e:
                got.append(code_of(e))
        async def abody():
            fx_v5f.f()
            asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
            t = asyncio.create_task(child())
            await t
        asyncio.run(cov.run_async("A", abody))
    expect(got == ["NESTED_SECTION"], f"child: {got}")
    expect_refuse(score(exp, cov.record()), "NESTED_SECTION")

@case("X92c", "lifecycle", "the id-3 tool raises at PY_START of the facade's __exit__ -> record() TRACE_ACTIVE; a second tracer PASS meanwhile; __exit__() again -> PASS {f:1}")
def x92c():
    class Injected(Exception):
        pass
    exp = EXP("F")
    cov = P.coverage_trace(exp)
    cov.__enter__()
    cov.run("G", fx_v5f.f)
    code = P._v5_faultpoints()["_CoverageTracer.__exit__"]
    tool = FaultTool()
    armed = [True]
    def on_start(c, off):
        if c is code and armed[0]:
            armed[0] = False
            raise Injected()
    try:
        tool.on(code, MON.events.PY_START, on_start)
        try:
            cov.__exit__(None, None, None)
            raise AssertionError("no Injected")
        except Injected:
            pass
    finally:
        tool.close()
    raises_code(cov.record, "TRACE_ACTIVE")
    exp2 = EXP("F")
    with P.coverage_trace(exp2) as cov2:
        cov2.run("G", fx_v5f.f)
    expect_pass(score(exp2, cov2.record()), {"G": {"fx_v5f:f": 1}})
    cov.__exit__(None, None, None)
    expect_pass(score(exp, cov.record()), {"G": {"fx_v5f:f": 1}})

@case("X96c", "scoring", "a genuine trace with gates_sha256 popped -> BAD_TRACE (never KeyError or STALE_TRACE)")
def x96c():
    exp, rec = _genuine_trace()
    r = dict(rec); r.pop("gates_sha256")
    expect_refuse(gate_outcome(exp, r, "G"), "BAD_TRACE")

@case("X103b", "scoring", "end as a list and as a dict -> BAD_TRACE; check_metrics REPORTED without raising")
def x103b():
    exp, rec = _genuine_trace()
    for end in (["returned"], {"end": "returned"}):
        r = json.loads(json.dumps(rec))
        r["sections"]["G"][0]["end"] = end
        expect_refuse(gate_outcome(exp, r, "G"), "BAD_TRACE")
        note = exp.check_metrics({"m": 1.0, "coverage_trace": r})["G:exercises"]["note"]
        expect(note.startswith("[V5:BAD_TRACE]"), note)

@case("X105d", "scoring", "a /3 trace carrying a retired note (PROFILER_LOST) or problem (FOREIGN_PROFILER) -> BAD_TRACE")
def x105d():
    exp, rec = _genuine_trace()
    r = json.loads(json.dumps(rec))
    r["sections"]["G"][0]["notes"] = ["[V5:PROFILER_LOST] a retired note"]
    expect_refuse(gate_outcome(exp, r, "G"), "BAD_TRACE")
    r = json.loads(json.dumps(rec))
    r["problems"] = ["[V5:FOREIGN_PROFILER] a retired problem"]
    expect_refuse(gate_outcome(exp, r, "G"), "BAD_TRACE")

@case("X109b", "scoring", "an old trace scored against a gates block that also adds a declared target -> STALE_TRACE")
def x109b():
    _, rec = _genuine_trace()
    expect_refuse(gate_outcome(EXP("FG"), rec, "G"), "STALE_TRACE")

@case("X117d", "scoring", "a smoke result carrying a trace that refuses NOT_EXERCISED -> the check_metrics note starts with [V5:NOT_EXERCISED]")
def x117d():
    exp = EXP("X122")
    note = exp.check_metrics({"m": 0.0, "smoke": True, "coverage_trace": load_trace("X122")})["G:exercises"]["note"]
    expect(note.startswith("[V5:NOT_EXERCISED]"), note)

@case("X120", "sections", "gate A declares f, gate B declares g; cov.run('A', g) then cov.run('B', f) -> A: NOT_EXERCISED")
def x120():
    exp = EXP("X120")
    with P.coverage_trace(exp) as cov:
        cov.run("A", fx_v5f.g)
        cov.run("B", fx_v5f.f)
    out = score(exp, cov.record())
    expect_refuse(out, "NOT_EXERCISED")
    expect("gate 'A'" in out[2], out[2][:200])

@case("X121", "sections", "X[f] with section 'Y', Y[g] with section 'X'; the harness opens each gate by gate name -> X: NOT_EXERCISED")
def x121():
    exp = EXP("X121")
    with P.coverage_trace(exp) as cov:
        cov.run("X", fx_v5f.f)
        cov.run("Y", fx_v5f.g)
    out = score(exp, cov.record())
    expect_refuse(out, "NOT_EXERCISED")
    expect("gate 'X'" in out[2], out[2][:200])

@case("X122b", "scoring", "X122 plus a swallowed NESTED_SECTION -> NESTED_SECTION")
def x122b():
    exp = EXP("X122")
    with P.coverage_trace(exp) as cov:
        def body():
            fx_v5f.f()
            try:
                cov.run("G", fx_v5f.f)
            except GateSpecError:
                pass
        cov.run("G", body)
    expect_refuse(score(exp, cov.record(), m=0.0), "NESTED_SECTION")

@case("X123", "attribution", "two live threads each open a section and dispatch g once through their own loop's call_soon -> NOT_EXERCISED; uncredited.dispatched == {g:2}; the message prints 2")
def x123():
    import asyncio
    exp = EXP("A_Gdecl")
    bar = threading.Barrier(2)
    errs = []
    with P.coverage_trace(exp) as cov:
        def worker():
            L = asyncio.new_event_loop()
            try:
                async def main():
                    L.call_soon(fx_v5f.g)
                    await asyncio.sleep(0)
                def body():
                    bar.wait(30)
                    L.run_until_complete(main())
                    bar.wait(30)
                cov.run("A", body)
            except Exception as e:                      # noqa: BLE001
                errs.append(repr(e))
            finally:
                L.close()
        ts = [threading.Thread(target=worker) for _ in range(2)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(30)
    rec = cov.record()
    expect(not errs, f"{errs}")
    out = score(exp, rec)
    expect_refuse(out, "NOT_EXERCISED")
    expect(rec["uncredited"]["dispatched"] == {"fx_v5f:g": 2}, f"uncredited {rec['uncredited']}")
    expect("dispatched {'fx_v5f:g': 2}" in out[2], out[2][:300])

@case("X133", "lifecycle", "an audit hook refuses the second __code__ write mid-mint -> enter raises the hook's error; retry REENTRY; record() TRACE_INCOMPLETE; a later trace PASS; code restored")
def x133():
    class Refused(Exception):
        pass
    me = threading.get_ident()
    st = {"n": 0, "armed": True}
    def hook(event, args):
        if (st["armed"] and event == "object.__setattr__" and threading.get_ident() == me
                and len(args) >= 2 and args[1] == "__code__"):
            st["n"] += 1
            if st["n"] == 2:
                st["armed"] = False
                raise Refused("the second __code__ write is refused")
    sys.addaudithook(hook)
    try:
        cov = P.coverage_trace(EXP("FG"))
        try:
            cov.__enter__()
            raise AssertionError("enter did not raise")
        except Refused:
            pass
        raises_code(cov.__enter__, "REENTRY")
        raises_code(cov.record, "TRACE_INCOMPLETE")
    finally:
        st["armed"] = False
    del cov
    gc.collect()
    exp = EXP("F")
    with P.coverage_trace(exp) as cov2:
        cov2.run("G", fx_v5f.f)
    expect_pass(score(exp, cov2.record()), {"G": {"fx_v5f:f": 1}})
    for k in (("fx_v5f", "f"), ("fx_v5f", "g")):
        expect(ORIG[k][0].__code__ is ORIG[k][1], f"{k} not restored")

@case("X135", "confirmation", "the id-3 tool calls PyThreadState_SetAsyncExc at the target's PY_START -> NOT_EXERCISED; the body never ran")
def x135():
    import ctypes
    class Async(Exception):
        pass
    exp = EXP("T135")
    box = []
    tool = FaultTool()
    try:
        with P.coverage_trace(exp) as cov:
            code = fx_b1.t135.__code__
            def on_start(c, off):
                if c is code:
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(threading.get_ident()), ctypes.py_object(Async))
            tool.on(code, MON.events.PY_START, on_start)
            def body():
                try:
                    fx_b1.t135(box)
                except Async:
                    pass
            try:
                cov.run("G", body)
            finally:
                tool.off(code)
    finally:
        tool.close()
    expect(box == [], "the body ran")
    expect_refuse(score(exp, cov.record()), "NOT_EXERCISED")

@case("X137", "monitoring", "inside G: call f, clear styxx's local events on g's minted code, call g -> NOT_EXERCISED for g; the message and notes contain MONITOR_LOST")
def x137():
    exp = EXP("FG")
    with P.coverage_trace(exp) as cov:
        def body():
            fx_v5f.f()
            MON.set_local_events(P._v5_state()["tool"], fx_v5f.g.__code__, 0)
            fx_v5f.g()
        cov.run("G", body)
    rec = cov.record()
    out = score(exp, rec)
    expect_refuse(out, "NOT_EXERCISED")
    expect("MONITOR_LOST" in out[2], out[2][:300])
    expect(any(n.startswith("[V5:MONITOR_LOST]") for n in rec["sections"]["G"][0]["notes"]), f"notes {rec['sections']}")

@case("X139", "mutex", "the id-3 tool, at PY_START of _enter_txn, runs `with coverage_trace(exp2): pass` on the same thread -> the nested enter REENTRANT; the outer trace PASS")
def x139():
    exp, exp2 = EXP("F"), EXP("G_ONLY") if "G_ONLY" in PREREGS else EXP("F")
    code = P._v5_faultpoints()["_enter_txn"]
    got = []
    tool = FaultTool()
    def on_start(c, off):
        if c is code and not got:
            try:
                with P.coverage_trace(exp2):
                    pass
                got.append(None)
            except GateSpecError as e:
                got.append(code_of(e))
    try:
        tool.on(code, MON.events.PY_START, on_start)
        cov = P.coverage_trace(exp)
        try:
            cov.__enter__()
        finally:
            tool.off(code)
        cov.run("G", fx_v5f.f)
        cov.__exit__(None, None, None)
    finally:
        tool.close()
    expect(got == ["REENTRANT"], f"the nested enter gave {got}")
    expect_pass(score(exp, cov.record()), {"G": {"fx_v5f:f": 1}})

def _x138(frozen_clock):
    exp1 = EXP("F")
    cov1 = P.coverage_trace(exp1)
    cov1.__enter__()
    cov1.run("G", fx_v5f.f)
    blocking, waiter_started = threading.Event(), threading.Event()
    code = P._v5_faultpoints()["_exit_txn"]
    out = {}
    pc = time.perf_counter
    real_sleep = time.sleep                        # the tool's own wait never uses a replaced time.sleep
    tool = FaultTool()
    def on_start(c, off):
        if c is code and not blocking.is_set():
            blocking.set()
            waiter_started.wait(30)
            t0 = pc()
            while pc() - t0 < 11.0:
                real_sleep(0.05)
    sleeps = [0]
    def waiter():
        blocking.wait(30)
        saved = (time.monotonic, time.sleep)
        if frozen_clock:
            real_sleep = time.sleep
            def counting_sleep(x):
                sleeps[0] += 1
                return real_sleep(x)
            time.monotonic = lambda: 0.0
            time.sleep = counting_sleep
        try:
            cov2 = P.coverage_trace(EXP("F"))
            waiter_started.set()
            t0 = pc()
            try:
                cov2.__enter__()
                out["code"] = None
            except GateSpecError as e:
                out["code"] = code_of(e)
            out["waited"] = pc() - t0
        finally:
            time.monotonic, time.sleep = saved
        out["sleeps"] = sleeps[0]
        blocking.wait(30)
    th = threading.Thread(target=waiter)
    th.start()
    try:
        tool.on(code, MON.events.PY_START, on_start)
        cov1.__exit__(None, None, None)
    finally:
        tool.close()
    th.join(60)
    expect_pass(score(exp1, cov1.record()), {"G": {"fx_v5f:f": 1}})
    expect(out.get("code") == "MACHINERY_BUSY" and out.get("waited", 0) >= 9.5, f"waiter {out}")
    res = {}
    def later():
        e = EXP("F")
        with P.coverage_trace(e) as c:
            c.run("G", fx_v5f.f)
        res["s"] = score(e, c.record())
    t2 = threading.Thread(target=later)
    t2.start()
    t2.join(30)
    expect_pass(res.get("s", ("none",)), {"G": {"fx_v5f:f": 1}})
    return out

@case("X138", "mutex", "the id-3 tool blocks the exit transaction 11 s from the waiter's start -> MACHINERY_BUSY in the waiter after >= 9.5 s; the first trace completes; a new tracer then PASS")
def x138():
    _x138(False)

@case("X138b", "mutex", "X138 with time.monotonic -> lambda: 0.0 and time.sleep -> a counting wrapper for the waiter's wait -> MACHINERY_BUSY after >= 9.5 s; the wrapper called 0 times")
def x138b():
    out = _x138(True)
    expect(out.get("sleeps") == 0, f"the counting sleep was called {out.get('sleeps')} times")

def _cut_moved_case(rebind, restore_before_exit, loop_job=False):
    import asyncio
    exp = EXP("A_F") if loop_job else EXP("F")
    H = asyncio.events.Handle
    BL = asyncio.base_events.BaseEventLoop
    try:
        if not loop_job:
            with P.coverage_trace(exp) as cov:
                def body():
                    rebind()
                    fx_v5f.f()
                    if restore_before_exit:
                        H._run = fx_cutw.ORIG_RUN
                if restore_before_exit:
                    cov.run("G", body)
                else:
                    rebind()
                    cov.run("G", fx_v5f.f)
            rec = cov.record()
        else:
            L = asyncio.new_event_loop()
            try:
                with P.coverage_trace(exp) as cov:
                    rebind()
                    async def other():
                        L.call_soon(fx_v5f.f)
                    async def main():
                        t = asyncio.ensure_future(other())
                        await asyncio.sleep(0)
                        cov.run("A", L._run_once)
                        await t
                    L.run_until_complete(main())
                rec = cov.record()
            finally:
                L.close()
    finally:
        H._run = fx_cutw.ORIG_RUN
        BL._run_once = fx_cutw.ORIG_RUN_ONCE
    return exp, rec

@case("X141", "cut", "the harness rebinds Handle._run to a wrapper during the trace and restores it after exit -> CUT_MOVED")
def x141():
    import asyncio
    exp, rec = _cut_moved_case(lambda: setattr(asyncio.events.Handle, "_run", fx_cutw.w141), False)
    expect_refuse(score(exp, rec), "CUT_MOVED")

@case("X141b", "cut", "Handle._run rebound to a reimplementation inside section G, f called, restored before exit -> CUT_MOVED (the per-hit check)")
def x141b():
    import asyncio
    exp, rec = _cut_moved_case(lambda: setattr(asyncio.events.Handle, "_run", fx_cutw.w141b), True)
    expect_refuse(score(exp, rec), "CUT_MOVED")

@case("X141c", "cut", "after __enter__, BaseEventLoop._run_once rebound to W (runs ready callbacks, no restore); A in a task of L calls L._run_once(), whose job calls f; restored after exit -> CUT_MOVED")
def x141c():
    import asyncio
    exp, rec = _cut_moved_case(lambda: setattr(asyncio.base_events.BaseEventLoop, "_run_once", fx_cutw.w141c), False, loop_job=True)
    expect_refuse(score(exp, rec), "CUT_MOVED")

@sub("X142")
def _sub_x142():
    from importlib.machinery import SourceFileLoader
    spec = importlib.util.spec_from_loader("v5f_copy_b", SourceFileLoader("v5f_copy_b", IMPL_PATH))
    B = importlib.util.module_from_spec(spec)
    sys.modules["v5f_copy_b"] = B
    spec.loader.exec_module(B)
    expA = EXP("A_F")
    covA = P.coverage_trace(expA)
    covA.__enter__()
    toolA = P._v5_state()["tool"]
    expB = B.Experiment(os.path.join(REPO, "PREREG_A_G.md"))
    with B.coverage_trace(expB) as covB:
        covB.run("A", fx_v5f.g)
    toolB = B._v5_state()["tool"]
    covA.run("A", fx_v5f.f)
    covA.__exit__(None, None, None)
    recA, recB = covA.record(), covB.record()
    def sc(E, exp, rec):
        try:
            v = exp.score({"m": 1.0, "coverage_trace": rec})
            return ["PASS", v.coverage]
        except E.GateSpecError as e:
            return ["REFUSE", code_of(e)]
    return {"A": sc(P, expA, recA), "B": sc(B, expB, recB), "tools": [toolA, toolB],
            "A_lost": any(n.startswith("[V5:MONITOR_LOST]") for o in recA["sections"]["A"] for n in o["notes"])}

@case("X142", "monitoring", "fresh subprocess: a second copy loaded under another name; A holds a tracer open, B enters and exits one on g; then A calls f and exits -> both PASS; tools 4 and 3; no MONITOR_LOST in A")
def x142():
    r = run_sub("X142")
    expect(r == {"A": ["PASS", {"A": {"fx_v5f:f": 1}}], "B": ["PASS", {"A": {"fx_v5f:g": 1}}], "tools": [4, 3],
                 "A_lost": False}, f"{r}")

@sub("X142b")
def _sub_x142b():
    n = {"eq": 0}
    class N(str):
        def __eq__(self, other):
            n["eq"] += 1
            return True
        __hash__ = str.__hash__
    name = N("other")
    MON.use_tool_id(4, name)
    def cb(*a):
        return None
    MON.register_callback(4, MON.events.RAISE, cb)
    exp = EXP("F")
    with P.coverage_trace(exp) as cov:
        cov.run("G", fx_v5f.f)
    rec = cov.record()
    tool = P._v5_state()["tool"]
    eq = n["eq"]
    prev = MON.register_callback(4, MON.events.RAISE, None)
    MON.register_callback(4, MON.events.RAISE, prev)
    return {"score": _outcome_json(score(exp, rec)), "tool": tool, "eq": eq,
            "id4_name_same": MON.get_tool(4) is name, "id4_cb_own": prev is cb}

@case("X142b", "monitoring", "fresh subprocess: another tool takes id 4 as N('other') (a str subclass whose __eq__ returns True and counts) -> PASS {f:1}; tool 3; the counter 0; id 4 untouched")
def x142b():
    r = run_sub("X142b")
    expect(r == {"score": ["PASS", {"G": {"fx_v5f:f": 1}}], "tool": 3, "eq": 0, "id4_name_same": True,
                 "id4_cb_own": True}, f"{r}")

def _binding_sub(patch, then_reload=False):
    """X156/X156b/X37b/X156c/X156d's subprocess body: returns the refusal code of coverage_trace()
    (twice for X156), and whether scoring works."""
    out = {}
    if patch == "set_events":
        real = MON.set_events
        MON.set_events = lambda *a: real(*a)
    elif patch == "version":
        class VI(tuple):
            pass
        sys.version_info = VI((sys.version_info[0], sys.version_info[1], 99, "final", 0))
    elif patch == "reload_chain":
        P.coverage_trace(EXP("F"))
        import itertools
        class Chain(itertools.chain):
            pass
        itertools.chain = Chain
        importlib.reload(P)
    codes = []
    for _ in range(2):
        try:
            P.coverage_trace(EXP("F"))
            codes.append(None)
        except P.GateSpecError as e:                # after a reload, the module's own (new) class
            codes.append(code_of(e))
            out.setdefault("message", str(e))
    out["codes"] = codes
    try:
        v = P.Experiment(os.path.join(REPO, "PREREG_F.md")).score({"m": 1.0, "coverage_trace": load_trace("F")})
        out["scoring"] = ["PASS", v.coverage]
    except P.GateSpecError as e:
        out["scoring"] = ["REFUSE", code_of(e)]
    return out

@sub("X156")
def _sub_x156():
    return _binding_sub("set_events")

@sub("X156b")
def _sub_x156b():
    return _binding_sub(None)

@sub("X37b")
def _sub_x37b():
    return _binding_sub("version")

@sub("X156c")
def _sub_x156c():
    return _binding_sub("reload_chain")

@sub("X156d")
def _sub_x156d():
    return _binding_sub(None)

def run_sub_patched(mode, patch):
    r = subprocess.run([sys.executable, RUNNER] + _impl_args() + ["--pre-import-patch", patch, "--sub", mode],
                       capture_output=True, text=True, timeout=120)
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("{")]
    expect(r.returncode == 0 and lines, f"subprocess {mode}: rc {r.returncode}\n{r.stderr[-2000:]}")
    return json.loads(lines[-1])

_SCORING_PASS = ["PASS", {"G": {"fx_v5f:f": 1}}]

@case("X156", "binding", "fresh subprocess: before the first coverage_trace(), sys.monitoring.set_events replaced by a pure-Python pass-through -> UNSUPPORTED_VERSION, and again at a second call")
def x156():
    r = run_sub("X156")
    expect(r["codes"] == ["UNSUPPORTED_VERSION", "UNSUPPORTED_VERSION"] and r["scoring"] == _SCORING_PASS, f"{r}")

@case("X156b", "binding", "fresh subprocess: before import, itertools.chain replaced by a Python subclass -> UNSUPPORTED_VERSION naming itertools.chain; scoring works")
def x156b():
    r = run_sub_patched("X156b", "chain")
    expect(r["codes"][0] == "UNSUPPORTED_VERSION" and "itertools.chain" in r.get("message", "")
           and r["scoring"] == _SCORING_PASS, f"{r}")

@case("X37b", "binding", "fresh subprocess: after import, sys.version_info replaced by a tuple subclass with micro 99 -> UNSUPPORTED_VERSION; scoring works")
def x37b():
    r = run_sub("X37b")
    expect(r["codes"][0] == "UNSUPPORTED_VERSION" and r["scoring"] == _SCORING_PASS, f"{r}")

@case("X156c", "binding", "fresh subprocess: one coverage_trace() binds; itertools.chain replaced by a subclass; importlib.reload; coverage_trace() again -> UNSUPPORTED_VERSION; scoring works")
def x156c():
    r = run_sub("X156c")
    expect(r["codes"][0] == "UNSUPPORTED_VERSION" and r["scoring"] == _SCORING_PASS, f"{r}")

@case("X156d", "binding", "fresh subprocess: before import, collections.deque replaced by a subclass named deque whose __init__ drops maxlen -> UNSUPPORTED_VERSION")
def x156d():
    r = run_sub_patched("X156d", "deque")
    expect(r["codes"][0] == "UNSUPPORTED_VERSION" and r["scoring"] == _SCORING_PASS, f"{r}")


# -- New violation cases, batch 2a: the id-5 injector, the id-3 tool's holds, and instruction sweeps -----
class Injected(Exception):
    """The exam's injected fault."""

class Injector:
    """The frozen id-5 injector (harness rules, "Injector rules"): INSTRUCTION events on the code objects
    _v5_faultpoints() returns at arming, filtered to one thread's live ident; restart_events() first.
    on_instr(code, offset) is called for every instruction of an armed code on that thread."""
    def __init__(self, keys, ident, on_instr, tid=5):
        self.t, self.ident, self.on_instr = tid, ident, on_instr
        fp = P._v5_faultpoints()
        self.codes = {id(fp[k]): fp[k] for k in keys}
        MON.use_tool_id(tid, "exam-injector")
        MON.restart_events()
        MON.register_callback(tid, MON.events.INSTRUCTION, self._cb)
        for c in self.codes.values():
            MON.set_local_events(tid, c, MON.events.INSTRUCTION)
    def _cb(self, code, offset):
        if id(code) in self.codes and threading.get_ident() == self.ident:
            return self.on_instr(code, offset)
    def close(self):
        for c in self.codes.values():
            MON.set_local_events(self.t, c, 0)
        MON.set_events(self.t, 0)
        MON.register_callback(self.t, MON.events.INSTRUCTION, None)
        MON.free_tool_id(self.t)

SWEEP_COUNTS = {}

def instruction_sweep(key, trial, max_trials=3000):
    """An instruction sweep over machinery function `key` (harness rules, "Instruction sweeps"). trial(k,
    arm) runs trial k: it starts its thread T, calls arm(T.ident, interference) before T reaches F, runs
    to the end and returns (ok, detail). Trials run k = 1, 2, ... until a trial in which T executes
    fewer than k instructions of F; that trial is not counted. Returns (counted, failures)."""
    failures, k = [], 1
    while k <= max_trials:
        box = {"n": 0}
        inj = []
        def arm(ident, interference, _k=k, _box=box):
            def on_instr(code, offset):
                _box["n"] += 1
                if _box["n"] == _k:
                    th = threading.Thread(target=interference)
                    th.start()
                    th.join(WATCHDOG_S)
            inj.append(Injector([key], ident, on_instr))
        try:
            ok, detail = trial(k, arm)
        finally:
            for i in inj:
                i.close()
        if box["n"] < k:
            SWEEP_COUNTS.setdefault(key, []).append(k - 1)
            return k - 1, failures
        if not ok:
            failures.append((k, detail))
        k += 1
    raise AssertionError(f"sweep over {key}: more than {max_trials} trials")

def notes_of(rec, sec):
    return [n for o in rec["sections"].get(sec, []) for n in o["notes"]]

def lost(rec, sec):
    return any(n.startswith("[V5:MONITOR_LOST]") for n in notes_of(rec, sec))

def envelope_ok(rec, base):
    """I6: counts <= the fault-free counts; each end in {fault-free end, raised, open}; notes within the
    fault-free notes plus OPEN_AT_EXIT; problems within the fault-free problems plus REENTRANT and
    MACHINERY_BUSY. `rec` None means record() refused TRACE_INCOMPLETE or TRACE_ACTIVE (allowed)."""
    if rec is None:
        return True, ""
    for sec, ops in rec["sections"].items():
        bops = base["sections"].get(sec, [])
        bcalls = collections.Counter()
        for o in bops:
            bcalls.update(o["calls"])
        calls = collections.Counter()
        for o in ops:
            calls.update(o["calls"])
        if any(v > bcalls.get(k, 0) for k, v in calls.items()):
            return False, f"over-count in {sec}: {dict(calls)} > {dict(bcalls)}"
        bends = {o["end"] for o in bops} | {"raised", "open"}
        if any(o["end"] not in bends for o in ops):
            return False, f"end outside the envelope in {sec}"
        bnotes = {_CODE.match(n).group(1) for o in bops for n in o["notes"]} | {"OPEN_AT_EXIT"}
        if any(_CODE.match(n).group(1) not in bnotes for o in ops for n in o["notes"]):
            return False, f"a note outside the envelope in {sec}: {[o['notes'] for o in ops]}"
    bprob = {_CODE.match(p).group(1) for p in base["problems"]} | {"REENTRANT", "MACHINERY_BUSY"}
    if any(_CODE.match(p).group(1) not in bprob for p in rec["problems"]):
        return False, f"a problem outside the envelope: {rec['problems']}"
    return True, ""

def record_or_none(cov):
    try:
        return cov.record()
    except GateSpecError as e:
        if code_of(e) in ("TRACE_INCOMPLETE", "TRACE_ACTIVE"):
            return None
        raise

def state_quiet():
    st = P._v5_state()
    return st["anchors"] == 0 and st["global_events"] == 0, st

@case("X92b", "fault", "during exit the id-5 injector raises Injected in _retire at the first instruction at which f.__code__ is again the original -> that trace TRACE_INCOMPLETE; a later trace PASS {f:1}")
def x92b():
    exp = EXP("F")
    orig = ORIG[("fx_v5f", "f")][1]
    cov = P.coverage_trace(exp)
    cov.__enter__()
    cov.run("G", fx_v5f.f)
    fired = []
    def on_instr(code, offset):
        if not fired and fx_v5f.f.__code__ is orig:
            fired.append(offset)
            raise Injected()
    inj = Injector(["_retire"], threading.get_ident(), on_instr)
    try:
        try:
            cov.__exit__(None, None, None)
        except Injected:
            pass
    finally:
        inj.close()
    expect(fired, "the injector never fired")
    raises_code(cov.record, "TRACE_INCOMPLETE")
    del cov
    gc.collect()
    exp2 = EXP("F")
    with P.coverage_trace(exp2) as c2:
        c2.run("G", fx_v5f.f)
    expect_pass(score(exp2, c2.record()), {"G": {"fx_v5f:f": 1}})

@case("X131", "fault", "the id-5 injector raises Injected(Exception) at the first instruction of _provenance after its entry (RESUME) -> Injected from __enter__ (not a GateSpecError); nothing minted")
def x131():
    import dis
    code = P._v5_faultpoints()["_provenance"]
    resume = {i.offset for i in dis.get_instructions(code) if i.opname == "RESUME"}
    before = P._v5_state()["mints"]
    fired = []
    def on_instr(c, offset):
        if not fired and offset not in resume:
            fired.append(offset)
            raise Injected()
    cov = P.coverage_trace(EXP("F"))
    inj = Injector(["_provenance"], threading.get_ident(), on_instr)
    try:
        try:
            cov.__enter__()
            raise AssertionError("__enter__ returned")
        except Injected:
            pass
    finally:
        inj.close()
        cov.__exit__(None, None, None)
    expect(P._v5_state()["mints"] == before, "something was minted")

@case("X132", "fault", "the injector faults every line of _open and _detach in turn, on a worker thread -> each faulted trace refuses or scores within I6; after exit anchors == 0; a later trace PASS")
def x132():
    base_exp = EXP("F")
    with P.coverage_trace(base_exp) as c0:
        c0.run("G", fx_v5f.f)
    base = c0.record()
    fp = P._v5_faultpoints()
    bad = []
    for key in ("_open", "_detach"):
        lines = sorted({ln for _, _, ln in fp[key].co_lines() if ln is not None})
        for line in lines:
            offs = {s for s, e, ln in fp[key].co_lines() if ln == line}
            exp = EXP("F")
            cov = P.coverage_trace(exp)
            cov.__enter__()
            go, fired = threading.Event(), []
            def work():
                go.wait(30)
                try:
                    cov.run("G", fx_v5f.f)
                except (Injected, GateSpecError):
                    pass
            th = threading.Thread(target=work)
            th.start()
            def on_instr(code, offset, _offs=offs):
                if not fired and any(s <= offset < s + 2 for s in _offs):
                    fired.append(offset)
                    raise Injected()
            inj = Injector([key], th.ident, on_instr)
            try:
                go.set()
                th.join(WATCHDOG_S)
            finally:
                inj.close()
            try:
                cov.__exit__(None, None, None)
            except Exception:                         # noqa: BLE001
                pass
            rec = record_or_none(cov)
            ok, why = envelope_ok(rec, base)
            quiet, st = state_quiet()
            if not ok or not quiet:
                bad.append((key, line, why, st["anchors"]))
    expect(not bad, f"outside I6 or anchors left: {bad[:5]}")
    exp2 = EXP("F")
    with P.coverage_trace(exp2) as c2:
        c2.run("G", fx_v5f.f)
    expect_pass(score(exp2, c2.record()), {"G": {"fx_v5f:f": 1}})

def _x143_trial(k, arm):
    expA, expB = EXP("A_T"), EXP("B_G")
    P_, Q_ = P.coverage_trace(expA), P.coverage_trace(expB)
    P_.__enter__(); Q_.__enter__()
    inB, release = threading.Event(), threading.Event()
    def t2():
        def body():
            inB.set()
            release.wait(30)
        Q_.run("B", body)
    T2 = threading.Thread(target=t2)
    T2.start()
    inB.wait(30)
    go = threading.Event()
    def t1():
        go.wait(30)
        def body():
            try:
                fx_v5f.t()
            except ValueError:
                pass
        P_.run("A", body)
    T1 = threading.Thread(target=t1)
    T1.start()
    def interference():
        release.set()
        T2.join(WATCHDOG_S)
    arm(T1.ident, interference)
    go.set()
    T1.join(WATCHDOG_S)
    release.set(); T2.join(WATCHDOG_S)
    P_.__exit__(None, None, None); Q_.__exit__(None, None, None)
    rec = P_.record()
    out = score(expA, rec)
    ok = out[0] == "PASS" and out[1] == {"A": {"fx_v5f:t": 1}} and not lost(rec, "A")
    return ok, f"{out[:2]} lost={lost(rec, 'A')}"

@case("X143", "sweep", "an instruction sweep over _commit on T1 while T2's section B closes (the last other anchor) -> every trial: A PASS {t:1}, no MONITOR_LOST")
def x143():
    n, fails = instruction_sweep("_commit", _x143_trial)
    expect(n > 0 and not fails, f"{n} trials; failing {fails[:3]}")

@case("X143b", "fault", "X143's setup; the id-3 tool holds T1 at PY_START of _commit until T2's close has cleared the event, then raises Injected at PY_START of T1's _unwind_on -> Injected from run(); body never ran; A end raised; no MONITOR_LOST; anchors 0, global_events 0")
def x143b():
    expA, expB = EXP("A_T"), EXP("B_G")
    P_, Q_ = P.coverage_trace(expA), P.coverage_trace(expB)
    P_.__enter__(); Q_.__enter__()
    inB, release = threading.Event(), threading.Event()
    def t2():
        def body():
            inB.set()
            release.wait(30)
        Q_.run("B", body)
    T2 = threading.Thread(target=t2)
    T2.start()
    inB.wait(30)
    ran, out = [], {}
    go = threading.Event()
    def t1():
        go.wait(30)
        try:
            P_.run("A", lambda: ran.append(1))
            out["r"] = "returned"
        except Injected:
            out["r"] = "Injected"
    T1 = threading.Thread(target=t1)
    T1.start()
    fp = P._v5_faultpoints()
    ccommit, cunw = fp["_commit"], fp["_unwind_on"]
    tool = FaultTool()
    def on_start(code, off):
        if threading.get_ident() != T1.ident:
            return
        if code is ccommit:
            release.set()
            T2.join(WATCHDOG_S)
        elif code is cunw:
            raise Injected()
    try:
        tool.on(ccommit, MON.events.PY_START, on_start)
        tool.on(cunw, MON.events.PY_START, on_start)
        go.set()
        T1.join(WATCHDOG_S)
    finally:
        tool.close()
    P_.__exit__(None, None, None); Q_.__exit__(None, None, None)
    rec = P_.record()
    expect(out.get("r") == "Injected" and not ran, f"run(): {out}, body ran {ran}")
    expect(rec["sections"]["A"][0]["end"] == "raised" and not lost(rec, "A"), f"A {rec['sections']['A']}")
    quiet, st = state_quiet()
    expect(quiet, f"state {st}")

@case("X144", "fault", "the id-3 tool raises Injected at the first return from _unwind_on in cov.run('A', f) -> Injected from run(); f not called; at once anchors 0, global_events 0; after exit A NOT_EXERCISED, end raised, no MONITOR_LOST; a later trace PASS {f:1}")
def x144():
    exp = EXP("A_F")
    code = P._v5_faultpoints()["_unwind_on"]
    ran = []
    fired = []
    tool = FaultTool()
    def on_ret(c, off, val):
        if c is code and not fired:
            fired.append(1)
            raise Injected()
    with P.coverage_trace(exp) as cov:
        try:
            tool.on(code, MON.events.PY_RETURN, on_ret)
            try:
                cov.run("A", lambda: ran.append(1))
                raise AssertionError("run() returned")
            except Injected:
                pass
            quiet, st = state_quiet()
        finally:
            tool.close()
    rec = cov.record()
    expect(not ran and quiet, f"body ran {ran}; state {st}")
    expect_refuse(score(exp, rec), "NOT_EXERCISED")
    expect(rec["sections"]["A"][0]["end"] == "raised" and not lost(rec, "A"), f"A {rec['sections']['A']}")
    exp2 = EXP("A_F")
    with P.coverage_trace(exp2) as c2:
        c2.run("A", fx_v5f.f)
    expect_pass(score(exp2, c2.record()), {"A": {"fx_v5f:f": 1}})

def _x145_trial(k, arm):
    expA, expB = EXP("A_T"), EXP("B_G")
    P_, Q_ = P.coverage_trace(expA), P.coverage_trace(expB)
    P_.__enter__(); Q_.__enter__()
    started, t2_done = threading.Event(), threading.Event()
    T1box = []
    def t1():
        def body():
            started.set()
            t2_done.wait(30)
            try:
                fx_v5f.t()
            except ValueError:
                pass
        P_.run("A", body)
    def interference():
        th = threading.Thread(target=t1)
        T1box.append(th)
        th.start()
        started.wait(30)
    go = threading.Event()
    def t2():
        go.wait(30)
        Q_.run("B", fx_v5f.g)
        t2_done.set()
    T2 = threading.Thread(target=t2)
    T2.start()
    arm(T2.ident, interference)
    go.set()
    T2.join(WATCHDOG_S)
    t2_done.set()
    for th in T1box:
        th.join(WATCHDOG_S)
    P_.__exit__(None, None, None); Q_.__exit__(None, None, None)
    if not T1box:
        return True, "interference never ran"
    rec = P_.record()
    out = score(expA, rec)
    ok = out[0] == "PASS" and out[1] == {"A": {"fx_v5f:t": 1}} and not lost(rec, "A")
    return ok, f"{out[:2]} lost={lost(rec, 'A')}"

@case("X145", "sweep", "an instruction sweep over _unwind_off on T2 closing B, the last anchor; the interference runs A on T1 until its body starts; t raises inside A's body after T2's run() returned -> every trial: A PASS {t:1}, no MONITOR_LOST")
def x145():
    n, fails = instruction_sweep("_unwind_off", _x145_trial)
    expect(n > 0 and not fails, f"{n} trials; failing {fails[:3]}")

def _hold_case(hold_key, event, t1_action, main_between, filt=None):
    """The id-3 tool holds T1 at `event` of `hold_key` (optionally filtered by filt(args)) until
    main_between() has run on the main thread; then T1 is released and joined."""
    code = P._v5_faultpoints()[hold_key]
    held, release = threading.Event(), threading.Event()
    out = {}
    go = threading.Event()
    def t1():
        go.wait(30)
        try:
            out["r"] = ("returned", t1_action())
        except GateSpecError as e:
            out["r"] = ("refused", code_of(e))
        except Exception as e:                        # noqa: BLE001
            out["r"] = ("raised", type(e).__name__)
    T1 = threading.Thread(target=t1)
    T1.start()
    tool = FaultTool()
    def cb(c, off, *args):
        if c is code and threading.get_ident() == T1.ident and not held.is_set() and (filt is None or filt(args)):
            held.set()
            release.wait(60)
    try:
        tool.on(code, event, cb)
        go.set()
        held.wait(30)
        main_between()
        release.set()
        T1.join(WATCHDOG_S)
    finally:
        release.set()
        tool.close()
    return out.get("r"), held.is_set()

@case("X146", "races", "the id-3 tool holds T1 at PY_START of _commit until the main thread's cov.__exit__() has returned -> T1 TRACE_INACTIVE; anchors 0, global_events 0; A end open with OPEN_AT_EXIT; problem TRACE_INACTIVE; score TRACE_INACTIVE")
def x146():
    exp = EXP("A_F")
    cov = P.coverage_trace(exp)
    cov.__enter__()
    r, held = _hold_case("_commit", MON.events.PY_START, lambda: cov.run("A", fx_v5f.f),
                         lambda: cov.__exit__(None, None, None))
    expect(held and r == ("refused", "TRACE_INACTIVE"), f"T1 {r} held {held}")
    quiet, st = state_quiet()
    expect(quiet, f"state {st}")
    rec = cov.record()
    a = rec["sections"]["A"][0]
    expect(a["end"] == "open" and any(n.startswith("[V5:OPEN_AT_EXIT]") for n in a["notes"]), f"A {a}")
    expect(_problem_codes(rec) == ["TRACE_INACTIVE"], f"problems {rec['problems']}")
    expect_refuse(score(exp, rec), "TRACE_INACTIVE")

@case("X146b", "races", "the id-3 tool holds T1 at its CALL of _get_running_loop in _open until cov.__exit__() has returned -> T1 TRACE_INACTIVE; anchors 0, global_events 0; problem TRACE_INACTIVE recorded")
def x146b():
    import asyncio
    grl = asyncio.events._get_running_loop
    exp = EXP("A_F")
    cov = P.coverage_trace(exp)
    cov.__enter__()
    r, held = _hold_case("_open", MON.events.CALL, lambda: cov.run("A", fx_v5f.f),
                         lambda: cov.__exit__(None, None, None), filt=lambda args: args and args[0] is grl)
    expect(held and r == ("refused", "TRACE_INACTIVE"), f"T1 {r} held {held}")
    quiet, st = state_quiet()
    expect(quiet, f"state {st}")
    expect("TRACE_INACTIVE" in _problem_codes(cov.record()), "no TRACE_INACTIVE recorded")

@case("X146c", "races", "T1 drives co = cov.run_async('A', af) (cov entered by __enter__); held at PY_START of _commit; main drops cov, gc.collect(), enters and exits a tracer on g (prunes A's dead core) -> co raises TRACE_INACTIVE; anchors 0, global_events 0")
def x146c():
    import asyncio
    exp = EXP("A_F")
    cov = P.coverage_trace(exp)
    cov.__enter__()
    async def af():
        return fx_v5f.f()
    co = cov.run_async("A", af)
    del cov
    def main_between():
        gc.collect()
        e2 = EXP("A_Gdecl")
        with P.coverage_trace(e2):
            pass
    def t1_action():
        return asyncio.run(co)
    r, held = _hold_case("_commit", MON.events.PY_START, t1_action, main_between)
    expect(held and r == ("refused", "TRACE_INACTIVE"), f"co {r} held {held}")
    quiet, st = state_quiet()
    expect(quiet, f"state {st}")

@case("X146d", "races", "X146's hold, then the id-5 injector raises Injected in _commit once anchors is 1, and at the first instruction of _detach in the finally; then a tracer on g -> Injected from run(); anchors 1 right after; 0 (and global_events 0) after g's transaction")
def x146d():
    exp = EXP("A_F")
    cov = P.coverage_trace(exp)
    cov.__enter__()
    state = {"commit": False, "detach": False}
    inj = []
    def on_instr(code, offset):
        fp = P._v5_faultpoints()
        if code is fp["_commit"] and not state["commit"] and P._v5_state()["anchors"] == 1:
            state["commit"] = True
            raise Injected()
        if code is fp["_detach"] and state["commit"] and not state["detach"]:
            state["detach"] = True
            raise Injected()
    def main_between():
        cov.__exit__(None, None, None)
    def t1_action():
        return cov.run("A", fx_v5f.f)
    # arm the injector on T1 once it exists: _hold_case starts T1; the injector is armed inside main_between's
    # predecessor, the hold (T1 is parked at PY_START of _commit when main_between runs)
    def main_between_and_arm():
        main_between()
        th = [t for t in threading.enumerate() if t is not threading.current_thread() and t.name.startswith("Thread")]
        idents = [t.ident for t in th if t.is_alive()]
        inj.append(Injector(["_commit", "_detach"], idents[-1], on_instr))
    try:
        r, held = _hold_case("_commit", MON.events.PY_START, t1_action, main_between_and_arm)
    finally:
        for i in inj:
            i.close()
    right_after = P._v5_state()["anchors"]
    expect(held and r == ("raised", "Injected"), f"T1 {r}")
    expect(right_after == 1, f"anchors right after: {right_after}")
    e2 = EXP("A_Gdecl")
    with P.coverage_trace(e2):
        pass
    quiet, st = state_quiet()
    expect(quiet, f"state after the second tracer's transaction {st}")

@case("X146e", "races", "the id-3 tool holds T1 at PY_START of _unwind_on (after step 8) until cov.__exit__() has returned; body reads _v5_state() -> run() returns uncredited; in body anchors 0, global_events 0; A end open with OPEN_AT_EXIT")
def x146e():
    exp = EXP("A_F")
    cov = P.coverage_trace(exp)
    cov.__enter__()
    seen = {}
    def body():
        st = P._v5_state()
        seen.update(anchors=st["anchors"], ge=st["global_events"])
        return 146
    r, held = _hold_case("_unwind_on", MON.events.PY_START, lambda: cov.run("A", body),
                         lambda: cov.__exit__(None, None, None))
    expect(held and r == ("returned", 146), f"T1 {r}")
    expect(seen == {"anchors": 0, "ge": 0}, f"in body {seen}")
    a = cov.record()["sections"]["A"][0]
    expect(a["end"] == "open" and any(n.startswith("[V5:OPEN_AT_EXIT]") for n in a["notes"]) and a["calls"] == {},
           f"A {a}")

@case("X147", "races", "200 trials: T1 runs cov.run('A', f) while the main thread calls cov.__exit__() -> each trial (i) TRACE_INACTIVE recorded, or (ii) f's value, no problem, end returned/open, at most {f:1}; always anchors 0, global_events 0, no MONITOR_LOST")
def x147():
    bad = []
    for i in range(200):
        exp = EXP("A_F")
        cov = P.coverage_trace(exp)
        cov.__enter__()
        out = {}
        def t1():
            try:
                out["r"] = ("returned", cov.run("A", fx_v5f.f))
            except GateSpecError as e:
                out["r"] = ("refused", code_of(e))
        T1 = threading.Thread(target=t1)
        T1.start()
        cov.__exit__(None, None, None)
        T1.join(WATCHDOG_S)
        rec = cov.record()
        quiet, st = state_quiet()
        ops = rec["sections"].get("A", [])
        calls = collections.Counter()
        for o in ops:
            calls.update(o["calls"])
        if out.get("r") == ("refused", "TRACE_INACTIVE"):
            ok = "TRACE_INACTIVE" in _problem_codes(rec)
        else:
            ok = (out.get("r") == ("returned", 1) and rec["problems"] == [] and
                  all(o["end"] in ("returned", "open") for o in ops) and calls.get("fx_v5f:f", 0) <= 1)
        if not ok or not quiet or lost(rec, "A"):
            bad.append((i, out.get("r"), rec["problems"], st))
    expect(not bad, f"{len(bad)} of 200 trials outside the set: {bad[:3]}")

def _x148_trial(k, arm):
    exp = EXP("A_F")
    cov = P.coverage_trace(exp)
    cov.__enter__()
    go = threading.Event()
    def t1():
        go.wait(30)
        cov.run("A", fx_v5f.f)
    T1 = threading.Thread(target=t1)
    T1.start()
    done = []
    def interference():
        cov.__exit__(None, None, None)
        done.append(1)
    arm(T1.ident, interference)
    go.set()
    T1.join(WATCHDOG_S)
    if not done:
        cov.__exit__(None, None, None)
    rec = cov.record()
    out = score(exp, rec)
    ok = out[0] == "PASS" and out[1] == {"A": {"fx_v5f:f": 1}} and not lost(rec, "A")
    return ok, f"{out[:2]} lost={lost(rec, 'A')}"

@case("X148", "sweep", "an instruction sweep over _detach on T1 (A's close); the interference runs cov.__exit__() to completion -> every trial: A PASS {f:1}, no MONITOR_LOST")
def x148():
    n, fails = instruction_sweep("_detach", _x148_trial)
    expect(n > 0 and not fails, f"{n} trials; failing {fails[:3]}")

def _x152_trial_for(key):
    def trial(k, arm):
        exp = EXP("A_F")
        bad = []
        with P.coverage_trace(exp) as cov:
            go = threading.Event()
            def t1():
                go.wait(30)
                cov.run("A", fx_v5f.f)
            T1 = threading.Thread(target=t1)
            T1.start()
            def interference():
                st = P._v5_state()
                if st["anchors"] == 0 and st["global_events"] != 0:
                    bad.append(dict(st))
            arm(T1.ident, interference)
            go.set()
            T1.join(WATCHDOG_S)
        return not bad, f"{bad[:1]}"
    return trial

@case("X152", "sweep", "cov.run('A', f); two instruction sweeps, over _detach and over _unwind_off; the interference reads _v5_state() -> no trial reads anchors == 0 with global_events != 0")
def x152():
    for key in ("_detach", "_unwind_off"):
        n, fails = instruction_sweep(key, _x152_trial_for(key))
        expect(n > 0 and not fails, f"{key}: {n} trials; failing {fails[:3]}")

def _x153_trial(k, arm):
    expA, expB = EXP("A_F"), EXP("B_G")
    P_, Q_ = P.coverage_trace(expA), P.coverage_trace(expB)
    P_.__enter__(); Q_.__enter__()
    gate, a_started, b_started = threading.Event(), threading.Event(), threading.Event()
    T2box = []
    def bodyA():
        fx_v5f.f()
        a_started.set()
        gate.wait(30)
    def bodyB():
        fx_v5f.g()
        b_started.set()
        gate.wait(30)
    def interference():
        th = threading.Thread(target=lambda: Q_.run("B", bodyB))
        T2box.append(th)
        th.start()
        b_started.wait(30)
    go = threading.Event()
    def t1():
        go.wait(30)
        P_.run("A", bodyA)
    T1 = threading.Thread(target=t1)
    T1.start()
    arm(T1.ident, interference)
    go.set()
    a_started.wait(30)
    gate.set()
    T1.join(WATCHDOG_S)
    for th in T2box:
        th.join(WATCHDOG_S)
    P_.__exit__(None, None, None); Q_.__exit__(None, None, None)
    if not T2box:
        return True, "interference never ran"
    ra, rb = P_.record(), Q_.record()
    oa, ob = score(expA, ra), score(expB, rb)
    ok = (oa[0] == "PASS" and oa[1] == {"A": {"fx_v5f:f": 1}} and ob[0] == "PASS" and ob[1] == {"B": {"fx_v5f:g": 1}}
          and not lost(ra, "A") and not lost(rb, "B"))
    return ok, f"A {oa[:2]} B {ob[:2]}"

@case("X153", "sweep", "an instruction sweep over _unwind_on on T1 (P's A); the interference runs Q's B on T2 until its body starts -> every trial: A PASS {f:1}, B PASS {g:1}, no MONITOR_LOST")
def x153():
    n, fails = instruction_sweep("_unwind_on", _x153_trial)
    expect(n > 0 and not fails, f"{n} trials; failing {fails[:3]}")

@case("X137d", "monitoring", "P(f, t) and Q(h): inside G call f, set_events(tool, 0), call t (raises out of its body, caught around the call), then a thread runs Q.run('B', h) -> P NOT_EXERCISED for t with MONITOR_LOST; Q PASS {h:1}, no MONITOR_LOST")
def x137d():
    expP, expQ = EXP("FT"), EXP("B_H")
    with P.coverage_trace(expP) as P_, P.coverage_trace(expQ) as Q_:
        def body():
            fx_v5f.f()
            MON.set_events(P._v5_state()["tool"], 0)
            try:
                fx_v5f.t()
            except ValueError:
                pass
            th = threading.Thread(target=lambda: Q_.run("B", fx_b1.h137))
            th.start()
            th.join(WATCHDOG_S)
        P_.run("G", body)
    rp, rq = P_.record(), Q_.record()
    op = score(expP, rp)
    expect_refuse(op, "NOT_EXERCISED")
    expect("fx_v5f:t" in op[2] and lost(rp, "G"), f"P {op[2][:200]} lost={lost(rp, 'G')}")
    expect_pass(score(expQ, rq), {"B": {"fx_b1:h137": 1}})
    expect(not lost(rq, "B"), "Q noted MONITOR_LOST")


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
for _cid in ('X07b / X07c', 'X14b', 'X16b', 'X24c', 'X24d', 'X24e', 'X25c', 'X25d', 'X26c', 'X26d', 'X26e', 'X26f', 'X29b', 'X30d', 'X32d', 'X34b', 'X34c', 'X35', 'X35b', 'X35c', 'X36', 'X55d', 'X57b', 'X57c', 'X58b', 'X59c', 'X59d', 'X65c', 'X65d', 'X65e', 'X65f', 'X65g', 'X76b', 'X78e', 'X78g', 'X83', 'X92c', 'X96c', 'X103b', 'X105d', 'X109b', 'X117d', 'X120', 'X121', 'X122b', 'X123', 'X133', 'X135', 'X137', 'X139', 'X138', 'X138b', 'X141', 'X141b', 'X141c', 'X142', 'X142b', 'X156', 'X156b', 'X37b', 'X156c', 'X156d'):
    TABLE[_cid] = "new violation cases"
for _cid in ('X92b', 'X131', 'X132', 'X143', 'X143b', 'X144', 'X145', 'X146', 'X146b', 'X146c', 'X146d', 'X146e', 'X147', 'X148', 'X152', 'X153', 'X137d'):
    TABLE[_cid] = "new violation cases"
for _cid in ("R05b", "R12", "R13", "R14", "R16", "R18a", "R18b", "R20", "R21", "R22", "X157", "X157b"):
    TABLE[_cid] = "new documented residuals"
for _cid in ("V54", "V55", "V67", "V52", "V28b", "V69b", "V69b-v", "V72", "V73"):
    TABLE[_cid] = "new valid cases"
for _cid in ("V01", "X40", "X55", "X59", "V07", "X33", "X73", "V18", "X76", "X60", "V14", "X109",
             "X90", "X32"):
    TABLE[_cid] = "v5e cases kept (every other v5e case keeps its id and outcome)"
TABLE["X90/X91"] = "v5e cases whose outcome changes"
for _cid in ("V48", "V49"):
    TABLE[_cid] = "new valid cases"                  # V49 replaces X75 and V48 replaces X80 (the delta table)
TABLE["X95"] = "v5e cases whose outcome changes"       # X91's row: same code, the text per case (M8)
TABLE["M10-S0"] = "M10 property (not a table row): _v5_state() before any tracer"

# Placements, from the harness rules' lists (only the cases this runner covers are listed).
MAIN = {"X92b", "X131", "X132", "X143", "X143b", "X144", "X145", "X146", "X146b", "X146c", "X146d", "X146e",
        "X147", "X148", "X152", "X153", "X137d", "X35", "X35b", "X35c", "X65e", "X65f", "X65g", "X141", "X141b", "X141c", "X138", "X138b", "X139",
        "X137c", "X143c", "X59e", "X59e-v", "V67", "V73", "R18a", "R18b", "R20"}
CHILD = {"X137-free"}                                  # the whole case in a fresh subprocess
SPAWNS = {"X36", "X142", "X142b", "X156", "X156b", "X37b", "X156c", "X156d", "R21", "X157", "X157b", "M10-S0", "V69b", "V69b-v", "X156f", "X156g", "X156g-ctl", "X156h", "X156i", "V72"}  # the case body spawns it
SCORING = {"X96c", "X103b", "X105d", "X109b", "X117d", "X95", "X93d", "X93e", "X96d", "X103c", "X112b", "X117b", "X117c", "X117e", "X117f", "X95b",
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
# The delta table's rows ("v5e cases whose outcome changes"; the port table below it) and where each is
# covered, or why it is not run.
DELTA_ROWS = {
    "X75": "retired; replaced by V49 (covered)", "X80": "retired; replaced by V48 (covered)",
    "X81 (<=3.11)": "retired (3.11 refused): covered by X37 on 3.10/3.11",
    "V26": "NOT YET: needs v5e's V26 shape", "V28": "NOT YET: needs v5e's V28 shape",
    "V30": "retired (no epochs); V28b covers hops (covered)",
    "V31": "retired; the leftover check requires getprofile()/gettrace() unchanged (applied to every case)",
    "X82, V33": "NOT YET: needs v5e's shapes (unkeyed on 3.12+)",
    "X95": "covered (X95)", "H1 mutant": "NOT YET: hazard sweeps", "H2 mutant": "NOT YET: hazard sweeps",
    "V34": "covered (the self-trace, V34)", "X91": "covered (X90/X91)",
    "port: X71c": "NOT YET", "port: leftover snapshot": "applied to every case (snap/leftover_diff)",
    "port: self-trace code list": "applied (V34's frozen names)", "port: H1 and H2 mutants": "NOT YET: hazard sweeps",
    "port: H5 (gc cost)": "NOT YET",
}
TABLE_ROWS = {"new violation cases": 137, "new valid cases": 45, "new documented residuals": 12,
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
        "delta_table_rows": DELTA_ROWS,
        "tables_not_yet_covered": ["exam-hole kill cases",
                                   "v5e cases whose outcome changes", "hazard sweeps (H1-H10)",
                                   "mutation audit witnesses not already in the case tables",
                                   "the rest of the new violation and valid cases",
                                   "the v5e cases kept (the v5e case tables)"],
        "instruction_sweeps_counted_trials": SWEEP_COUNTS,
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
