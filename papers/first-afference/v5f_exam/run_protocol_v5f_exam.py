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
_ap.add_argument("--list", action="store_true", help="print the case ids and exit")
_ap.add_argument("--out", default=None)
_ap.add_argument("--make-traces", action="store_true")
_ap.add_argument("--child-case", default=None)
_ap.add_argument("--sub", default=None)
_ap.add_argument("--pre-import-patch", default=None, help="chain|deque: replaced before the implementation is imported (X156b, X156d)")
_ap.add_argument("--deps-path", "--greenlet-path", dest="greenlet_path", default=os.environ.get("V5F_DEPS_PATH"),
                 help="a directory holding the exam's pinned third-party libraries for this interpreter: "
                      "greenlet 3.5.6 (X137f, X158d) and coverage 7.16 (V50)")
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
        a += ["--deps-path", ARGS.greenlet_path]
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
        import enum
        class Color(enum.Enum):
            RED = 1
            def fit(self): return 1
        def _run(cfg):
            import fx_v5f
            return fx_v5f.f() + cfg
        def fw(ev=None, inside=None):
            if ev is not None:
                inside.set()
                ev.wait(30)
            return 36
        E70 = []
        BODY = [0]
        def hbody():
            BODY[0] += 1
            return 1
        def f70(box=None):
            if box is not None:
                E70[0].set()
                E70[1].wait(30)
                raise KeyError("f70")
            return 1
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
        def w61(self):                                 # V61 (and V64, which names V61's wrapper): calls the original
            return ORIG_RUN(self)
        def w62(self):                                 # V62: rebound and restored with no hit between
            return ORIG_RUN(self)
        def w141c(self):                               # X141c: runs ready callbacks, no restore
            for _ in range(len(self._ready)):
                h = self._ready.popleft()
                if not h._cancelled:
                    h._context.run(h._callback, *h._args)
    ''',
    # valid-case fixtures
    "fx_v10b.py": '''
        import sys, types
        def _thing(): return 10
        def __getattr__(name):
            if name == "thing":
                return _thing
            raise AttributeError(name)
        class _M(types.ModuleType):
            pass
        sys.modules[__name__].__class__ = _M
    ''',
    "fx_v11clib.py": '''
        import functools
        def wrap(fn):
            @functools.wraps(fn)
            def w(*a, **k):
                return fn(*a, **k)
            return w
    ''',
    "fx_v11c.py": '''
        import fx_v11clib
        def base(): return 11
        _t = base
        for _ in range(16):
            _t = fx_v11clib.wrap(_t)
        target = _t
    ''',
    "fx_v38lib.py": '''
        import functools
        def logged(fn):
            @functools.wraps(fn)
            def inner(*a, **k):
                return fn(*a, **k)
            return inner
    ''',
    "fx_v38.py": '''
        import functools
        from fx_v38lib import logged
        class Memo:
            def __init__(self, fn):
                functools.update_wrapper(self, fn)
                self.fn = fn
            def __call__(self, *a):
                return self.fn(*a)
        @logged
        @Memo
        def fit(): return 38
    ''',
    "fx_v40.py": '''
        COUNT = {"n": 0}
        def _fit(): return 40
        class Reg:
            def __getattribute__(self, name):
                COUNT["n"] += 1
                raise KeyError(name)
        registry = Reg()
        object.__setattr__(registry, "fit", _fit)
        class Meta(type):
            def __getattribute__(cls, name):
                COUNT["n"] += 1
                raise KeyError(name)
        class K(metaclass=Meta):
            def fit(self): return 41
    ''',
    "fx_v40b.py": '''
        COUNT = {"eq": 0}
        def _fit(): return 40
        class Meta(type):
            def __eq__(cls, other):
                COUNT["eq"] += 1
                raise RuntimeError("the metaclass __eq__ ran")
            __hash__ = type.__hash__
        class Reg(metaclass=Meta):
            pass
        registry = Reg()
        registry.fit = _fit
    ''',
    "fx_v47.py": '''
        COV = None
        def job(x):
            import fx_v5f
            return COV.run("B", fx_v5f.g) + x
    ''',
    "fx_x30b.py": '''
        import fx_v11clib
        def _deep_inner(x): return x
        _t = _deep_inner
        for _ in range(17):
            _t = fx_v11clib.wrap(_t)
        deep17 = _t                    # X30b: this module's code only 17 hops down
    ''',
    "fx_probe.py": '''
        # G_FI's probe module: nothing else uses it
        def probe(): return "probe"
    ''',
    "fx_gfi.py": '''
        # G_FI's single-thread scenario's targets: A declares f and g; the sentinel S declares h
        def f(): return 1
        def g(): return 2
        def h(): return 3
        def body():
            return f() + g() + h()
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
    "fx_r11.py": '''
        # revision 11's fixtures: X35e's fresh wrapper (aiodebug 2.3.0's shape), X57d's blk, X137j's lev
        import asyncio.events
        def enable():
            orig = asyncio.events.Handle._run
            def instrumented(self):
                return orig(self)
            asyncio.events.Handle._run = instrumented
        def blk(ev=None, inside=None):
            if ev is not None:
                inside.set()
                ev.wait(30)
            return 57
        def lev():
            return 137
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
import fx_probe, fx_gfi                                             # noqa: E402
import fx_b1, fx_x26c, fx_x26d, fx_x30d, fx_x30dlib, fx_x35b, fx_x35c, fx_cutw   # noqa: E402
import fx_r11   # noqa: E402

# The kept v5e cases (revision 11, GAP-37): the frozen v5e runner's registrations, fixtures and helpers,
# generated into v5e_port.py by tools/gen_v5e_port.py and bound to the implementation under test.
from pathlib import Path                                                   # noqa: E402
sys.path.insert(0, HERE)
import v5e_port                                                            # noqa: E402
v5e_port.bind(P)
v5e_port._load_fixtures(Path(WORK) / "v5e_fixtures")

ORIG = {}
# every fixture module imported at start (harness rules: every fixture function's __code__ restored; C5)
for mod in (fx_v5f, fx_stub, fx_swap, fx_pep, fx_x59e, fx_x14d, fx_x24f, fx_r05b, fx_r13a, fx_r13b, fx_r18, fx_r20,
            fx_probe, fx_gfi, fx_b1, fx_x26c, fx_x26d, fx_x30d, fx_x30dlib, fx_x35b, fx_x35c, fx_cutw, fx_r11):
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
    "B_F": gates({"B": ["fx_v5f:f"]}),
    "V10B": gates({"G": ["fx_v10b:thing"]}),
    "X30B": gates({"G": ["fx_x30b:deep17"]}),
    "H_F": gates({"H": ["fx_v5f:f"]}),
    "HB": gates({"G": ["fx_b1:hbody"]}),
    "PROBE": gates({"P": ["fx_probe:probe"]}),
    "GFI": gates({"A": ["fx_gfi:f", "fx_gfi:g"], "S": ["fx_gfi:h"]}),
    "X140": gates({"A": ["fx_gfi:f"], "B": ["fx_gfi:g"], "C": ["fx_gfi:h"]}),
    "DRV": gates({"A": ["fx_gfi:f"]}),
    "DRV2": gates({"B": ["fx_gfi:f"]}),
    "V11C": gates({"G": ["fx_v11c:target"]}),
    "F_G0": gates({"G0": ["fx_v5f:f"]}),
    "FW": gates({"G": ["fx_b1:fw"]}),
    "V38": gates({"G": ["fx_v38:fit"]}),
    "V40": gates({"G": ["fx_v40:registry.fit", "fx_v40:K.fit"]}),
    "V40B": gates({"G": ["fx_v40b:registry.fit"]}),
    "AB_FF": gates({"A": ["fx_v5f:f"], "B": ["fx_v5f:f"]}),
    "V42": gates({"G_fast": ["fx_v5f:f"], "G_slow": ["fx_v5f:g"]}, sections={"G_fast": "run", "G_slow": "run"}),
    "V45": gates({"G": ["fx_b1:ABase.fit", "fx_b1:Color.fit"]}),
    "F70": gates({"A": ["fx_b1:f70"]}),
    "A_T135": gates({"A": ["fx_b1:t135"]}),
    "B_FG": gates({"B": ["fx_v5f:f", "fx_v5f:g"]}),
    "C_F": gates({"C": ["fx_v5f:f"]}),
    "D_F": gates({"D": ["fx_v5f:f"]}),
    "A_G": gates({"A": ["fx_v5f:g"]}),
    "R05B": gates({"G": ["fx_r05b:real"]}),
    "R13": gates({"G": ["fx_r13a:cached"]}),
    "BLK": gates({"G": ["fx_r11:blk"]}),
    "W_F": gates({"W": ["fx_v5f:f"]}),
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


# -- New violation cases, batch 2b: fresh-subprocess cases on tool ids, callbacks and audit hooks -------
E5 = ("PY_START", "PY_RESUME", "PY_RETURN", "PY_YIELD", "PY_UNWIND")

def ev(name):
    return getattr(MON.events, name)

def cb_of(tool, name):
    """Read a callback by exchange and restore (sys.monitoring has no getter; X154b)."""
    c = MON.register_callback(tool, ev(name), None)
    MON.register_callback(tool, ev(name), c)
    return c

def is_styxx_cb(c):
    return c is not None and getattr(c, "__module__", None) == IMPL_MOD

def any_score(exp, rec, m=1.0):
    """score() that also catches the GateSpecError of a reloaded implementation."""
    try:
        v = exp.score({"m": m, "coverage_trace": rec})
        return ["PASS", v.coverage]
    except Exception as e:                            # noqa: BLE001
        c = code_of(e)
        if c is None:
            raise
        return ["REFUSE", c]

def audit_on_register(actions):
    """An audit hook acting on the case thread's sys.monitoring.register_callback events: actions maps
    the n-th event (1-based) to a callable; each runs once; the hook disarms after the last."""
    me = threading.get_ident()
    st = {"n": 0, "armed": True}
    last = max(actions)
    def hook(event, args):
        if st["armed"] and event == "sys.monitoring.register_callback" and threading.get_ident() == me:
            st["n"] += 1
            a = actions.get(st["n"])
            if st["n"] >= last:
                st["armed"] = False
            if a is not None:
                a()
    sys.addaudithook(hook)
    return st

def in_thread(fn):
    th = threading.Thread(target=fn)
    th.start()
    th.join(WATCHDOG_S)

def other_takes(tid, name="other", five=False, raise_cb=False):
    MON.use_tool_id(tid, name)
    own = {}
    if five:
        for e in E5:
            own[e] = (lambda *a, _e=e: None)
            MON.register_callback(tid, ev(e), own[e])
    if raise_cb:
        own["RAISE"] = lambda *a: None
        MON.register_callback(tid, MON.events.RAISE, own["RAISE"])
    return own

@sub("X137b")
def _sub_x137b():
    exp = EXP("FG")
    own = {}
    with P.coverage_trace(exp) as cov:
        def body():
            fx_v5f.f()
            t = P._v5_state()["tool"]
            MON.free_tool_id(t)
            own.update(other_takes(t, raise_cb=True))
            MON.set_events(t, MON.events.RAISE)
            own["t"] = t
            fx_v5f.g()
        cov.run("G", body)
        cov.run("G", fx_v5f.f)
    rec = cov.record()
    t = own["t"]
    after = {"owner_other": MON.get_tool(t) == "other", "events_raise": MON.get_events(t) == MON.events.RAISE,
             "raise_cb_own": cb_of(t, "RAISE") is own["RAISE"]}
    exp2 = EXP("F")
    with P.coverage_trace(exp2) as c2:
        c2.run("G", fx_v5f.f)
    return {"first": any_score(exp, rec), "lost": lost(rec, "G"), "after": after,
            "tool2": P._v5_state()["tool"], "second": any_score(exp2, c2.record())}

@case("X137b", "monitoring", "fresh subprocess: X137's free variant with another tool taking the freed id (RAISE callback, global RAISE); G runs f again after -> PASS {f:2, g:1} with MONITOR_LOST; the other tool's events and callback untouched; a second tracer takes id 3, PASS {f:1}")
def x137b():
    r = run_sub("X137b")
    expect(r == {"first": ["PASS", {"G": {"fx_v5f:f": 2, "fx_v5f:g": 1}}], "lost": True,
                 "after": {"owner_other": True, "events_raise": True, "raise_cb_own": True},
                 "tool2": 3, "second": ["PASS", {"G": {"fx_v5f:f": 1}}]}, f"{r}")

@sub("X137e")
def _sub_x137e():
    expP = EXP("A_F")
    P_ = P.coverage_trace(expP)
    P_.__enter__()
    P_.run("A", fx_v5f.f)
    code = P._v5_faultpoints()["_ensure_tool"]
    tool = FaultTool()
    done = []
    def on_start(c, off):
        if c is code and not done:
            done.append(1)
            MON.free_tool_id(P._v5_state()["tool"])
    try:
        tool.on(code, MON.events.PY_START, on_start)
        Q_ = P.coverage_trace(EXP("A_G"))
        Q_.__enter__()
    finally:
        tool.close()
    Q_.__exit__(None, None, None)
    P_.__exit__(None, None, None)
    rec = P_.record()
    return {"P": any_score(expP, rec), "lost": lost(rec, "A"), "tool_ours": P._v5_state()["tool_ours"], "freed": bool(done)}

@case("X137e", "monitoring", "fresh subprocess: P runs A(f); Q's enter, at PY_START of _ensure_tool, frees styxx's id; Q exits, P exits -> P PASS {f:1} with MONITOR_LOST; tool_ours True")
def x137e():
    r = run_sub("X137e")
    expect(r == {"P": ["PASS", {"A": {"fx_v5f:f": 1}}], "lost": True, "tool_ours": True, "freed": True}, f"{r}")

def _x137g_i(register_five):
    expP, expQ = EXP("A_F"), EXP("B_FG")
    P_ = P.coverage_trace(expP)
    P_.__enter__()
    MON.free_tool_id(4)
    other_takes(4, five=register_five)
    Q_ = P.coverage_trace(expQ)
    Q_.__enter__()
    tool = P._v5_state()["tool"]
    le = [MON.get_local_events(4, fx_v5f.f.__code__), MON.get_local_events(3, fx_v5f.f.__code__)]
    P_.run("A", fx_v5f.f)
    Q_.run("B", fx_v5f.f)
    Q_.run("B", fx_v5f.g)
    Q_.__exit__(None, None, None)
    P_.__exit__(None, None, None)
    rp, rq = P_.record(), Q_.record()
    return {"tool": tool, "local_events_nonzero": [bool(x) for x in le], "P": any_score(expP, rp), "P_lost": lost(rp, "A"),
            "Q": any_score(expQ, rq), "Q_lost": lost(rq, "B")}

@sub("X137g")
def _sub_x137g():
    return _x137g_i(True)

@sub("X137i")
def _sub_x137i():
    return _x137g_i(False)

@case("X137g", "monitoring", "fresh subprocess: P(f) entered; another tool frees and takes id 4 with its own five callbacks; Q(f, g) joins P's mint and rebinds to id 3 -> tool 3; P PASS {f:1} with MONITOR_LOST; Q PASS {f:1, g:1}, no MONITOR_LOST")
def x137g():
    r = run_sub("X137g")
    r.pop("local_events_nonzero")
    expect(r == {"tool": 3, "P": ["PASS", {"A": {"fx_v5f:f": 1}}], "P_lost": True,
                 "Q": ["PASS", {"B": {"fx_v5f:f": 1, "fx_v5f:g": 1}}], "Q_lost": False}, f"{r}")

@case("X137i", "monitoring", "fresh subprocess: X137g with the other tool taking id 4 by use_tool_id only; f's local events non-zero on ids 4 and 3 before P's call -> tool 3; P PASS {f:1} with MONITOR_LOST; Q PASS {f:1, g:1}, no MONITOR_LOST (no double count)")
def x137i():
    r = run_sub("X137i")
    expect(r == {"tool": 3, "local_events_nonzero": [True, True], "P": ["PASS", {"A": {"fx_v5f:f": 1}}], "P_lost": True,
                 "Q": ["PASS", {"B": {"fx_v5f:f": 1, "fx_v5f:g": 1}}], "Q_lost": False}, f"{r}")

@sub("X137h")
def _sub_x137h():
    expP, expQ, expR, expS = EXP("A_Gdecl"), EXP("B_H"), EXP("A_T"), EXP("A_Gdecl")
    P_ = P.coverage_trace(expP); P_.__enter__()               # id 4
    MON.free_tool_id(4)
    Uown = other_takes(4, name="U", raise_cb=True)            # U: only a RAISE callback
    Q_ = P.coverage_trace(expQ); Q_.__enter__()               # rebinds to id 3
    R_ = P.coverage_trace(expR); R_.__enter__()
    def body():
        MON.free_tool_id(3)
        other_takes(3, name="V", five=True)                   # V keeps the inherited PY_UNWIND
        try:
            fx_v5f.t()
        except ValueError:
            pass
    R_.run("A", body)
    MON.register_callback(4, MON.events.RAISE, None)          # U unregisters and frees id 4
    MON.free_tool_id(4)
    S_ = P.coverage_trace(expS); S_.__enter__()
    tool_after_S = P._v5_state()["tool"]
    for c in (S_, Q_, R_, P_):
        c.__exit__(None, None, None)
    out = {"tool_after_S": tool_after_S}
    for name, c, e, sec in (("P", P_, expP, "A"), ("Q", Q_, expQ, "B"), ("R", R_, expR, "A"), ("S", S_, expS, "A")):
        rec = c.record()
        out[name] = [any_score(e, rec)[:2][0], any_score(e, rec)[1] if any_score(e, rec)[0] == "REFUSE" else None,
                     any(n.startswith("[V5:MONITOR_LOST]") for o in rec["sections"].get(sec, []) for n in o["notes"])
                     or any("MONITOR_LOST" in p for p in rec["problems"]), rec_lost_any(rec)]
    return out

def rec_lost_any(rec):
    """MONITOR_LOST anywhere in a record: in any opening's notes (a trace with no opening carries it in
    the scoring message only, so the message is read instead: see the case)."""
    return any(n.startswith("[V5:MONITOR_LOST]") for ops in rec["sections"].values() for o in ops for n in o["notes"])

@case("X137h", "monitoring", "fresh subprocess, revision 7 form: U takes id 4 (RAISE only), Q rebinds to 3, V takes id 3 inside R's A (five callbacks, inherited PY_UNWIND), t raises; U frees 4; S rebinds to 4 -> tool 4; R NOT_EXERCISED for t with MONITOR_LOST; P and Q NOT_EXERCISED with MONITOR_LOST; S NOT_EXERCISED, no MONITOR_LOST")
def x137h():
    r = run_sub("X137h")
    expect(r.get("tool_after_S") == 4, f"{r}")
    expect(r["R"][:2] == ["REFUSE", "NOT_EXERCISED"] and r["R"][3] is True, f"R {r['R']}")
    for k in ("P", "Q", "S"):
        expect(r[k][:2] == ["REFUSE", "NOT_EXERCISED"], f"{k} {r[k]}")
    # P, Q and S open no section, so MONITOR_LOST can appear only in the scoring message: X137h_msg reads it
    m = run_sub("X137h_msg")
    expect(m == {"P": True, "Q": True, "S": False}, f"MONITOR_LOST in the NOT_EXERCISED messages: {m}")

@sub("X137h_msg")
def _sub_x137h_msg():
    """X137h again, reading MONITOR_LOST from the scoring messages of the traces that open no section."""
    expP, expQ, expR, expS = EXP("A_Gdecl"), EXP("B_H"), EXP("A_T"), EXP("A_Gdecl")
    P_ = P.coverage_trace(expP); P_.__enter__()
    MON.free_tool_id(4)
    other_takes(4, name="U", raise_cb=True)
    Q_ = P.coverage_trace(expQ); Q_.__enter__()
    R_ = P.coverage_trace(expR); R_.__enter__()
    def body():
        MON.free_tool_id(3)
        other_takes(3, name="V", five=True)
        try:
            fx_v5f.t()
        except ValueError:
            pass
    R_.run("A", body)
    MON.register_callback(4, MON.events.RAISE, None)
    MON.free_tool_id(4)
    S_ = P.coverage_trace(expS); S_.__enter__()
    for c in (S_, Q_, R_, P_):
        c.__exit__(None, None, None)
    def msg(e, c):
        try:
            e.score({"m": 1.0, "coverage_trace": c.record()})
            return False
        except GateSpecError as x:
            return "MONITOR_LOST" in str(x)
    return {"P": msg(expP, P_), "Q": msg(expQ, Q_), "S": msg(expS, S_)}

def _x154b_trial(k, pre_enter=False):
    exp = EXP("A_F")
    other = {}
    def act():
        def th():
            t = P._v5_state()["tool"]
            if t is None:              # X154c: the first acquisition is in progress; the row's outcome names id 4 (GAP-43)
                t = 4
            MON.free_tool_id(t)
            other["t"] = t
            other.update(other_takes(t, five=True))
        in_thread(th)
    if pre_enter:
        audit_on_register({k: act})
        cov = P.coverage_trace(exp)
        cov.__enter__()
        tool_after_enter = P._v5_state()["tool"]
        cov.run("A", fx_v5f.f)
        cov.__exit__(None, None, None)
    else:
        cov = P.coverage_trace(exp)
        cov.__enter__()
        cov.run("A", fx_v5f.f)
        audit_on_register({k: act})
        cov.__exit__(None, None, None)
        tool_after_enter = None
    rec = cov.record()
    t = other["t"]
    cbs = {e: ("styxx" if is_styxx_cb(cb_of(t, e)) else ("own" if cb_of(t, e) is other.get(e) else "other")) for e in E5}
    return {"score": any_score(exp, rec), "lost": lost(rec, "A"), "owner_other": MON.get_tool(t) == "other",
            "cbs": cbs, "tool_after_enter": tool_after_enter, "t": t}

@sub("X154b")
def _sub_x154b(k):
    return _x154b_trial(int(k))

@case("X154b", "monitoring", "an audit-hook sweep of the exit's registration, trials k = 1..5, one fresh subprocess each -> __exit__ returns; PASS {f:1} with MONITOR_LOST; the other tool owns the id; its callbacks its own except the k-th event's, which is styxx's")
def x154b():
    bad = []
    for k in range(1, 6):
        r = run_sub(f"X154b:{k}")
        want = {e: ("styxx" if i == k - 1 else "own") for i, e in enumerate(E5)}
        if not (r["score"] == ["PASS", {"A": {"fx_v5f:f": 1}}] and r["lost"] and r["owner_other"] and r["cbs"] == want):
            bad.append((k, r))
    expect(not bad, f"{bad}")

@sub("X154c")
def _sub_x154c():
    return _x154b_trial(5, pre_enter=True)

@case("X154c", "monitoring", "fresh subprocess, before any tracer: X154b's hook with k = 5 installed before the first enter -> tool 3 after the enter; the other tool owns id 4 and its PY_UNWIND callback is styxx's; PASS {f:1}, no MONITOR_LOST")
def x154c():
    r = run_sub("X154c")
    want = {e: ("styxx" if e == "PY_UNWIND" else "own") for e in E5}
    expect(r["tool_after_enter"] == 3 and r["t"] == 4 and r["owner_other"] and r["cbs"] == want
           and r["score"] == ["PASS", {"A": {"fx_v5f:f": 1}}] and not r["lost"], f"{r}")

@sub("X154d")
def _sub_x154d():
    expP, expQ = EXP("A_F"), EXP("B_G")
    P_ = P.coverage_trace(expP); P_.__enter__()
    P_.run("A", fx_v5f.f)
    MON.free_tool_id(P._v5_state()["tool"])
    def free_again():
        in_thread(lambda: MON.free_tool_id(P._v5_state()["tool"]))
    t0 = P._v5_state()["tool"]
    audit_on_register({1: free_again, 2: free_again})
    Q_ = P.coverage_trace(expQ); Q_.__enter__()
    t1 = P._v5_state()["tool"]
    Q_.run("B", fx_v5f.g)
    Q_.__exit__(None, None, None)
    P_.__exit__(None, None, None)
    rp, rq = P_.record(), Q_.record()
    return {"tool_unchanged": t0 == t1, "P": any_score(expP, rp), "P_lost": lost(rp, "A"),
            "Q": any_score(expQ, rq), "Q_lost": lost(rq, "B")}

@case("X154d", "monitoring", "fresh subprocess, variant (a): P runs A(f); styxx's id freed; an audit hook frees it again at the 1st and 2nd register_callback events of Q's enter -> tool unchanged; P PASS {f:1} with MONITOR_LOST; Q PASS {g:1}, no MONITOR_LOST (variant (b): GAP-41)")
def x154d():
    r = run_sub("X154d")
    expect(r == {"tool_unchanged": True, "P": ["PASS", {"A": {"fx_v5f:f": 1}}], "P_lost": True,
                 "Q": ["PASS", {"B": {"fx_v5f:g": 1}}], "Q_lost": False}, f"{r}")

@sub("X154e")
def _sub_x154e():
    def boom():
        raise RuntimeError("the 3rd register_callback")
    audit_on_register({3: boom})
    cov = P.coverage_trace(EXP("F"))
    try:
        cov.__enter__()
        first = None
    except RuntimeError:
        first = "RuntimeError"
    name4 = MON.get_tool(4)
    tool_mid = P._v5_state()["tool"]
    cov.__exit__(None, None, None)
    exp2 = EXP("A_F")
    with P.coverage_trace(exp2) as c2:
        c2.run("A", fx_v5f.f)
    rec = c2.record()
    return {"first": first, "id4_styxx": isinstance(name4, str) and name4.startswith("styxx.protocol/"),
            "tool_mid": tool_mid, "tool": P._v5_state()["tool"], "score": any_score(exp2, rec), "lost": lost(rec, "A")}

@case("X154e", "monitoring", "fresh subprocess: an audit hook raises RuntimeError at the 3rd register_callback of the first enter -> RuntimeError; id 4 named styxx's while tool is None; a second tracer adopts id 4: tool 4, PASS {f:1}, no MONITOR_LOST")
def x154e():
    r = run_sub("X154e")
    expect(r == {"first": "RuntimeError", "id4_styxx": True, "tool_mid": None, "tool": 4,
                 "score": ["PASS", {"A": {"fx_v5f:f": 1}}], "lost": False}, f"{r}")

@sub("X155")
def _sub_x155(k):
    k = int(k)
    exp = EXP("FG")
    cov = P.coverage_trace(exp)
    cov.__enter__()
    def body():
        fx_v5f.f()
        MON.free_tool_id(P._v5_state()["tool"])
        fx_v5f.g()
    cov.run("G", body)
    won = {}
    def interference():
        try:
            MON.use_tool_id(4, "other")
            won["other"] = True
        except ValueError:
            won["other"] = False
    box = {"n": 0}
    def on_instr(code, offset):
        box["n"] += 1
        if box["n"] == k:
            in_thread(interference)
    inj = Injector(["_take"], threading.get_ident(), on_instr)
    try:
        try:
            cov.__exit__(None, None, None)
            raised = None
        except Exception as e:                        # noqa: BLE001
            raised = type(e).__name__
    finally:
        inj.close()
    rec = cov.record()
    keeps = (MON.get_tool(4) == "other") if won.get("other") else None
    return {"n": box["n"], "raised": raised, "lost": lost(rec, "G"), "other_won": won.get("other"), "other_keeps": keeps}

@case("X155", "sweep", "fresh subprocess per trial: X137's free variant; an instruction sweep over _take on the exiting thread; the interference calls use_tool_id(4, 'other') -> every trial: __exit__ raises nothing; MONITOR_LOST; if the other tool won, it keeps id 4")
def x155():
    k, bad = 1, []
    while k < 500:
        r = run_sub(f"X155:{k}")
        if r["n"] < k:
            break
        if not (r["raised"] is None and r["lost"] and (r["other_won"] is not True or r["other_keeps"] is True)):
            bad.append((k, r))
        k += 1
    SWEEP_COUNTS.setdefault("_take (X155, one subprocess per trial)", []).append(k - 1)
    expect(k > 1 and not bad, f"{k - 1} trials; failing {bad[:3]}")

@sub("X157c")
def _sub_x157c():
    expP = EXP("A_T")
    P_ = P.coverage_trace(expP); P_.__enter__()
    MON.free_tool_id(P._v5_state()["tool"])
    def body():
        try:
            fx_v5f.t()
        except ValueError:
            pass
    P_.run("A", body)
    Denied = _denied_hook(2)
    try:
        P.coverage_trace(EXP("A_G")).__enter__()
        q = None
    except Denied:
        q = "Denied"
    P_.__exit__(None, None, None)
    rec = P_.record()
    return {"q": q, "P": any_score(expP, rec), "lost": lost(rec, "A")}

@case("X157c", "monitoring", "fresh subprocess: P(t) with styxx's id freed; A calls t (raises), caught; an audit hook raises Denied at the 2nd register_callback of Q's enter -> Denied; P NOT_EXERCISED for t with MONITOR_LOST")
def x157c():
    r = run_sub("X157c")
    expect(r == {"q": "Denied", "P": ["REFUSE", "NOT_EXERCISED"], "lost": True}, f"{r}")

def _x158(variant, replacement="own", inject=False):
    expP, expQ = EXP("A_F"), EXP("B_F")
    P_ = P.coverage_trace(expP); P_.__enter__()
    Q_ = P.coverage_trace(expQ); Q_.__enter__()
    P_.run("A", fx_v5f.f)
    t = P._v5_state()["tool"]
    MON.register_callback(t, MON.events.PY_START, (lambda *a: None) if replacement == "own" else None)
    Q_.run("B", fx_v5f.f)
    raised = None
    if inject:
        state = {"armed": False, "fired": False}
        rcode = P._v5_faultpoints()["_register"]
        tool = FaultTool()
        def on_ret(c, off, val):
            if c is rcode and threading.get_ident() == me:
                state["armed"] = True
        me = threading.get_ident()
        def on_instr(code, offset):
            if state["armed"] and not state["fired"]:
                state["fired"] = True
                raise Injected()
        inj = Injector(["_exit_txn"], me, on_instr)
        try:
            tool.on(rcode, MON.events.PY_RETURN, on_ret)
            try:
                P_.__exit__(None, None, None)
            except Injected:
                raised = "Injected"
        finally:
            inj.close()
            tool.close()
        Q_.__exit__(None, None, None)
    elif variant == "a":
        P_.__exit__(None, None, None); Q_.__exit__(None, None, None)
    else:
        Q_.__exit__(None, None, None); P_.__exit__(None, None, None)
    try:
        rp = P_.record()
        pout = [any_score(expP, rp), lost(rp, "A")]
    except GateSpecError as e:
        pout = [["REFUSE", code_of(e)], None]
    rq = Q_.record()
    return {"raised": raised, "P": pout, "Q": [any_score(expQ, rq), lost(rq, "B")],
            "start_cb_styxx": is_styxx_cb(cb_of(t, "PY_START")), "tool_ours": P._v5_state()["tool_ours"]}

_X158_WANT = {"raised": None, "P": [["PASS", {"A": {"fx_v5f:f": 1}}], True], "Q": [["REFUSE", "NOT_EXERCISED"], True],
              "start_cb_styxx": True, "tool_ours": True}

@sub("X158")
def _sub_x158(variant):
    return _x158(variant)

@sub("X158c")
def _sub_x158c(variant):
    return _x158(variant, replacement=None)

@sub("X158b")
def _sub_x158b():
    return _x158("a", inject=True)

@case("X158", "monitoring", "fresh subprocess: P and Q on f; after P's A, an outside party replaces styxx's PY_START callback; Q's B; variants (a) P exits first, (b) Q first -> P PASS {f:1} with MONITOR_LOST; Q NOT_EXERCISED with MONITOR_LOST; styxx's callback repaired; tool_ours True")
def x158():
    for v in ("a", "b"):
        r = run_sub(f"X158:{v}")
        expect(r == _X158_WANT, f"variant ({v}): {r}")

@case("X158c", "monitoring", "fresh subprocess: X158 with the outside party registering None over styxx's PY_START callback, both variants -> as X158")
def x158c():
    for v in ("a", "b"):
        r = run_sub(f"X158c:{v}")
        expect(r == _X158_WANT, f"variant ({v}): {r}")

@case("X158b", "monitoring", "fresh subprocess: X158 (a) with the id-5 injector raising in _exit_txn right after _register returns on P's thread -> Injected from P's __exit__; P TRACE_INCOMPLETE; Q NOT_EXERCISED with MONITOR_LOST")
def x158b():
    r = run_sub("X158b")
    expect(r["raised"] == "Injected" and r["P"][0] == ["REFUSE", "TRACE_INCOMPLETE"]
           and r["Q"] == [["REFUSE", "NOT_EXERCISED"], True], f"{r}")

@sub("X158e")
def _sub_x158e():
    exps = {k: EXP(k) for k in ("A_F", "B_F", "C_F", "D_F")}
    P_ = P.coverage_trace(exps["A_F"]); P_.__enter__()
    Q_ = P.coverage_trace(exps["B_F"]); Q_.__enter__()
    P_.run("A", fx_v5f.f); Q_.run("B", fx_v5f.f)
    importlib.reload(P)
    R_ = P.coverage_trace(P.Experiment(os.path.join(REPO, "PREREG_C_F.md"))); R_.__enter__()
    R_.run("C", fx_v5f.f)
    P_.__exit__(None, None, None)
    S_ = P.coverage_trace(P.Experiment(os.path.join(REPO, "PREREG_D_F.md"))); S_.__enter__()
    S_.run("D", fx_v5f.f)
    for c in (Q_, R_, S_):
        c.__exit__(None, None, None)
    out = {}
    for name, c, key, sec in (("P", P_, "A_F", "A"), ("Q", Q_, "B_F", "B"), ("R", R_, "C_F", "C"), ("S", S_, "D_F", "D")):
        rec = c.record()
        e = P.Experiment(os.path.join(REPO, f"PREREG_{key}.md"))
        out[name] = [any_score(e, rec), lost(rec, sec)]
    return out

@case("X158e", "monitoring", "fresh subprocess: P and Q live across importlib.reload; R entered after it; P exits; S entered after that exit -> every trace PASS its one call; P, Q and R with MONITOR_LOST; S none")
def x158e():
    r = run_sub("X158e")
    want = {k: [["PASS", {s: {"fx_v5f:f": 1}}], k != "S"] for k, s in (("P", "A"), ("Q", "B"), ("R", "C"), ("S", "D"))}
    expect(r == want, f"{r}")

def _have_greenlet():
    try:
        import greenlet
        return greenlet.__version__ == "3.5.6"
    except ImportError:
        return False

@sub("X137f")
def _sub_x137f():
    import greenlet
    expX, expY = EXP("A_T"), EXP("B_G")
    X = P.coverage_trace(expX); X.__enter__()
    MON.free_tool_id(P._v5_state()["tool"])
    def body():
        try:
            fx_v5f.t()
        except ValueError:
            pass
    X.run("A", body)
    Y = P.coverage_trace(expY)
    def g1_run():
        X.__exit__(None, None, None)
    def g2_run():
        g1 = greenlet.greenlet(g1_run, parent=greenlet.getcurrent())
        audit_on_register({5: lambda: g1.switch()})
        Y.__enter__()
    g2 = greenlet.greenlet(g2_run)
    g2.switch()
    Y.run("B", fx_v5f.g)
    Y.__exit__(None, None, None)
    rx, ry = X.record(), Y.record()
    return {"X": any_score(expX, rx), "X_lost": lost(rx, "A"), "Y": any_score(expY, ry), "Y_lost": lost(ry, "B")}

@case("X137f", "greenlet", "fresh subprocess, greenlet 3.5.6: X(t) with styxx's id freed; A calls t; g2's reconciling enter of Y switches, at the 5th register_callback of its reclaim, to g1, which runs X.__exit__ -> X NOT_EXERCISED for t with MONITOR_LOST; Y PASS {g:1}, no MONITOR_LOST")
def x137f():
    if not ARGS.greenlet_path and not _have_greenlet():
        raise NotRun("the pinned greenlet 3.5.6 is not importable (pass --greenlet-path)")
    r = run_sub("X137f")
    expect(r == {"X": ["REFUSE", "NOT_EXERCISED"], "X_lost": True, "Y": ["PASS", {"B": {"fx_v5f:g": 1}}], "Y_lost": False}, f"{r}")

@sub("X158d")
def _sub_x158d():
    import greenlet
    expP, expQ = EXP("A_F"), EXP("B_F")
    P_ = P.coverage_trace(expP); P_.__enter__()
    Q_ = P.coverage_trace(expQ); Q_.__enter__()
    P_.run("A", fx_v5f.f)
    t = P._v5_state()["tool"]
    ran = []
    main = greenlet.getcurrent()
    class Repl:
        def __call__(self, *a):
            return None
        def __del__(self):
            def g2_run():
                Q_.__exit__(None, None, None)
                ran.append(1)
            greenlet.greenlet(g2_run, parent=main).switch()
    MON.register_callback(t, MON.events.PY_START, Repl())
    Q_.run("B", fx_v5f.f)
    P_.__exit__(None, None, None)
    rp, rq = P_.record(), Q_.record()
    return {"P": any_score(expP, rp), "P_lost": lost(rp, "A"), "Q": any_score(expQ, rq), "Q_lost": lost(rq, "B"),
            "finalizer_ran": bool(ran), "P_problems": [x[:160] for x in rp["problems"]]}

@case("X158d", "greenlet", "fresh subprocess, greenlet 3.5.6: X158 (a) where the replacement's __del__ switches to g2, which runs Q.__exit__ -> P PASS {f:1} with MONITOR_LOST; Q NOT_EXERCISED with MONITOR_LOST; the finalizer ran inside P's registration")
def x158d():
    if not ARGS.greenlet_path and not _have_greenlet():
        raise NotRun("the pinned greenlet 3.5.6 is not importable (pass --greenlet-path)")
    r = run_sub("X158d")
    r.pop("P_problems", None)
    expect(r == {"P": ["PASS", {"A": {"fx_v5f:f": 1}}], "P_lost": True, "Q": ["REFUSE", "NOT_EXERCISED"], "Q_lost": True,
                 "finalizer_ran": True}, f"{r}")


# -- New valid cases (expected union counts) ---------------------------------------------------------
def pass_counts(exp, rec, counts):
    expect_pass(score(exp, rec), counts)

@case("V10b", "valid", "a module whose __class__ is a ModuleType subclass serves the target only through PEP 562 -> {target:1}")
def v10b():
    m = importlib.import_module("fx_v10b")
    exp = EXP("V10B")
    with P.coverage_trace(exp) as cov:
        cov.run("G", lambda: m.thing())
    pass_counts(exp, cov.record(), {"G": {"fx_v10b:thing": 1}})

@case("V11c", "valid", "the target sits exactly 16 hops down a foreign functools.wraps chain -> {target:1}")
def v11c():
    m = importlib.import_module("fx_v11c")
    exp = EXP("V11C")
    with P.coverage_trace(exp) as cov:
        cov.run("G", m.target)
    pass_counts(exp, cov.record(), {"G": {"fx_v11c:target": 1}})

@case("V15b", "valid", "outer and inner preregs both name their gate and section 'G', nested on one stack; variant: a case section named like the self-trace section (G0) -> both {f:1}")
def v15b():
    for key, sec in (("F", "G"), ("F_G0", "G0")):
        eo, ei = EXP(key), EXP(key)
        with P.coverage_trace(eo) as co, P.coverage_trace(ei) as ci:
            co.run(sec, lambda: ci.run(sec, fx_v5f.f))
        pass_counts(eo, co.record(), {sec: {"fx_v5f:f": 1}})
        pass_counts(ei, ci.record(), {sec: {"fx_v5f:f": 1}})

@case("V19b", "valid", "in a task of a running loop L, section A calls L._run_once(), which runs a callback that opens section B of the same tracer and calls g -> B opens (no NESTED_SECTION); B {g:1}")
def v19b():
    import asyncio
    exp = EXP("AB")
    L = asyncio.new_event_loop()
    try:
        with P.coverage_trace(exp) as cov:
            async def other():
                L.call_soon(lambda: cov.run("B", fx_v5f.g))
            async def main():
                t = asyncio.ensure_future(other())
                await asyncio.sleep(0)
                cov.run("A", L._run_once)
                await t
            L.run_until_complete(main())
        rec = cov.record()
    finally:
        L.close()
    expect(rec["problems"] == [], f"problems {rec['problems']}")
    expect([o["calls"] for o in rec["sections"]["B"]] == [{"fx_v5f:g": 1}], f"B {rec['sections'].get('B')}")

@case("V35", "valid", "an eager child does await asyncio.sleep(0), then cov.run_async('B', ...) -> exact counts, PASS")
def v35():
    import asyncio
    exp = EXP("AB")
    with P.coverage_trace(exp) as cov:
        async def gb():
            return fx_v5f.g()
        async def child():
            await asyncio.sleep(0)
            await cov.run_async("B", gb)
        async def ab():
            fx_v5f.f()
            asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
            await asyncio.create_task(child())
        asyncio.run(cov.run_async("A", ab))
    pass_counts(exp, cov.record(), {"A": {"fx_v5f:f": 1}, "B": {"fx_v5f:g": 1}})

@case("V36", "valid", "a benign gc.freeze() inside a section, with no clone -> {f:1}")
def v36():
    exp = EXP("F")
    try:
        with P.coverage_trace(exp) as cov:
            def body():
                fx_v5f.f()
                gc.freeze()
            cov.run("G", body)
        rec = cov.record()
    finally:
        gc.unfreeze()
        gc.collect()        # GAP-39
    pass_counts(exp, rec, {"G": {"fx_v5f:f": 1}})

@case("V36b", "valid", "a frozen list of 1,000 objects before the trace; inside: f once, then the list deleted (the count falls); a worker enters f after __enter__ and is inside it while the tracer exits -> PASS {f:1}, no CLONE_ALIVE")
def v36b():
    exp = EXP("FW")
    ev = threading.Event()
    box = {"objs": [object() for _ in range(1000)]}
    try:
        gc.freeze()
        expect(gc.get_freeze_count() > 0, "the freeze count is 0")
        inside = threading.Event()
        with P.coverage_trace(exp) as cov:
            w = threading.Thread(target=lambda: fx_b1.fw(ev, inside))
            w.start()
            inside.wait(30)
            def body():
                fx_b1.fw()
                box.pop("objs")
            cov.run("G", body)
        rec = cov.record()
        ev.set()
        w.join(30)
    finally:
        ev.set()
        gc.unfreeze()
        gc.collect()        # GAP-39
    pass_counts(exp, rec, {"G": {"fx_b1:fw": 1}})
    expect(not any(p.startswith("[V5:CLONE_ALIVE]") for p in rec["problems"]), f"{rec['problems']}")

@case("V37", "valid", "a pure-Python profiler that forwards events, started inside a section -> {f:1}; still installed after close and exit; it saw the later call")
def v37():
    exp = EXP("F")
    saw = []
    prev = sys.getprofile()
    def prof(frame, event, arg):
        if event == "call" and frame.f_code is fx_v5f.f.__code__:
            saw.append(1)
        if prev is not None:
            prev(frame, event, arg)
    try:
        with P.coverage_trace(exp) as cov:
            def body():
                sys.setprofile(prof)
                fx_v5f.f()
            cov.run("G", body)
            still_after_close = sys.getprofile() is prof
        still_after_exit = sys.getprofile() is prof
    finally:
        sys.setprofile(prev)
    pass_counts(exp, cov.record(), {"G": {"fx_v5f:f": 1}})
    expect(still_after_close and still_after_exit and saw, f"installed {still_after_close}/{still_after_exit}, saw {saw}")

@case("V38", "valid", "@logged @Memo def fit: wraps over a class-based wrapper whose instance's own __dict__ has __wrapped__ (update_wrapper) -> {fit:1}")
def v38():
    m = importlib.import_module("fx_v38")
    exp = EXP("V38")
    with P.coverage_trace(exp) as cov:
        cov.run("G", m.fit)
    pass_counts(exp, cov.record(), {"G": {"fx_v38:fit": 1}})

@case("V39", "valid", "sections given as a StrEnum, a (str, Enum) member and a numpy.str_-like subclass -> PASS; the record's keys are exact str")
def v39():
    import enum
    class SE(enum.StrEnum):
        G = "G"
    class SM(str, enum.Enum):
        G = "G"
    class NpStr(str):                                   # numpy.str_-like: a plain str subclass
        pass
    exp = EXP("F")
    with P.coverage_trace(exp) as cov:
        for sec in (SE.G, SM.G, NpStr("G")):
            cov.run(sec, fx_v5f.f)
    rec = cov.record()
    pass_counts(exp, rec, {"G": {"fx_v5f:f": 3}})
    expect(all(type(k) is str for k in rec["sections"]), f"keys {[type(k) for k in rec['sections']]}")

@case("V40", "valid", "a registry whose __getattribute__ raises KeyError; a class whose metaclass __getattribute__ raises -> {target:1} each; no user side effects")
def v40():
    m = importlib.import_module("fx_v40")
    m.COUNT["n"] = 0
    exp = EXP("V40")
    with P.coverage_trace(exp) as cov:
        def body():
            m._fit()
            type.__dict__["__dict__"].__get__(m.K)["fit"](None)
        cov.run("G", body)
    pass_counts(exp, cov.record(), {"G": {"fx_v40:registry.fit": 1, "fx_v40:K.fit": 1}})
    expect(m.COUNT["n"] == 0, f"user __getattribute__ ran {m.COUNT['n']} time(s)")

@case("V40b", "valid", "a step through an instance registry whose class's metaclass defines a raising, counting __eq__; target mod:registry.fit in its own __dict__; variant: fn of a section returns such an instance -> {fit:1}; the __eq__ counter 0 in both")
def v40b():
    m = importlib.import_module("fx_v40b")
    m.COUNT["eq"] = 0
    exp = EXP("V40B")
    with P.coverage_trace(exp) as cov:
        cov.run("G", m._fit)
        cov.run("G", lambda: m.registry)                 # the variant: fn returns such an instance
    pass_counts(exp, cov.record(), {"G": {"fx_v40b:registry.fit": 1}})
    expect(m.COUNT["eq"] == 0, f"__eq__ ran {m.COUNT['eq']} time(s)")

@case("V41", "valid", "gates A and B both declare f; each section calls f once -> A {f:1}, B {f:1}")
def v41():
    exp = EXP("AB_FF")
    with P.coverage_trace(exp) as cov:
        cov.run("A", fx_v5f.f)
        cov.run("B", fx_v5f.f)
    pass_counts(exp, cov.record(), {"A": {"fx_v5f:f": 1}, "B": {"fx_v5f:f": 1}})

@case("V42", "valid", "G_fast[f] and G_slow[g] share section 'run'; one cov.run('run', ...) calls both -> both PASS")
def v42():
    exp = EXP("V42")
    with P.coverage_trace(exp) as cov:
        cov.run("run", lambda: (fx_v5f.f(), fx_v5f.g()))
    pass_counts(exp, cov.record(), {"G_fast": {"fx_v5f:f": 1}, "G_slow": {"fx_v5f:g": 1}})

@case("V43", "valid", "a gate whose section is 'harness', not its name -> PASS")
def v43():
    exp = EXP("X78G")
    with P.coverage_trace(exp) as cov:
        cov.run("harness", fx_v5f.f)
    pass_counts(exp, cov.record(), {"G": {"fx_v5f:f": 1}})

@case("V44", "valid", "cov.run('G', _run, 1) with def _run(cfg): return f() + cfg -> {f:1}")
def v44():
    exp = EXP("F")
    with P.coverage_trace(exp) as cov:
        cov.run("G", fx_b1._run, 1)
    pass_counts(exp, cov.record(), {"G": {"fx_v5f:f": 1}})

@case("V45", "valid", "a method of an abc.ABC subclass; a method of an Enum -> {target:1} each")
def v45():
    exp = EXP("V45")
    with P.coverage_trace(exp) as cov:
        cov.run("G", lambda: (fx_b1.ALeaf().fit(), fx_b1.Color.RED.fit()))
    pass_counts(exp, cov.record(), {"G": {"fx_b1:ABase.fit": 1, "fx_b1:Color.fit": 1}})

@sub("V47")
def _sub_v47():
    import warnings, concurrent.futures, multiprocessing
    m = importlib.import_module("fx_v47")
    exp = EXP("AB")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        with P.coverage_trace(exp) as cov:
            m.COV = cov
            def body():
                fx_v5f.f()
                with concurrent.futures.ProcessPoolExecutor(2, mp_context=multiprocessing.get_context("fork")) as ex:
                    return list(ex.map(m.job, [1, 2, 3]))
            vals = cov.run("A", body)
        m.COV = None
    rec = cov.record()
    st = P._v5_state()
    return {"vals": vals, "A": [o["calls"] for o in rec["sections"]["A"]], "B_in_trace": "B" in rec["sections"],
            "score": any_score(exp, rec), "fork_warning": any(issubclass(x.category, DeprecationWarning) and "fork" in str(x.message) for x in w),
            "state": [st["anchors"], st["global_events"], st["mints"]]}

@case("V47", "valid", "fresh subprocess: a fork ProcessPoolExecutor inside section A whose jobs call COV.run('B', g) -> A PASS; the jobs return their values; B SECTION_ABSENT in the parent's trace; _v5_state() clean; no multi-threaded-fork DeprecationWarning")
def v47():
    r = run_sub("V47")
    expect(r == {"vals": [3, 4, 5], "A": [{"fx_v5f:f": 1}], "B_in_trace": False, "score": ["REFUSE", "SECTION_ABSENT"],
                 "fork_warning": False, "state": [0, 0, []]}, f"{r}")

def _coverage_core(core):
    try:
        import coverage
    except ImportError:
        raise NotRun("coverage 7.16 is not importable (pass --deps-path)")
    os.environ["COVERAGE_CORE"] = core
    try:
        c = coverage.Coverage(data_file=None, include=[os.path.join(FIX, "*")])
    finally:
        os.environ.pop("COVERAGE_CORE", None)
    exp = EXP("F")
    c.start()
    try:
        with P.coverage_trace(exp) as cov:
            cov.run("G", fx_v5f.f)
    finally:
        c.stop()
    lines = c.get_data().lines(fx_v5f.__file__) or []
    return exp, cov.record(), lines, getattr(c, "_collector", None)

@case("V50", "valid", "coverage.py 7.16, sysmon core and ctrace core, running across the section -> {f:1}; coverage records the minted function's lines")
def v50():
    fline = fx_v5f.f.__code__.co_firstlineno
    for core in ("sysmon", "ctrace"):
        exp, rec, lines, _ = _coverage_core(core)
        pass_counts(exp, rec, {"G": {"fx_v5f:f": 1}})
        expect(fline in lines, f"{core}: coverage lines {sorted(lines)[:10]}, f at {fline}")

@case("V51", "valid", "a pdb/bdb settrace tracer active over the section (no debug command) -> exact counts")
def v51():
    import bdb
    exp = EXP("F")
    db = bdb.Bdb()
    with P.coverage_trace(exp) as cov:
        def body():
            db.reset()
            sys.settrace(db.trace_dispatch)
            try:
                return fx_v5f.f()
            finally:
                sys.settrace(None)
        cov.run("G", body)
    pass_counts(exp, cov.record(), {"G": {"fx_v5f:f": 1}})

@case("V53", "valid", "a defaultdict result carrying the exact-dict record -> PASS")
def v53():
    exp, rec = _genuine_trace()
    v = exp.score(collections.defaultdict(float, {"m": 1.0, "coverage_trace": rec}))
    expect(v.coverage == {"G": {"fx_v5f:f": 1}}, f"{v.coverage}")

def _profiler():
    saw = []
    def prof(frame, event, arg):
        if event == "call":
            saw.append(frame.f_code)
    return prof, saw

@case("V57", "valid", "the case thread installs a pure-Python profiler on itself before entering; the section runs on a worker thread -> after exit sys.getprofile() on the case thread is that profiler; {f:1}")
def v57():
    exp = EXP("F")
    prof, _ = _profiler()
    prev = sys.getprofile()
    sys.setprofile(prof)
    try:
        with P.coverage_trace(exp) as cov:
            in_thread(lambda: cov.run("G", fx_v5f.f))
        after = sys.getprofile() is prof
    finally:
        sys.setprofile(prev)
    pass_counts(exp, cov.record(), {"G": {"fx_v5f:f": 1}})
    expect(after, "the case thread's profiler was changed")

@case("V58", "valid", "on a case-owned thread: cov.run('G', body), body calls f then sys.setprofile(prof) -> after run, sys.getprofile() is prof; {f:1}; no note")
def v58():
    exp = EXP("F")
    prof, _ = _profiler()
    got = {}
    with P.coverage_trace(exp) as cov:
        def th():
            def body():
                fx_v5f.f()
                sys.setprofile(prof)
            cov.run("G", body)
            got["after"] = sys.getprofile() is prof
            sys.setprofile(None)
        in_thread(th)
    rec = cov.record()
    pass_counts(exp, rec, {"G": {"fx_v5f:f": 1}})
    expect(got.get("after") and rec["sections"]["G"][0]["notes"] == [], f"{got} {rec['sections']['G']}")

@case("V59", "valid", "a pure-Python profiler installed while another opening is open on the same thread (another task on the same loop), then a section opens -> the open succeeds; exact counts")
def v59():
    import asyncio
    exp = EXP("AB")
    prof, _ = _profiler()
    prev = sys.getprofile()
    try:
        with P.coverage_trace(exp) as cov:
            async def main():
                gate = asyncio.Event()
                async def a1():
                    fx_v5f.f()
                    await gate.wait()
                async def b1():
                    return fx_v5f.g()
                t1 = asyncio.ensure_future(cov.run_async("A", a1))
                await asyncio.sleep(0)
                sys.setprofile(prof)
                await cov.run_async("B", b1)
                gate.set()
                await t1
            asyncio.run(main())
            sys.setprofile(prev)
    finally:
        sys.setprofile(prev)
    pass_counts(exp, cov.record(), {"A": {"fx_v5f:f": 1}, "B": {"fx_v5f:g": 1}})

@case("V60", "valid", "inside G: call f, install a foreign pure-Python profiler, call g; removed after close -> {f:1, g:1}, no note; the profiler saw g")
def v60():
    exp = EXP("FG")
    prof, saw = _profiler()
    prev = sys.getprofile()
    try:
        with P.coverage_trace(exp) as cov:
            def body():
                fx_v5f.f()
                sys.setprofile(prof)
                fx_v5f.g()
            cov.run("G", body)
            sys.setprofile(prev)
    finally:
        sys.setprofile(prev)
    rec = cov.record()
    pass_counts(exp, rec, {"G": {"fx_v5f:f": 1, "fx_v5f:g": 1}})
    expect(rec["sections"]["G"][0]["notes"] == [] and fx_v5f.g.__code__ in saw or any(c.co_name == "g" for c in saw),
           "the profiler did not see g")

@case("V61", "valid", "after coverage_trace() and before __enter__, Handle._run rebound to a top-level fixture wrapper that calls the original; a section calls f; restored after exit -> PASS {f:1}, no CUT_MOVED")
def v61():
    import asyncio
    H = asyncio.events.Handle
    exp = EXP("F")
    try:
        cov = P.coverage_trace(exp)
        H._run = fx_cutw.w61
        with cov:
            cov.run("G", fx_v5f.f)
    finally:
        H._run = fx_cutw.ORIG_RUN
    pass_counts(exp, cov.record(), {"G": {"fx_v5f:f": 1}})

@case("V62", "valid", "inside the trace, Handle._run rebound and restored with no declared call in between; then G calls f -> PASS {f:1}")
def v62():
    import asyncio
    H = asyncio.events.Handle
    exp = EXP("F")
    try:
        with P.coverage_trace(exp) as cov:
            H._run = fx_cutw.w62
            H._run = fx_cutw.ORIG_RUN
            cov.run("G", fx_v5f.f)
    finally:
        H._run = fx_cutw.ORIG_RUN
    pass_counts(exp, cov.record(), {"G": {"fx_v5f:f": 1}})

@case("V63", "valid", "cov.run('A', loop.run_until_complete, main()) with X65d's loop, main opens cov.run_async('B', ...) calling g -> B opens, no NESTED_SECTION; B {g:1}; A counts nothing from the loop")
def v63():
    import asyncio, operator
    exp = EXP("AB")
    class L(asyncio.SelectorEventLoop):
        def _run_once(self):
            hs = [self._ready.popleft() for _ in range(len(self._ready))]
            list(map(operator.call, [functools.partial(h._context.run, h._callback, *h._args)
                                     for h in hs if not h._cancelled]))
    loop = L()
    try:
        with P.coverage_trace(exp) as cov:
            async def gb():
                return fx_v5f.g()
            async def main():
                return await cov.run_async("B", gb)
            cov.run("A", loop.run_until_complete, main())
        rec = cov.record()
    finally:
        loop.close()
    expect(rec["problems"] == [], f"problems {rec['problems']}")
    expect([o["calls"] for o in rec["sections"]["B"]] == [{"fx_v5f:g": 1}], f"B {rec['sections'].get('B')}")
    expect([o["calls"] for o in rec["sections"]["A"]] == [{}], f"A {rec['sections'].get('A')}")

@case("V64", "valid", "an outer tracer entered; Handle._run rebound to V61's module-level wrapper; an inner tracer entered and exited; restored; then the outer's section calls f -> outer PASS {f:1}, no CUT_MOVED")
def v64():
    import asyncio
    H = asyncio.events.Handle
    exp = EXP("F")
    try:
        with P.coverage_trace(exp) as cov:
            H._run = fx_cutw.w61
            with P.coverage_trace(EXP("A_G")):
                pass
            H._run = fx_cutw.ORIG_RUN
            cov.run("G", fx_v5f.f)
    finally:
        H._run = fx_cutw.ORIG_RUN
    pass_counts(exp, cov.record(), {"G": {"fx_v5f:f": 1}})

@case("V65", "valid", "X138 with the block set to 7 s from the waiter's start -> the waiter's enter succeeds after waiting at least 6 s; both traces PASS")
def v65():
    exp1 = EXP("F")
    cov1 = P.coverage_trace(exp1)
    cov1.__enter__()
    cov1.run("G", fx_v5f.f)
    blocking, waiter_started = threading.Event(), threading.Event()
    code = P._v5_faultpoints()["_exit_txn"]
    out = {}
    pc, real_sleep = time.perf_counter, time.sleep
    tool = FaultTool()
    def on_start(c, off):
        if c is code and not blocking.is_set():
            blocking.set()
            waiter_started.wait(30)
            t0 = pc()
            while pc() - t0 < 7.0:
                real_sleep(0.05)
    def waiter():
        blocking.wait(30)
        exp2 = EXP("F")
        cov2 = P.coverage_trace(exp2)
        waiter_started.set()
        t0 = pc()
        cov2.__enter__()
        out["waited"] = pc() - t0
        cov2.run("G", fx_v5f.f)
        cov2.__exit__(None, None, None)
        out["s"] = score(exp2, cov2.record())
    th = threading.Thread(target=waiter)
    th.start()
    try:
        tool.on(code, MON.events.PY_START, on_start)
        cov1.__exit__(None, None, None)
    finally:
        tool.close()
    th.join(60)
    pass_counts(exp1, cov1.record(), {"G": {"fx_v5f:f": 1}})
    expect(out.get("waited", 0) >= 6.0, f"waited {out.get('waited')}")
    expect_pass(out.get("s", ("none",)), {"G": {"fx_v5f:f": 1}})

@case("V68", "valid", "the id-3 tool blocks the exit transaction 3 s; meanwhile a third thread runs cov2.run('B', g) on a tracer entered before -> it returns within 1 s; cov2 PASS {g:1}; the first trace completes")
def v68():
    exp1, exp2 = EXP("F"), EXP("B_G")
    cov1 = P.coverage_trace(exp1); cov1.__enter__()
    cov1.run("G", fx_v5f.f)
    cov2 = P.coverage_trace(exp2); cov2.__enter__()
    code = P._v5_faultpoints()["_exit_txn"]
    blocking = threading.Event()
    out = {}
    pc, real_sleep = time.perf_counter, time.sleep
    tool = FaultTool()
    def on_start(c, off):
        if c is code and not blocking.is_set():
            blocking.set()
            t0 = pc()
            while pc() - t0 < 3.0:
                real_sleep(0.05)
    def third():
        blocking.wait(30)
        t0 = pc()
        out["v"] = cov2.run("B", fx_v5f.g)
        out["dt"] = pc() - t0
    th = threading.Thread(target=third)
    th.start()
    try:
        tool.on(code, MON.events.PY_START, on_start)
        cov1.__exit__(None, None, None)
    finally:
        tool.close()
    th.join(30)
    cov2.__exit__(None, None, None)
    expect(out.get("v") == 2 and out.get("dt", 9) < 1.0, f"{out}")
    pass_counts(exp2, cov2.record(), {"B": {"fx_v5f:g": 1}})
    pass_counts(exp1, cov1.record(), {"G": {"fx_v5f:f": 1}})

@sub("V69")
def _sub_v69():
    n = [0]
    real = MON.set_events
    def se(*a):
        n[0] += 1
        return real(*a)
    exp = EXP("F")
    P.coverage_trace(exp)
    MON.set_events = se
    try:
        with P.coverage_trace(exp) as cov:
            cov.run("G", fx_v5f.f)
    finally:
        MON.set_events = real
    rec = cov.record()
    return {"score": any_score(exp, rec), "lost": lost(rec, "G"), "calls": n[0]}

@case("V69", "valid", "fresh subprocess: after the first coverage_trace(), sys.monitoring.set_events replaced by a counting pass-through; a trace calling f -> PASS {f:1}, no MONITOR_LOST, the counter 0")
def v69():
    r = run_sub("V69")
    expect(r == {"score": ["PASS", {"G": {"fx_v5f:f": 1}}], "lost": False, "calls": 0}, f"{r}")

@case("V70", "valid", "a stranded pending entry of f on T2 (its unwind not delivered after the last anchor closed), then f(None) with no anchor -> P NOT_EXERCISED; calls {}, unattributed {}, dispatched {}; no MONITOR_LOST")
def v70():
    exp = EXP("F70")
    entered, go = threading.Event(), threading.Event()
    fx_b1.E70[:] = [entered, go]
    t2_go = threading.Event()
    def t2():
        t2_go.wait(30)
        try:
            fx_b1.f70(True)
        except KeyError:
            pass
        fx_b1.f70(None)
    T2 = threading.Thread(target=t2)
    with P.coverage_trace(exp) as cov:
        T2.start()
        def body():
            t2_go.set()
            entered.wait(30)
        cov.run("A", body)
        go.set()
        T2.join(30)
    rec = cov.record()
    expect_refuse(score(exp, rec), "NOT_EXERCISED")
    expect([o["calls"] for o in rec["sections"]["A"]] == [{}] and rec["uncredited"] == {"dispatched": {}, "unattributed": {}},
           f"{rec['sections']} {rec['uncredited']}")
    expect(not lost(rec, "A"), "MONITOR_LOST")

@sub("V71")
def _sub_v71(event):
    exp = EXP("A_T135")
    box = []
    me = threading.get_ident()
    st = {"armed": False}
    def hook(ev_, args):
        if st["armed"] and ev_ == event and threading.get_ident() == me:
            st["armed"] = False
            raise RuntimeError("V71 hook")
    sys.addaudithook(hook)
    with P.coverage_trace(exp) as cov:
        st["armed"] = True
        try:
            cov.run("A", fx_b1.t135, box)
            first = None
        except RuntimeError:
            first = "RuntimeError"
        st["armed"] = False
        ran_first = list(box)
        anchors = P._v5_state()["anchors"]
        cov.run("A", fx_b1.t135, box)
    rec = cov.record()
    return {"first": first, "ran_first": ran_first, "anchors": anchors, "n_openings": len(rec["sections"]["A"]),
            "notes": rec["sections"]["A"][0]["notes"], "problems": rec["problems"], "score": any_score(exp, rec)}

@case("V71", "valid", "fresh subprocess: an audit hook raises at the first sys._getframe (variants: object.__getattr__, builtins.id) event of one cov.run('A', f); then cov.run('A', f) again -> the first raises; f did not run; anchors 0; one opening of A, PASS {f:1}, no OPEN_AT_EXIT, no problem")
def v71():
    for event in ("sys._getframe", "object.__getattr__", "builtins.id"):
        r = run_sub(f"V71:{event}")
        expect(r == {"first": "RuntimeError", "ran_first": [], "anchors": 0, "n_openings": 1, "notes": [], "problems": [],
                     "score": ["PASS", {"A": {"fx_b1:t135": 1}}]}, f"{event}: {r}")

@sub("V72b")
def _sub_v72b():
    exp = EXP("F")
    cov = P.coverage_trace(exp)
    cov.__enter__()
    cov.run("G", fx_v5f.f)
    me = threading.get_ident()
    arm = {"on": True}
    def hook(event, args):
        if arm["on"] and event == "sys.monitoring.register_callback" and threading.get_ident() == me:
            arm["on"] = False
            raise RuntimeError("V72 hook")
    sys.addaudithook(hook)
    try:
        cov.__exit__(None, None, None)
    except RuntimeError:
        pass
    def rd():
        try:
            cov.record()
            return None
        except GateSpecError as e:
            return code_of(e)
    first = rd()
    exp2 = EXP("F")
    with P.coverage_trace(exp2) as c2:
        c2.run("G", fx_v5f.f)
    return {"first": first, "second_trace": any_score(exp2, c2.record()), "again": rd()}

@case("V72b", "valid", "fresh subprocess: V72's first tracer (its __exit__ raised inside X5): record() TRACE_INCOMPLETE; a second tracer runs (prunes the first core); record() again -> TRACE_INCOMPLETE both times")
def v72b():
    r = run_sub("V72b")
    expect(r == {"first": "TRACE_INCOMPLETE", "second_trace": ["PASS", {"G": {"fx_v5f:f": 1}}], "again": "TRACE_INCOMPLETE"}, f"{r}")


# -- revision 11: the new cases (X35e, X57d, R24, X117g, V72b, X137j, R23) --------------------------------
def _codes(problems):
    return [code_of(p) for p in problems]

@case("X35e", "cut", "rev. 11 (GAP-34); main thread before the self-trace, fresh wrapper: fx_r11.enable() binds Handle._run to enable.<locals>.instrumented (aiodebug's shape); coverage_trace() twice while bound -> CUT_UNAVAILABLE, CUT_UNAVAILABLE; restored; coverage_trace() again -> constructed")
def x35e():
    import asyncio
    H = asyncio.events.Handle
    run0 = H.__dict__["_run"]
    got = []
    fx_r11.enable()
    try:
        expect(H.__dict__["_run"].__qualname__ == "enable.<locals>.instrumented", "fixture shape")
        for _ in range(2):
            try:
                P.coverage_trace(EXP("F"))
                got.append("constructed")
            except GateSpecError as e:
                got.append(code_of(e))
    finally:
        H._run = run0
    try:
        c3 = P.coverage_trace(EXP("F"))
        got.append("constructed")
        del c3
    except GateSpecError as e:
        got.append(code_of(e))
    expect(got == ["CUT_UNAVAILABLE", "CUT_UNAVAILABLE", "constructed"], f"{got}")

@case("X57d", "identity", "rev. 11 (GAP-36, W066); main thread before the self-trace: P(blk) entered; 2,000 lists, gc.freeze(); Q(blk) entered (joins P's mint); a worker blocks inside blk; Q exits; worker released, joined; P exits; gc.unfreeze() -> Q's problems exactly [CLONE_ALIVE], P's empty")
def x57d():
    ev, inside = threading.Event(), threading.Event()
    keep = []
    w = None
    try:
        cP = P.coverage_trace(EXP("BLK"))
        cP.__enter__()
        try:
            keep.append([[] for _ in range(2000)])
            gc.freeze()
            cQ = P.coverage_trace(EXP("BLK"))
            cQ.__enter__()
            w = threading.Thread(target=fx_r11.blk, args=(ev, inside))
            w.start()
            expect(inside.wait(30), "worker never entered blk")
            cQ.__exit__(None, None, None)
            ev.set()
            w.join(30)
        finally:
            ev.set()
            cP.__exit__(None, None, None)
        rq, rp = cQ.record(), cP.record()
    finally:
        ev.set()
        if w is not None:
            w.join(30)
        gc.unfreeze()
        keep.clear()
        gc.collect()        # GAP-39: 3.12.3 restores its boot count at a full collection
    expect(_codes(rq["problems"]) == ["CLONE_ALIVE"], f"Q problems {rq['problems']}")
    expect(rp["problems"] == [], f"P problems {rp['problems']}")

@case("R24", "residual", "rev. 11 (GAP-36, W076); main thread before the self-trace: 300,000 lists, gc.freeze(); in section A a same-globals clone of M_T is made and called; gc.unfreeze(), lists deleted, gc.collect(), gc.freeze() (count not above its value at mint); clone kept through exit; gc.unfreeze() -> PASS {f:1}, no CLONE_ALIVE")
def r24():
    box = {"lists": [[] for _ in range(300000)]}
    keep = []
    counts = {}
    try:
        gc.freeze()
        exp = EXP("A_F")
        with P.coverage_trace(exp) as cov:
            counts["mint"] = gc.get_freeze_count()
            def body():
                keep.append(types.FunctionType(fx_v5f.f.__code__, fx_v5f.f.__globals__))
                keep[0](0)
                gc.unfreeze()
                box.pop("lists")
                gc.collect()
                gc.freeze()
                counts["refrozen"] = gc.get_freeze_count()
            cov.run("A", body)
        rec = cov.record()
    finally:
        gc.unfreeze()
        keep.clear()
        box.clear()
        gc.collect()        # GAP-39
    expect(counts["refrozen"] <= counts["mint"], f"precondition: the count rose {counts}")
    expect_pass(score(exp, rec), {"A": {"fx_v5f:f": 1}})
    expect(not any(p.startswith("[V5:CLONE_ALIVE]") for p in rec["problems"]), f"{rec['problems']}")

@case("X117g", "scoring", "rev. 11 (GAP-36, W224): check_metrics({'m': I(3)}), I an int subclass counting __float__ and __bool__ -> usable; __float__ called exactly once, __bool__ never")
def x117g():
    n = {"float": 0, "bool": 0}
    class I(int):
        def __float__(self):
            n["float"] += 1
            return int.__float__(self)
        def __bool__(self):
            n["bool"] += 1
            return int.__bool__(self)
    m = EXP("F").check_metrics({"m": I(3)})["G"]
    expect(m["present"] is True and m["usable"] is True, f"{m}")
    expect(n == {"float": 1, "bool": 0}, f"user methods called: {n}")

def _x137j(with_section):
    mon = sys.monitoring
    E = mon.events
    exp = EXP("F")
    with P.coverage_trace(exp) as c1:
        c1.run("G", fx_v5f.f)
    t = P._v5_state()["tool"]
    mon.free_tool_id(t)
    mon.use_tool_id(t, "other137j")
    def line_cb(code, line):
        return None
    def start_cb(code, offset):
        return None
    mon.register_callback(t, E.LINE, line_cb)
    mon.register_callback(t, E.PY_START, start_cb)
    mon.set_events(t, E.LINE)
    mon.set_local_events(t, fx_r11.lev.__code__, E.PY_START)
    mon.free_tool_id(t)
    exp2 = EXP("F")
    with P.coverage_trace(exp2) as c2:
        if with_section:
            c2.run("G", fx_v5f.f)
    def cb(ev):
        prev = mon.register_callback(t, ev, None)
        mon.register_callback(t, ev, prev)
        return prev
    lc, sc = cb(E.LINE), cb(E.PY_START)
    return {"tool_ours": P._v5_state()["tool_ours"], "same_id": P._v5_state()["tool"] == t,
            "global_events": mon.get_events(t), "local_events": mon.get_local_events(t, fx_r11.lev.__code__),
            "line_cb_other": lc is line_cb, "start_cb_styxx": getattr(sc, "__module__", None) == P.__name__,
            "second": _outcome_json(score(exp2, c2.record())), "PY_START": E.PY_START}

# The row says only that the second tracer "runs". Both shapes are run: with no section, the
# reconciliation's _unwind_off(None) is what clears the foreign global events (F39); with a section,
# the opener's _unwind_on also rewrites them. The row's outcome must hold in both.
@sub("X137j")
def _sub_x137j():
    return _x137j(False)

@sub("X137j-sec")
def _sub_x137j_sec():
    return _x137j(True)

@case("X137j", "residual", "rev. 11 (GAP-36, W141); fresh subprocess: a tracer runs and exits; its id freed; another tool takes it, registers LINE and PY_START callbacks, sets global LINE and local PY_START on a fixture's code, frees it; a second tracer runs and exits -> tool_ours True; global events 0; local events still PY_START; LINE callback the other's; PY_START callback styxx's")
def x137j():
    for mode, second in (("X137j", ["REFUSE", "SECTION_ABSENT"]), ("X137j-sec", ["PASS", {"G": {"fx_v5f:f": 1}}])):
        r = run_sub(mode)
        pys = r.pop("PY_START")
        expect(r == {"tool_ours": True, "same_id": True, "global_events": 0, "local_events": pys,
                     "line_cb_other": True, "start_cb_styxx": True, "second": second}, f"{mode}: {r}")

@case("R23", "residual", "rev. 11 (GAP-36, W074); inside the self-trace: in section A, f is called; u.__code__ = f.__code__ (M_T), u a function of f's module; u() called; u.__code__ restored before the section closes -> PASS {f:2}, no problem")
def r23():
    exp = EXP("A_F")
    u = fx_v5f.other
    u0 = u.__code__
    try:
        with P.coverage_trace(exp) as cov:
            def body():
                fx_v5f.f()
                u.__code__ = fx_v5f.f.__code__
                try:
                    u()
                finally:
                    u.__code__ = u0
            cov.run("A", body)
        rec = cov.record()
    finally:
        u.__code__ = u0
    expect_pass(score(exp, rec), {"A": {"fx_v5f:f": 2}})
    expect(rec["problems"] == [], f"problems {rec['problems']}")



# -- X72b, X65b, X30b (their v5e base shapes are spec data from revision 11) --------------------------
@case("X72b", "scoring", "X72's trace (gather children inside run_async): the message contains exactly dispatched {'fx_v5f:f': 2}, unattributed {}; check_metrics G:exercises usable False, note [V5:NOT_EXERCISED]")
def x72b():
    import asyncio
    exp = EXP("F")
    with P.coverage_trace(exp) as cov:
        async def main():
            async def child():
                fx_v5f.f()
            await asyncio.gather(child(), child())
        asyncio.run(cov.run_async("G", main))
    rec = cov.record()
    out = score(exp, rec)
    expect_refuse(out, "NOT_EXERCISED")
    expect("dispatched {'fx_v5f:f': 2}, unattributed {}" in out[2], out[2][:300])
    cm = exp.check_metrics({"m": 1.0, "coverage_trace": rec})["G:exercises"]
    expect(cm["usable"] is False and cm["note"].startswith("[V5:NOT_EXERCISED]"), f"{cm}")

@case("X65b", "cut", "V15's inner tracer entered and exited inside the outer; then section A runs a loop serving another thread's run_coroutine_threadsafe and call_soon_threadsafe jobs calling f -> A: NOT_EXERCISED with dispatched {f:2}")
def x65b():
    import asyncio
    exp, e_in = EXP("AB"), EXP("H_F")
    ready, bdone, box = threading.Event(), threading.Event(), {}
    with P.coverage_trace(exp) as cov:
        with P.coverage_trace(e_in) as inner:              # V15's inner tracer, inside the outer
            inner.run("H", fx_v5f.f)
        async def main_a():
            box["loop"] = asyncio.get_running_loop()
            ready.set()
            while not bdone.is_set():
                await asyncio.sleep(0.005)
        async def job():
            fx_v5f.f()
        def b():
            try:
                ready.wait(10)
                fx_v5f.g()
                asyncio.run_coroutine_threadsafe(job(), box["loop"]).result(10)
                done = threading.Event()
                box["loop"].call_soon_threadsafe(fx_v5f.f)
                box["loop"].call_soon_threadsafe(done.set)
                done.wait(10)
            finally:
                bdone.set()
        ta = threading.Thread(target=lambda: cov.run("A", asyncio.run, main_a()))
        tb = threading.Thread(target=lambda: cov.run("B", b))
        ta.start(); tb.start()
        ta.join(30); tb.join(30)
    rec = cov.record()
    out = score(exp, rec)
    expect_refuse(out, "NOT_EXERCISED")
    expect("gate 'A'" in out[2], out[2][:200])
    expect(rec["uncredited"]["dispatched"] == {"fx_v5f:f": 2}, f"uncredited {rec['uncredited']}")

@case("X30b", "identity", "this module's code 17 hops down a foreign wraps chain: the walk is bounded -> FOREIGN_DEFINITION")
def x30b():
    importlib.import_module("fx_x30b")
    enter_refuses("X30B", "FOREIGN_DEFINITION")


# -- Hazard sweeps (main thread, before the self-trace) -----------------------------------------------
import signal as _signal

class Timeout(Exception):
    pass

ARMED = [True]          # the flood raises only while this is set: the harness's own loop is flood-safe

def _flood(interval, exc):
    def handler(signum, frame):
        if ARMED[0]:
            raise exc()
    old = _signal.signal(_signal.SIGALRM, handler)
    _signal.setitimer(_signal.ITIMER_REAL, interval, interval)
    return old

def _unflood(old):
    _signal.setitimer(_signal.ITIMER_REAL, 0, 0)
    _signal.signal(_signal.SIGALRM, old)

@case("H1", "hazard", "finalizers (a cycle whose __del__ calls a target, or enters and exits a tracer) at gen-0 thresholds 1-40 across open, close, record, the callbacks, enter and exit, 10 s watchdog -> no hang; no problem other than REENTRANT")
def h1():
    unraisable = []
    old_hook, old_thr = sys.unraisablehook, gc.get_threshold()
    sys.unraisablehook = lambda u: unraisable.append(type(u.exc_value).__name__)
    bad = []
    class Cyc:
        def __init__(self, kind):
            self.kind, self.me = kind, self
        def __del__(self):
            if self.kind == "call":
                fx_v5f.f()
            else:
                with P.coverage_trace(EXP("A_G")):
                    pass
    def junk(n):
        for i in range(n):
            Cyc("call" if i % 2 else "trace")
    try:
        for t in range(1, 41):
            out = {}
            def trial():
                gc.set_threshold(t)
                exp = EXP("F")
                junk(20)
                cov = P.coverage_trace(exp)
                junk(20)
                with cov:
                    junk(20)
                    cov.run("G", lambda: (junk(10), fx_v5f.f(), junk(10)))
                    junk(20)
                junk(20)
                out["rec"] = cov.record()
                gc.set_threshold(*old_thr)
            th = threading.Thread(target=trial, daemon=True)
            th.start()
            th.join(10.0)
            if th.is_alive():
                bad.append((t, "HANG"))
                break
            rec = out.get("rec")
            if rec is None:
                bad.append((t, "no record"))
                continue
            extra = set(_problem_codes(rec)) - {"REENTRANT"}
            if extra:
                bad.append((t, sorted(extra)))
    finally:
        gc.set_threshold(*old_thr)
        sys.unraisablehook = old_hook
        gc.collect()
    expect(not bad, f"{bad[:5]}")

@case("H2", "hazard", "ported from v5e (spec data, run_protocol_v5e._h2_trials): SIGALRM Timeout(Exception) in a tight traced loop (f, g) after a target call, 20 trials, each loop running until the handler has run -> 20/20 propagated, 20/20 PASS, 20/20 handler ran, 20/20 ok")
def h2():
    tmp = v5e_port._Tmp(Path(WORK))
    try:
        r = v5e_port._h2_trials(tmp.exp(v5e_port.G1(v5e_port.T("f"))), v5e_port._fx())
    finally:
        tmp.close()
    H2_REPORT.update(r)
    expect(r["propagated"] == r["passed"] == r["handler_ran"] == r["ok"] == 20, f"{r}")

H2_REPORT = {}

@case("H3", "hazard", "kept from v5e (spec data, run_protocol_v5e._h3_trials): KeyboardInterrupt raised from a signal inside a traced section, 5 trials -> 5/5 propagate, 5/5 ok (no profile or trace function left, the machinery quiet, f restored)")
def h3():
    tmp = v5e_port._Tmp(Path(WORK))
    try:
        r = v5e_port._h3_trials(tmp.exp(v5e_port.G1(v5e_port.T("f"))), v5e_port._fx())
    finally:
        tmp.close()
    expect(r["propagated"] == r["ok"] == 5, f"{r}")

@case("H4", "hazard", "performance: the Cost table re-measured (reported, not gated)")
def h4():
    n = 20000
    exp = EXP("F")
    t0 = time.perf_counter()
    for _ in range(n):
        fx_v5f.f()
    base = time.perf_counter() - t0
    with P.coverage_trace(exp) as cov:
        def body():
            for _ in range(n):
                fx_v5f.f()
        t0 = time.perf_counter()
        cov.run("G", body)
        traced = time.perf_counter() - t0
        t0 = time.perf_counter()
        for _ in range(200):
            cov.run("G", fx_v5f.g)
        sections = (time.perf_counter() - t0) / 200
    H4_REPORT.update(untraced_call_us=round(base / n * 1e6, 3), traced_call_us=round(traced / n * 1e6, 3),
                     section_open_close_us=round(sections * 1e6, 2))

H4_REPORT = {}

@case("H5", "hazard", "gc cost: no gc call at resolution or close; the exit scan is refcount-gated (read from gc's audit events on a trace whose target has no extra reference)")
def h5():
    me = threading.get_ident()
    st = {"on": False, "events": []}
    def hook(event, args):
        if st["on"] and event.startswith("gc.") and threading.get_ident() == me:
            st["events"].append(event)
    sys.addaudithook(hook)
    exp = EXP("F")
    with P.coverage_trace(exp):                           # the cut and the codes are now known
        pass
    try:
        st["on"] = True
        cov = P.coverage_trace(exp)
        with cov:
            cov.run("G", fx_v5f.f)
        st["on"] = False
    finally:
        st["on"] = False
    expect(st["events"] == [], f"gc audit events during resolution, open/close and exit: {st['events']}")
    expect_pass(score(exp, cov.record()), {"G": {"fx_v5f:f": 1}})

@case("H7", "hazard", "user locks: a `with lock:` loop inside a section under a SIGALRM flood for 30 s -> 0 harness locks left held; 0 hangs")
def h7():
    exp = EXP("F")
    lock = threading.Lock()
    deadline = time.monotonic() + 30.0
    n = [0]
    with P.coverage_trace(exp) as cov:
        def body():
            fx_v5f.f()
            while time.monotonic() < deadline:
                try:
                    with lock:
                        n[0] += 1
                except Timeout:
                    pass
        ARMED[0] = False
        old = _flood(0.0005, Timeout)
        try:
            while True:
                try:
                    ARMED[0] = False
                    if time.monotonic() >= deadline:
                        break
                    ARMED[0] = True
                    cov.run("G", body)
                    ARMED[0] = False
                except Timeout:
                    ARMED[0] = False
        finally:
            ARMED[0] = False
            _unflood(old)
            ARMED[0] = True
    expect(not lock.locked(), "the harness lock is left held")
    expect(n[0] > 0, "the loop never ran")

@case("H8", "hazard", "body-less credit: a SIGALRM flood with one section per call, each call counting its body runs, 8 s -> credited <= body runs")
def h8():
    exp = EXP("HB")
    fx_b1.BODY[0] = 0
    deadline = time.monotonic() + 8.0
    with P.coverage_trace(exp) as cov:
        ARMED[0] = False
        old = _flood(0.0002, Timeout)
        try:
            while True:
                try:
                    ARMED[0] = False
                    if time.monotonic() >= deadline:
                        break
                    ARMED[0] = True
                    cov.run("G", fx_b1.hbody)
                    ARMED[0] = False
                except Timeout:
                    ARMED[0] = False
        finally:
            ARMED[0] = False
            _unflood(old)
            ARMED[0] = True
    rec = cov.record()
    credited = sum(o["calls"].get("fx_b1:hbody", 0) for o in rec["sections"].get("G", []))
    H8_REPORT.update(credited=credited, body_runs=fx_b1.BODY[0])
    expect(credited <= fx_b1.BODY[0], f"credited {credited} > body runs {fx_b1.BODY[0]}")

H8_REPORT = {}


# -- H10: G_SIG's three L-DELIVERY cells (Stated limits, "G_SIG (frozen decision)") ----------------------
H10_REPORT = {}
CELL_SECONDS = 60.0            # G_SIG: 60 s per cell on each verified interpreter

class _ProbeWorker:
    """One long-lived thread that runs every probe cycle. "Another thread" must really be another
    thread: a fresh thread started after a scenario thread died can reuse its ident, and an RLock
    (H6's M1) left held by the dead thread would then be re-entered instead of blocking."""
    def __init__(self):
        import queue
        self.q = queue.Queue()
        self.th = threading.Thread(target=self._loop, daemon=True, name="probe-worker")
        self.th.start()
    def _loop(self):
        while True:
            job, done, out = self.q.get()
            try:
                out["v"] = job()
            except BaseException as e:                 # noqa: BLE001
                out["exc"] = e
            done.set()
    def run(self, job, timeout):
        done, out = threading.Event(), {}
        self.q.put((job, done, out))
        return done.wait(timeout), out
_PROBE_WORKER = [None]

def probe_cycle(timeout=5.0):
    """G_FI's probe cycle, on another thread (the long-lived probe worker): coverage_trace(EXP_PROBE),
    with cov: cov.run('P', probe), then score. It completes iff it finishes within the timeout and
    the score is PASS {probe:1}. A worker that did not finish is abandoned (it may be blocked)."""
    def job():
        exp = EXP("PROBE")
        with P.coverage_trace(exp) as cov:
            cov.run("P", fx_probe.probe)
        return score(exp, cov.record())
    if _PROBE_WORKER[0] is None:
        _PROBE_WORKER[0] = _ProbeWorker()
    done, out = _PROBE_WORKER[0].run(job, timeout)
    if not done:
        _PROBE_WORKER[0] = None
        return False
    s = out.get("v", ("",))
    return s[0] == "PASS" and s[1] == {"P": {"fx_probe:probe": 1}}

def _poisoned(before):
    # G_SIG's poison test as written (revision 3, N8): every field but `cut` and `tool` (C5's test).
    # It has no R9-6 exemption for `tool_ours`; see GAP-45.
    gc.collect()
    ok = probe_cycle()
    after = dict(P._v5_state()); after.pop("pid", None)
    diff = [k for k, v in before.items() if k not in ("cut", "tool") and after.get(k) != v]
    return (not ok) or bool(diff), diff

def _gap45_only(before_tool_none, poisoned, diff):
    """True when a cell is poisoned only by `tool_ours` at the process's first acquisition (GAP-45)."""
    return poisoned and before_tool_none and diff == ["tool_ours"]

def _raise_from_callee(box, err):
    # Arms after this frame's RESUME, so untraced nothing between arming and the handler checks the eval
    # breaker (the error is built once; RAISE and the unwind do not check it). The exception leaves this
    # frame, so PY_UNWIND fires for it: that callback is where L-DELIVERY can replace it.
    err.__traceback__ = None      # a re-raised instance would otherwise grow its traceback each round
    ARMED[0] = True
    box["inflight"] = True
    raise err

def _except_flow(deadline, box):
    err = ValueError("flow")
    while True:
        if time.monotonic() >= deadline:
            return
        try:
            try:
                _raise_from_callee(box, err)
            except ValueError:
                box["inflight"] = False
                ARMED[0] = False
                box["handled"] += 1
        except Timeout:
            ARMED[0] = False
            if box["inflight"]:
                box["lost"] += 1
                box["inflight"] = False

def _cleanup_flow(deadline, box, lock):
    while True:
        if time.monotonic() >= deadline:
            return
        try:
            with lock:
                ARMED[0] = True
                box["work"] += 1
                ARMED[0] = False
            try:
                box["entered"] += 1
                ARMED[0] = True
                fx_v5f.f()
                ARMED[0] = False
            finally:
                ARMED[0] = False
                box["cleaned"] += 1
        except Timeout:
            ARMED[0] = False

@case("H10", "hazard", "L-DELIVERY cells, 60 s each under a 20 us SIGALRM flood: (a) an except ValueError flow outside every section with a trace active -> 0 lost handlers; (b) the same inside a section, reported; (c) with-lock and try/finally flows inside a section -> 0 skipped cleanups, 0 leaks; no cell poisoned")
def h10():
    exp = EXP("F")
    lock = threading.Lock()
    res = {}
    for cell in ("a", "b", "c"):
        before = dict(P._v5_state()); before.pop("pid", None)
        first_acq = before["tool"] is None
        box = {"inflight": False, "handled": 0, "lost": 0, "work": 0, "entered": 0, "cleaned": 0}
        with P.coverage_trace(exp) as cov:
            if cell == "a":
                cov.run("G", fx_v5f.f)                    # one section, fault-free, before the flood
                expect(P._v5_state()["global_events"] == 0, "global_events != 0 before arming")
            ARMED[0] = False
            old = _flood(0.00002, Timeout)
            try:
                deadline = time.monotonic() + CELL_SECONDS
                if cell == "a":
                    _except_flow(deadline, box)
                elif cell == "b":
                    cov.run("G", lambda: (fx_v5f.f(), _except_flow(deadline, box)))
                else:
                    cov.run("G", _cleanup_flow, deadline, box, lock)
            finally:
                ARMED[0] = False
                _unflood(old)
                ARMED[0] = True
        del cov
        poisoned, diff = _poisoned(before)
        res[cell] = dict(box, poisoned=poisoned, diff=diff, lock_left_held=lock.locked(),
                         gap45_only=_gap45_only(first_acq, poisoned, diff))
    H10_REPORT.update(res)
    expect(res["a"]["lost"] == 0 and res["a"]["handled"] > 0, f"cell (a): {res['a']}")
    expect(res["c"]["entered"] == res["c"]["cleaned"] and not res["c"]["lock_left_held"], f"cell (c): {res['c']}")
    expect(not any(r["poisoned"] and not r["gap45_only"] for r in res.values()), f"poisoned: {res}")
    if any(r["poisoned"] for r in res.values()):
        raise KnownGapFailure("GAP-45", f"poisoned only by tool_ours at the first acquisition: {res}")


# -- H6: the no-hang fault sweep, the deterministic core of G_FI (single-thread scenario) ---------------
H6_REPORT = {}

def _gfi_scenario(box):
    """The single-thread scenario (G_FI): constructs its tracer only through coverage_trace(), catches
    nothing. Gate A declares f and g; the sentinel gate S declares h, which the scenario calls only
    outside S's section (inside A)."""
    cov = P.coverage_trace(EXP("GFI"))
    box["cov"] = cov
    with cov:
        cov.run("A", fx_gfi.body)
    return cov

def _run_scenario(inject=None):
    """Runs the scenario on a new thread. inject = (key, offset, k, exc): raise exc at the k-th execution
    of offset in _v5_faultpoints()[key] on that thread. Returns (box, raised, unraisable, fired)."""
    box = {}
    unraisable, excepthooked = [], []
    old_u, old_e = sys.unraisablehook, threading.excepthook
    sys.unraisablehook = lambda u: unraisable.append(u.exc_value)
    threading.excepthook = lambda a: excepthooked.append(a.exc_value)
    go = threading.Event()
    def t():
        go.wait(30)
        try:
            _gfi_scenario(box)
        except BaseException as e:                     # noqa: BLE001  C2/C6 read it
            box["raised"] = e
    th = threading.Thread(target=t, daemon=True)
    th.start()
    fired, counts, inj = [], collections.Counter(), None
    if inject is not None:
        key, offset, k, exc = inject
        def on_instr(code, off):
            if off == offset:
                counts[off] += 1
                if counts[off] == k and not fired:
                    fired.append(1)
                    raise exc
        inj = Injector([key], th.ident, on_instr)
    try:
        go.set()
        th.join(WATCHDOG_S)
    finally:
        if inj is not None:
            inj.close()
        sys.unraisablehook, threading.excepthook = old_u, old_e
    return box, th.is_alive(), unraisable + excepthooked, bool(fired)

def _discovery():
    fp = P._v5_faultpoints()
    counts = collections.Counter()
    box = {}
    go = threading.Event()
    def t():
        go.wait(30)
        _gfi_scenario(box)
    th = threading.Thread(target=t, daemon=True)
    th.start()
    def on_instr(code, off):
        counts[(keyof[id(code)], off)] += 1
    keyof = {id(c): k for k, c in fp.items()}
    inj = Injector(list(fp), th.ident, on_instr)
    try:
        go.set()
        th.join(WATCHDOG_S)
    finally:
        inj.close()
    return {(k, off, n) for (k, off), c in counts.items() for n in (1, 2) if c >= n}

def _within_I6_gfi(rec, base):
    ok, why = envelope_ok(rec, base)
    if not ok:
        return False, why
    if rec is not None and sorted(rec["problems"]) != sorted(base["problems"]):
        return False, f"problems {rec['problems']} != baseline {base['problems']}"
    return True, ""

SWEEP_STOP_UNCLEAN = 10

def _sweep_must_stop(unclean):
    """A sweep that has already failed stops early: at its first C3 failure (a hang, or a probe cycle
    that did not complete: the machinery may be held, so every later point would wait out its
    watchdog too) or at its tenth unclean
    point. The verdict is FAIL either way; a clean sweep never stops early."""
    return bool(unclean) and (len(unclean) >= SWEEP_STOP_UNCLEAN
                              or any(b.startswith("C3") for b in unclean[-1][1]))

def _bounded_exit(cov, timeout=5.0):
    """The harness's own __exit__ of a still-active tracer, on a thread with G_FI's 5 s bound (a
    mutant can leave the machinery held; the harness must not hang on it). True iff it returned."""
    out = {}
    def t():
        try:
            cov.__exit__(None, None, None)
            out["ok"] = True
        except BaseException as e:                     # noqa: BLE001
            out["exc"] = e
    th = threading.Thread(target=t, daemon=True)
    th.start()
    th.join(timeout)
    if "exc" in out:
        raise out["exc"]
    return out.get("ok", False)

@case("H6", "hazard", "the no-hang fault sweep (G_FI's deterministic core, single-thread scenario): the id-5 injector raises at each executed instruction of every _v5_faultpoints() code, one point per run (k <= 2) -> every point clean: C1, C2, C3, C5, C6, C7, C8")
def h6():
    base_box, hung, _, _ = _run_scenario()
    expect(not hung and "raised" not in base_box, f"the baseline failed: {base_box.get('raised')!r}")
    base = base_box["cov"].record()
    del base_box
    d1, d2 = _discovery(), _discovery()
    expect(d1 == d2, f"the two discovery runs differ ({len(d1)} vs {len(d2)} points): the G_FI run is void")
    points = sorted(d1, key=lambda p: (p[0], p[1], p[2]))
    unclean, unreached = [], 0
    for key, offset, k in points:
        s0 = dict(P._v5_state()); s0.pop("pid", None)
        exc = Injected(f"{key}@{offset}#{k}")
        box, hung, hooked, fired = _run_scenario((key, offset, k, exc))
        if not fired:
            unreached += 1
            continue
        bad = []
        if hung:
            bad.append("C3: the scenario hung")
        raised = box.get("raised")
        c2 = (raised is exc or any(x is exc for x in hooked)
              or (isinstance(raised, GateSpecError) and code_of(raised) == "UNRESOLVED" and raised.__cause__ is exc))
        if not c2:
            bad.append(f"C2: injected exception not seen (raised {type(raised).__name__})")
        if raised is not None and raised is not exc and not (isinstance(raised, GateSpecError) and raised.__cause__ is exc):
            bad.append(f"C6: another exception left the scenario: {raised!r}")
        cov = box.get("cov")
        active = False
        if cov is not None:
            try:
                rec = cov.record()
            except GateSpecError as e:
                rec = None
                active = code_of(e) == "TRACE_ACTIVE" and "the tracer is active" in str(e)
            if rec is not None:
                ok, why = _within_I6_gfi(rec, base)
                if not ok:
                    bad.append("C1/C8: " + why)
                if rec["sections"].get("S"):
                    bad.append("C1: the sentinel section S was opened")
        if not probe_cycle():
            bad.append("C3: the probe cycle did not complete")
        st = P._v5_state()
        for m in st["mints"]:
            if m["holders"] != (1 if active else 0) or not m["installed"]:
                bad.append(f"C7: mint {m}")
        if active and cov is not None and not _bounded_exit(cov):
            bad.append("C3: the harness's exit of the still-active tracer did not return within 5 s")
        elif active and cov is not None:
            try:
                rec = cov.record()
                ok, why = _within_I6_gfi(rec, base)
                if not ok:
                    bad.append("C8 (step 5): " + why)
            except GateSpecError as e:
                bad.append(f"C8 (step 5): record() refused {code_of(e)}")
        box.clear(); del cov, raised, exc
        gc.collect()
        if not probe_cycle():
            bad.append("C5: the second probe cycle did not complete")
        s1 = dict(P._v5_state()); s1.pop("pid", None)
        diff = [f for f, v in s0.items() if f not in ("cut", "tool") and s1.get(f) != v]
        if diff:
            bad.append(f"C5: _v5_state() differs from S0 in {diff}")
        for kk, (fn, code) in ORIG.items():
            if fn.__code__ is not code:
                bad.append(f"C5: {kk} not restored")
                fn.__code__ = code
        if bad:
            unclean.append(((key, offset, k), bad[:3]))
            if _sweep_must_stop(unclean):
                H6_REPORT["stopped_early_at"] = str((key, offset, k))
                break
    H6_REPORT.update(points=len(points), unreached=unreached, unclean=len(unclean), first_unclean=unclean[:5])
    expect(not unclean, f"{len(unclean)} of {len(points)} points not clean: {unclean[:3]}")


# -- X140 (H9): the back-edge trials, made deterministic ---------------------------------------------------
class ThrowHandled:
    """An awaitable that handles a thrown cancellation and then returns: the coroutine awaiting it takes
    the SEND loop's throw-then-return path (M7, _run_async)."""
    def __await__(self):
        try:
            yield "suspend"
        except BaseException:                          # the thrown cancellation is handled here
            return "handled"
        return "normal"

def _x140_scenario(box):
    """X140's scenario: 3 openings, one run_async driven through a thrown-then-handled cancellation;
    constructs its tracer only through coverage_trace() and catches nothing but the StopIteration that
    ends the driven coroutine."""
    import asyncio
    cov = P.coverage_trace(EXP("X140"))
    box["cov"] = cov
    with cov:
        cov.run("A", fx_gfi.f)
        cov.run("B", fx_gfi.g)
        async def af():
            fx_gfi.h()
            return await ThrowHandled()
        co = cov.run_async("C", af)
        co.send(None)
        try:
            co.throw(asyncio.CancelledError())
        except StopIteration:
            pass
    box["rec"] = cov.record()
    return cov

def _x140_scenario_b(box):
    """X140's scenario, variant (b). The row says the run_async opening is "driven through a
    thrown-then-handled cancellation" and does not say whether the coroutine then completes (variant
    (a), _x140_scenario) or stays suspended. Here it handles the cancellation, awaits again and is
    still suspended at exit, so exit's X3 detaches it; it is closed after record(). The row's outcome
    must hold in both variants (see SPEC_GAPS GAP-49)."""
    import asyncio
    cov = P.coverage_trace(EXP("X140"))
    box["cov"] = cov
    async def af():
        fx_gfi.h()
        await ThrowHandled()
        await Suspend()
    co = cov.run_async("C", af)
    with cov:
        cov.run("A", fx_gfi.f)
        cov.run("B", fx_gfi.g)
        co.send(None)
        co.throw(asyncio.CancelledError())
    box["rec"] = cov.record()
    co.close()
    return cov

def _gfi_point(scenario, key, offset, k, exc, base, sentinel=None):
    """One G_FI point on `scenario`, checked in G_FI's order (C2, C6, C1/C8, C3, C7, step 5, C5).
    Returns (fired, bad)."""
    s0 = dict(P._v5_state()); s0.pop("pid", None)
    box, unraisable, hooked = {}, [], []
    old_u, old_e = sys.unraisablehook, threading.excepthook
    sys.unraisablehook = lambda u: unraisable.append(u.exc_value)
    threading.excepthook = lambda a: hooked.append(a.exc_value)
    go = threading.Event()
    def t():
        go.wait(30)
        try:
            scenario(box)
        except BaseException as e:                     # noqa: BLE001
            box["raised"] = e
    th = threading.Thread(target=t, daemon=True)
    th.start()
    fired, counts = [], collections.Counter()
    def on_instr(code, off):
        if off == offset:
            counts[off] += 1
            if counts[off] == k and not fired:
                fired.append(1)
                raise exc
    inj = Injector([key], th.ident, on_instr)
    try:
        go.set()
        th.join(WATCHDOG_S)
    finally:
        inj.close()
        sys.unraisablehook, threading.excepthook = old_u, old_e
    if not fired:
        return False, []
    bad = []
    if th.is_alive():
        bad.append("C3: the scenario hung")
    raised = box.get("raised")
    if not (raised is exc or any(x is exc for x in unraisable + hooked)
            or (isinstance(raised, GateSpecError) and code_of(raised) == "UNRESOLVED" and raised.__cause__ is exc)):
        bad.append(f"C2: the injected exception was not seen (raised {type(raised).__name__})")
    if raised is not None and raised is not exc and not (isinstance(raised, GateSpecError) and raised.__cause__ is exc):
        bad.append(f"C6: {raised!r}")
    cov = box.get("cov")
    active, rec = False, None
    if cov is not None:
        try:
            rec = cov.record()
        except GateSpecError as e:
            active = code_of(e) == "TRACE_ACTIVE" and "the tracer is active" in str(e)
        if rec is not None:
            ok, why = _within_I6_gfi(rec, base)
            if not ok:
                bad.append("C1/C8: " + why)
            if sentinel and rec["sections"].get(sentinel):
                bad.append("C1: the sentinel section was opened")
    if not probe_cycle():
        bad.append("C3: the probe cycle did not complete")
    for m in P._v5_state()["mints"]:
        if m["holders"] != (1 if active else 0) or not m["installed"]:
            bad.append(f"C7: mint {m}")
    if active and not _bounded_exit(cov):
        bad.append("C3: the harness's exit of the still-active tracer did not return within 5 s")
    elif active:
        try:
            ok, why = _within_I6_gfi(cov.record(), base)
            if not ok:
                bad.append("C8 (step 5): " + why)
        except GateSpecError as e:
            bad.append(f"C8 (step 5): record() refused {code_of(e)}")
    box.clear()
    del cov, raised, rec
    gc.collect()
    if not probe_cycle():
        bad.append("C5: the second probe cycle did not complete")
    s1 = dict(P._v5_state()); s1.pop("pid", None)
    diff = [f for f, v in s0.items() if f not in ("cut", "tool") and s1.get(f) != v]
    if diff:
        bad.append(f"C5: _v5_state() differs from S0 in {diff}")
    for kk, (fn, code) in ORIG.items():
        if fn.__code__ is not code:
            bad.append(f"C5: {kk} not restored")
            fn.__code__ = code
    return True, bad

X140_REPORT = {}
CALLBACK_ONLY = ("_on_entry", "_on_exit", "_on_unwind", "_outcome", "_publish")

@case("X140", "back-edge", "for every JUMP_BACKWARD[_NO_INTERRUPT] in every _v5_faultpoints() code, one trial per scenario variant: KeyboardInterrupt the first time that offset executes, in a scenario with 3 openings (one run_async driven through a thrown-then-handled cancellation; (a) it then completes, (b) it stays suspended through exit, GAP-49); callback-only functions under the direct-call driver -> every trial clean by G_FI's rules; UNREACHED counted clean")
def x140():
    import dis
    fp = P._v5_faultpoints()
    trials, unreached, unclean = 0, [], []
    for tag, scen in (("a", _x140_scenario), ("b", _x140_scenario_b)):
        base_box = {}
        scen(base_box)
        base = base_box["rec"]
        del base_box
        for key, code in fp.items():
            if key in CALLBACK_ONLY or _sweep_must_stop(unclean):
                continue
            for ins in dis.get_instructions(code):
                if _sweep_must_stop(unclean):
                    break
                if not ins.opname.startswith("JUMP_BACKWARD"):
                    continue
                trials += 1
                fired, bad = _gfi_point(scen, key, ins.offset, 1, KeyboardInterrupt(f"{key}@{ins.offset}"), base)
                if not fired:
                    unreached.append(f"({tag}) {key}@{ins.offset}")
                elif bad:
                    unclean.append((f"({tag}) {key}@{ins.offset}", bad[:3]))
    cb_trials, cb_unreached, cb_unclean = (0, [], []) if _sweep_must_stop(unclean) else cover_driver_backedges()
    X140_REPORT.update(scenario_trials=trials, scenario_unreached=len(unreached), unreached=unreached,
                       callback_trials=cb_trials, callback_unreached=cb_unreached, unclean=len(unclean) + len(cb_unclean))
    expect(not unclean and not cb_unclean, f"not clean: {(unclean + cb_unclean)[:4]}")


# -- cover_driver (G_COVER's frozen direct-call driver, the part X140 needs) ---------------------------------
def _tramp(on_entry, on_exit, code, exit_off):
    """The driver's trampoline (revision 3, N7): called as FunctionType(this code, vars(<target module>)),
    it is the target's frame for _on_entry and _on_exit, which read sys._getframe(1)."""
    on_entry(code, 0)
    on_exit(code, exit_off, None)

def _driver_fns():
    fp = P._v5_faultpoints()
    g = vars(P)
    return {k: types.FunctionType(fp[k], g, k) for k in CALLBACK_ONLY}

def _driver_scenario(box):
    """Direct calls of the callback-only functions inside real traces opened through the public API:
    outcome c (one holder), two holders (a second tracer on the same target), and d (dispatched through
    a stdlib loop's Handle._run, a cut frame)."""
    import asyncio
    fns = _driver_fns()
    tramp = types.FunctionType(_tramp.__code__, vars(fx_gfi), "tramp")
    cov = P.coverage_trace(EXP("DRV"))
    cov2 = P.coverage_trace(EXP("DRV2"))
    box["cov"] = cov
    with cov, cov2:
        code = fx_gfi.f.__code__
        def step():
            tramp(fns["_on_entry"], fns["_on_exit"], code, 2)
        cov.run("A", step)
        cov.run("A", lambda: cov2.run("B", step))
        L = asyncio.new_event_loop()
        try:
            async def via_loop():
                L.call_soon(step)
                await asyncio.sleep(0)
            cov.run("A", L.run_until_complete, via_loop())
        finally:
            L.close()
    box["rec"] = cov.record()
    return cov

def cover_driver_backedges():
    import dis
    base_box = {}
    _driver_scenario(base_box)
    base = base_box["rec"]
    del base_box
    fp = P._v5_faultpoints()
    trials, unreached, unclean = 0, [], []
    for key in CALLBACK_ONLY:
        for ins in dis.get_instructions(fp[key]):
            if _sweep_must_stop(unclean):
                break
            if not ins.opname.startswith("JUMP_BACKWARD"):
                continue
            trials += 1
            fired, bad = _gfi_point(_driver_scenario, key, ins.offset, 1, KeyboardInterrupt(f"{key}@{ins.offset}"), base)
            if not fired:
                unreached.append(f"{key}@{ins.offset}")
            elif bad:
                unclean.append((f"driver {key}@{ins.offset}", bad[:3]))
    return trials, unreached, unclean


# -- X140f (H9): SIGALRM floods during __exit__ with 100k suspended openings ---------------------------------
class Suspend:
    def __await__(self):
        yield "suspend"
        return None

X140F_REPORT = {}
X71C_REPORT = {}

def union_of(rec, section):
    out = {}
    for o in rec["sections"].get(section, []):
        for k, v in o["calls"].items():
            out[k] = out.get(k, 0) + v
    return out

@case("X71c", "v5e ported", "the v5f port row (main thread before the self-trace): witness W on f active; G's tracer exits inside G's on-stack opening, with 100,000 suspended run_async('G') openings; a 0.2 ms SIGALRM handler calls f once, the first time anchors are below their value at exit start and above 2; a trial lands iff W's union has f; void trials repeated up to 20 -> some trial lands; no landed trial credits G; G NOT_EXERCISED, W {f:1}")
def x71c():
    trials = []
    for trial in range(20):
        exp, wexp = EXP("F"), EXP("W_F")
        fire = {"armed": False, "start": None, "fired": 0}
        def handler(signum, frame):
            if fire["armed"]:
                n = P._v5_state()["anchors"]
                if n < fire["start"] and n > 2:
                    fire["armed"] = False
                    fire["fired"] += 1
                    fx_v5f.f()
        cos = []
        with P.coverage_trace(wexp) as wit:
            cov = P.coverage_trace(exp)
            cov.__enter__()
            async def af():
                await Suspend()
            for _ in range(100_000):
                co = cov.run_async("G", af)
                co.send(None)
                cos.append(co)
            def body():
                old = _signal.signal(_signal.SIGALRM, handler)
                try:
                    fire["start"] = P._v5_state()["anchors"]
                    fire["armed"] = True
                    _signal.setitimer(_signal.ITIMER_REAL, 0.0002, 0.0002)
                    cov.__exit__(None, None, None)
                finally:
                    _signal.setitimer(_signal.ITIMER_REAL, 0, 0)
                    fire["armed"] = False
                    _signal.signal(_signal.SIGALRM, old)
            wit.run("W", cov.run, "G", body)
        for co in cos:
            co.close()
        del cos
        wrec, rec = wit.record(), cov.record()
        wu = union_of(wrec, "W")
        gu = union_of(rec, "G")
        landed = wu.get("fx_v5f:f", 0) == 1
        out = score(exp, rec)
        trials.append({"landed": landed, "fired": fire["fired"], "G_union": gu, "G": list(out[:2])})
        gc.collect()
        if landed:
            break
    X71C_REPORT.update(trials=len(trials), landed=sum(t["landed"] for t in trials), last=trials[-1])
    landed = [t for t in trials if t["landed"]]
    expect(landed, f"no trial landed in {len(trials)}: {trials[:3]}")
    expect(all(t["G_union"] == {} and t["G"] == ["REFUSE", "NOT_EXERCISED"] for t in landed), f"a landed trial credited G: {landed}")

@case("X140f", "back-edge", "SIGALRM floods raising KeyboardInterrupt during cov.__exit__ with 100k suspended openings, 50 trials -> each trial PASS, or TRACE_ACTIVE then __exit__() -> PASS, or TRACE_INCOMPLETE; no hang; leftovers clean after the next enter")
def x140f():
    outcomes = collections.Counter()
    bad = []
    for trial in range(50):
        exp = EXP("F")
        cov = P.coverage_trace(exp)
        cov.__enter__()
        cov.run("G", fx_v5f.f)
        async def af():
            await Suspend()
        cos = []
        for _ in range(100_000):
            co = cov.run_async("G", af)
            co.send(None)
            cos.append(co)
        ARMED[0] = False
        old = _flood(0.001, KeyboardInterrupt)
        try:
            ARMED[0] = True
            cov.__exit__(None, None, None)
            ARMED[0] = False
        except KeyboardInterrupt:
            ARMED[0] = False
        finally:
            ARMED[0] = False
            _unflood(old)
            ARMED[0] = True
        try:
            rec = cov.record()
            out = score(exp, rec)
            kind = "PASS" if out[0] == "PASS" and out[1] == {"G": {"fx_v5f:f": 1}} else f"record {out[:2]}"
        except GateSpecError as e:
            c = code_of(e)
            if c == "TRACE_ACTIVE":
                cov.__exit__(None, None, None)
                out = score(exp, cov.record())
                kind = "TRACE_ACTIVE, then PASS" if out[0] == "PASS" and out[1] == {"G": {"fx_v5f:f": 1}} else f"TRACE_ACTIVE, then {out[:2]}"
            else:
                kind = c
        outcomes[kind] += 1
        if kind not in ("PASS", "TRACE_ACTIVE, then PASS", "TRACE_INCOMPLETE"):
            bad.append((trial, kind))
        for co in cos:
            co.close()
        del cos, cov
        gc.collect()
        e2 = EXP("A_G")
        with P.coverage_trace(e2):
            pass
        quiet, st = state_quiet()
        if not quiet or st["mints"]:
            bad.append((trial, "leftovers", st))
    X140F_REPORT.update(outcomes=dict(outcomes))
    expect(not bad, f"{bad[:3]}")


# =================================================================================================
# The kept v5e cases (revision 11, GAP-37): rev11/v5e_cases_kept.json is spec data
# =================================================================================================
V5E_KEPT = os.path.join(HERE, "..", "protocol_v5f_design", "rev11", "v5e_cases_kept.json")
V5E_ROWS = json.load(open(V5E_KEPT, encoding="utf-8"))["rows"]
V5E_CASES = {}
for _k, _v in list(v5e_port.violations().items()) + list(v5e_port.valids().items()) + list(v5e_port.residuals().items()):
    V5E_CASES[_k] = _v
V5E_CASES["X118"] = ("NOT_EXERCISED", v5e_port.x118_p1_retro)    # the v5e main's own registration (M_RETRO)

def _with_p1(fn):
    """X118 and R11 use P1's harness, which the v5e runner loads once at start (v5e_port._load_p1)."""
    def wrapped(tmp):
        if "run_p1" not in sys.modules:
            v5e_port._load_p1()
        return fn(tmp)
    return wrapped
for _k in ("X118", "R11"):
    V5E_CASES[_k] = (V5E_CASES[_k][0], _with_p1(V5E_CASES[_k][1]))
# Rows the runner covers with a case of its own, in the placement the row names (not from v5e_port):
V5E_ELSEWHERE = {"H1": "H1", "H2": "H2", "H3": "H3", "H4": "H4",
                 "V34": "V34 (the self-trace; the delta row's frozen names)", "X71c": "X71c (the port row)"}
_CODE_IN = re.compile(r"\b[A-Z][A-Z_]{3,}\b")     # the first reason code the v5f_outcome names

def _v5e_run(fn):
    """One v5e case, as the v5e runner's run_case judges it: returned / refused / assert / crash."""
    tmp = v5e_port._Tmp(Path(WORK))
    try:
        val = fn(tmp)
        return "returned", val
    except (GateSpecError, v5e_port.GateSpecError, v5e_port._Reported) as e:
        return "refused", str(e)
    except v5e_port.CaseFailure as e:
        return "assert", str(e)
    finally:
        tmp.close()

def _v5e_make(row):
    rid, status, v5f = row["id"], row["status"], row["v5f_outcome"]
    kind, fn = V5E_CASES[rid]
    violation = row["source"].startswith(("Violation", "v5e runner registration")) or (
        row["source"].startswith("v5e runner ADDITIONS") and rid.startswith("X"))
    def body():
        if violation:
            code = _CODE_IN.search(v5f).group(0)
            expect(code == kind, f"spec data: v5f_outcome {v5f!r} names {code!r}, the v5e registration {kind!r}")
            out, detail = _v5e_run(fn)
            expect(out == "refused" and str(detail).startswith(f"[V5:{code}]"),
                   f"expected [V5:{code}], got {out}: {str(detail)[:600]}")
            if rid == "X91":                                   # changed row: the text per case (M8)
                expect("the tracer was never entered" in detail, f"X91 text: {detail[:300]}")
        else:
            out, detail = _v5e_run(fn)
            expect(out == "returned", f"expected the row's property ({v5f}), got {out}: {str(detail)[:600]}")
    return body

for _row in V5E_ROWS:
    _rid = _row["id"]
    if _row["status"] == "retired" or _rid in V5E_ELSEWHERE:
        continue
    if _rid not in V5E_CASES:
        continue                                       # reported as uncovered (see V5E_COVERAGE)
    case("v5e:" + _rid, "v5e " + _row["status"],
         f"{_rid} ({_row['status']}; {_row['source']}): v5f outcome {_row['v5f_outcome']}"
         + ("" if _row["v5f_sub_assertions"].startswith("every sub-assertion") else f"; sub-assertions: {_row['v5f_sub_assertions']}"))(_v5e_make(_row))

V5E_COVERAGE = {"rows": len(V5E_ROWS), "retired_not_run": sorted(r["id"] for r in V5E_ROWS if r["status"] == "retired"),
                "covered_elsewhere": V5E_ELSEWHERE,
                "ported_cases": sorted("v5e:" + r["id"] for r in V5E_ROWS
                                       if r["status"] != "retired" and r["id"] not in V5E_ELSEWHERE and r["id"] in V5E_CASES),
                "no_registration": sorted(r["id"] for r in V5E_ROWS
                                          if r["status"] != "retired" and r["id"] not in V5E_ELSEWHERE and r["id"] not in V5E_CASES)}


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
for _cid in ('X137b', 'X137e', 'X137g', 'X137i', 'X137h', 'X154b', 'X154c', 'X154d', 'X154e', 'X155', 'X157c', 'X158', 'X158c', 'X158b', 'X158e', 'X137f', 'X158d'):
    TABLE[_cid] = "new violation cases"
for _cid in ("X72b", "X65b", "X30b", "X140", "X140f"):
    TABLE[_cid] = "new violation cases"
for _cid in ("X35e", "X57d", "X117g"):                 # revision 11
    TABLE[_cid] = "new violation cases"
for _cid in ("H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H10"):
    TABLE[_cid] = "hazard sweeps"
for _cid in ("R05b", "R12", "R13", "R14", "R16", "R18a", "R18b", "R20", "R21", "R22", "X157", "X157b", "R23", "R24", "X137j"):
    TABLE[_cid] = "new documented residuals"
for _cid in ('V10b', 'V11c', 'V15b', 'V19b', 'V35', 'V36', 'V36b', 'V37', 'V38', 'V39', 'V40', 'V40b', 'V41', 'V42', 'V43', 'V44', 'V45', 'V47', 'V50', 'V51', 'V53', 'V57', 'V58', 'V59', 'V60', 'V61', 'V62', 'V63', 'V64', 'V65', 'V68', 'V69', 'V70', 'V71', 'V72b'):
    TABLE[_cid] = "new valid cases"
for _cid in ("V54", "V55", "V67", "V52", "V28b", "V69b", "V69b-v", "V72", "V73"):
    TABLE[_cid] = "new valid cases"
for _cid in ("V01", "X40", "X55", "X59", "V07", "X33", "X73", "V18", "X76", "X60", "V14", "X109",
             "X90", "X32"):
    TABLE[_cid] = "v5e cases kept (every other v5e case keeps its id and outcome)"
TABLE["X90/X91"] = "v5e cases whose outcome changes"
for _cid in ("V48", "V49"):
    TABLE[_cid] = "new valid cases"                  # V49 replaces X75 and V48 replaces X80 (the delta table)
TABLE["X95"] = "v5e cases whose outcome changes"       # X91's row: same code, the text per case (M8)
TABLE["X71c"] = "v5e cases kept (revision 11 spec data)"
TABLE["M10-S0"] = "M10 property (not a table row): _v5_state() before any tracer"
for _cid in V5E_COVERAGE["ported_cases"]:
    TABLE[_cid] = "v5e cases kept (revision 11 spec data)"

# Placements, from the harness rules' lists (only the cases this runner covers are listed).
MAIN = {"X71c", "X35e", "X57d", "R24", "X140f", "X140", "H6", "H10", "H1", "H2", "H3", "H4", "H5", "H7", "H8", "V61", "V62", "V64", "V65", "V68", "V70", "X92b", "X131", "X132", "X143", "X143b", "X144", "X145", "X146", "X146b", "X146c", "X146d", "X146e",
        "X147", "X148", "X152", "X153", "X137d", "X35", "X35b", "X35c", "X65e", "X65f", "X65g", "X141", "X141b", "X141c", "X138", "X138b", "X139",
        "X137c", "X143c", "X59e", "X59e-v", "V67", "V73", "R18a", "R18b", "R20"}
CHILD = {"X137-free"}                                  # the whole case in a fresh subprocess
SPAWNS = {"X137j", "V47", "V69", "V71", "V72b", "X137b", "X137e", "X137g", "X137i", "X137h", "X154b", "X154c", "X154d", "X154e", "X155", "X157c",
          "X158", "X158c", "X158b", "X158e", "X137f", "X158d", "X36", "X142", "X142b", "X156", "X156b", "X37b", "X156c", "X156d", "R21", "X157", "X157b", "M10-S0", "V69b", "V69b-v", "X156f", "X156g", "X156g-ctl", "X156h", "X156i", "V72"}  # the case body spawns it
SCORING = {"X117g", "V53", "X96c", "X103b", "X105d", "X109b", "X117d", "X95", "X93d", "X93e", "X96d", "X103c", "X112b", "X117b", "X117c", "X117e", "X117f", "X95b",
           "X122", "X109", "X37"}                      # read prebuilt traces; run on every interpreter
SELF_TARGETS = [f"{IMPL_MOD}:{q}" for q in ("Experiment._check_coverage", "_resolve_target", "_open",
                                          "_exit", "_run")]
GATE_OF = {"new violation cases": "VIOL", "new valid cases": "VALID",
           "v5e cases kept (every other v5e case keeps its id and outcome)": "V5E",
           "M10 property (not a table row): _v5_state() before any tracer": "M10",
           "v5e cases whose outcome changes": "DELTA", "hazard sweeps": "HAZ"}

# Cases whose row the reference, written from the text, does not meet: each is a spec contradiction
# recorded in SPEC_GAPS.md. The case still asserts its row as written (it is not adapted); its failure
# is reported apart, so that a new failure is never hidden among them.
KNOWN_GAPS = {
    "X137h": "GAP-42 (P and S open no section, so SECTION_ABSENT precedes NOT_EXERCISED)",
    "X158d": "GAP-44 (under greenlets the reference gives P CODE_SWAPPED, not PASS)",
    "v5e:X72": "GAP-46 (the kept v5e sub-assertion requires v5e's NOT_EXERCISED sentence; v5f's fixed sentence differs)",
    "v5e:X73": "GAP-46 (the kept v5e sub-assertion requires v5e's NOT_EXERCISED sentence; v5f's fixed sentence differs)",
}

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
# "The exam-hole kill cases": each verifier key and the v5f case(s) that implement it (the table's third
# column). A key is covered iff every case it names ran and passed in this run.
KILL_MAP = {
    "exam-mut-section-decl-clauses": ["X07b / X07c"],
    "examhole-clone-alive-single-tracer": ["X57c"],
    "examhole-clone-called-first-tracer": ["X55d"],
    "examhole-code-swapped-single-tracer": ["X59c"],
    "examhole-stop-read-before-mint": ["X34"],           # and cut_current, asserted by every case's leftover check
    "examhole-union-over-all-sections": ["X120", "V41"],
    "examhole-declared-section-field-never-scored": ["V42", "V43", "X121", "X78g"],
    "examhole-dispatch-cut-by-name": ["V44"],
    "examhole-walk-bound-2-hops": ["V11c", "X30b"],
    "examhole-class-step-exact-type": ["V45", "X14b"],
    "examhole-module-step-exact-type": ["V10b", "X16b"],
    "examhole-inherited-direct-base-only": ["X14c"],
    "examhole-cache-body-module-check": ["X25c", "X25d"],
    "exam-hole-coverage-on-failing-bar": ["X122", "X122b"],
    "exam-hole-score-step-order": ["X96c", "X78e"],
    "exam-hole-diagnostic-texts": ["X72b"],
    "exam-mut-stop-cleared-by-inner-exit": ["X65b"],
    "exam-mut-nested-by-section-name": ["V15b"],
    "exam-mut-restore-over-swapped-code": ["X59d"],
    "exam-mut-close-removes-foreign-profiler": ["V58"],
    "exam-mut-exit-removes-foreign-profiler": ["V57"],
    "exam-mut-double-exit-state-leak": ["V52"],
    "exam-mut-hop-close-drops-closer-hook": ["V28b"],
    "exam-mut-foreign-profiler-first-open-only": ["V59"],
    "exam-mut-target-set-before-stale": ["X109b"],
    "exam-mut-profiler-lost-only-if-none": ["V60", "X137"],
    "exam-mut-bad-trace-end-type": ["X103c"],
    "exam-mut-problems-before-bad-count": ["X112b"],
    "exam-mut-uncredited-last-thread-wins": ["X123"],
}

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
TABLE_ROWS = {"new violation cases": 140, "new valid cases": 46, "new documented residuals": 15,   # revision 11 counts
              "exam-hole kill cases": 30, "v5e cases whose outcome changes": 20, "v5e cases kept (revision 11 spec data)": sum(1 for r in V5E_ROWS if r["status"] != "retired")}

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
    v5e_code = [getattr(fn, "__qualname__", "?") for fn, code in v5e_port.FIXTURE_CODES if fn.__code__ is not code]
    if v5e_code:
        bad.append(("v5e fixture __code__", v5e_code[:6]))
    v5e_bind = [f"{m.__name__}.{k}" for m, k, v in v5e_port.FIXTURE_BINDINGS if vars(m).get(k) is not v]
    if v5e_bind:
        bad.append(("v5e fixture bindings", v5e_bind[:6]))
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

class NotRun(Exception):
    """A case the runner cannot run in this environment (for example, a pinned library is missing)."""

class KnownGapFailure(AssertionError):
    """A case whose every other check passed, failing only on a reading recorded as a spec gap.
    Its detail starts with the gap id, and the report puts it with the known spec gaps."""
    def __init__(self, gap, msg):
        super().__init__(f"{gap}: {msg}")

def _call(fn):
    try:
        fn()
        return True, ""
    except NotRun as e:
        return None, f"NOT RUN: {e}"
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
    if ARGS.list:
        print("\n".join(BY_ID))
        return 0
    t0 = time.monotonic()
    only = set(ARGS.only.split(",")) if ARGS.only else None
    ids = [cid for cid, _, _, _ in CASES if not only or cid in only]
    res = {}
    def record(cid, ok, detail, left, secs, note=None):
        if isinstance(detail, str) and detail.startswith("NOT RUN:"):
            skipped[cid] = detail
            return
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
    for cid, r in res.items():
        if not r["ok"] and cid in KNOWN_GAPS:
            r["known_spec_gap"] = KNOWN_GAPS[cid]
        elif not r["ok"] and str(r.get("detail", "")).startswith("KnownGapFailure: GAP-"):
            r["known_spec_gap"] = r["detail"].split(":")[1].strip()
    n_ok = sum(r["ok"] for r in res.values())
    n_gap = sum(1 for r in res.values() if not r["ok"] and "known_spec_gap" in r)
    all_ok = n_ok == len(res) and (selfinfo is None or selfinfo["ok"])
    only_gaps = n_ok + n_gap == len(res) and (selfinfo is None or selfinfo["ok"])
    if TRACING:
        verdict = "PASS" if all_ok else ("FAIL_ONLY_KNOWN_SPEC_GAPS" if only_gaps else "FAIL")
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
        "kill_cases": {k: {"cases": v, "covered": all(res.get(c, {}).get("ok") for c in v)} for k, v in KILL_MAP.items()},
        "tables_not_yet_covered": ["exam-hole kill cases",
                                   "v5e cases whose outcome changes", "hazard sweeps (H1-H10)",
                                   "mutation audit witnesses not already in the case tables",
                                   "the rest of the new violation and valid cases",
                                   "the v5e cases kept (the v5e case tables)"],
        "instruction_sweeps_counted_trials": SWEEP_COUNTS,
        "v5e_kept_coverage": V5E_COVERAGE, "v5e_kept_sha256": _sha(V5E_KEPT), "v5e_port_sha256": _sha(v5e_port.__file__), "h2_report": H2_REPORT, "h4_performance_report": H4_REPORT, "h8_report": H8_REPORT, "h6_report": H6_REPORT,
        "h10_report": H10_REPORT, "x71c_report": X71C_REPORT, "x140_report": X140_REPORT, "x140f_report": X140F_REPORT,
        "n_cases_run": len(res), "n_passed": n_ok, "n_failed_known_spec_gaps": n_gap,
        "known_spec_gaps": KNOWN_GAPS, "verdict": verdict,
        "seconds": round(time.monotonic() - t0, 2),
    }
    if ARGS.out:
        with open(ARGS.out, "w") as fh:
            json.dump(receipt, fh, indent=1, default=str)
            fh.write("\n")
    for cid, r in res.items():
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {cid:10s} [{r['placement']:10s}] {r['table'][:24]:24s} "
              f"{r['row'][:90]}" + ("" if r["ok"] else f"\n        -> {r['detail'][:300]} leftover={r['leftover']}"
                                     + (f"\n        (known spec gap: {r['known_spec_gap']})" if "known_spec_gap" in r else "")))
    if selfinfo:
        print(f"self-trace: {selfinfo['outcome']} problems={selfinfo['problems']}")
    print(f"CPython {receipt['python']} [{mode}]: {n_ok}/{len(res)} cases pass; {n_gap} fail on known spec gaps; "
          f"{len(skipped)} not run")
    print(f"VERDICT: {verdict}", flush=True)
    return 0 if all_ok else (2 if only_gaps else 1)


def child_case(cid):
    b = snap()
    ok, detail = _call(BY_ID[cid][2])
    left = leftover_diff(b, snap())
    print(json.dumps({"ok": ok and not left, "detail": detail, "leftover": [list(map(str, x)) for x in left]}))
    return 0


if __name__ == "__main__":
    if ARGS.sub:
        name, _, arg = ARGS.sub.partition(":")
        print(json.dumps(SUB[name](arg) if arg else SUB[name]()))
        sys.exit(0)
    if ARGS.child_case:
        sys.exit(child_case(ARGS.child_case))
    if ARGS.make_traces:
        sys.exit(make_traces())
    rc = main()
    sys.stdout.flush()
    os._exit(rc)
