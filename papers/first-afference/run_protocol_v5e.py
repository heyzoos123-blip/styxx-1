"""Protocol v5e exam (mint-and-anchor), per PREREG_protocol_v5e_mint_anchor_2026_09_24.md.

FROZEN WITH THE PREREG, BEFORE THE v5e IMPLEMENTATION EXISTS. The prereg carries this file's sha256
and the sha256 of every file the exam depends on, as lines ``FROZEN_<NAME>_SHA256: <hex>`` for NAME
in RUNNER, MUTATION_GATE, RUN_PROTOCOL_V5, RUN_P1, P1_PREREG, P1_RESULT, POWER_QUARANTINED,
CORPUS_PROVENANCE_RESCORE, V5D_RESULT, V5D_PREREG (see FROZEN_FILES; the last two are X95's
inputs). ``exam_frozen`` is 1.0 only if every one matches, the lines are read from the prereg AS
FIRST COMMITTED and the working-tree prereg is byte-identical to that commit, and that commit is an
ancestor of the first commit whose styxx/protocol.py carries the /2 tracer id, if one exists yet
(G_EXAM_FROZEN: frozen before any implementation).

Written from DESIGN_protocol_v5e_mint_anchor_2026_09_24.md ("Exam cases required") plus the exam
brief's amendments A1-A10, against exactly the v5e API (coverage_trace / cov.run / cov.run_async /
cov.record, _resolve_target, Experiment._check_coverage / check_metrics, and the module globals
_hook, _LOCK, _MINTED, _BY_FN, _ANCHORS, _THREADS, _ACTIVE, _STOP, _TRACER_ID).

WHAT THE EXAM ASSUMES OF THE IMPLEMENTATION, beyond the spec's prose (the prereg and the N-version
brief must state these): (1) Experiment._check_coverage returns {declared target: union count} and
Verdict.coverage carries it per gate; valid and residual cases compare it, the only place "union
over openings" is visible. (2) Like _hook, the registries are module globals the machinery reaches
by global name at call time; X71c rebinds _ANCHORS for the length of one __exit__. (3) __exit__
performs step 1 (_by_code emptied) before its first access to _ANCHORS, as the spec orders it.

Cases, under their spec ids:
* violation cases X01-X118: pass only if the refusal message STARTS WITH the case's own
  ``[V5:CODE]`` (X117 uses the exam sentinel REPORTED; X118 is the P1 retro, run in G2's section).
  Each is isolated: every other rule it could meet is trivially satisfied (other gates are
  satisfied, the target is also called normally, ...), so deleting its rule makes it score or fail
  differently instead of refusing for a later reason. Sub-assertions the spec names are checked
  too (X32 raised AND at score, X33 code untouched, X60-X62 every gate refuses, X70 ambiguous = 1
  on both openings, X71 end open + OPEN_AT_EXIT, X72/X73 the new wording, not "never executed",
  the fixed sentence, and -- re-scored with one diagnostic changed at a time -- the dispatched and
  unattributed counts and the non-returned ends in the message, X74 LAZY_RESULT, X75
  PROFILER_LOST, X76 an unrelated gate also refuses, X80/X81 the foreign profiler left installed,
  X118 the exact section record and the committed metric). In X60-X69 every off-stack call is
  OBSERVED (a foreign thread's work runs inside an opening of a second, unrelated tracer, so the
  hook is live there) and the case pins where it went in ``uncredited``: a call on a thread with
  no hook would satisfy NOT_EXERCISED by construction. X92 injects its fault by the IDENTITY of the
  builtin the exit's clone scan calls (a profiler raising at the c_call of sys.getrefcount or
  gc.get_referrers, on a thread the case owns), never by rebinding a name.
  ADDITIONS (not in the spec's list; each isolates a condition the spec's text names that no
  listed case isolates, so that deleting or weakening it is detected):
  resolution and identity: X02b (exercises a JSON object), X12b (a class lacks the name in its own
  and every base __dict__), X25b (cache body bound in the namespace that held the wrapper), X30b
  (this module's code 17 hops down a foreign wraps chain: the walk is bounded), X30c (a self-cycle:
  the walk is cycle-detected), X31b/X59b (CODE_SWAPPED at entry/exit to an EQUAL code object:
  identity, not equality), X55b/X55c (CLONE_CALLED under an equal copy of T's globals / under
  globals carrying only the module's __name__: f_globals by identity);
  lifecycle and recording: X32b (REENTRY on an exited tracer, recorded), X71c (a hit DURING exit on
  the exiting tracer's still-registered opening: _by_code is emptied first; the audit row X71
  cannot see), X74b/X74c (LAZY_RESULT for a generator / async generator), X78b (two problems: the
  FIRST one's code), X78c (a problem and an unexercised target: problems before coverage), X78d /
  X79c / X80b (open-check order: UNDECLARED before NESTED, TRACE_INACTIVE before UNDECLARED, NESTED
  before FOREIGN_PROFILER), X79b (run on a never-entered tracer);
  score step 3, one edit per exact-type/shape clause, so a clause coded as its own raise is
  detected when deleted (int keys, missing/extra keys, non-lists) or weakened to isinstance (dict,
  list and str subclasses): X93b (trace a dict subclass), X96b (top-level key missing), X97b/X97c/
  X98b (targets a dict subclass / str-subclass keys / values), X99b/X99c (sections a dict subclass /
  str-subclass keys), X100b/X100c (a section a list subclass / a tuple of valid openings), X101b/
  X102b (an opening a dict subclass / with an extra key), X104b-X104e (notes a tuple / a str-
  subclass note / a note without a code / notes a list subclass), X105b/X105c (a problem without a
  code / of a str subclass), X106b (problems a list subclass), X107b/X107c (uncredited a dict
  subclass / with an extra key), X108b-X108m (each of calls, ambiguous, dispatched, unattributed:
  a dict subclass, an int key, a str-subclass key), X110b (an extra undeclared target), X115b
  (unattributed with an undeclared key).
* valid cases V01-V34: pass only if score() returns PASS, the union of calls over each listed
  section's openings is EXACTLY the listed counts, score() credits each declaring gate with that
  union (Verdict.coverage), every section's note codes are EXACTLY the listed ones (none when
  unlisted; V27 may carry PROFILER_LOST) and every opening's end is as listed ("returned" when
  unlisted). ADDITIONS: V11b (provenance through a 2-hop wraps chain), V25b/V25c (run_async closes
  in its finally on a raise and on cancellation). V34 has two parts: a nested tracer that declares
  the machinery itself (every target >= 1 and _CoverageTracer.run exactly the number of inner
  runs), and, after the self-trace exits, the outer self-trace (every declared target of every
  G-gate >= 1, one returned opening per case run, no problems, registries empty, _ACTIVE 0, no
  profiler left, every declared function's __code__ restored).
* residual cases R01-R11: pass only with the documented (pinned) outcome and union.
* hazard sweeps H1-H3, each paired with a detection mutant built in a SUBPROCESS; H4 is reported.
  H2's mutant wraps the module global _hook in `except Exception`. H1's mutant DEVIATES from A6's
  wording, which is an equivalent mutant (a fresh lock only the hook takes never deadlocks: CPython
  does not re-enter a profile function): a mutant-owned non-reentrant lock is held while any of
  _open/_close/__enter__/__exit__ is on a thread's stack (class-level wrappers) and the hook
  wrapper takes it on hits; a CONTROL child installs the same wrappers with the hook untouched.
  h1_mutant_detected is 1 only if the control never hangs and a mutant hang's innermost frame
  (the head of faulthandler's dump) is the mutant hook. See _install_mutant.

How cases run (A1, A8). Each case runs in its own thread whose target is
``cov.run(<gate section>, case)`` inside the exam's outer self-trace, with a 30 s join watchdog
(an expiry fails the case; after 3 expiries the remaining cases are marked aborted, and the
self-trace's exit is bounded, so the exam never hangs). Immediately before each case the exam
snapshots the registries (_MINTED, _BY_FN, _ANCHORS by key and identity, _THREADS by value),
_ACTIVE, sys.getprofile() on the case thread, threading.getprofile(), every fixture function's
__code__ and every fixture module binding; after the case each must be as it was (fixture code:
its ORIGINAL, per A1; the detail names what changed during this case), or the case fails. Cases
that deliberately disturb a thread's profiler (V26, V27, V30, V31, V33, X75, X80, X80b, X81, X92)
do it on a fresh sub-thread they own: the case thread's hook is the outer self-trace's. Hazards run
before the self-trace: H2 and H3 on this process's main thread (each trial's loop runs until the
signal handler has run, bounded, so a late signal cannot land outside the trial; a faulthandler
guard kills rather than hangs the exam); H1, its control and both mutants in subprocesses with hard
timeouts, on the subprocess's main thread (H1's 10 s watchdog is faulthandler's).

Mutation audit notes for the prereg: the "last-close removal" row is an EQUIVALENT mutant (the
hook removes itself at the very next event, which in _close is its own sys.getprofile() call);
removing it together with self-removal is detected by V21, V23 and V31. "Emptying _by_code at
exit" is detected by X71c, not X71.

Corpus differential (A2): run_protocol_v5.differential()'s outcome comparison over a PINNED
population -- result files tracked at HEAD (read as committed) whose prereg exists, minus the v5
exams' own preregs (v5e's and aux_v5e's included), restricted to exactly the rows of the frozen
census in corpus_provenance_rescore.json; the nested-metrics rule applies to exactly its
"reproduced" results. If a census row is missing or the rule did not apply to exactly those six,
n_results_v5_scored is 0. The committed-verdict comparison is reported, not gated.

Modes (A4). ``--smoke``: plumbing only, a small subset, INVALID verdict by type.
``--smoke --full-battery``: every case, still INVALID by type. ``--smoke --full-battery
--mutation-mode``: every case except the hazard sweeps H1-H3 and the stress run V32 (the frozen
fast mode mutation_gate.py uses); it also exits 3 when a residual case fails, since
mutation_gate.py reads violation/valid/retro/crash fields but counts any non-zero exit as a
detection. A scored run is the bare command; it reads run_protocol_v5e_mutation_gate.json (A5).
Env: STYXX_V5_IMPORT_ROOT (put FIRST on sys.path, so styxx is imported from there) and
STYXX_V5_RESULT_OUT (where the result goes instead of papers/first-afference/
protocol_v5e_result*.json). Fixtures and case preregs live in temp dirs created at run time; the
process writes nothing else (not even .pyc files).

Gate sections (A8): each G-gate's section is found in the prereg by the metric it reads:
violations run in the section of the gate reading frac_violation_cases_refused_with_expected_code,
valid cases in frac_valid_cases_exact's, X118 in p1_retro_exact's, residuals in
frac_residuals_as_documented's. Version keys (A7): X81 on <= 3.11; V33 and X82 on >= 3.12.
"""
from __future__ import annotations

import asyncio
import functools
import gc
import hashlib
import importlib
import importlib.machinery
import importlib.util
import json
import os
import queue
import random
import re
import sched
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.dont_write_bytecode = True          # this process writes nothing into the repo, not even .pyc
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IMPORT_ROOT = os.environ.get("STYXX_V5_IMPORT_ROOT") or None
RESULT_OUT = os.environ.get("STYXX_V5_RESULT_OUT") or None
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
if IMPORT_ROOT:
    sys.path.insert(0, str(Path(IMPORT_ROOT).resolve()))      # FIRST: styxx comes from here
import styxx.protocol as P                                       # noqa: E402
from styxx.protocol import (Experiment, GateSpecError, _select_gates_block,  # noqa: E402
                            coverage_trace)

PREREG = "PREREG_protocol_v5e_mint_anchor_2026_09_24.md"
P1_PREREG = "PREREG_p1_power_refusal_2026_08_08.md"
V5_OWN_PREREGS = {"PREREG_protocol_v5_coverage_2026_09_24.md",
                  "PREREG_protocol_v5b_coverage_2026_09_24.md",
                  "PREREG_protocol_v5c_repair_2026_09_24.md",
                  "PREREG_protocol_v5d_repair_2026_09_24.md", PREREG,
                  "PREREG_protocol_v5e_aux_2026_09_24.md"}     # aux_v5e.py's receipt, not corpus
TRACER_ID = "styxx.protocol.coverage_trace/2"
WATCHDOG_S = 30.0
ABORT_AFTER_WATCHDOGS = 3      # after this many expiries the rest are marked aborted, not run
FIXED_SENTENCE = ("work on other threads, pools, executors or asyncio tasks is credited only to a "
                  "section that work opens itself")
NE_WORDING = "not executed on the stack of any opening of section"   # NOT_EXERCISED's wording (J2)
# the builtins the exit's refcount-gated clone scan calls, captured by IDENTITY at import: X92 and
# H4 recognise them in a profiler's c_call events, whatever name the implementation reaches them by
_GETREFCOUNT, _GET_REFERRERS = sys.getrefcount, gc.get_referrers

HAZARD_CHILD = "--hazard-child" in sys.argv
SMOKE = "--smoke" in sys.argv
FULL = (not SMOKE) or "--full-battery" in sys.argv
MUTATION = "--mutation-mode" in sys.argv
if MUTATION and not (SMOKE and "--full-battery" in sys.argv) and not HAZARD_CHILD:
    raise SystemExit("--mutation-mode is only valid together with --smoke --full-battery")

# A3: every file this exam depends on, frozen by sha256 in the prereg as FROZEN_<NAME>_SHA256.
FROZEN_FILES = {
    "RUNNER": Path(__file__).resolve(),
    "MUTATION_GATE": HERE / "mutation_gate.py",
    "RUN_PROTOCOL_V5": HERE / "run_protocol_v5.py",
    "RUN_P1": HERE / "run_p1.py",
    "P1_PREREG": HERE / P1_PREREG,
    "P1_RESULT": HERE / "p1_result.json",
    "POWER_QUARANTINED": ROOT / "styxx" / "power_QUARANTINED.py.txt",
    "CORPUS_PROVENANCE_RESCORE": HERE / "corpus_provenance_rescore.json",
    # X95's inputs: the committed v5d receipt whose /1 trace must refuse WRONG_TRACER, and its prereg
    "V5D_RESULT": HERE / "protocol_v5d_result.json",
    "V5D_PREREG": HERE / "PREREG_protocol_v5d_repair_2026_09_24.md",
}
# A9: the metric names the prereg's gates use.
M_VIOL = "frac_violation_cases_refused_with_expected_code"
M_VALID = "frac_valid_cases_exact"
M_RETRO = "p1_retro_exact"
M_RESID = "frac_residuals_as_documented"


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# -- fixtures (A10: written to a temp dir at run time, never into the repo) -------------------------

FX, OTHER, DEC, REEXP, LAZY = "_v5e_fx", "_v5e_other", "_v5e_dec", "_v5e_re", "_v5e_lazy"
GA_RAISE, PLAIN, BROKEN, SYNTAX, PKG = ("_v5e_ga_raise", "_v5e_plain", "_v5e_broken",
                                        "_v5e_syntax", "_v5e_pkg")
IMPL_NEW, IMPL_OLD = "_v5e_impl_new", "_v5e_impl_old"
CYR = "f\u0430"                        # 'f' + CYRILLIC SMALL LETTER A: a real, non-ASCII identifier

FIXTURES = {
    FX: '''"""v5e exam fixtures (temp dir, never the repo)."""
import dataclasses
import functools
import types


def f(): return 1
def g(): return 2
def h(): return 3


alias_f = f


def ''' + CYR + '''(): return 4          # X04: resolvable ONLY if the ASCII rule is deleted


class Base:
    def fit(self): return 8


class Sub(Base):
    pass


default_model = Sub()


class Slots:
    __slots__ = ("fn",)

    def __init__(self): self.fn = f


SL = Slots()
P = functools.partial(f)


class K:
    @staticmethod
    def s(): return 5

    @classmethod
    def c(cls): return 7

    @property
    def p(self): return 9


class Timed:                                     # T01b: class-based update_wrapper
    def __init__(self, fn, label):
        functools.update_wrapper(self, fn)
        self.fn, self.label = fn, label

    def __call__(self, *a): return self.fn(*a)


def _tb_impl(x): return x * 2


tb_fast = Timed(_tb_impl, "fast")
tb_safe = Timed(_tb_impl, "safe")


class Model:
    def run(self): return 1


_default = Model()
bound_run = _default.run


def m23(): return 23
def g27(): return 27
def h26(): return 26


@functools.lru_cache(None)
def cached(x): return x + 1


@functools.lru_cache(None)
def cached54(x): return x + 1


@functools.lru_cache(None)
def cached_r07(x): return x + 1


def _impl(x): return x


fast = functools.lru_cache(None)(_impl)


class CacheHolder:
    def _body(x): return x
    fast = functools.lru_cache(None)(_body)       # X25b: body bound in the holder's namespace
cabs = functools.lru_cache(None)(abs)

_ns = {"__name__": __name__}
exec("def made(): return 0", _ns)
made = _ns["made"]


def x31_t(): return 31
def x31_u(): return -31
def a33_good(): return 33


def _make(k):
    def check(x): return x > k
    return check


check_low, check_high = _make(1), _make(2)


def deco_nowraps(fn):
    def w(*a): return fn(*a)
    return w


def _raw(x): return x


entry_a = deco_nowraps(_raw)
entry_b = deco_nowraps(_raw)


def _timed(fn):
    def timed_inner(*a): return fn(*a)
    return timed_inner


def _score_all_impl(): return 10


score_all = _timed(_score_all_impl)


def cheap_path(): return 11


def make_mul(k):
    return lambda x, k=k: x * k


double = make_mul(2)


def make_scorer(metric, strict):
    def score(x, strict=strict):
        v = metric(x)
        if strict and v < 0:
            raise ValueError("negative")
        return v
    return score


score_lenient = make_scorer(abs, False)


@dataclasses.dataclass
class DA:
    a: int = 0


@dataclasses.dataclass
class DB:
    a: int = 0


def f48(): return 48


def _run(x): return x


@functools.wraps(_run)
def run_fast(x): return _run(x)


@functools.wraps(_run)
def run_safe(x): return _run(x)


def run_plain(x): return _run(x)


def retrying(fn):
    @functools.wraps(fn)
    def w(*a): return fn(*a)
    return w


def _core(x): return x + 1


@functools.wraps(_core)
def public(x): return _core(x)


def other_entry(x): return retrying(_core)(x)


def f53(): return 53
def f55(): return 55
def f56(): return 56
def f57(): return 57
def f58(): return 58
def u58(): return -58
def f59(): return 59
def u59(): return -59
def f_r04(): return 4


def gen():
    yield 1
    yield 2


def gen69():
    yield 1
    f()
    yield 2


def gen_r09():
    f()
    yield 1


def r05_real(): return "real"
def r05_stub(): return "stub"
def r06_real(): return "real"


@functools.singledispatch
def dispatch(x): return "obj"


@dispatch.register(int)
def _dispatch_int(x): return "int"


NS = types.SimpleNamespace(handler=lambda: 5)


def score(x): return x


def deprecated(fn):
    @functools.wraps(fn)
    def w(*a): return fn(*a)
    return w


score_v1 = deprecated(score)
score_legacy = deprecated(score)


class Cyc:                                       # R08: cyclic garbage whose finalizer calls a target
    def __init__(self, fn):
        self.me, self.fn = self, fn

    def __del__(self):
        self.fn()
''',
    OTHER: '''import functools


def stub(): return 0


def deco_nowraps(fn):
    def w(*a): return fn(*a)
    return w


def deco_wraps(fn):
    @functools.wraps(fn)
    def w(*a): return fn(*a)
    return w


def make_fake():
    def fake(*a): return "fake"
    return fake
''',
    DEC: '''from _v5e_other import deco_nowraps, deco_wraps, make_fake


@deco_wraps
def wrapped_entry(x): return x * 2


@deco_nowraps
def nowraps_entry(x): return x * 3


@deco_wraps
@deco_wraps
def wrapped2(x): return x * 4                    # V11b: a 2-hop foreign wraps chain


def _deep_inner(x): return x


def _chain(fn, n):
    for _ in range(n):
        fn = deco_wraps(fn)
    return fn


deep17 = _chain(_deep_inner, 17)                 # X30b: this module's code only 17 hops down


cyc = make_fake()                                # X30c: a foreign function whose chain is a cycle
cyc.__wrapped__ = cyc
''',
    REEXP: "from _v5e_fx import f  # noqa: F401\n",
    LAZY: '''def _lazy(): return 7


def __getattr__(name):
    if name == "lazy_fn":
        return _lazy
    raise AttributeError(name)
''',
    GA_RAISE: '''def __getattr__(name):
    raise RuntimeError("lazy loader failed for " + name)
''',
    PLAIN: "def f(): return 1\n",
    BROKEN: "raise RuntimeError('optional backend not configured')\n",
    SYNTAX: "def f(:\n    pass\n",
    PKG + "/__init__": '''from . import sub


def fn(): return 1


sub.fn = fn                     # X16: sub.fn is a function DEFINED in this package's namespace
''',
    PKG + "/sub": "x = 1\n",
    IMPL_NEW: "def score_null(x):\n    return x + 1\n",
    IMPL_OLD: "def score_null(x):\n    return x + 1\n",
}
IMPORTABLE = [FX, OTHER, DEC, REEXP, LAZY, GA_RAISE, PLAIN, PKG, PKG + ".sub", IMPL_NEW, IMPL_OLD]
FIXTURE_CODES: list = []        # (function, original __code__), captured once at load
FIXTURE_BINDINGS: list = []     # (module, name, object) for every fixture module binding


def _write_fixtures(fixdir: Path):
    for name, src in FIXTURES.items():
        p = fixdir / f"{name}.py"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src, encoding="utf-8")


def _collect_functions(obj, out, depth=0):
    if depth > 3:
        return
    if type(obj) is types.FunctionType:
        if all(obj is not f for f, _ in out):
            out.append((obj, obj.__code__))
            w = obj.__dict__.get("__wrapped__")
            if w is not None:
                _collect_functions(w, out, depth + 1)
    elif isinstance(obj, (staticmethod, classmethod)):
        _collect_functions(obj.__func__, out, depth + 1)
    elif isinstance(obj, property):
        _collect_functions(obj.fget, out, depth + 1)
    elif isinstance(obj, functools.partial):
        _collect_functions(obj.func, out, depth + 1)
    elif isinstance(obj, types.MethodType):
        _collect_functions(obj.__func__, out, depth + 1)
    elif isinstance(obj, types.SimpleNamespace):
        for v in vars(obj).values():
            _collect_functions(v, out, depth + 1)
    elif isinstance(obj, type):
        for v in list(vars(obj).values()):
            _collect_functions(v, out, depth + 1)
    elif hasattr(obj, "__wrapped__") and not isinstance(obj, types.ModuleType):
        try:
            w = object.__getattribute__(obj, "__dict__").get("__wrapped__")
        except Exception:                                           # noqa: BLE001
            w = None
        if w is not None:
            _collect_functions(w, out, depth + 1)
    if type(obj) is types.FunctionType and hasattr(obj, "registry"):   # singledispatch
        for v in list(obj.registry.values()):
            _collect_functions(v, out, depth + 1)


def _load_fixtures(fixdir: Path):
    _write_fixtures(fixdir)
    sys.path.insert(0, str(fixdir))
    importlib.invalidate_caches()
    for name in IMPORTABLE:
        importlib.import_module(name)
    for name in IMPORTABLE:
        mod = sys.modules[name]
        for k, v in list(vars(mod).items()):
            FIXTURE_BINDINGS.append((mod, k, v))
            _collect_functions(v, FIXTURE_CODES)


def _fx():
    return sys.modules[FX]


def T(name, mod=FX):
    return f"{mod}:{name}"


# -- the P1 harness, loaded exactly as run_protocol_v5d._load_p1 does it ---------------------------

P1_PUBLIC = [f"styxx.power:{n}" for n in ("effective_n", "order_stat_bar", "false_positive_rate",
                                           "min_detectable_bar", "reachable")]


def _load_p1():
    path = ROOT / "styxx" / "power_QUARANTINED.py.txt"
    loader = importlib.machinery.SourceFileLoader("styxx.power", str(path))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("styxx.power", loader))
    sys.modules["styxx.power"] = mod
    loader.exec_module(mod)
    spec = importlib.util.spec_from_file_location("run_p1", HERE / "run_p1.py")
    run_p1 = importlib.util.module_from_spec(spec)
    sys.modules["run_p1"] = run_p1
    spec.loader.exec_module(run_p1)
    for k, v in list(vars(mod).items()):
        _collect_functions(v, FIXTURE_CODES)
    return run_p1


# -- plumbing -------------------------------------------------------------------------------------

class CaseFailure(Exception):
    """The case's own stated property does not hold (not a refusal, not a crash)."""


class _Reported(Exception):
    """X117's exam sentinel: check_metrics reported instead of raising."""


class _InjectedFault(Exception):
    """X92's fault, injected into the tracer's exit checks."""


def need(cond, msg):
    if not cond:
        raise CaseFailure(msg)


def _commit_prereg(tmp: Path, spec) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / "PREREG_case.md"
    body = spec if isinstance(spec, str) else json.dumps(spec)
    p.write_text("# case\n\n```gates\n" + body + "\n```\n", encoding="utf-8")
    # a scratch repo: never signed, so the exam does not depend on the user's signing setup
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=exam@local", "-c", "user.name=exam",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "case"]):
        subprocess.run(cmd, cwd=tmp, check=True, capture_output=True)
    return p


def _spec(**gates):
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, **extra} for n, extra in gates.items()}
    return {"gates": g,
            "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"},
                         {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "SMOKE"}


def G1(*targets, **more):
    return _spec(G={"exercises": list(targets)}, **more)


def AB(a, b):
    return _spec(A={"exercises": list(a)}, B={"exercises": list(b)})


class _Tmp:
    def __init__(self, base: Path):
        self.d = Path(tempfile.mkdtemp(prefix="case_", dir=str(base)))
        self.n = 0

    def exp(self, spec) -> Experiment:
        self.n += 1
        return Experiment(_commit_prereg(self.d / f"r{self.n}", spec))

    def close(self):
        shutil.rmtree(self.d, ignore_errors=True)


class _T(threading.Thread):
    """A daemon thread that keeps its exception for the case to inspect."""

    def __init__(self, target, *args, **kwargs):
        super().__init__(target=target, args=args, kwargs=kwargs, daemon=True)
        self.exc = None

    def run(self):
        try:
            super().run()
        except BaseException as e:                                  # noqa: BLE001
            self.exc = e


def _join(*threads, timeout=15.0):
    for t in threads:
        t.join(timeout)
        if t.is_alive():
            raise CaseFailure(f"thread {t.name} still running after {timeout}s")
    for t in threads:
        if isinstance(t.exc, GateSpecError):     # never let a sub-thread refusal pose as the case's
            raise CaseFailure(f"sub-thread refused: {str(t.exc)[:200]}")
        if t.exc is not None:
            raise t.exc


def _res(rec, **extra):
    return {"m": 1.0, "coverage_trace": rec, **extra}


def _score(exp, rec):
    return exp.score(_res(rec))


def _trace(exp, harness):
    with coverage_trace(exp) as cov:
        harness(cov)
    return cov.record()


def _union(rec, section) -> dict:
    out = {}
    for o in (rec.get("sections", {}).get(section) or []):
        for k, v in o["calls"].items():
            out[k] = out.get(k, 0) + v
    return out


def _codes(strings) -> set:
    out = set()
    for s in strings:
        m = re.match(r"\[V5:([A-Z_]+)\] ", s) if isinstance(s, str) else None
        if m:
            out.add(m.group(1))
    return out


def _gate_passes(exp, rec, gate):
    try:
        exp._check_coverage(gate, _res(rec))
    except GateSpecError as e:
        raise CaseFailure(f"gate {gate!r} should pass here but refused: {str(e)[:200]}") from None


def _refuses_for(exp, rec, gate, passing=()):
    """The refusal of *gate* (propagated); every gate in *passing* must pass first."""
    for g in passing:
        _gate_passes(exp, rec, g)
    exp._check_coverage(gate, _res(rec))
    return exp.score(_res(rec))


def _all_refuse(exp, rec, code):
    """Every declaring gate refuses with *code*; then the score's own refusal propagates."""
    res, bad = _res(rec), {}
    for g in exp.coverage:
        try:
            exp._check_coverage(g, res)
            bad[g] = "passed"
        except GateSpecError as e:
            if not str(e).startswith(f"[V5:{code}]"):
                bad[g] = str(e)[:160]
    need(not bad, f"not every declaring gate refused {code}: {bad}")
    return exp.score(res)


def _code_list(strings) -> list:
    return sorted(m.group(1) for s in strings
                  for m in [re.match(r"\[V5:([A-Z_]+)\] ", s) if isinstance(s, str) else None] if m)


def _expect(exp, rec, unions, notes=None, ends=None, maybe_notes=None):
    """A valid/residual property: PASS, exactly *unions* per section, and, for EVERY section of the
    trace, exactly the listed note codes (a multiset over its openings; none when unlisted; codes in
    *maybe_notes* may appear any number of times) and every opening's end as listed ("returned"
    when unlisted)."""
    v = exp.score(_res(rec))
    need(v.verdict == "PASS", f"verdict {v.verdict!r}, not PASS")
    got = {s: _union(rec, s) for s in unions}
    need(got == unions, f"union counts {got} != expected {unions}")
    # what score() credits: the union over every opening of the gate's section (Verdict.coverage)
    for g, c in exp.coverage.items():
        if c["section"] in unions:
            want = {t: unions[c["section"]].get(t) for t in c["exercises"]}
            need((v.coverage or {}).get(g) == want,
                 f"score() credited gate {g!r} with {(v.coverage or {}).get(g)}, not {want}")
    for s in set(notes or {}) | set(ends or {}):
        need(s in rec["sections"], f"section {s!r} has no opening")
    for s, ops in rec["sections"].items():
        opt = set((maybe_notes or {}).get(s, ()))
        have = [c for c in _code_list(n for o in ops for n in o["notes"]) if c not in opt]
        want = sorted(c for c in (notes or {}).get(s, ()) if c not in opt)
        need(have == want, f"section {s!r}: note codes {have}, expected exactly {want}"
             + (f" (plus any of {sorted(opt)})" if opt else ""))
        end = (ends or {}).get(s, "returned")
        got_ends = [o["end"] for o in ops]
        need(all(e == end for e in got_ends), f"section {s!r}: ends {got_ends}, expected all {end!r}")
    return {"verdict": v.verdict, "unions": got}


class _Yield:
    def __await__(self):
        yield


class _D(dict):
    """A dict subclass: every trace type check is exact, so this is not a dict to score()."""


class _L(list):
    """A list subclass (see _D)."""


class _S(str):
    """A str subclass (see _D)."""


def _edit_case(edit, targets=None, calls=None):
    """A genuine trace of G, edited, then scored: every clause except the edited one holds."""
    targets = targets or [T("f")]
    calls = calls or (lambda: _fx().f())

    def case(tmp):
        exp = tmp.exp(G1(*targets))
        rec = _trace(exp, lambda cov: cov.run("G", calls))
        edit(rec)
        return _score(exp, rec)
    return case


# -- violation cases: id -> (expected code, case) ------------------------------------------------

def violations() -> dict:
    fx = _fx
    V = {}

    # ---- declaration (parse) ----
    def decl(exercises, call=None, extra_gate=True):
        def case(tmp):
            gates = {"G": {"exercises": exercises}}
            if extra_gate:
                gates["H"] = {"exercises": [T("g")]}
            exp = tmp.exp(_spec(**gates))

            def h(cov):
                if "G" in exp.coverage_sections:
                    cov.run("G", call or (lambda: fx().f()))
                if "H" in exp.coverage_sections:
                    cov.run("H", fx().g)
            return _score(exp, _trace(exp, h))
        return case
    V["X01"] = ("DECL", decl([]))
    V["X02"] = ("DECL", decl(T("f")))
    V["X03"] = ("DECL", decl([T("f") + "\n"]))
    V["X04"] = ("DECL", decl([T(CYR)], call=lambda: getattr(fx(), CYR)()))
    V["X05"] = ("DECL", decl([T("f"), T("f")]))
    # addition: "exercises is not a ... list" alone (X02's str is also refused entry by entry): a
    # JSON object whose keys are valid, distinct targets passes every other DECL clause
    V["X02b"] = ("DECL", decl({T("f"): 1}))

    def x06(tmp):
        exp = tmp.exp(_spec(G={"section": "S"}, H={"exercises": [T("g")]}))
        return _score(exp, _trace(exp, lambda cov: cov.run("H", fx().g)))
    V["X06"] = ("SECTION_DECL", x06)

    def x07(tmp):
        exp = tmp.exp(_spec(G={"exercises": [T("f")], "section": 5}))
        return _score(exp, _trace(exp, lambda cov: cov.run(5, fx().f)))
    V["X07"] = ("SECTION_DECL", x07)

    def x08(tmp):
        exp = tmp.exp(_spec(G={}))
        with coverage_trace(exp) as cov:
            pass
        return _score(exp, cov.record())
    V["X08"] = ("NOTHING_DECLARED", x08)

    # ---- resolution ----
    def resolve_case(target, call=None):
        def case(tmp):
            exp = tmp.exp(G1(target))
            return _score(exp, _trace(exp, lambda cov: cov.run("G", call or (lambda: None))))
        return case
    V["X10"] = ("UNRESOLVED", resolve_case(T("f", BROKEN)))
    V["X11"] = ("UNRESOLVED", resolve_case(T("f", SYNTAX)))
    V["X12"] = ("UNRESOLVED", resolve_case(T("nope", PLAIN)))
    V["X13"] = ("UNRESOLVED", resolve_case(T("lazy", GA_RAISE)))
    # addition: the reason-code table's fourth UNRESOLVED condition (a class lacks the name in its
    # own and every base __dict__), which no listed case reaches
    V["X12b"] = ("UNRESOLVED", resolve_case(T("Base.nope_x12b"), lambda: None))
    V["X14"] = ("INHERITED", resolve_case(T("Sub.fit"), lambda: fx().Sub().fit()))
    V["X15"] = ("INSTANCE_PATH", resolve_case(T("default_model.fit"),
                                              lambda: fx().default_model.fit()))
    V["X16"] = ("INSTANCE_PATH", resolve_case(T("sub.fn", PKG), lambda: sys.modules[PKG].sub.fn()))
    V["X17"] = ("INSTANCE_PATH", resolve_case(T("SL.fn"), lambda: fx().SL.fn()))
    V["X18"] = ("NOT_A_FUNCTION", resolve_case(T("P"), lambda: fx().P()))
    V["X19"] = ("NOT_A_FUNCTION", resolve_case(T("K.p"), lambda: fx().K().p))
    V["X20"] = ("NOT_A_FUNCTION", resolve_case(T("tb_fast"), lambda: fx().tb_fast(1)))
    V["X21"] = ("NOT_A_FUNCTION", resolve_case("builtins:len", lambda: len([])))
    V["X22"] = ("NOT_A_FUNCTION", resolve_case(T("bound_run"), lambda: fx().bound_run()))

    def x23(tmp):
        from unittest import mock
        with mock.patch(f"{FX}.m23"):
            return resolve_case(T("m23"), lambda: fx().m23())(tmp)
    V["X23"] = ("NOT_A_FUNCTION", x23)
    V["X24"] = ("NOT_A_FUNCTION", resolve_case(T("cabs"), lambda: fx().cabs(-1)))

    def x25(tmp):
        fx().fast.cache_clear()
        try:
            return resolve_case(T("fast"), lambda: fx().fast(1))(tmp)
        finally:
            fx().fast.cache_clear()
    V["X25"] = ("NOT_A_FUNCTION", x25)

    def x25b(tmp):
        fx().CacheHolder.fast.cache_clear()
        try:
            return resolve_case(T("CacheHolder.fast"), lambda: fx().CacheHolder.fast(1))(tmp)
        finally:
            fx().CacheHolder.fast.cache_clear()
    # addition: step 4's second namespace ("nor in the namespace that held obj")
    V["X25b"] = ("NOT_A_FUNCTION", x25b)

    def rebound(name, value_fn, call):
        def case(tmp):
            mod = fx()
            orig = getattr(mod, name)
            setattr(mod, name, value_fn())
            try:
                return resolve_case(T(name), call)(tmp)
            finally:
                setattr(mod, name, orig)
        return case
    V["X26"] = ("FOREIGN_DEFINITION", rebound("h26", lambda: sys.modules[OTHER].stub,
                                              lambda: fx().h26()))

    def x27(tmp):
        from unittest import mock
        with mock.patch(f"{FX}.g27", autospec=True):
            return resolve_case(T("g27"), lambda: fx().g27())(tmp)
    V["X27"] = ("FOREIGN_DEFINITION", x27)
    V["X28"] = ("FOREIGN_DEFINITION", resolve_case(T("nowraps_entry", DEC),
                                                   lambda: sys.modules[DEC].nowraps_entry(1)))
    V["X29"] = ("FOREIGN_DEFINITION", resolve_case(T("f", REEXP), lambda: sys.modules[REEXP].f()))
    V["X30"] = ("FOREIGN_DEFINITION", resolve_case(T("made"), lambda: fx().made()))
    # additions: the provenance walk is bounded and cycle-detected. The declaring module's own code
    # sits 17 hops down a foreign wraps chain (beyond "at most 16 hops" on either count of the
    # object itself); and a foreign function whose own-dict __wrapped__ is itself
    V["X30b"] = ("FOREIGN_DEFINITION", resolve_case(T("deep17", DEC),
                                                    lambda: sys.modules[DEC].deep17(1)))
    V["X30c"] = ("FOREIGN_DEFINITION", resolve_case(T("cyc", DEC), lambda: sys.modules[DEC].cyc()))

    def x31(tmp):
        mod = fx()
        fn = mod.x31_t
        e_out, e_in = tmp.exp(G1(T("x31_t"))), tmp.exp(G1(T("x31_t")))
        with coverage_trace(e_out):
            minted = fn.__code__
            fn.__code__ = mod.x31_u.__code__            # swapped under the enclosing trace
            try:
                inner = coverage_trace(e_in)
                inner.__enter__()                      # must refuse CODE_SWAPPED here
                # (reached only if the entry check is missing) restore first, so the exit tripwire
                # cannot stand in for the entry check, then show the inner trace would pass
                fn.__code__ = minted
                try:
                    inner.run("G", fn)
                finally:
                    inner.__exit__(None, None, None)
                return _score(e_in, inner.record())
            finally:
                fn.__code__ = minted
    V["X31"] = ("CODE_SWAPPED", x31)

    def x31b(tmp):
        mod = fx()
        fn = mod.x31_t
        e_out, e_in = tmp.exp(G1(T("x31_t"))), tmp.exp(G1(T("x31_t")))
        with coverage_trace(e_out):
            minted = fn.__code__
            fn.__code__ = minted.replace()             # an EQUAL copy: identity, never equality
            try:
                inner = coverage_trace(e_in)
                inner.__enter__()                      # must refuse CODE_SWAPPED here
                fn.__code__ = minted                   # (see X31)
                try:
                    inner.run("G", fn)
                finally:
                    inner.__exit__(None, None, None)
                return _score(e_in, inner.record())
            finally:
                fn.__code__ = minted
    # addition: the entry check compares by identity (X31's swap is to unequal code)
    V["X31b"] = ("CODE_SWAPPED", x31b)

    def x32(tmp):
        exp = tmp.exp(G1(T("f")))
        cov, raised = coverage_trace(exp), None
        with cov:
            cov.run("G", fx().f)
            try:
                with cov:
                    pass
            except GateSpecError as e:
                raised = str(e)
        need(raised is not None and raised.startswith("[V5:REENTRY]"),
             f"second entry was not refused REENTRY: {raised!r}")
        return _score(exp, cov.record())
    V["X32"] = ("REENTRY", x32)

    def x32b(tmp):
        exp = tmp.exp(G1(T("f")))
        cov, raised = coverage_trace(exp), None
        with cov:
            cov.run("G", fx().f)
        try:
            with cov:                                   # re-entering an EXITED tracer
                pass
        except GateSpecError as e:
            raised = str(e)
        need(raised is not None and raised.startswith("[V5:REENTRY]"),
             f"re-entry after exit was not refused REENTRY: {raised!r}")
        return _score(exp, cov.record())
    # addition: REENTRY on an exited tracer ("not new"), recorded because it was entered before
    V["X32b"] = ("REENTRY", x32b)

    def x33(tmp):
        exp = tmp.exp(G1(T("a33_good"), T("z33_nope")))     # sorted: the good one resolves first
        orig = fx().a33_good.__code__
        try:
            with coverage_trace(exp) as cov:
                cov.run("G", fx().a33_good)
        except GateSpecError:
            need(fx().a33_good.__code__ is orig,
                 "a refused entry left the resolvable target's __code__ minted")
            raise
        return _score(exp, cov.record())
    V["X33"] = ("UNRESOLVED", x33)

    # ---- identity ----
    def ident(target, call):
        def case(tmp):
            exp = tmp.exp(G1(target))
            return _score(exp, _trace(exp, lambda cov: cov.run("G", call)))
        return case
    V["X40"] = ("NOT_EXERCISED", ident(T("check_low"), lambda: fx().check_high(0)))
    V["X41"] = ("NOT_EXERCISED", ident(T("entry_a"), lambda: fx().entry_b(1)))
    V["X42"] = ("NOT_EXERCISED", ident(T("score_all"), lambda: fx()._timed(fx().cheap_path)()))
    V["X43"] = ("NOT_EXERCISED", ident(T("double"), lambda: fx().make_mul(3)(5)))
    V["X44"] = ("NOT_EXERCISED", ident(T("score_lenient"),
                                       lambda: fx().make_scorer(abs, True)(3)))
    V["X45"] = ("NOT_EXERCISED", ident(T("score_null", IMPL_NEW),
                                       lambda: sys.modules[IMPL_OLD].score_null(1)))

    def exec_copy():
        src_mod = sys.modules[IMPL_NEW]
        src = Path(src_mod.__file__).read_text(encoding="utf-8")
        copy = types.ModuleType("_v5e_impl_copy")
        copy.__file__ = src_mod.__file__
        # dont_inherit: this runner's own __future__ flags must not make the copy's code unequal
        exec(compile(src, src_mod.__file__, "exec", dont_inherit=True), copy.__dict__)
        return copy.score_null(1)
    V["X46"] = ("NOT_EXERCISED", ident(T("score_null", IMPL_NEW), exec_copy))
    V["X47"] = ("NOT_EXERCISED", ident(T("DA.__init__"), lambda: fx().DB(3)))

    def x48(tmp):
        clone = types.FunctionType(fx().f48.__code__, fx().f48.__globals__)   # before the trace
        return ident(T("f48"), lambda: clone())(tmp)
    V["X48"] = ("NOT_EXERCISED", x48)
    V["X49"] = ("NOT_EXERCISED", ident(T("run_fast"), lambda: fx().run_plain(1)))
    V["X50"] = ("NOT_EXERCISED", ident(T("run_fast"), lambda: fx().run_safe(1)))
    V["X51"] = ("NOT_EXERCISED", ident(T("public"), lambda: fx().other_entry(1)))
    V["X52"] = ("NOT_EXERCISED", ident(T("wrapped_entry", DEC),
                                       lambda: sys.modules[DEC].wrapped_entry.__wrapped__(2)))

    def rebind53():
        mod = fx()
        orig = mod.f53
        mod.f53 = lambda: 0                           # a local stub, bound during the trace
        try:
            return mod.f53()
        finally:
            mod.f53 = orig
    V["X53"] = ("NOT_EXERCISED", ident(T("f53"), rebind53))

    def x54(tmp):
        fx().cached54.cache_clear()
        fx().cached54(9)                              # the body ran BEFORE the trace; only hits follow
        try:
            return ident(T("cached54"), lambda: fx().cached54(9))(tmp)
        finally:
            fx().cached54.cache_clear()
    V["X54"] = ("NOT_EXERCISED", x54)

    # ---- tripwires (the target is also called normally, so only the tripwire can refuse) ----
    V["X55"] = ("CLONE_CALLED", ident(T("f55"), lambda: (
        fx().f55(), types.FunctionType(fx().f55.__code__, {})())))
    V["X56"] = ("CLONE_CALLED", ident(T("f56"), lambda: (fx().f56(), exec(fx().f56.__code__, {}))))
    # additions: f_globals is compared by IDENTITY. An EQUAL copy of T's globals, and globals that
    # merely carry the module's __name__, are foreign too (X55/X56's {} is unequal to anything)
    V["X55b"] = ("CLONE_CALLED", ident(T("f55"), lambda: (
        fx().f55(), types.FunctionType(fx().f55.__code__, dict(fx().f55.__globals__))())))
    V["X55c"] = ("CLONE_CALLED", ident(T("f55"), lambda: (
        fx().f55(), types.FunctionType(fx().f55.__code__, {"__name__": FX})())))

    def x57(tmp):
        keep = []
        try:
            exp = tmp.exp(G1(T("f57")))
            rec = _trace(exp, lambda cov: cov.run("G", lambda: (
                fx().f57(), keep.append(types.FunctionType(fx().f57.__code__,
                                                           fx().f57.__globals__)))))
            return _score(exp, rec)
        finally:
            keep.clear()
    V["X57"] = ("CLONE_ALIVE", x57)

    def x58(tmp):
        mod = fx()
        orig_u = mod.u58.__code__
        try:
            exp = tmp.exp(G1(T("f58")))

            def body():
                mod.f58()
                mod.u58.__code__ = mod.f58.__code__   # U kept, holding the minted code
                mod.u58()
            rec = _trace(exp, lambda cov: cov.run("G", body))
            return _score(exp, rec)
        finally:
            mod.u58.__code__ = orig_u
    V["X58"] = ("CLONE_ALIVE", x58)

    def x59(tmp):
        mod = fx()
        orig = mod.f59.__code__
        try:
            exp = tmp.exp(G1(T("f59")))

            def body():
                mod.f59()
                mod.f59.__code__ = mod.u59.__code__
            rec = _trace(exp, lambda cov: cov.run("G", body))
            return _score(exp, rec)
        finally:
            mod.f59.__code__ = orig
    V["X59"] = ("CODE_SWAPPED", x59)

    def x59b(tmp):
        mod = fx()
        orig = mod.f59.__code__
        try:
            exp = tmp.exp(G1(T("f59")))

            def body():
                mod.f59()
                mod.f59.__code__ = mod.f59.__code__.replace()     # an EQUAL copy of the mint
            rec = _trace(exp, lambda cov: cov.run("G", body))
            return _score(exp, rec)
        finally:
            mod.f59.__code__ = orig
    # addition: the exit check compares by identity (X59's swap is to unequal code)
    V["X59b"] = ("CODE_SWAPPED", x59b)

    # ---- attribution ----
    # Every call these cases make off the section's own stack is OBSERVED: the thread or task it
    # runs on has the styxx hook live (a foreign thread's work runs inside an opening of a second,
    # unrelated tracer), so each case also pins where the call went in `uncredited`. A call on a
    # thread with no hook would satisfy NOT_EXERCISED by construction and test nothing.
    def other_tracer(tmp):
        return coverage_trace(tmp.exp(G1(T("h"))))     # declares h only: never credits f or g

    def uncredited_is(rec, dispatched, unattributed):
        want = {"dispatched": dispatched, "unattributed": unattributed}
        need(rec["uncredited"] == want,
             f"the off-stack calls were not observed where expected: {rec['uncredited']} != {want}")

    def x60(tmp):
        exp = tmp.exp(AB([T("f")], [T("f")]))
        b_open, called, box = threading.Event(), threading.Event(), {}

        def child():
            b_open.wait(10)
            cov2.run("G", fx().f)                       # observed; on no opening of exp's tracer
            called.set()

        def a():
            box["t"] = _T(child)
            box["t"].start()

        def b():
            b_open.set()
            need(called.wait(10), "the thread started in A never called f")
        with coverage_trace(exp) as cov, other_tracer(tmp) as cov2:
            cov.run("A", a)
            cov.run("B", b)
            _join(box["t"])
        rec = cov.record()
        uncredited_is(rec, {}, {T("f"): 1})
        return _all_refuse(exp, rec, "NOT_EXERCISED")
    V["X60"] = ("NOT_EXERCISED", x60)

    def x61(tmp):
        exp = tmp.exp(AB([T("f")], [T("f")]))
        go, a_open, a_release = (threading.Event() for _ in range(3))
        called = [threading.Event(), threading.Event()]

        def unsectioned(i):
            go.wait(10)
            cov2.run("G", fx().f)                       # observed; on no opening of exp's tracer
            called[i].set()

        def a():
            a_open.set()
            a_release.wait(10)

        def b():
            go.set()
            need(all(c.wait(10) for c in called), "the unsectioned threads never called f")
        with coverage_trace(exp) as cov, other_tracer(tmp) as cov2:
            ths = [_T(unsectioned, i) for i in range(2)]  # two threads: record() merges them all
            for th in ths:
                th.start()                              # started outside any section
            ta = _T(cov.run, "A", a)
            ta.start()
            need(a_open.wait(10), "A never opened")
            try:
                cov.run("B", b)                         # A and B both open during the calls
            finally:
                a_release.set()
            _join(ta, *ths)
        rec = cov.record()
        uncredited_is(rec, {}, {T("f"): 2})
        return _all_refuse(exp, rec, "NOT_EXERCISED")
    V["X61"] = ("NOT_EXERCISED", x61)

    def x62(tmp):
        exp = tmp.exp(AB([T("f")], [T("f")]))
        with coverage_trace(exp) as cov:
            async def main():
                box = {}

                async def work():
                    await asyncio.sleep(0)
                    fx().f()

                async def a():
                    box["t"] = asyncio.ensure_future(work())

                async def b():
                    await box["t"]
                await cov.run_async("A", a)
                await cov.run_async("B", b)
            asyncio.run(main())
        rec = cov.record()
        uncredited_is(rec, {T("f"): 1}, {})
        return _all_refuse(exp, rec, "NOT_EXERCISED")
    V["X62"] = ("NOT_EXERCISED", x62)

    def x63(tmp):
        exp = tmp.exp(AB([T("f")], [T("g")]))
        pool = ThreadPoolExecutor(max_workers=1)
        b1, b2 = threading.Barrier(2, timeout=10), threading.Barrier(2, timeout=10)

        def a():
            pool.submit(fx().h).result(10)            # starts the pool's one worker, inside A
            b1.wait()
            b2.wait()

        def b():
            b1.wait()
            fx().g()
            pool.submit(cov2.run, "G", fx().f).result(10)   # B's job (unsectioned for exp's
            b2.wait()                                       # tracer), observed on A's worker
        try:
            with coverage_trace(exp) as cov, other_tracer(tmp) as cov2:
                ta, tb = _T(cov.run, "A", a), _T(cov.run, "B", b)
                ta.start()
                tb.start()
                _join(ta, tb)
        finally:
            pool.shutdown(wait=True)
        rec = cov.record()
        uncredited_is(rec, {}, {T("f"): 1})
        return _refuses_for(exp, rec, "A", passing=["B"])
    V["X63"] = ("NOT_EXERCISED", x63)

    def x64(tmp):
        exp = tmp.exp(AB([T("f")], [T("g")]))

        class Pool:                                   # t12: a lazily started pool of consumer tasks
            def __init__(self):
                self.q, self.workers = None, []

            async def submit(self, fn):
                if self.q is None:
                    self.q = asyncio.Queue()
                    self.workers = [asyncio.ensure_future(self._work()) for _ in range(2)]
                fut = asyncio.get_running_loop().create_future()
                await self.q.put((fn, fut))
                return await fut

            async def _work(self):
                while True:
                    fn, fut = await self.q.get()
                    fut.set_result(fn())

            async def close(self):
                for w in self.workers:
                    w.cancel()
                await asyncio.gather(*self.workers, return_exceptions=True)
        with coverage_trace(exp) as cov:
            async def main():
                pool, a_started, b_done = Pool(), asyncio.Event(), asyncio.Event()

                async def gate_a():
                    await pool.submit(fx().h)         # A's work: h only; starts the workers
                    a_started.set()
                    await b_done.wait()               # A stays open while B's job runs

                async def gate_b():
                    await a_started.wait()
                    await pool.submit(fx().f)         # B's job, on A-created worker tasks
                    fx().g()
                    b_done.set()
                await asyncio.gather(cov.run_async("A", gate_a), cov.run_async("B", gate_b))
                await pool.close()
            asyncio.run(main())
        rec = cov.record()
        uncredited_is(rec, {T("f"): 1}, {})
        return _refuses_for(exp, rec, "A", passing=["B"])
    V["X64"] = ("NOT_EXERCISED", x64)

    def x65(tmp):
        exp = tmp.exp(AB([T("f")], [T("g")]))
        ready, bdone, box = threading.Event(), threading.Event(), {}

        async def main_a():
            box["loop"] = asyncio.get_running_loop()
            ready.set()
            while not bdone.is_set():
                await asyncio.sleep(0.005)

        async def job():
            fx().f()

        def b():
            try:
                need(ready.wait(10), "A's loop never started")
                fx().g()
                asyncio.run_coroutine_threadsafe(job(), box["loop"]).result(10)
                done = threading.Event()
                box["loop"].call_soon_threadsafe(fx().f)
                box["loop"].call_soon_threadsafe(done.set)
                need(done.wait(10), "call_soon_threadsafe never ran")
            finally:
                bdone.set()
        with coverage_trace(exp) as cov:
            ta = _T(cov.run, "A", asyncio.run, main_a())
            tb = _T(cov.run, "B", b)
            ta.start()
            tb.start()
            _join(ta, tb)
        rec = cov.record()
        uncredited_is(rec, {T("f"): 2}, {})
        return _refuses_for(exp, rec, "A", passing=["B"])
    V["X65"] = ("NOT_EXERCISED", x65)

    def x66(tmp):
        exp = tmp.exp(G1(T("f")))
        closed, box = threading.Event(), {}

        def body():
            box["t"] = _T(lambda: (closed.wait(10), cov2.run("G", fx().f)))
            box["t"].start()
        with coverage_trace(exp) as cov, other_tracer(tmp) as cov2:
            cov.run("G", body)
            closed.set()
            _join(box["t"])
        rec = cov.record()
        uncredited_is(rec, {}, {T("f"): 1})
        return _score(exp, rec)
    V["X66"] = ("NOT_EXERCISED", x66)

    def x67(tmp):
        exp = tmp.exp(G1(T("f")))
        with coverage_trace(exp) as cov:
            async def main():
                box = {}

                async def work():
                    await asyncio.sleep(0)
                    fx().f()

                async def gsec():
                    box["t"] = asyncio.ensure_future(work())
                await cov.run_async("G", gsec)
                await box["t"]                          # awaited after G closed
            asyncio.run(main())
        rec = cov.record()
        uncredited_is(rec, {T("f"): 1}, {})
        return _score(exp, rec)
    V["X67"] = ("NOT_EXERCISED", x67)

    def x68(tmp):
        exp = tmp.exp(G1(T("f")))
        closed, box = threading.Event(), {}

        def body():
            def child():
                box["gc"] = _T(lambda: (closed.wait(10), cov2.run("G", fx().f)))
                box["gc"].start()
            c = _T(child)
            c.start()
            _join(c)
        with coverage_trace(exp) as cov, other_tracer(tmp) as cov2:
            cov.run("G", body)
            closed.set()
            _join(box["gc"])
        rec = cov.record()
        uncredited_is(rec, {}, {T("f"): 1})
        return _score(exp, rec)
    V["X68"] = ("NOT_EXERCISED", x68)

    def x69(tmp):
        exp = tmp.exp(G1(T("f")))
        box = {}

        def body():
            box["gen"] = fx().gen69()
            next(box["gen"])                            # suspended before it calls f
        with coverage_trace(exp) as cov:
            cov.run("G", body)
            next(box["gen"])                            # resumed after G closed, unsectioned
            box["gen"].close()
        rec = cov.record()
        uncredited_is(rec, {}, {T("f"): 1})
        return _score(exp, rec)
    V["X69"] = ("NOT_EXERCISED", x69)

    def x70(tmp):
        exp = tmp.exp(AB([T("f")], [T("g")]))

        async def aw():
            await _Yield()
            fx().f()                                    # runs only after the resume inside B
        with coverage_trace(exp) as cov:
            c = cov.run_async("A", aw)
            c.send(None)

            def b():
                fx().g()
                try:
                    c.send(None)
                except StopIteration:
                    pass
            cov.run("B", b)
        rec = cov.record()
        amb = {s: [o["ambiguous"] for o in rec["sections"].get(s, [])] for s in ("A", "B")}
        need(amb == {"A": [{T("f"): 1}], "B": [{T("f"): 1}]},
             f"ambiguous should be 1 on both openings: {amb}")
        return _refuses_for(exp, rec, "A", passing=["B"])
    V["X70"] = ("NOT_EXERCISED", x70)

    def x71(tmp):
        exp = tmp.exp(G1(T("f")))
        go, rel = threading.Event(), threading.Event()

        def body():
            go.set()
            rel.wait(10)
            fx().f()                                    # the only call: after the tracer exited
        with coverage_trace(exp) as cov:
            t = _T(cov.run, "G", body)
            t.start()
            need(go.wait(10), "section never opened")
        rel.set()
        _join(t)
        rec = cov.record()
        ops = rec["sections"].get("G", [])
        need(len(ops) == 1 and ops[0]["end"] == "open" and "OPEN_AT_EXIT" in _codes(ops[0]["notes"]),
             f"expected one opening, end 'open', OPEN_AT_EXIT note: {ops}")
        return _score(exp, rec)
    V["X71"] = ("NOT_EXERCISED", x71)

    def x71c(tmp):
        """A hit DURING exit, on the stack of the exiting tracer's still-registered opening: only
        exit step 1 (`_by_code` emptied before anything else) keeps it from being credited. The
        tap is the module global `_ANCHORS` rebound to a dict subclass whose first access by the
        exit itself (on this thread, not from inside the profile hook) calls the target once; a
        witness tracer that also declares f proves the call was observed."""
        exp = tmp.exp(G1(T("f")))
        wexp = tmp.exp(_spec(W={"exercises": [T("f")]}))
        me, fire = threading.get_ident(), {"armed": False, "fired": 0}
        hook_code = P._hook.__code__

        def tapped(name):
            base = getattr(dict, name)

            def m(self, *a):
                if fire["armed"] and threading.get_ident() == me:
                    f = sys._getframe(1)
                    while f is not None and f.f_code is not hook_code:
                        f = f.f_back
                    if f is None:                       # the exit's own access, not the hook's
                        fire["armed"] = False
                        fire["fired"] += 1
                        fx().f()
                return base(self, *a)
            return m

        class Tap(dict):
            pass
        for name in ("get", "pop", "__getitem__", "__delitem__", "__contains__", "__setitem__",
                     "setdefault", "items", "values", "keys", "__iter__", "__len__", "copy"):
            setattr(Tap, name, tapped(name))
        with coverage_trace(wexp) as wit:               # keeps a tracer active; witnesses the hit
            cov = coverage_trace(exp)
            cov.__enter__()

            def body():
                saved = P._ANCHORS
                tap = Tap(saved)
                P._ANCHORS = tap
                try:
                    fire["armed"] = True
                    cov.__exit__(None, None, None)      # exit inside G's still-open opening
                finally:
                    fire["armed"] = False
                    now = dict(dict.items(P._ANCHORS))  # the tap, or a dict exit rebound it to
                    saved.clear()
                    saved.update(now)
                    P._ANCHORS = saved
            wit.run("W", cov.run, "G", body)
        need(fire["fired"] == 1,
             f"the exit never reached the module global _ANCHORS (tap fired {fire['fired']} times)")
        need(_union(wit.record(), "W") == {T("f"): 1},
             f"the call made during exit was not observed: witness {wit.record()['sections']}")
        return _score(exp, cov.record())
    # addition: the audit row "emptying _by_code at exit" (X71 cannot see it: its call comes after
    # exit has deregistered every anchor and dropped the tracer from each mint)
    V["X71c"] = ("NOT_EXERCISED", x71c)

    def msg_case(case, *must, forbid=()):
        def wrapped(tmp):
            try:
                return case(tmp)
            except GateSpecError as e:
                missing = [m for m in must if m not in str(e)]
                need(not missing, f"refusal lacks {missing}: {str(e)[:240]}")
                present = [m for m in forbid if m in str(e)]
                need(not present, f"refusal contains {present}: {str(e)[:240]}")
                raise
        return wrapped

    def msg_lists_diagnostics(exp, rec, target):
        """NOT_EXERCISED's message lists the dispatched/unattributed COUNTS and the non-returned
        ENDS: re-scored with one of them changed, the message changes and shows the new value."""
        def refusal(edit):
            r2 = json.loads(json.dumps(rec))
            edit(r2)
            try:
                _score(exp, r2)
            except GateSpecError as e:
                need(str(e).startswith("[V5:NOT_EXERCISED]"), f"edited trace: {str(e)[:160]}")
                return str(e)
            raise CaseFailure("an edited trace was not refused")
        for bucket in ("dispatched", "unattributed"):
            a = refusal(lambda r: r["uncredited"].__setitem__(bucket, {target: 3}))
            b = refusal(lambda r: r["uncredited"].__setitem__(bucket, {target: 7}))
            need(a != b and "7" in b, f"the message does not carry the {bucket} count: {b[:300]}")
        a = refusal(lambda r: [o.__setitem__("end", "returned") for o in r["sections"]["G"]])
        b = refusal(lambda r: [o.__setitem__("end", "raised") for o in r["sections"]["G"]])
        need(a != b and "raised" in b, f"the message does not list a non-returned end: {b[:300]}")

    def x72(tmp):
        exp = tmp.exp(G1(T("f")))

        async def main():
            async def child():
                fx().f()
            await asyncio.gather(child(), child())
        rec = _trace(exp, lambda cov: asyncio.run(cov.run_async("G", main)))
        need(rec["uncredited"]["dispatched"] == {T("f"): 2},
             f"both children's calls belong under 'dispatched': {rec['uncredited']}")
        msg_lists_diagnostics(exp, rec, T("f"))
        return _score(exp, rec)
    V["X72"] = ("NOT_EXERCISED", msg_case(x72, NE_WORDING, FIXED_SENTENCE, forbid=("never executed",)))

    def x73(tmp):
        exp = tmp.exp(G1(T("f")))

        async def main():
            fx().f()
        rec = _trace(exp, lambda cov: cov.run("G", asyncio.run, main()))
        need(rec["uncredited"]["dispatched"] == {T("f"): 1},
             f"the loop's call belongs under 'dispatched': {rec['uncredited']}")
        msg_lists_diagnostics(exp, rec, T("f"))
        return _score(exp, rec)
    V["X73"] = ("NOT_EXERCISED", msg_case(x73, NE_WORDING, FIXED_SENTENCE, forbid=("never executed",)))

    def x74(tmp):
        exp = tmp.exp(G1(T("f")))

        async def afn():
            fx().f()
        box = {}
        try:
            rec = _trace(exp, lambda cov: box.__setitem__("c", cov.run("G", afn)))
        finally:
            if "c" in box:
                box["c"].close()
        return _score(exp, rec)
    V["X74"] = ("NOT_EXERCISED", msg_case(x74, "LAZY_RESULT"))

    def lazy(make):
        def case(tmp):
            exp = tmp.exp(G1(T("f")))
            box = {}
            try:
                rec = _trace(exp, lambda cov: box.__setitem__("r", cov.run("G", make)))
            finally:
                r = box.get("r")
                if isinstance(r, types.GeneratorType):
                    r.close()
            return _score(exp, rec)
        return case

    def genfn():
        fx().f()
        yield 1

    async def agenfn():
        fx().f()
        yield 1
    # additions: LAZY_RESULT's other two result types (generator, async generator)
    V["X74b"] = ("NOT_EXERCISED", msg_case(lazy(genfn), "LAZY_RESULT"))
    V["X74c"] = ("NOT_EXERCISED", msg_case(lazy(agenfn), "LAZY_RESULT"))

    def x75(tmp):
        exp = tmp.exp(G1(T("f")))

        def body():
            sys.setprofile(None)                        # the harness drops the hook first
            fx().f()
        with coverage_trace(exp) as cov:
            t = _T(cov.run, "G", body)                  # a fresh thread the case owns
            t.start()
            _join(t)
        return _score(exp, cov.record())
    V["X75"] = ("NOT_EXERCISED", msg_case(x75, "PROFILER_LOST"))

    # ---- open-time refusals, recorded; each gate otherwise satisfied ----
    def x76(tmp):
        exp = tmp.exp(_spec(G={"exercises": [T("f")]}, H={"exercises": [T("g")]},
                            U={"exercises": [T("h")]}))
        raised = []
        with coverage_trace(exp) as cov:
            def gbody():
                fx().f()
                try:
                    cov.run("H", fx().g)                # same-tracer nested open, swallowed
                except GateSpecError as e:
                    raised.append(str(e))
            cov.run("G", gbody)
            cov.run("H", fx().g)
            cov.run("U", fx().h)                        # an unrelated gate, fully satisfied
        need(raised and raised[0].startswith("[V5:NESTED_SECTION]"),
             f"the nested open was not refused NESTED_SECTION: {raised}")
        return _all_refuse(exp, cov.record(), "NESTED_SECTION")
    V["X76"] = ("NESTED_SECTION", x76)

    def x77(tmp):
        exp = tmp.exp(AB([T("f")], [T("g")]))
        q, errs = queue.Queue(), []

        def consumer():
            fx().f()                                    # A's own work
            while True:
                job = q.get()
                if job is None:
                    return
                try:
                    job()
                except GateSpecError as e:
                    errs.append(str(e))
        with coverage_trace(exp) as cov:
            th = _T(cov.run, "A", consumer)
            th.start()
            q.put(lambda: cov.run("B", fx().g))         # a sectioned job on a sectioned consumer
            q.put(None)
            _join(th)
            cov.run("B", fx().g)                        # B otherwise satisfied
        need(errs and errs[0].startswith("[V5:NESTED_SECTION]"),
             f"the sectioned job was not refused NESTED_SECTION: {errs}")
        return _all_refuse(exp, cov.record(), "NESTED_SECTION")
    V["X77"] = ("NESTED_SECTION", x77)

    def x78(tmp):
        exp = tmp.exp(G1(T("f")))
        raised = []
        with coverage_trace(exp) as cov:
            cov.run("G", fx().f)
            try:
                cov.run("NOT_A_GATE", fx().f)
            except GateSpecError as e:
                raised.append(str(e))
        need(raised and raised[0].startswith("[V5:UNDECLARED_SECTION]"),
             f"the undeclared open was not refused UNDECLARED_SECTION: {raised}")
        return _score(exp, cov.record())
    V["X78"] = ("UNDECLARED_SECTION", x78)

    def x79(tmp):
        exp = tmp.exp(G1(T("f")))
        raised = []
        with coverage_trace(exp) as cov:
            cov.run("G", fx().f)
        try:
            cov.run("G", fx().f)
        except GateSpecError as e:
            raised.append(str(e))
        need(raised and raised[0].startswith("[V5:TRACE_INACTIVE]"),
             f"run after exit was not refused TRACE_INACTIVE: {raised}")
        return _score(exp, cov.record())                # record taken afterwards
    V["X79"] = ("TRACE_INACTIVE", x79)

    # additions: score step 7 takes the FIRST problem's own code and runs before coverage; and the
    # open-time checks run in the spec's order (TRACE_INACTIVE, UNDECLARED_SECTION, NESTED_SECTION,
    # FOREIGN_PROFILER). Each case is otherwise satisfied.
    def x78b(tmp):
        exp = tmp.exp(G1(T("f55")))
        with coverage_trace(exp) as cov:
            try:
                cov.run("NOT_A_GATE", fx().f55)          # recorded first
            except GateSpecError:
                pass
            cov.run("G", lambda: (fx().f55(), types.FunctionType(fx().f55.__code__, {})()))
        rec = cov.record()                               # CLONE_CALLED is recorded second, at exit
        need(_code_list(rec["problems"][:1]) == ["UNDECLARED_SECTION"]
             and "CLONE_CALLED" in _code_list(rec["problems"]),
             f"problems {rec['problems']}")
        return _score(exp, rec)
    V["X78b"] = ("UNDECLARED_SECTION", x78b)

    def x78c(tmp):
        exp = tmp.exp(G1(T("f")))
        with coverage_trace(exp) as cov:
            try:
                cov.run("NOT_A_GATE", fx().f)
            except GateSpecError:
                pass
            cov.run("G", fx().g)                         # G opened; f never called in it
        return _score(exp, cov.record())
    V["X78c"] = ("UNDECLARED_SECTION", x78c)

    def x78d(tmp):
        exp = tmp.exp(G1(T("f")))
        raised = []
        with coverage_trace(exp) as cov:
            def gbody():
                fx().f()
                try:
                    cov.run("NOT_A_GATE", fx().f)        # undeclared AND nested in G
                except GateSpecError as e:
                    raised.append(str(e))
            cov.run("G", gbody)
        need(raised and raised[0].startswith("[V5:UNDECLARED_SECTION]"),
             f"undeclared and nested was not refused UNDECLARED_SECTION first: {raised}")
        return _score(exp, cov.record())
    V["X78d"] = ("UNDECLARED_SECTION", x78d)

    def x79b(tmp):
        exp = tmp.exp(G1(T("f")))
        return coverage_trace(exp).run("G", fx().f)      # a tracer never entered
    V["X79b"] = ("TRACE_INACTIVE", x79b)

    def x79c(tmp):
        exp = tmp.exp(G1(T("f")))
        raised = []
        with coverage_trace(exp) as cov:
            cov.run("G", fx().f)
        try:
            cov.run("NOT_A_GATE", fx().f)               # after exit AND undeclared
        except GateSpecError as e:
            raised.append(str(e))
        need(raised and raised[0].startswith("[V5:TRACE_INACTIVE]"),
             f"after exit and undeclared was not refused TRACE_INACTIVE first: {raised}")
        return _score(exp, cov.record())
    V["X79c"] = ("TRACE_INACTIVE", x79c)

    def x80b(tmp):
        exp = tmp.exp(_spec(G={"exercises": [T("f")]}, H={"exercises": [T("g")]}))
        out = {}

        def prof(frame, event, arg):
            return None
        with coverage_trace(exp) as cov:
            def gbody():
                fx().f()
                sys.setprofile(prof)                    # a foreign profiler appears inside G
                try:
                    cov.run("H", fx().g)                # nested AND under a foreign profiler
                except GateSpecError as e:
                    out["raised"] = str(e)
                finally:
                    sys.setprofile(None)
            t = _T(cov.run, "G", gbody)                 # a fresh thread the case owns
            t.start()
            _join(t)
            cov.run("H", fx().g)                        # H otherwise satisfied
        need(out.get("raised", "").startswith("[V5:NESTED_SECTION]"),
             f"nested under a foreign profiler was not refused NESTED_SECTION first: {out}")
        return _score(exp, cov.record())
    V["X80b"] = ("NESTED_SECTION", x80b)

    def foreign_profiler(make_profiler):
        def case(tmp):
            exp = tmp.exp(G1(T("f")))
            out = {}

            def foreign():
                prof, stop = make_profiler()
                try:
                    try:
                        cov.run("G", fx().f)
                        out["raised"] = None
                    except GateSpecError as e:
                        out["raised"] = str(e)
                    out["kept"] = sys.getprofile() is prof
                finally:
                    stop()
            with coverage_trace(exp) as cov:
                t = _T(foreign)                         # a fresh thread the case owns
                t.start()
                _join(t)
                cov.run("G", fx().f)                    # G otherwise satisfied
            need(out.get("raised") and out["raised"].startswith("[V5:FOREIGN_PROFILER]"),
                 f"the open under a foreign profiler was not refused: {out.get('raised')!r}")
            need(out.get("kept"), "the foreign profiler was not left installed")
            return _score(exp, cov.record())
        return case

    def py_profiler():
        def prof(frame, event, arg):
            return None
        sys.setprofile(prof)
        return prof, lambda: sys.setprofile(None)
    V["X80"] = ("FOREIGN_PROFILER", foreign_profiler(py_profiler))

    def c_profiler():
        import cProfile
        pr = cProfile.Profile()
        pr.enable()
        return pr, pr.disable
    if sys.version_info < (3, 12):
        V["X81"] = ("FOREIGN_PROFILER", foreign_profiler(c_profiler))

    if sys.version_info >= (3, 12):
        def x82(tmp):
            exp = tmp.exp(G1(T("f"), T("g")))

            async def child():
                fx().f()
                await asyncio.sleep(0)
                fx().g()

            async def main():
                asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
                await asyncio.create_task(child())
            rec = _trace(exp, lambda cov: asyncio.run(cov.run_async("G", main)))
            need(_union(rec, "G") == {T("f"): 1}, f"eager first step: {_union(rec, 'G')}")
            return _score(exp, rec)
        V["X82"] = ("NOT_EXERCISED", x82)

    # ---- record() ----
    def x90(tmp):
        exp = tmp.exp(G1(T("f")))
        with coverage_trace(exp) as cov:
            cov.run("G", fx().f)
            rec = cov.record()                          # inside the trace
        return _score(exp, rec)
    V["X90"] = ("TRACE_ACTIVE", x90)

    def x91(tmp):
        exp = tmp.exp(G1(T("f")))
        cov = coverage_trace(exp)
        rec = cov.record()                              # before enter
        with cov:
            cov.run("G", fx().f)
        return _score(exp, rec)
    V["X91"] = ("TRACE_ACTIVE", x91)

    def x92(tmp):
        """The fault is injected by the IDENTITY of the builtin the exit's clone scan calls: on a
        thread the case owns (its last close removed the styxx hook), a profiler raises at the
        c_call of sys.getrefcount (or gc.get_referrers), however the implementation reaches it."""
        exp = tmp.exp(G1(T("f")))
        cov, box = coverage_trace(exp), {}

        def fault(frame, event, arg):
            if event == "c_call" and (arg is _GETREFCOUNT or arg is _GET_REFERRERS):
                raise _InjectedFault("fault injected into the exit checks")

        def owned():
            cov.__enter__()
            cov.run("G", fx().f)
            sys.setprofile(fault)
            try:
                cov.__exit__(None, None, None)
                box["exit"] = "completed"
            except _InjectedFault:
                box["exit"] = "interrupted"
            finally:
                sys.setprofile(None)
        t = _T(owned)
        t.start()
        _join(t)
        need(box.get("exit") == "interrupted", f"the injected fault did not interrupt exit: {box}")
        return _score(exp, cov.record())
    V["X92"] = ("TRACE_INCOMPLETE", x92)

    # ---- score ----
    def x93(tmp):
        exp = tmp.exp(G1(T("f")))
        _trace(exp, lambda cov: cov.run("G", fx().f))
        return exp.score({"m": 1.0})                    # the trace is missing
    V["X93"] = ("NO_TRACE", x93)

    def x93b(tmp):
        exp = tmp.exp(G1(T("f")))
        rec = _trace(exp, lambda cov: cov.run("G", fx().f))
        return exp.score({"m": 1.0, "coverage_trace": _D(rec)})
    # addition: "not an exact dict" (a dict subclass is not a trace)
    V["X93b"] = ("NO_TRACE", x93b)

    def x94(tmp):
        exp = tmp.exp(G1(T("f")))
        rec = _trace(exp, lambda cov: cov.run("G", fx().f))
        return exp._check_coverage("G", [_res(rec)])    # the result is not a dict
    V["X94"] = ("NO_TRACE", x94)

    def x95(tmp):
        v5d = json.loads((HERE / "protocol_v5d_result.json").read_text(encoding="utf-8"))
        exp = Experiment(HERE / "PREREG_protocol_v5d_repair_2026_09_24.md")
        need(exp.coverage, "the v5d prereg declares no coverage")
        return exp._check_coverage(next(iter(exp.coverage)), v5d)
    V["X95"] = ("WRONG_TRACER", x95)

    def op0(rec):
        return rec["sections"]["G"][0]
    V["X96"] = ("BAD_TRACE", _edit_case(lambda r: r.__setitem__("extra", 1)))
    V["X97"] = ("BAD_TRACE", _edit_case(lambda r: r["targets"].__setitem__(1, "x")))
    V["X98"] = ("BAD_TRACE", _edit_case(lambda r: r["targets"].__setitem__(T("f"), 1)))
    V["X99"] = ("BAD_TRACE", _edit_case(lambda r: r["sections"].__setitem__(
        None, [dict(op0(r))])))
    V["X100"] = ("BAD_TRACE", _edit_case(lambda r: r["sections"].__setitem__("G", {T("f"): 1})))
    V["X101"] = ("BAD_TRACE", _edit_case(lambda r: r["sections"].__setitem__("Z", [])))
    V["X102"] = ("BAD_TRACE", _edit_case(lambda r: op0(r).pop("notes")))
    V["X103"] = ("BAD_TRACE", _edit_case(lambda r: op0(r).__setitem__("end", "finished")))
    V["X104"] = ("BAD_TRACE", _edit_case(lambda r: op0(r)["notes"].append("[V5:MADE_UP] x")))
    V["X105"] = ("BAD_TRACE", _edit_case(lambda r: r["problems"].append("[V5:MADE_UP] x")))
    V["X106"] = ("BAD_TRACE", _edit_case(lambda r: r.__setitem__("problems", ())))
    V["X107"] = ("BAD_TRACE", _edit_case(lambda r: r["uncredited"].pop("dispatched")))
    V["X108"] = ("BAD_TRACE", _edit_case(lambda r: op0(r)["calls"].__setitem__(1, 1)))
    # additions: step 3's exact-type and exact-shape conditions the listed cases do not isolate
    V["X96b"] = ("BAD_TRACE", _edit_case(lambda r: r.pop("problems")))
    V["X97b"] = ("BAD_TRACE", _edit_case(lambda r: r.__setitem__("targets", _D(r["targets"]))))
    V["X99b"] = ("BAD_TRACE", _edit_case(lambda r: r.__setitem__("sections", _D(r["sections"]))))
    V["X101b"] = ("BAD_TRACE", _edit_case(lambda r: r["sections"]["G"].__setitem__(
        0, _D(op0(r)))))
    V["X104b"] = ("BAD_TRACE", _edit_case(lambda r: op0(r).__setitem__("notes", ())))
    V["X104c"] = ("BAD_TRACE", _edit_case(lambda r: op0(r)["notes"].append(
        _S("[V5:LAZY_RESULT] a str subclass"))))
    V["X104d"] = ("BAD_TRACE", _edit_case(lambda r: op0(r)["notes"].append("no code here")))
    V["X105b"] = ("BAD_TRACE", _edit_case(lambda r: r["problems"].append("no code here")))
    V["X106b"] = ("BAD_TRACE", _edit_case(lambda r: r.__setitem__("problems", _L())))
    V["X107b"] = ("BAD_TRACE", _edit_case(lambda r: r.__setitem__("uncredited",
                                                                   _D(r["uncredited"]))))
    V["X108b"] = ("BAD_TRACE", _edit_case(lambda r: op0(r).__setitem__("ambiguous", _D())))
    # additions: one edit per remaining exact-type/shape clause, so a clause coded as its own raise
    # is detected when deleted (each other clause holds). _S keys/values catch isinstance weakening
    # (an _S key equal to a declared target also passes BAD_COUNT); int keys catch deletion.
    V["X97c"] = ("BAD_TRACE", _edit_case(lambda r: r.__setitem__(
        "targets", {_S(k): v for k, v in r["targets"].items()})))
    V["X98b"] = ("BAD_TRACE", _edit_case(lambda r: r.__setitem__(
        "targets", {k: _S(v) for k, v in r["targets"].items()})))
    V["X99c"] = ("BAD_TRACE", _edit_case(lambda r: r.__setitem__(
        "sections", {_S(k): v for k, v in r["sections"].items()})))
    V["X100b"] = ("BAD_TRACE", _edit_case(lambda r: r["sections"].__setitem__(
        "G", _L(r["sections"]["G"]))))
    V["X100c"] = ("BAD_TRACE", _edit_case(lambda r: r["sections"].__setitem__(
        "G", tuple(r["sections"]["G"]))))              # a non-list of valid openings
    V["X102b"] = ("BAD_TRACE", _edit_case(lambda r: op0(r).__setitem__("extra", 1)))
    V["X104e"] = ("BAD_TRACE", _edit_case(lambda r: op0(r).__setitem__("notes", _L())))
    V["X105c"] = ("BAD_TRACE", _edit_case(lambda r: r["problems"].append(
        _S("[V5:NESTED_SECTION] a str subclass"))))
    V["X107c"] = ("BAD_TRACE", _edit_case(lambda r: r["uncredited"].__setitem__("extra", {})))

    def count_dict(which):
        """The count dict *which* of G's trace (calls/ambiguous of the opening, or a bucket)."""
        def get(r):
            return op0(r)[which] if which in ("calls", "ambiguous") else r["uncredited"][which]

        def put(r, d):
            (op0(r) if which in ("calls", "ambiguous") else r["uncredited"])[which] = d
        return get, put

    def cd_subclass(which):
        get, put = count_dict(which)
        return _edit_case(lambda r: put(r, _D(get(r))))

    def cd_key(which, key):
        get, put = count_dict(which)
        return _edit_case(lambda r: put(r, {**{k: v for k, v in get(r).items() if k != T("f")},
                                            key: 1}))
    V["X108c"] = ("BAD_TRACE", cd_key("calls", _S(T("f"))))
    V["X108d"] = ("BAD_TRACE", cd_key("unattributed", 1))
    V["X108e"] = ("BAD_TRACE", cd_subclass("calls"))
    V["X108f"] = ("BAD_TRACE", cd_key("ambiguous", 1))
    V["X108g"] = ("BAD_TRACE", cd_key("ambiguous", _S(T("f"))))
    V["X108h"] = ("BAD_TRACE", cd_subclass("dispatched"))
    V["X108i"] = ("BAD_TRACE", cd_key("dispatched", 1))
    V["X108j"] = ("BAD_TRACE", cd_key("dispatched", _S(T("f"))))
    V["X108k"] = ("BAD_TRACE", cd_subclass("unattributed"))
    V["X108m"] = ("BAD_TRACE", cd_key("unattributed", _S(T("f"))))

    def x109(tmp):
        a = tmp.exp(G1(T("f")))
        bs = G1(T("f"))
        bs["gates"]["G"]["value"] = 0.6
        b = tmp.exp(bs)
        return _score(b, _trace(a, lambda cov: cov.run("G", fx().f)))
    V["X109"] = ("STALE_TRACE", x109)
    V["X110"] = ("TARGET_SET", _edit_case(lambda r: r["targets"].pop(T("g")),
                                          targets=[T("f"), T("g")],
                                          calls=lambda: (_fx().f(), _fx().g())))
    V["X111"] = ("BAD_COUNT", _edit_case(lambda r: op0(r)["calls"].__setitem__(T("f"), True)))
    V["X112"] = ("BAD_COUNT", _edit_case(lambda r: op0(r)["calls"].__setitem__(T("f"), 0)))
    V["X113"] = ("BAD_COUNT", _edit_case(lambda r: op0(r)["calls"].__setitem__(T("h"), 1)))
    V["X114"] = ("BAD_COUNT", _edit_case(lambda r: op0(r)["ambiguous"].__setitem__(T("h"), 1)))
    V["X115"] = ("BAD_COUNT", _edit_case(
        lambda r: r["uncredited"]["dispatched"].__setitem__(T("h"), 1)))
    V["X115b"] = ("BAD_COUNT", _edit_case(
        lambda r: r["uncredited"]["unattributed"].__setitem__(T("h"), 1)))
    # addition: TARGET_SET is set EQUALITY (X110 removes a target; this adds an undeclared one)
    V["X110b"] = ("TARGET_SET", _edit_case(lambda r: r["targets"].__setitem__(T("h"), "x.py:1")))

    def x116(tmp):
        exp = tmp.exp(_spec(G={"exercises": [T("f")]}, H={"exercises": [T("g")]}))
        return _score(exp, _trace(exp, lambda cov: cov.run("H", fx().g)))
    V["X116"] = ("SECTION_ABSENT", x116)

    def x117(tmp):
        exp = tmp.exp(G1(T("f")))
        for bad in (None, [], "s", 5):
            try:
                out = exp.check_metrics(bad)
            except BaseException as e:                 # noqa: BLE001  a raise is a crash here
                raise RuntimeError(f"check_metrics({bad!r}) raised {type(e).__name__}: {e}") from None
            ent = out.get("G:exercises") if isinstance(out, dict) else None
            need(isinstance(ent, dict) and ent.get("usable") is False,
                 f"check_metrics({bad!r}) did not report usable False: {ent!r}")
        raise _Reported("[V5:REPORTED] check_metrics(None / [] / 's' / 5) reported usable: False "
                        "without raising")
    V["X117"] = ("REPORTED", x117)
    return V


def x118_p1_retro(tmp):
    """G2: P1's own harness, unmodified, with P1's G4 declaring the five public functions."""
    import numpy as np
    run_p1 = sys.modules["run_p1"]
    committed = json.loads((HERE / "p1_result.json").read_text(encoding="utf-8"))
    gates = json.loads(_select_gates_block((HERE / P1_PREREG).read_text(encoding="utf-8")))
    gates["gates"]["G4_refuses_degenerate"]["exercises"] = P1_PUBLIC
    exp = tmp.exp(json.dumps(gates))
    with coverage_trace(exp) as cov:
        deg = cov.run("G4_refuses_degenerate", run_p1.degenerate,
                      np.random.default_rng(run_p1.SEED))
    rec = cov.record()
    res = dict(committed)
    res["coverage_trace"] = rec
    res["degenerate_refusal_rate"] = round(float(np.mean([c["refused"] for c in deg])), 4)
    need(res["degenerate_refusal_rate"] == committed.get("degenerate_refusal_rate") == 1.0,
         f"degenerate_refusal_rate {res['degenerate_refusal_rate']} (committed "
         f"{committed.get('degenerate_refusal_rate')!r}, spec 1.0)")
    want = {"G4_refuses_degenerate": [{"calls": {"styxx.power:reachable": 12}, "ambiguous": {},
                                       "end": "returned", "notes": []}]}
    need(rec["sections"] == want, f"section record {rec['sections']} != {want}")
    need(rec["uncredited"] == {"dispatched": {}, "unattributed": {}},
         f"uncredited not empty: {rec['uncredited']}")
    need(rec["problems"] == [], f"problems: {rec['problems']}")
    try:
        return exp.score(res)
    except GateSpecError as e:
        four = [t for t in P1_PUBLIC if t != "styxx.power:reachable"]
        missing = [t for t in four if t not in str(e)]
        need(not missing, f"the refusal does not name {missing}: {str(e)[:240]}")
        raise


# -- valid cases: id -> (expected property, case) ----------------------------------------------

def valids() -> dict:
    fx = _fx
    V = {}

    def one(targets, call, unions, **kw):
        def case(tmp):
            exp = tmp.exp(G1(*targets))
            return _expect(exp, _trace(exp, lambda cov: cov.run("G", call)), unions, **kw)
        return case

    V["V01"] = ("{f:1}", one([T("f")], lambda: fx().f(), {"G": {T("f"): 1}}))
    V["V02"] = ("{f:1, alias_f:1}", one([T("f"), T("alias_f")], lambda: fx().f(),
                                        {"G": {T("f"): 1, T("alias_f"): 1}}))
    V["V03"] = ("{double:1}", one([T("double")], lambda: fx().double(5), {"G": {T("double"): 1}}))
    V["V04"] = ("{entry_a:1}", one([T("entry_a")], lambda: fx().entry_a(1),
                                   {"G": {T("entry_a"): 1}}))
    V["V05"] = ("{DA.__init__:1}", one([T("DA.__init__")], lambda: fx().DA(),
                                       {"G": {T("DA.__init__"): 1}}))
    V["V06"] = ("{dispatch:1}", one([T("dispatch")], lambda: fx().dispatch(1),
                                    {"G": {T("dispatch"): 1}}))

    def v07(tmp):
        fx().cached.cache_clear()
        try:
            return one([T("cached")], lambda: (fx().cached(1), fx().cached(1)),
                       {"G": {T("cached"): 1}})(tmp)
        finally:
            fx().cached.cache_clear()
    V["V07"] = ("{cached:1}", v07)
    V["V08"] = ("{NS.handler:1}", one([T("NS.handler")], lambda: fx().NS.handler(),
                                      {"G": {T("NS.handler"): 1}}))
    V["V09"] = ("{Base.fit:1}", one([T("Base.fit")], lambda: fx().Sub().fit(),
                                    {"G": {T("Base.fit"): 1}}))
    V["V10"] = ("{lazy_fn:1}", one([T("lazy_fn", LAZY)], lambda: sys.modules[LAZY].lazy_fn(),
                                   {"G": {T("lazy_fn", LAZY): 1}}))
    V["V11"] = ("{wrapped_entry:1}", one([T("wrapped_entry", DEC)],
                                         lambda: sys.modules[DEC].wrapped_entry(2),
                                         {"G": {T("wrapped_entry", DEC): 1}}))
    # addition: provenance passes through a chain longer than one hop
    V["V11b"] = ("{wrapped2:1}", one([T("wrapped2", DEC)], lambda: sys.modules[DEC].wrapped2(2),
                                     {"G": {T("wrapped2", DEC): 1}}))
    V["V12"] = ("{K.s:1, K.c:1}", one([T("K.s"), T("K.c")], lambda: (fx().K.s(), fx().K.c()),
                                      {"G": {T("K.s"): 1, T("K.c"): 1}}))
    V["V13"] = ("{score:1}", one([T("score")], lambda: fx().score_v1(1), {"G": {T("score"): 1}}))
    V["V14"] = ("{gen:3}", one([T("gen")], lambda: list(fx().gen()), {"G": {T("gen"): 3}}))

    def v15(tmp):
        mod = fx()
        orig = mod.f.__code__
        e_out, e_in = tmp.exp(_spec(G={"exercises": [T("f")]})), tmp.exp(_spec(H={"exercises": [T("f")]}))
        box = {}
        with coverage_trace(e_out) as outer:
            def gbody():
                with coverage_trace(e_in) as inner:
                    inner.run("H", mod.f)
                box["inner"] = inner.record()
            outer.run("G", gbody)
        a = _expect(e_out, outer.record(), {"G": {T("f"): 1}})
        b = _expect(e_in, box["inner"], {"H": {T("f"): 1}})
        need(mod.f.__code__ is orig, "f.__code__ not restored after both tracers")
        return {"outer": a, "inner": b}
    V["V15"] = ("outer {f:1}, inner {f:1}; code restored", v15)

    def v16(tmp):
        mod = fx()
        of, og = mod.f.__code__, mod.g.__code__
        e1, e2 = tmp.exp(G1(T("f"))), tmp.exp(G1(T("f"), T("g")))
        t1, t2 = coverage_trace(e1), coverage_trace(e2)
        t1.__enter__()
        try:
            t2.__enter__()
            try:
                t1.run("G", mod.f)
                t2.run("G", lambda: (mod.f(), mod.g()))
            finally:
                t1.__exit__(None, None, None)          # non-LIFO: the outer one first
        finally:
            t2.__exit__(None, None, None)
        a = _expect(e1, t1.record(), {"G": {T("f"): 1}})
        b = _expect(e2, t2.record(), {"G": {T("f"): 1, T("g"): 1}})
        need(mod.f.__code__ is of and mod.g.__code__ is og, "code not restored after non-LIFO exit")
        return {"t1": a, "t2": b}
    V["V16"] = ("t1 {f:1}, t2 {f:1, g:1}; code restored", v16)

    def v17(tmp):
        e1, e2 = tmp.exp(G1(T("f"))), tmp.exp(G1(T("f")))
        start, rounds = threading.Barrier(2, timeout=10), threading.Barrier(2, timeout=10)
        box = {}

        def worker(key, e, n):
            with coverage_trace(e) as cov:
                start.wait()

                def body():
                    for i in range(5):
                        rounds.wait()
                        if i < n:
                            fx().f()
                cov.run("G", body)
                start.wait()
            box[key] = (e, cov.record())
        t1, t2 = _T(worker, "a", e1, 3), _T(worker, "b", e2, 5)
        t1.start()
        t2.start()
        _join(t1, t2)
        return {"a": _expect(*box["a"], {"G": {T("f"): 3}}),
                "b": _expect(*box["b"], {"G": {T("f"): 5}})}
    V["V17"] = ("{f:3} and {f:5}", v17)

    def v18(tmp):
        exp = tmp.exp(G1(T("f"), T("g")))

        async def main():
            fx().f()
            await asyncio.sleep(0)
            fx().g()
        rec = _trace(exp, lambda cov: asyncio.run(cov.run_async("G", main)))
        return _expect(exp, rec, {"G": {T("f"): 1, T("g"): 1}})
    V["V18"] = ("{f:1, g:1}", v18)

    def v19(tmp):
        exp = tmp.exp(AB([T("f")], [T("g")]))

        def a(cov):
            async def job():
                fx().g()

            async def main():
                await asyncio.gather(cov.run_async("B", job), cov.run_async("B", job))
            fx().f()
            asyncio.run(main())
        rec = _trace(exp, lambda cov: cov.run("A", a, cov))
        return _expect(exp, rec, {"A": {T("f"): 1}, "B": {T("g"): 2}})
    V["V19"] = ("A {f:1}, B {g:2}", v19)

    def v20(tmp):
        exp = tmp.exp(G1(T("g")))

        def h(cov):
            async def job():
                fx().g()

            async def main():
                await asyncio.gather(*(cov.run_async("G", job) for _ in range(5)))
            asyncio.run(main())
        return _expect(exp, _trace(exp, h), {"G": {T("g"): 5}})
    V["V20"] = ("{g:5}", v20)

    def v21(tmp):
        exp = tmp.exp(G1(T("f")))
        profs = []

        def h(cov):
            def job():
                cov.run("G", fx().f)
                return sys.getprofile()                 # the last close on this thread removed it

            async def main():
                return await asyncio.to_thread(job)
            profs.append(asyncio.run(main()))
            with ThreadPoolExecutor(4) as ex:
                profs.extend(ex.map(lambda _: job(), range(8)))
        out = _expect(exp, _trace(exp, h), {"G": {T("f"): 9}})
        need(all(p is None for p in profs), f"hooked threads left: {profs}")
        return out
    V["V21"] = ("{f:9}; no hooked threads left", v21)

    def v22(tmp):
        exp = tmp.exp(G1(T("f")))
        bar = threading.Barrier(2, timeout=10)

        def shard(cov, n):
            def body():
                bar.wait()
                for _ in range(n):
                    fx().f()
                bar.wait()
            cov.run("G", body)

        def h(cov):
            t1, t2 = _T(shard, cov, 3), _T(shard, cov, 4)
            t1.start()
            t2.start()
            _join(t1, t2)
        return _expect(exp, _trace(exp, h), {"G": {T("f"): 7}})
    V["V22"] = ("{f:7} (3 + 4)", v22)

    def v23(tmp):
        from multiprocessing.pool import ThreadPool
        exp = tmp.exp(G1(T("f")))
        profs = []

        def h(cov):
            pool = ThreadPool(2)
            try:
                profs.extend(pool.map(lambda _: (cov.run("G", fx().f), sys.getprofile())[1],
                                      range(4)))
            finally:
                pool.terminate()                        # terminate without join
        out = _expect(exp, _trace(exp, h), {"G": {T("f"): 4}})
        need(all(p is None for p in profs), f"hooked threads left: {profs}")
        return out
    V["V23"] = ("{f:4}", v23)

    def v24(tmp):
        exp = tmp.exp(G1(T("f")))
        stop, box = threading.Event(), {}

        def body():
            box["d"] = _T(lambda: stop.wait(30))       # a library daemon thread outliving G
            box["d"].start()
            fx().f()
        try:
            rec = _trace(exp, lambda cov: cov.run("G", body))
            need(box["d"].is_alive(), "the daemon thread did not outlive the section")
            return _expect(exp, rec, {"G": {T("f"): 1}})
        finally:
            stop.set()
            if "d" in box:
                box["d"].join(10)
    V["V24"] = ("{f:1}", v24)

    def v25(tmp):
        exp = tmp.exp(G1(T("f"), T("g")))

        def case(x):
            fx().f()
            fx().g()
            raise ValueError("refused as expected")

        def h(cov):
            for x in range(3):
                try:
                    cov.run("G", case, x)
                except ValueError:
                    pass
        return _expect(exp, _trace(exp, h), {"G": {T("f"): 3, T("g"): 3}}, ends={"G": "raised"})
    V["V25"] = ("{f:3, g:3}; ends raised", v25)

    # additions: run_async closes in its finally too, on a raise and on cancellation (a close
    # skipped there is tidied by exit as OPEN_AT_EXIT, which only the end state shows)
    def v25b(tmp):
        exp = tmp.exp(G1(T("f")))

        async def boom():
            fx().f()
            raise ValueError("refused as expected")

        async def main(cov):
            for _ in range(3):
                try:
                    await cov.run_async("G", boom)
                except ValueError:
                    pass
        rec = _trace(exp, lambda cov: asyncio.run(main(cov)))
        return _expect(exp, rec, {"G": {T("f"): 3}}, ends={"G": "raised"})
    V["V25b"] = ("{f:3}; ends raised (run_async)", v25b)

    def v25c(tmp):
        exp = tmp.exp(G1(T("f")))

        async def slow(started):
            fx().f()
            started.set()
            await asyncio.sleep(30)

        async def main(cov):
            started = asyncio.Event()
            t = asyncio.ensure_future(cov.run_async("G", slow, started))
            await started.wait()
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        rec = _trace(exp, lambda cov: asyncio.run(main(cov)))
        return _expect(exp, rec, {"G": {T("f"): 1}}, ends={"G": "raised"})
    V["V25c"] = ("{f:1}; end raised (run_async cancelled)", v25c)

    def on_own_thread(fn):
        """Run fn on a fresh thread the case owns (the case thread's hook is the outer trace's)."""
        box = {}

        def run():
            box["v"] = fn()
            box["prof_after"] = sys.getprofile()
        t = _T(run)
        t.start()
        _join(t)
        return box

    def v26(tmp):
        exp = tmp.exp(G1(T("f")))
        box = {}

        def h(cov):
            box.update(on_own_thread(lambda: cov.run("G", lambda: (fx().f(), sys.setprofile(None)))))
        rec = _trace(exp, h)
        return _expect(exp, rec, {"G": {T("f"): 1}}, notes={"G": ["PROFILER_LOST"]})
    V["V26"] = ("{f:1}; PROFILER_LOST note", v26)

    def v27(tmp):
        exp = tmp.exp(G1(T("f")))

        def deep(n):
            return deep(n + 1)

        def body():
            fx().f()
            try:
                deep(0)
            except RecursionError:
                pass

        def h(cov):
            on_own_thread(lambda: cov.run("G", body))
        # the RecursionError may or may not land in the hook: PROFILER_LOST is allowed, not asserted
        return _expect(exp, _trace(exp, h), {"G": {T("f"): 1}}, maybe_notes={"G": ["PROFILER_LOST"]})
    V["V27"] = ("{f:1}", v27)

    def v28(tmp):
        exp = tmp.exp(G1(T("f")))

        async def aw():
            fx().f()
            await _Yield()

        def h(cov):
            c = cov.run_async("G", aw)
            c.send(None)                                # opened here, suspended

            def fin():
                try:
                    c.send(None)
                except StopIteration:
                    pass
            t = _T(fin)                                 # closed on another thread
            t.start()
            _join(t)
        return _expect(exp, _trace(exp, h), {"G": {T("f"): 1}}, notes={"G": ["THREAD_HOP"]})
    V["V28"] = ("{f:1}; THREAD_HOP note", v28)

    def v29(tmp):
        exp = tmp.exp(G1(T("f")))
        go, rel = threading.Event(), threading.Event()

        def body():
            fx().f()
            go.set()
            rel.wait(10)
        with coverage_trace(exp) as cov:
            t = _T(cov.run, "G", body)
            t.start()
            need(go.wait(10), "section never opened")
        rel.set()
        _join(t)
        return _expect(exp, cov.record(), {"G": {T("f"): 1}}, notes={"G": ["OPEN_AT_EXIT"]},
                       ends={"G": "open"})
    V["V29"] = ("{f:1}; end open; OPEN_AT_EXIT", v29)

    def v30(tmp):
        exp = tmp.exp(AB([T("f")], [T("g")]))

        def h(cov):
            async def a():
                sys.setprofile(None)                    # A drops the hook ...
                await asyncio.sleep(0.02)
                fx().f()                                # ... B has reinstalled it by now

            async def b():
                await asyncio.sleep(0)
                fx().g()

            async def main():
                await asyncio.gather(cov.run_async("A", a), cov.run_async("B", b))
            on_own_thread(lambda: asyncio.run(main()))
        return _expect(exp, _trace(exp, h), {"A": {T("f"): 1}, "B": {T("g"): 1}},
                       notes={"A": ["PROFILER_LOST"]})
    V["V30"] = ("A {f:1} with PROFILER_LOST; B {g:1}", v30)

    def v31(tmp):
        exp = tmp.exp(G1(T("f")))
        out = {}

        def h(cov):
            def sub():
                saved = []
                cov.run("G", lambda: (fx().f(), saved.append(sys.getprofile())))
                out["after_close"] = sys.getprofile()
                sys.setprofile(saved[0])                # the harness reinstalls the saved hook
                fx().g()                                # one event outside any section
                out["after_event"] = sys.getprofile()
                sys.setprofile(None)
            on_own_thread(sub)
        rec = _trace(exp, h)
        need(out.get("after_close") is None, f"last close left the hook: {out.get('after_close')!r}")
        need(out.get("after_event") is None,
             f"the reinstalled hook did not remove itself: {out.get('after_event')!r}")
        return _expect(exp, rec, {"G": {T("f"): 1}})
    V["V31"] = ("sys.getprofile() is None after one event", v31)

    if not MUTATION:
        V["V32"] = ("recorded equals expected, 0 cross-credit, no leftovers, 3 runs", v32_stress)

    if sys.version_info >= (3, 12):
        def v33(tmp):
            exp = tmp.exp(G1(T("f")))

            def sub(cov):
                import cProfile
                pr = cProfile.Profile()
                pr.enable()
                try:
                    cov.run("G", fx().f)
                finally:
                    pr.disable()
            return _expect(exp, _trace(exp, lambda cov: on_own_thread(lambda: sub(cov))),
                           {"G": {T("f"): 1}})
        V["V33"] = ("{f:1}", v33)

    V["V34"] = ("machinery targets >= 1 and _CoverageTracer.run == inner runs (nested "
                "machinery tracer); the outer self-trace: every declared target >= 1, one "
                "returned opening per case run, no problems, nothing left after exit", v34_nested)
    return V


MACHINERY = ["styxx.protocol:_CoverageTracer.run", "styxx.protocol:_CoverageTracer._open",
             "styxx.protocol:_CoverageTracer._close", "styxx.protocol:_CoverageTracer.record",
             "styxx.protocol:_CoverageTracer.__enter__", "styxx.protocol:_CoverageTracer.__exit__",
             "styxx.protocol:_resolve_target", "styxx.protocol:Experiment._check_coverage"]
V34_TRACERS, V34_RUNS = 3, 2


def v34_nested(tmp):
    """V34 part 1: a tracer declaring the machinery itself; every target >= 1, run == inner runs."""
    e_self, e_in = tmp.exp(_spec(S={"exercises": MACHINERY})), tmp.exp(G1(T("f")))
    verdicts = []

    def battery():
        for _ in range(V34_TRACERS):
            with coverage_trace(e_in) as c:
                for _ in range(V34_RUNS):
                    c.run("G", _fx().f)
            verdicts.append(e_in.score(_res(c.record())).verdict)
    with coverage_trace(e_self) as ts:
        ts.run("S", battery)
    rec = ts.record()
    u = _union(rec, "S")
    need(verdicts == ["PASS"] * V34_TRACERS, f"inner verdicts {verdicts}")
    need(all(u.get(t, 0) >= 1 for t in MACHINERY),
         f"machinery targets not exercised: {[t for t in MACHINERY if u.get(t, 0) < 1]}")
    need(u.get(MACHINERY[0]) == V34_TRACERS * V34_RUNS,
         f"_CoverageTracer.run counted {u.get(MACHINERY[0])}, inner runs {V34_TRACERS * V34_RUNS}")
    v = e_self.score(_res(rec))
    need(v.verdict == "PASS", f"machinery trace verdict {v.verdict}")
    return {"nested_union": u}


def v32_stress(tmp):
    """8 threads, 40 tasks, unsectioned noise (tasks and a thread); 3 runs, fixed seeds."""
    exp = tmp.exp(AB([T("f")], [T("g")]))
    runs = []
    for seed in (1, 2, 3):
        before = _registries()
        rng, expect = random.Random(seed), {"A": 0, "B": 0}
        fx = _fx()

        async def task_body(sec, n):
            for _ in range(n):
                fx.f() if sec == "A" else fx.g()
                await asyncio.sleep(0)

        async def noise(n):
            for _ in range(n):
                fx.f()
                fx.g()
                await asyncio.sleep(0)

        def thread_body(sec, n):
            for _ in range(n):
                fx.f() if sec == "A" else fx.g()
        with coverage_trace(exp) as cov:
            async def main():
                jobs = []
                for _ in range(40):
                    sec, n = rng.choice("AB"), rng.randint(1, 20)
                    expect[sec] += n
                    jobs.append(cov.run_async(sec, task_body, sec, n))
                jobs += [noise(30) for _ in range(5)]
                await asyncio.gather(*jobs)
            ths = []
            for _ in range(8):
                sec, n = rng.choice("AB"), rng.randint(100, 2000)
                expect[sec] += n
                ths.append(_T(cov.run, sec, thread_body, sec, n))
            ths.append(_T(lambda: [fx.f() for _ in range(5000)]))     # unsectioned thread
            for t in ths:
                t.start()
            asyncio.run(main())
            _join(*ths, timeout=60)
        rec = cov.record()
        got = {"A": _union(rec, "A").get(T("f"), 0), "B": _union(rec, "B").get(T("g"), 0)}
        cross = _union(rec, "A").get(T("g"), 0) + _union(rec, "B").get(T("f"), 0)
        _expect(exp, rec, {"A": {T("f"): expect["A"]}, "B": {T("g"): expect["B"]}})
        need(got == expect and cross == 0, f"seed {seed}: expected {expect} got {got} cross {cross}")
        need(_registries_equal(before), f"seed {seed}: leftover after the run")
        runs.append({"seed": seed, "expected": expect, "recorded": got, "cross": cross})
    return {"runs": runs}


# -- residual cases: id -> (documented outcome, case) --------------------------------------------

def residuals() -> dict:
    fx = _fx
    R = {}

    def r01(tmp):
        exp = tmp.exp(AB([T("f")], [T("g")]))
        q, started, bdone = queue.Queue(), threading.Event(), threading.Event()

        def consumer():
            started.set()
            while True:
                job = q.get()
                if job is None:
                    return
                job()
                q.task_done()

        def a(cov):
            th = _T(cov.run, "A", consumer)            # A's sectioned, long-lived consumer
            th.start()
            started.wait(10)
            bdone.wait(10)
            q.put(None)
            _join(th)

        def b():
            started.wait(10)
            fx().g()
            q.put(fx().f)                              # B's job, drained by A's consumer
            q.join()
            bdone.set()
        with coverage_trace(exp) as cov:
            ta, tb = _T(cov.run, "A", a, cov), _T(cov.run, "B", b)
            ta.start()
            tb.start()
            _join(ta, tb)
        return _expect(exp, cov.record(), {"A": {T("f"): 1}})
    R["R01"] = ("A PASS {f:1}", r01)

    def r02(tmp):
        exp = tmp.exp(AB([T("f")], [T("g")]))
        jobs = []

        def h(cov):
            cov.run("B", lambda: (fx().g(), jobs.append(fx().f)))
            cov.run("A", lambda: [j() for j in jobs])  # A drains B's queued job inline
        return _expect(exp, _trace(exp, h), {"A": {T("f"): 1}})
    R["R02"] = ("A PASS", r02)

    def one(targets, call, unions):
        def case(tmp):
            exp = tmp.exp(G1(*targets))
            return _expect(exp, _trace(exp, lambda cov: cov.run("G", call)), unions)
        return case
    R["R03"] = ("PASS", one([T("f")], lambda: types.FunctionType(fx().f.__code__,
                                                                 fx().f.__globals__)(),
                            {"G": {T("f"): 1}}))
    R["R04"] = ("PASS", one([T("f_r04")], lambda: exec(fx().f_r04.__code__,
                                                        fx().f_r04.__globals__),
                            {"G": {T("f_r04"): 1}}))

    def rebound(name, value_fn, unions):
        def case(tmp):
            mod = fx()
            orig = getattr(mod, name)
            setattr(mod, name, value_fn())
            try:
                return one([T(name)], lambda: getattr(mod, name)(), unions)(tmp)
            finally:
                setattr(mod, name, orig)
        return case
    R["R05"] = ("PASS", rebound("r05_real", lambda: fx().r05_stub, {"G": {T("r05_real"): 1}}))
    R["R06"] = ("PASS", rebound("r06_real",
                                lambda: functools.wraps(fx().r06_real)(sys.modules[OTHER].make_fake()),
                                {"G": {T("r06_real"): 1}}))
    R["R07"] = ("PASS", one([T("cached_r07")], lambda: fx().cached_r07.__wrapped__(1),
                            {"G": {T("cached_r07"): 1}}))

    def r08(tmp):
        exp = tmp.exp(AB([T("f")], [T("g")]))
        was = gc.isenabled()
        gc.disable()
        try:
            def b():
                fx().g()
                fx().Cyc(fx().f)                       # B's object: cyclic garbage from here on

            def h(cov):
                cov.run("B", b)
                cov.run("A", gc.collect)               # collected on A's stack
            return _expect(exp, _trace(exp, h), {"A": {T("f"): 1}})
        finally:
            if was:
                gc.enable()
    R["R08"] = ("A PASS", r08)

    def r09(tmp):
        exp = tmp.exp(AB([T("f")], [T("g")]))
        box = {}

        def h(cov):
            cov.run("B", lambda: (fx().g(), box.__setitem__("gen", fx().gen_r09())))
            cov.run("A", lambda: next(box["gen"]))     # created in B, resumed in A
            box["gen"].close()
        return _expect(exp, _trace(exp, h), {"A": {T("f"): 1}})
    R["R09"] = ("credited to A", r09)

    def r10(tmp):
        exp = tmp.exp(AB([T("f")], [T("g")]))
        s = sched.scheduler(time.monotonic, time.sleep)

        def h(cov):
            cov.run("B", lambda: (fx().g(), s.enter(0, 1, fx().f)))
            cov.run("A", s.run)                        # A's scheduler runs B's job
        return _expect(exp, _trace(exp, h), {"A": {T("f"): 1}})
    R["R10"] = ("A PASS", r10)

    def r11(tmp):
        import numpy as np
        run_p1 = sys.modules["run_p1"]
        committed = json.loads((HERE / "p1_result.json").read_text(encoding="utf-8"))
        gates = json.loads(_select_gates_block((HERE / P1_PREREG).read_text(encoding="utf-8")))
        gates["gates"]["G1_historical_in_sample"]["exercises"] = ["styxx.power:order_stat_bar"]
        exp = tmp.exp(json.dumps(gates))
        with coverage_trace(exp) as cov:
            cov.run("G1_historical_in_sample", run_p1.historical,
                    np.random.default_rng(run_p1.SEED))
        rec = cov.record()
        res = dict(committed)
        res["coverage_trace"] = rec
        v = exp.score(res)
        u = _union(rec, "G1_historical_in_sample")
        need(u == {"styxx.power:order_stat_bar": 1}, f"G1 companion union {u}")
        return {"verdict": v.verdict, "union": u}
    R["R11"] = ("order_stat_bar:1", r11)
    return R


# -- the case runner (A1, A8) --------------------------------------------------------------------

def _registries():
    def ids(d):
        return {k: v for k, v in dict(d).items()}
    return {"_MINTED": ids(P._MINTED), "_BY_FN": ids(P._BY_FN), "_ANCHORS": ids(P._ANCHORS),
            "_THREADS": {k: (tuple(v) if isinstance(v, (list, tuple)) else repr(v))
                         for k, v in dict(P._THREADS).items()},
            "_ACTIVE": P._ACTIVE}


def _registries_equal(before) -> bool:
    now = _registries()
    return (all(set(before[k]) == set(now[k]) and all(before[k][x] is now[k][x] for x in before[k])
                for k in ("_MINTED", "_BY_FN", "_ANCHORS"))
            and before["_THREADS"] == now["_THREADS"] and before["_ACTIVE"] == now["_ACTIVE"])


def _snapshot():
    return {"reg": _registries(), "prof": sys.getprofile(),
            "tprof": threading.getprofile() if hasattr(threading, "getprofile") else None,
            "not_original": {id(fn) for fn, code in FIXTURE_CODES if fn.__code__ is not code}}


def _leftover(before) -> str | None:
    after = _snapshot()
    out = []
    for k in ("_MINTED", "_BY_FN", "_ANCHORS"):
        a, b = before["reg"][k], after["reg"][k]
        if set(a) != set(b) or any(a[x] is not b[x] for x in a):
            out.append(f"{k} {len(a)}->{len(b)} entries")
    if before["reg"]["_THREADS"] != after["reg"]["_THREADS"]:
        out.append(f"_THREADS {before['reg']['_THREADS']} -> {after['reg']['_THREADS']}")
    if before["reg"]["_ACTIVE"] != after["reg"]["_ACTIVE"]:
        out.append(f"_ACTIVE {before['reg']['_ACTIVE']} -> {after['reg']['_ACTIVE']}")
    if after["prof"] is not before["prof"]:
        out.append(f"sys.getprofile() on the case thread {before['prof']!r} -> {after['prof']!r}")
    if after["tprof"] is not before["tprof"]:
        out.append(f"threading.getprofile() {before['tprof']!r} -> {after['tprof']!r}")
    # A1: every fixture __code__ must be its ORIGINAL; a leak fails every later case too, so the
    # detail says which were changed during THIS case (the first leaking case) and which already were
    swapped = [(fn, fn.__code__ is not code and id(fn) not in before["not_original"])
               for fn, code in FIXTURE_CODES if fn.__code__ is not code]
    if swapped:
        now = [getattr(fn, "__qualname__", "?") for fn, new in swapped if new]
        old = [getattr(fn, "__qualname__", "?") for fn, new in swapped if not new]
        out.append(f"fixture __code__ not original: changed during this case {now[:6]}"
                   + (f"; already before it {old[:6]}" if old else ""))
    rebound = [f"{m.__name__}.{k}" for m, k, v in FIXTURE_BINDINGS if vars(m).get(k) is not v]
    if rebound:
        out.append(f"fixture bindings changed: {rebound[:6]}")
    return "; ".join(out) or None


def _describe(val) -> str:
    if hasattr(val, "verdict") and hasattr(val, "coverage"):
        return f"scored {val.verdict} coverage={val.coverage}"
    try:
        return json.dumps(val, default=str)[:600]
    except Exception:                                                # noqa: BLE001
        return repr(val)[:600]


def run_case(cov, section, case_id, fn, base: Path) -> dict:
    """One case in its own thread: target = cov.run(<gate section>, case), 30 s watchdog."""
    box = {}

    def case():
        tmp = _Tmp(base)
        before = _snapshot()
        t0 = time.monotonic()
        try:
            val = fn(tmp)
            box["outcome"], box["detail"] = "returned", _describe(val)
        except (GateSpecError, _Reported) as e:
            box["outcome"], box["detail"] = "refused", str(e)
        except CaseFailure as e:
            box["outcome"], box["detail"] = "assert", str(e)
        except BaseException as e:                                  # noqa: BLE001
            tb = traceback.extract_tb(e.__traceback__)[-3:]
            where = " <- ".join(f"{Path(fr.filename).name}:{fr.lineno}" for fr in reversed(tb))
            box["outcome"], box["detail"] = "crash", f"{type(e).__name__}: {e} [{where}]"
        finally:
            box["seconds"] = round(time.monotonic() - t0, 3)
            tmp.close()
        box["leftover"] = _leftover(before)

    def target():
        try:
            cov.run(section, case)
        except BaseException as e:                                  # noqa: BLE001
            box.setdefault("outcome", "crash")
            box["detail"] = (box.get("detail") or "") + f" | outer cov.run raised {e!r}"
    th = threading.Thread(target=target, name=f"case-{case_id}", daemon=True)
    th.start()
    th.join(WATCHDOG_S)
    if th.is_alive():
        return {"outcome": "watchdog", "detail": f"still running after {WATCHDOG_S}s",
                "leftover": "case thread still running", "seconds": WATCHDOG_S}
    return {"outcome": box.get("outcome", "crash"), "detail": str(box.get("detail"))[:600],
            "leftover": box.get("leftover"), "seconds": box.get("seconds")}


# -- hazard sweeps H1-H3 (+H4 reported) ----------------------------------------------------------

def _hazard_clean(fx) -> str | None:
    bad = []
    if sys.getprofile() is not None:
        bad.append(f"profiler {sys.getprofile()!r}")
    for k in ("_MINTED", "_BY_FN", "_ANCHORS", "_THREADS"):
        if getattr(P, k):
            bad.append(f"{k} not empty")
    if P._ACTIVE != 0:
        bad.append(f"_ACTIVE {P._ACTIVE}")
    if fx.f.__code__ is not _HAZ_CODES.get("f", fx.f.__code__):
        bad.append("f.__code__ not restored")
    return "; ".join(bad) or None


_HAZ_CODES: dict = {}


H_SIGNAL_MAX_S = 10.0     # a signal trial's loop runs until the handler has run, at most this long


def _spin(fx, fired):
    """The tight traced loop of H2/H3 (hits and non-hits), until the signal handler has run.

    It is its own frame on purpose: on 3.12+ a loop's JUMP_BACKWARD lies OUTSIDE the exception-table
    range of a try around the loop (measured: 5 of 800 loaded 3.13 trials had the Timeout escape the
    try from the back edge), so a handler run there would skip an `except` in the same frame. Raised
    anywhere in here, the exception leaves through the caller's CALL of _spin, which its try covers."""
    end = time.monotonic() + H_SIGNAL_MAX_S
    while not fired[0] and time.monotonic() < end:
        fx.f()
        fx.g()


def _h2_trials(exp, fx, n=20) -> dict:
    """SIGALRM Timeout(Exception) in a tight traced loop after a target call (main thread). The
    loop runs until the handler has RUN (bounded), in its own frame (see _spin), so the Timeout is
    raised inside the try however late a loaded machine delivers the signal: a Timeout that does
    not reach the `except` was swallowed, not late."""
    class Timeout(Exception):
        pass
    fired = [False]

    def handler(signum, frame):
        fired[0] = True
        raise Timeout()
    _HAZ_CODES["f"] = fx.f.__code__
    old = signal.signal(signal.SIGALRM, handler)
    trials = []
    try:
        for _ in range(n):
            st = {"propagated": False}
            fired[0] = False

            def body():
                fx.f()
                try:
                    signal.setitimer(signal.ITIMER_REAL, 0.01)
                    _spin(fx, fired)
                except Timeout:
                    st["propagated"] = True
            try:
                with coverage_trace(exp) as cov:
                    cov.run("G", body)
                rec = cov.record()
                try:
                    v = exp.score(_res(rec))
                    st["verdict"] = v.verdict
                except GateSpecError as e:
                    st["verdict"] = str(e)[:80]
            except Timeout:
                st["verdict"] = "Timeout escaped the section"
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            st["handler_ran"] = fired[0]
            st["leftover"] = _hazard_clean(fx)
            st["ok"] = st["propagated"] and st.get("verdict") == "PASS" and not st["leftover"]
            trials.append(st)
    finally:
        signal.signal(signal.SIGALRM, old)
    return {"n": n, "propagated": sum(t["propagated"] for t in trials),
            "passed": sum(t.get("verdict") == "PASS" for t in trials),
            "handler_ran": sum(t["handler_ran"] for t in trials),
            "ok": sum(t["ok"] for t in trials),
            "leftovers": [t["leftover"] for t in trials if t["leftover"]][:3]}


def _h3_trials(exp, fx, n=5) -> dict:
    """KeyboardInterrupt raised from a signal inside a traced section (main thread); the loop runs
    until the handler has run (bounded), as in H2."""
    fired = [False]

    def handler(signum, frame):
        fired[0] = True
        raise KeyboardInterrupt
    _HAZ_CODES["f"] = fx.f.__code__
    old = signal.signal(signal.SIGALRM, handler)
    trials = []
    try:
        for _ in range(n):
            st = {"propagated": False}
            fired[0] = False

            def body():
                fx.f()
                signal.setitimer(signal.ITIMER_REAL, 0.01)
                _spin(fx, fired)
            try:
                with coverage_trace(exp) as cov:
                    cov.run("G", body)
            except KeyboardInterrupt:
                st["propagated"] = True
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            st["leftover"] = _hazard_clean(fx)
            st["ok"] = st["propagated"] and not st["leftover"]
            trials.append(st)
    finally:
        signal.signal(signal.SIGALRM, old)
    return {"n": n, "propagated": sum(t["propagated"] for t in trials),
            "ok": sum(t["ok"] for t in trials),
            "leftovers": [t["leftover"] for t in trials if t["leftover"]][:3]}


H1_SITES = ("open", "close", "record", "hook", "exit")
# Each site x gen-0 threshold is swept twice: plainly, and inside an enclosing opening of a second
# tracer of the same experiment (the shape every in-process case of this exam has), which keeps
# the hook installed and the target minted while _close and __exit__ run. On 3.12+ the collector
# runs only at eval-breaker checkpoints, and the plain sweep's collections land inside the hook
# itself (where profiling is off); the carried sweep reaches the machinery on 3.10-3.13 alike.
H1_POINTS = [(carried, s, k) for carried in (False, True) for s in H1_SITES for k in range(1, 41)]
H1_MACHINERY = ("_open", "_close", "__enter__", "__exit__")   # the spec's _LOCK holders
H1_MUTANT_HOOK = "_h1_mutant_hook"                            # the name faulthandler must show


def _h1_child(exp, fx, start: int):
    """Runs on the subprocess's main thread; prints H1_DONE <i> after each point. A hang is
    ended by faulthandler after 10 s (exit code 1); the parent reads how far it got."""
    import faulthandler

    class Res:
        def __init__(self):
            self.me = self

        def __del__(self):
            fx.f()                                     # a finalizer that calls a declared target

    def litter(k):
        gc.collect()
        gc.disable()
        for _ in range(5):
            Res()
        gc.set_threshold(k)
        gc.enable()

    def point(site, k):
        with coverage_trace(exp) as cov:
            if site == "open":
                litter(k)
                cov.run("G", fx.f)
            elif site == "close":
                cov.run("G", lambda: (fx.f(), litter(k)))
            elif site == "hook":
                cov.run("G", lambda: (litter(k), fx.f()))
            else:
                cov.run("G", fx.f)
                if site == "exit":
                    litter(k)
        if site == "record":
            litter(k)
        cov.record()
    thresholds = gc.get_threshold()
    for i in range(start, len(H1_POINTS)):
        carried, site, k = H1_POINTS[i]
        faulthandler.dump_traceback_later(10, exit=True)
        try:
            if carried:
                with coverage_trace(exp) as carrier:
                    carrier.run("G", point, site, k)
            else:
                point(site, k)
        finally:
            gc.set_threshold(*thresholds)
            gc.enable()
            faulthandler.cancel_dump_traceback_later()
        print(f"H1_DONE {i}", flush=True)


def _install_mutant(kind, mode):
    """The detection mutants (and H1's control), in the child only.

    H2 mutant: the module global _hook wrapped in `except Exception`.

    H1 (deviation from A6's wording, which is an EQUIVALENT mutant: a fresh lock taken only by the
    hook never deadlocks, because CPython never re-enters a profile function, so a finalizer run
    inside the hook cannot reach it again). What the spec guards against is the hook taking a lock
    the MACHINERY holds while it allocates. The mutant owns a non-reentrant Lock M and wraps
    _CoverageTracer._open/_close/__enter__/__exit__ at class level so a thread holds M while any of
    them is on its stack (a per-thread depth counter: acquire on 0->1, release on 1->0); the hook
    wrapper takes M on hits (calls of minted code). This is independent of how the implementation
    names, stores or nests its own lock. The CONTROL installs the same wrappers with the hook
    untouched; detection counts only if the control never hangs and the mutant's hang shows the
    mutant hook as the innermost frame of faulthandler's dump (see _h1_sweep).
    """
    orig = P._hook
    if kind == "H2":
        def mutant(frame, event, arg):
            try:
                return orig(frame, event, arg)
            except Exception:                                       # noqa: BLE001
                pass
        P._hook = mutant
        return
    M, depth = threading.Lock(), threading.local()

    def hold(meth):
        def w(*a, **k):
            d = getattr(depth, "n", 0)
            if d == 0:
                M.acquire()
            depth.n = d + 1
            try:
                return meth(*a, **k)
            finally:
                depth.n -= 1
                if depth.n == 0:
                    M.release()
        return w
    for name in H1_MACHINERY:
        setattr(P._CoverageTracer, name, hold(getattr(P._CoverageTracer, name)))
    if mode != "mutant":
        return

    def _h1_mutant_hook(frame, event, arg):
        if event == "call" and P._MINTED.get(id(frame.f_code)) is not None:
            with M:
                return orig(frame, event, arg)
        return orig(frame, event, arg)
    P._hook = _h1_mutant_hook


def hazard_child(argv):
    kind, mode, prereg, fixdir, start = argv[0], argv[1], argv[2], argv[3], int(argv[4])
    sys.path.insert(0, fixdir)
    fx = importlib.import_module(FX)
    exp = Experiment(prereg)
    if mode in ("mutant", "control"):
        _install_mutant(kind, mode)
    if kind == "H1":
        _h1_child(exp, fx, start)
        out = {"done": True}
    else:
        out = _h2_trials(exp, fx)
    print("HAZARD_RESULT " + json.dumps(out), flush=True)
    os._exit(0)


def _child(kind, mode, prereg, fixdir, start=0, timeout=120):
    cmd = [sys.executable, str(Path(__file__).resolve()), "--hazard-child", kind, mode,
           str(prereg), str(fixdir), str(start)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        return p.returncode, p.stdout, p.stderr, False
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        return None, out, err, True


_FRAME_RE = re.compile(r'^\s*File "(?P<file>[^"]*)", line (?P<line>\d+) in (?P<name>\S+)', re.M)


def _dump_head(err: str) -> list:
    """The first (innermost) frames of faulthandler's dump: "file:line in name" strings."""
    i = err.find("Timeout (")
    return [f"{Path(m['file']).name}:{m['line']} in {m['name']}"
            for m in _FRAME_RE.finditer(err[i:] if i >= 0 else err)][:8]


def _h1_sweep(mode, prereg, fixdir, stop_after) -> dict:
    """Run the 400 sweep points in child processes; a point whose child is killed by its 10 s
    faulthandler watchdog (or the parent's hard timeout) is a hang; the sweep resumes after it.
    Each hang keeps the head (innermost frames) of the dump, which says WHERE it hung."""
    hangs, errors, start, runs = [], [], 0, 0
    while start < len(H1_POINTS) and len(hangs) + len(errors) < stop_after and runs < 60:
        runs += 1
        code, out, err, timed_out = _child("H1", mode, prereg, fixdir, start)
        done = [int(x.split()[1]) for x in out.splitlines() if x.startswith("H1_DONE ")]
        last = max(done) if done else start - 1
        if code == 0 and "HAZARD_RESULT" in out:
            break
        at = last + 1
        head = _dump_head(err)
        row = {"point": list(H1_POINTS[at]) if at < len(H1_POINTS) else None, "exit": code,
               "timed_out": timed_out, "innermost": head[0] if head else None,
               "stack_head": head, "stderr_tail": err.strip()[-200:]}
        (hangs if timed_out or "Timeout (" in err else errors).append(row)
        start = at + 1
    sites = {}
    for h in hangs:
        if h["point"]:
            key = f"{'carried ' if h['point'][0] else ''}{h['point'][1]}"
            sites[key] = sites.get(key, 0) + 1
    return {"hangs": len(hangs), "errors": len(errors), "hang_points": hangs,
            "error_points": errors, "hangs_per_site": sites, "child_runs": runs,
            "points": len(H1_POINTS)}


def hazards(fixdir: Path, base: Path) -> dict:
    fx = _fx()
    out = {}
    tmp = _Tmp(base)
    exp = tmp.exp(G1(T("f")))
    t0 = time.monotonic()
    out["H1"] = _h1_sweep("real", exp.prereg, fixdir, stop_after=5)
    out["H1_control"] = _h1_sweep("control", exp.prereg, fixdir, stop_after=1)
    out["H1_mutant"] = _h1_sweep("mutant", exp.prereg, fixdir, stop_after=1)
    in_hook = [h for h in out["H1_mutant"]["hang_points"]
               if (h["innermost"] or "").endswith(f" in {H1_MUTANT_HOOK}")]
    out["H1_mutant_detection"] = {
        "control_clean": out["H1_control"]["hangs"] == 0 and out["H1_control"]["errors"] == 0,
        "mutant_hangs_in_the_mutant_hook": len(in_hook)}
    import faulthandler
    faulthandler.dump_traceback_later(300, exit=True)  # in-process signal cases: die, never hang
    try:
        out["H2"] = _h2_trials(exp, fx)
        out["H3"] = _h3_trials(exp, fx)
    finally:
        faulthandler.cancel_dump_traceback_later()
    code, stdout, err, timed_out = _child("H2", "mutant", exp.prereg, fixdir, timeout=300)
    line = [x for x in stdout.splitlines() if x.startswith("HAZARD_RESULT ")]
    out["H2_mutant"] = (json.loads(line[-1].split(" ", 1)[1]) if line else
                        {"error": f"exit {code} timed_out={timed_out}: {err.strip()[-300:]}"})
    out["seconds"] = round(time.monotonic() - t0, 2)
    tmp.close()
    return out


def h4_reported(base: Path) -> dict:
    """H4 (reported, not gated): one open+close on a 1M-object heap; gc runs during resolution;
    and whether the exit ran the gated gc.get_referrers scan with no live clone (it should not)."""
    tmp = _Tmp(base)
    exp = tmp.exp(G1(T("f")))
    heap = [[] for _ in range(1_000_000)]
    events = []
    calls = {"getrefcount": 0, "get_referrers": 0}
    run_ms, n_run = float("nan"), 0

    def cb(phase, info):
        if phase == "start":
            events.append(info.get("generation"))

    def count(frame, event, arg):                  # c_calls by IDENTITY of the builtin
        if event == "c_call":
            if arg is _GETREFCOUNT:
                calls["getrefcount"] += 1
            elif arg is _GET_REFERRERS:
                calls["get_referrers"] += 1
    was = gc.isenabled()
    gc.disable()                                   # any collection seen now is an explicit one
    gc.callbacks.append(cb)
    try:
        cov = coverage_trace(exp)
        cov.__enter__()
        n_enter = len(events)
        try:
            t0 = time.perf_counter()
            cov.run("G", _fx().f)
            run_ms = (time.perf_counter() - t0) * 1000
            n_run = len(events) - n_enter
        finally:
            prev = sys.getprofile()                # None: the last close removed the hook
            sys.setprofile(count)
            try:
                cov.__exit__(None, None, None)
            finally:
                sys.setprofile(None)
            if prev is not None and prev is not P._hook:
                sys.setprofile(prev)
    finally:
        gc.callbacks.remove(cb)
        if was:
            gc.enable()
    del heap
    tmp.close()
    return {"one_open_run_close_ms_on_1M_heap": round(run_ms, 3), "under_1ms": run_ms < 1.0,
            "gc_collections_during_enter": n_enter, "gc_collections_during_run": n_run,
            "gc_collections_during_exit": len(events) - n_enter - n_run,
            "exit_getrefcount_calls": calls["getrefcount"],
            "exit_gc_get_referrers_calls_with_no_live_clone": calls["get_referrers"]}


# -- corpus differential (A2) --------------------------------------------------------------------

def _git(args, cwd=None, data=None) -> tuple:
    p = subprocess.run(["git", *args], cwd=str(cwd or ROOT), input=data, capture_output=True,
                       timeout=300)
    return p.returncode, p.stdout


def _head_results() -> dict:
    """{repo path: bytes} for every papers/*/*_result.json TRACKED AT HEAD, content as committed."""
    rc, out = _git(["ls-tree", "-r", "-z", "--name-only", "HEAD", "--", "papers"])
    names = [n for n in out.decode("utf-8", "replace").split("\0")
             if re.fullmatch(r"papers/[^/]+/[^/]*_result\.json", n)] if rc == 0 else []
    rc, blob = _git(["cat-file", "--batch"], data="".join(f"HEAD:{n}\n" for n in names).encode())
    got, i = {}, 0
    for n in names if rc == 0 else []:
        j = blob.index(b"\n", i)
        head = blob[i:j].split()
        if len(head) == 3 and head[1] == b"blob":
            size = int(head[2])
            got[n] = blob[j + 1:j + 1 + size]
            i = j + 1 + size + 1
        else:
            i = j + 1                                # "<name> missing"
    return got


def differential(attempt_b) -> dict:
    """run_protocol_v5.differential()'s semantics (pinned v4 vs this implementation, outcomes
    compared by its _outcome), over a PINNED population, plus the frozen nested-dict rule.

    Population: every papers/*/*_result.json tracked at HEAD (read as committed, not from the
    working tree) whose prereg exists, minus the v5 exams' own preregs (v5e's and its aux's
    included), restricted to exactly the result files of the frozen census
    (corpus_provenance_rescore.json "census_rows"): n_results_v5_scored is computed over exactly
    those rows. A result committed later is reported, not scored. Nested-dict rule: for exactly the
    results the census lists as "reproduced", both versions score result["metrics"]. In a scored run,
    if a census row is missing at HEAD or the rule was not applied to exactly the reproduced set,
    the frozen population is not what was measured and n_results_v5_scored is 0 (G4 refuses)."""
    v4 = attempt_b._pinned_v4()
    cpr = json.loads((HERE / "corpus_provenance_rescore.json").read_text(encoding="utf-8"))
    nested = set(cpr["reproduced"])
    census = [r["result"] for r in cpr["census_rows"]]
    rows = {}
    for path, raw in _head_results().items():
        try:
            d = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(d, dict) or not isinstance(d.get("prereg"), str):
            continue
        res_file = ROOT / path
        prereg_path = res_file.parent / d["prereg"]
        if not prereg_path.is_file() or prereg_path.name in V5_OWN_PREREGS:
            continue
        rows[f"{res_file.parent.name}/{res_file.name}"] = (prereg_path, d)
    population = [n for n in census if n in rows]
    missing = [n for n in census if n not in rows]
    not_in_census = sorted(set(rows) - set(census))
    if SMOKE:
        population = population[:5]
    disagree, vs_committed, n_raised, applied = [], [], 0, []
    for name in population:
        prereg_path, d = rows[name]
        scored = d
        if name in nested:
            scored = d.get("metrics")
            applied.append(name)
        if isinstance(scored, dict):
            o4 = attempt_b._outcome(v4.Experiment, prereg_path, scored)
            o5 = attempt_b._outcome(Experiment, prereg_path, scored)
        else:
            o4 = o5 = "RAISED:no metrics sub-dict"
        n_raised += o5.startswith("RAISED:")
        if o4 != o5:
            disagree.append({"result": name, "v4": o4[:300], "v5": o5[:300]})
        committed = d.get("verdict")
        if isinstance(committed, str) and o5 != committed:
            vs_committed.append({"result": name, "committed": committed[:200], "v5": o5[:200]})
    rule_exact = set(applied) == nested
    complete = not missing and rule_exact
    computed = len(population) - n_raised
    problem = None
    if not SMOKE and not complete:
        problem = (f"frozen population not reproduced: census rows missing at HEAD {missing[:10]}; "
                   f"nested rule applied to {sorted(applied)}, frozen reproduced {sorted(nested)}")
    return {"n_pairable_results": len(population), "n_v5_raised_on": n_raised,
            "n_v4_v5_outcome_disagreements": len(disagree), "v4_v5_disagreements": disagree,
            "n_results_v5_scored": 0 if problem else computed,
            "n_results_v5_scored_computed": computed,
            "nested_metrics_rule_applied_to": applied,
            "nested_metrics_rule_exact": rule_exact,
            "population": {"rule": "committed at HEAD, prereg exists, not a v5 exam's own prereg, "
                                   "and a row of the frozen census",
                           "n_census_rows": len(census), "n_pairable_at_head": len(rows),
                           "census_rows_missing_at_head": missing,
                           "at_head_not_in_census_not_scored": not_in_census,
                           "complete": complete, "problem": problem},
            "ungated_n_v5_differs_from_committed_verdict": len(vs_committed),
            "ungated_v5_differs_from_committed_verdict": vs_committed,
            "v4_pin": {"commit": attempt_b.V4_COMMIT, "sha256": attempt_b.V4_SHA}}


# -- frozen dependencies (A3) and the mutation gate (A5) ----------------------------------------

def frozen_check() -> dict:
    """A3 and G_EXAM_FROZEN. The FROZEN_<NAME>_SHA256 lines are read from the prereg AS FIRST
    COMMITTED (the commit Experiment treats as the freeze), the working-tree prereg must be
    byte-identical to it, and that commit must precede the first commit whose styxx/protocol.py
    carries the v5e tracer id (the implementation), if one exists yet."""
    prereg = HERE / PREREG
    rel = prereg.relative_to(ROOT).as_posix()
    rc, out = _git(["log", "--diff-filter=A", "--format=%H", "--follow", "--", PREREG], cwd=HERE)
    hashes = out.decode().split() if rc == 0 else []
    first = hashes[-1] if hashes else None
    committed = None
    if first:
        rc, blob = _git(["show", f"{first}:{rel}"])
        committed = blob if rc == 0 else None
    wt = prereg.read_bytes() if prereg.is_file() else None
    unchanged = committed is not None and wt == committed
    text = committed.decode("utf-8", "replace") if committed else ""
    rc, out = _git(["log", "--reverse", "--format=%H", "-S", TRACER_ID, "--", "styxx/protocol.py"])
    impl_first = (out.decode().split() or [None])[0] if rc == 0 else None
    if first and impl_first:
        before_impl = (impl_first != first
                       and _git(["merge-base", "--is-ancestor", first, impl_first])[0] == 0)
    else:
        before_impl = first is not None
    rows, ok = {}, unchanged and before_impl
    for name, path in FROZEN_FILES.items():
        got = _sha(path) if path.is_file() else None
        found = sorted(set(re.findall(rf"FROZEN_{name}_SHA256: ([0-9a-f]{{64}})", text)))
        want = found[0] if len(found) == 1 else None
        match = got is not None and want == got
        ok = ok and match
        rows[name] = {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                      "sha256": got, "expected": want, "match": match,
                      "note": None if len(found) == 1 else f"{len(found)} FROZEN_{name}_SHA256 lines"}
    return {"exam_frozen": 1.0 if ok else 0.0, "files": rows,
            "prereg_first_commit": first, "prereg_unchanged_since_first_commit": unchanged,
            "first_implementation_commit": impl_first,
            "prereg_committed_before_implementation": before_impl}


def mutation_gate_metrics(own_sha, impl_sha, frozen) -> dict:
    p = HERE / "run_protocol_v5e_mutation_gate.json"
    out = {"path": str(p.relative_to(ROOT)), "mutation_frac_detected": 0.0,
           "mutation_hygiene_violations": None}
    try:
        mg = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        out["problem"] = f"unreadable: {e}"
        return out
    want_gen = frozen["files"]["MUTATION_GATE"]["expected"]
    checks = {"impl_sha256": mg.get("impl_sha256") == impl_sha,
              "runner_sha256": mg.get("runner_sha256") == own_sha,
              "generator_sha256": want_gen is not None and mg.get("generator_sha256") == want_gen}
    out["checks"] = checks
    out["baseline_clean"] = mg.get("baseline_clean")
    if not all(checks.values()):
        out["problem"] = f"receipt does not match this run: {checks}"
        return out
    frac = mg.get("frac_refusal_mutants_detected")
    out["mutation_frac_detected"] = (float(frac) if mg.get("baseline_clean") is True
                                     and isinstance(frac, (int, float)) else 0.0)
    hyg = mg.get("n_hygiene_violations")
    out["mutation_hygiene_violations"] = hyg if isinstance(hyg, int) else None
    out["survivors"] = [f"line {s.get('line')}: {s.get('statement')}" for s in
                        mg.get("survivors", [])][:20]
    return out


# -- main -----------------------------------------------------------------------------------------

API = ["coverage_trace", "_CoverageTracer", "_resolve_target", "_hook", "_LOCK", "_MINTED",
       "_BY_FN", "_ANCHORS", "_THREADS", "_ACTIVE", "_STOP", "_TRACER_ID"]


def _section_for(self_exp, metric) -> str:
    gates = [g for g, m in self_exp.metric_paths.items() if m == metric]
    if len(gates) != 1:
        raise SystemExit(f"the prereg must have exactly one gate reading {metric!r}; found {gates}")
    g = gates[0]
    return self_exp.coverage[g]["section"] if g in self_exp.coverage else g


def main() -> int:
    t_start = time.monotonic()
    missing = [a for a in API if not hasattr(P, a)]
    if missing or getattr(P, "_TRACER_ID", None) != TRACER_ID:
        print(f"styxx.protocol lacks the v5e API: missing {missing}, "
              f"_TRACER_ID={getattr(P, '_TRACER_ID', None)!r}", file=sys.stderr)
        return 2
    impl_path = Path(P.__file__).resolve()
    if IMPORT_ROOT and not impl_path.is_relative_to(Path(IMPORT_ROOT).resolve()):
        print(f"STYXX_V5_IMPORT_ROOT={IMPORT_ROOT} but styxx.protocol came from {impl_path}",
              file=sys.stderr)
        return 2
    own_sha, impl_sha = _sha(__file__), _sha(impl_path)
    frozen = frozen_check()
    mode = ("scored" if not SMOKE else "smoke-mutation-mode" if MUTATION
            else "smoke-full-battery" if FULL else "smoke")

    base = Path(tempfile.mkdtemp(prefix="v5e_exam_"))
    fixdir = Path(tempfile.mkdtemp(prefix="v5efix_"))
    _load_fixtures(fixdir)
    run_p1 = _load_p1()                   # before the self-trace: G2 declares run_p1:degenerate

    self_exp = Experiment(HERE / PREREG, require_power_basis=True, require_nonvacuous_gates=True)
    sec = {m: _section_for(self_exp, m) for m in (M_VIOL, M_VALID, M_RETRO, M_RESID)}

    viol, vals, resid = violations(), valids(), residuals()
    skipped = sorted({"X81", "V33", "X82"} - set(viol) - set(vals))
    if MUTATION:
        skipped += ["V32 (mutation mode)", "H1-H3 (mutation mode)"]
    if SMOKE and not FULL:
        viol = dict(list(viol.items())[:6])
        vals = dict(list(vals.items())[:4])
        resid = dict(list(resid.items())[:2])

    # hazard sweeps and signal cases: before the self-trace (H1 and mutants in subprocesses)
    haz = hazards(fixdir, base) if FULL and not MUTATION else None
    h4 = h4_reported(base) if FULL else None

    pre_codes = [(fn, fn.__code__) for fn in (
        P._CoverageTracer._open, P._CoverageTracer.__exit__, P._CoverageTracer.record,
        P._CoverageTracer.run, P._CoverageTracer._close, P._CoverageTracer.__enter__,
        P.Experiment._check_coverage, P._resolve_target, run_p1.degenerate)]
    vres, gres, rres, runs_per_section = {}, {}, {}, {}
    retro = None
    t_battery = time.monotonic()
    watchdogs = []

    def run(section, case_id, fn):
        runs_per_section[section] = runs_per_section.get(section, 0) + 1
        if len(watchdogs) >= ABORT_AFTER_WATCHDOGS:        # the exam never hangs: see run_case
            return {"outcome": "aborted", "detail": f"not run: {len(watchdogs)} watchdog "
                    f"expiries ({watchdogs}) before it", "leftover": None, "seconds": 0.0}
        r = run_case(cov, section, case_id, fn, base)
        if r["outcome"] == "watchdog":
            watchdogs.append(case_id)
        return r
    cov = coverage_trace(self_exp)
    cov.__enter__()
    try:
        for k, (code, fn) in viol.items():
            r = run(sec[M_VIOL], k, fn)
            ok = (r["outcome"] == "refused" and r["detail"].startswith(f"[V5:{code}]")
                  and not r["leftover"])
            vres[k] = {"expected": code, "outcome": r["outcome"], "ok": ok, "detail": r["detail"],
                       "leftover": r["leftover"], "seconds": r["seconds"]}
        r = run(sec[M_RETRO], "X118", x118_p1_retro)
        ok = (r["outcome"] == "refused" and r["detail"].startswith("[V5:NOT_EXERCISED]")
              and not r["leftover"])
        retro = {"expected": "NOT_EXERCISED", "outcome": r["outcome"], "ok": ok,
                 "detail": r["detail"], "leftover": r["leftover"], "seconds": r["seconds"]}
        vres["X118"] = retro
        for k, (want, fn) in vals.items():
            r = run(sec[M_VALID], k, fn)
            gres[k] = {"expected": want, "outcome": r["outcome"],
                       "ok": r["outcome"] == "returned" and not r["leftover"],
                       "detail": r["detail"], "leftover": r["leftover"], "seconds": r["seconds"]}
        for k, (want, fn) in resid.items():
            r = run(sec[M_RESID], k, fn)
            rres[k] = {"expected": want, "outcome": r["outcome"],
                       "ok": r["outcome"] == "returned" and not r["leftover"],
                       "detail": r["detail"], "leftover": r["leftover"], "seconds": r["seconds"]}
    finally:
        if watchdogs:                  # a hung case may hold the tracer's lock: bound the exit
            ex = _T(cov.__exit__, None, None, None)
            ex.start()
            ex.join(WATCHDOG_S)
        else:
            cov.__exit__(None, None, None)
    battery_s = round(time.monotonic() - t_battery, 2)
    try:
        self_trace = cov.record()
    except GateSpecError as e:
        self_trace = {"record_refused": str(e)}
    except Exception as e:                                          # noqa: BLE001
        self_trace = {"record_refused": f"{type(e).__name__}: {e}"}

    # V34 part 2: the outer self-trace itself, and what it left behind
    if "V34" in gres:
        probs = []
        if not isinstance(self_trace, dict) or "sections" not in self_trace:
            probs.append(f"no self-trace: {self_trace}")
        else:
            if self_trace.get("problems"):
                probs.append(f"self-trace problems {self_trace['problems'][:3]}")
            for g, c in self_exp.coverage.items():
                u = _union(self_trace, c["section"])
                lack = [t for t in c["exercises"] if u.get(t, 0) < 1]
                if lack:
                    probs.append(f"{g}: declared machinery not exercised {lack}")
            for s, n in runs_per_section.items():
                ops = self_trace["sections"].get(s, [])
                if len(ops) != n or any(o["end"] != "returned" for o in ops):
                    probs.append(f"section {s!r}: {len(ops)} openings "
                                 f"(ends {sorted({o['end'] for o in ops})}) for {n} case runs")
        left = [k for k in ("_MINTED", "_BY_FN", "_ANCHORS", "_THREADS") if getattr(P, k)]
        if left or P._ACTIVE:
            probs.append(f"after the self-trace: {left} not empty, _ACTIVE={P._ACTIVE}")
        if sys.getprofile() is not None:
            probs.append(f"main thread profiler left: {sys.getprofile()!r}")
        stale = [getattr(fn, "__qualname__", "?") for fn, c in pre_codes if fn.__code__ is not c]
        if stale:
            probs.append(f"__code__ not restored after the self-trace: {stale}")
        v34 = gres["V34"]
        v34["outer_self_trace"] = probs or "ok"
        v34["ok"] = bool(v34["ok"] and not probs)

    import run_protocol_v5 as attempt_b       # the committed v4 pin and _outcome, reused unchanged
    diff = differential(attempt_b)
    mg = (mutation_gate_metrics(own_sha, impl_sha, frozen) if not SMOKE else
          {"mutation_frac_detected": None, "mutation_hygiene_violations": None,
           "note": "not read in a smoke run"})

    def frac(d):
        return round(sum(v["ok"] for v in d.values()) / len(d), 4) if d else 0.0
    allc = list(vres.values()) + list(gres.values()) + list(rres.values())
    res = {"prereg": PREREG, "smoke": SMOKE, "mode": mode, "python": sys.version.split()[0],
           "impl_path": str(impl_path), "impl_sha256": impl_sha, "runner_sha256": own_sha,
           "exam_frozen": frozen["exam_frozen"], "frozen_files": frozen["files"],
           "freeze": {k: v for k, v in frozen.items() if k not in ("exam_frozen", "files")},
           "gate_sections": sec,
           "violation_cases": vres, "valid_cases": gres, "residual_cases": rres,
           "version_or_mode_skipped": skipped,
           "n_violation_cases": len(vres), "n_valid_cases": len(gres),
           "n_residual_cases": len(rres),
           M_VIOL: frac(vres), M_VALID: frac(gres), M_RESID: frac(rres),
           M_RETRO: 1.0 if retro and retro["ok"] else 0.0,
           "n_crashes": sum(v["outcome"] in ("crash", "watchdog", "aborted") for v in allc),
           "n_watchdog_expiries": sum(v["outcome"] == "watchdog" for v in allc),
           "hazards": haz, "h4_reported": h4,
           "h1_hangs": (haz["H1"]["hangs"] + haz["H1"]["errors"]) if haz else None,
           "h1_mutant_detected": ((1 if haz["H1_mutant_detection"]["control_clean"]
                                   and haz["H1_mutant_detection"]["mutant_hangs_in_the_mutant_hook"]
                                   else 0) if haz else None),
           "h2_propagated": haz["H2"]["ok"] if haz else None,
           "h2_mutant_detected": ((1 if haz["H2_mutant"].get("propagated", 20) < 20 else 0)
                                  if haz else None),
           "h3_ok": haz["H3"]["ok"] if haz else None,
           **diff,
           "mutation_gate": mg,
           "mutation_frac_detected": mg["mutation_frac_detected"],
           "mutation_hygiene_violations": mg["mutation_hygiene_violations"],
           "timings": {"battery_seconds": battery_s,
                       "total_seconds": round(time.monotonic() - t_start, 2)},
           "coverage_trace": self_trace}

    try:
        res["metric_check"] = self_exp.check_metrics(res)
        bad = sorted(n for n, dd in res["metric_check"].items() if not dd["usable"])
        if bad and not SMOKE:
            raise SystemExit(f"unresolvable gate metrics or coverage: {bad}")
        v = self_exp.score(res, smoke=SMOKE)
        res["verdict"], res["gates"] = v.verdict, v.gates
        res["coverage"], res["prereg_commit"] = v.coverage, v.prereg_commit
        res["gates_sha256"] = v.gates_sha256
    except BaseException as exc:                                    # noqa: BLE001
        res["verdict"] = f"UNSCORED__{type(exc).__name__}: {exc}"
    res["timings"]["total_seconds"] = round(time.monotonic() - t_start, 2)

    out = (Path(RESULT_OUT) if RESULT_OUT else
           HERE / f"protocol_v5e_result{'_smoke' if SMOKE else ''}.json")
    out.write_text(json.dumps(res, indent=2, default=str) + "\n", encoding="utf-8")
    shutil.rmtree(base, ignore_errors=True)
    shutil.rmtree(fixdir, ignore_errors=True)

    print(f"mode {mode} | python {res['python']} | impl {impl_path}")
    print(f"exam_frozen {res['exam_frozen']} | crashes {res['n_crashes']} "
          f"(watchdog {res['n_watchdog_expiries']})")
    for label, d in (("violation", vres), ("valid", gres), ("residual", rres)):
        print(f"{label} cases ok: {sum(v['ok'] for v in d.values())} of {len(d)}")
        for k, v in d.items():
            if not v["ok"]:
                print(f"  FAILED {k}: expected {v['expected']}; {v['outcome']}: "
                      f"{v['detail'][:170]} | leftover={v['leftover']}")
    if haz:
        print(f"H1 hangs {res['h1_hangs']}, control hangs {haz['H1_control']['hangs']}, mutant "
              f"hangs {haz['H1_mutant']['hangs']} at "
              f"{[(h['point'], h['innermost']) for h in haz['H1_mutant']['hang_points']]}")
        print(f"H1 hangs {res['h1_hangs']}, mutant detected {res['h1_mutant_detected']} | "
              f"H2 ok {res['h2_propagated']}/20, mutant detected {res['h2_mutant_detected']} "
              f"({haz['H2_mutant'].get('propagated')}/20 propagated) | H3 ok {res['h3_ok']}/5")
    print(f"differential: {diff['n_pairable_results']} pairable, "
          f"{diff['n_v4_v5_outcome_disagreements']} disagreements, "
          f"v5 scored {diff['n_results_v5_scored']} (nested rule exact "
          f"{diff['nested_metrics_rule_exact']}, population {diff['population']['problem'] or 'ok'})")
    print(f"freeze: {res['freeze']}")
    print(f"timings {res['timings']}")
    print(f"VERDICT: {res['verdict']}", flush=True)
    code = 0
    if MUTATION and any(not v["ok"] for v in rres.values()):
        code = 3
    if res["n_watchdog_expiries"] or any(t.is_alive() and not t.daemon
                                         for t in threading.enumerate()
                                         if t is not threading.main_thread()):
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    return code


if __name__ == "__main__":
    if HAZARD_CHILD:
        hazard_child(sys.argv[sys.argv.index("--hazard-child") + 1:])
    sys.exit(main())
