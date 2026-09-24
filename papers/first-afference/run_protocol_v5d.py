"""Protocol v5 round-3 exam, per PREREG_protocol_v5d_repair_2026_09_24.md.

FROZEN WITH THE PREREG, BEFORE THE ROUND-3 IMPLEMENTATION (round 2's process finding: the v5c
cases were committed with the implementation, so nothing proved they were not tuned). The
prereg carries this file's sha256; G_EXAM_FROZEN refuses any other bytes.

Built on the round-2 exam (docstring below), plus every round-2 red-team case and every
surviving exam mutant turned into a case.


What changed from run_protocol_v5.py, each because round 1 of the red team showed the gap:
a violation mutant passes only by refusing with its OWN [V5:CODE] (any other refusal, a verdict,
or a crash fails it); each mutant is isolated so no other check can catch it; a valid case
passes only if the counts it names are the counts recorded and the profilers are left as found;
every round-1 red-team case is in the battery; the P1 retro must refuse for exactly the stated
reason with exactly the stated trace; and the exam's self-declared coverage names the resolver,
section entry/exit and record, not only the one-line factory.
"""
from __future__ import annotations

import asyncio
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from styxx.protocol import (Experiment, GateSpecError, _select_gates_block,  # noqa: E402
                            _thread_profile, coverage_trace)

PREREG = "PREREG_protocol_v5d_repair_2026_09_24.md"
SMOKE = "--smoke" in sys.argv

FIX = "_v5c_fix"
T, O = f"{FIX}:target", f"{FIX}:other"
FIXTURES = {
    FIX: '''
import dataclasses
import functools


def target(): return 1
def other(): return 2
def helper(): return target()


def _deco(f):
    @functools.wraps(f)
    def w(*a, **k): return f(*a, **k)
    return w


@_deco
def wrapped(): return 3


@_deco
def wrapped_sibling(): return 33


def _nowraps(f):
    def inner(*a, **k): return f(*a, **k)
    return inner


@_nowraps
def entry_a(): return 5


@_nowraps
def entry_b(): return 6


def _make(k):
    def check(x): return x > k
    return check


check_low, check_high = _make(1), _make(2)


class K:
    def meth(self): return 4

    @staticmethod
    def stat(): return 5

    @classmethod
    def cm(cls): return 7


class Base:
    def fit(self): return 8


class Sub(Base):
    pass


class Other(Base):
    pass


@dataclasses.dataclass
class NullModel:
    k: int = 0


@dataclasses.dataclass
class AltModel:
    k: int = 0


alias = target


def _timed(fn):
    def inner(*a, **k): return fn(*a, **k)
    return inner


def _score_all_impl(): return 10


score_all = _timed(_score_all_impl)


def cheap_path(): return 11


def _run(): return 12


@functools.wraps(_run)
def run_fast(): return _run()


@functools.wraps(_run)
def run_safe(): return _run()


default_model = Sub()
''',
    "_v5c_impl_new": "def score_null(x):\n    return x + 1\n",
    "_v5c_impl_old": "def score_null(x):\n    return x + 1\n",
    "_v5c_broken": "raise RuntimeError('optional backend not configured')\n",
    "_v5c_syntax": "def f(:\n    pass\n",
    "_v5c_cycle": ("def f(): return 1\ndef g(): return 2\n"
                   "f.__wrapped__ = g\ng.__wrapped__ = f\n"),
}


# -- plumbing ---------------------------------------------------------------------------------

def _commit_prereg(tmp: Path, spec) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / "PREREG_case.md"
    body = spec if isinstance(spec, str) else json.dumps(spec)
    p.write_text("# case\n\n```gates\n" + body + "\n```\n", encoding="utf-8")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=exam@local", "-c", "user.name=exam",
                 "commit", "-qm", "case"]):
        subprocess.run(cmd, cwd=tmp, check=True)
    return p


def _spec(**gates):
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, **extra} for n, extra in gates.items()}
    return {"gates": g,
            "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"},
                         {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "SMOKE"}


class _Tmp:
    def __init__(self):
        self._d = tempfile.TemporaryDirectory()
        self.n = 0

    def exp(self, spec) -> Experiment:
        self.n += 1
        return Experiment(_commit_prereg(Path(self._d.name) / f"r{self.n}", spec))

    def close(self):
        self._d.cleanup()


def _guarded(fn):
    """Run one case; never let it leave the process's profilers changed. Returns
    (kind, payload, leaked) where kind is 'refused' (payload = message), 'scored'
    (payload = dict from the case) or 'crash' (payload = repr)."""
    before_sys, before_thr = sys.getprofile(), _thread_profile()
    tmp = _Tmp()
    try:
        kind, payload = "scored", fn(tmp)
    except GateSpecError as e:
        kind, payload = "refused", str(e)
    except Exception as e:                                          # noqa: BLE001
        kind, payload = "crash", f"{type(e).__name__}: {e}"
    finally:
        tmp.close()
    leaked = sys.getprofile() is not before_sys or _thread_profile() is not before_thr
    sys.setprofile(before_sys)
    threading.setprofile(before_thr)
    return kind, payload, leaked


def _score_traced(tmp, spec, harness, edit=None):
    fx = sys.modules[FIX]
    exp = tmp.exp(spec)
    with coverage_trace(exp) as cov:
        harness(cov, fx)
    res = {"m": 1.0, "coverage_trace": cov.record()}
    if edit:
        edit(res)
    v = exp.score(res)
    return {"verdict": v.verdict, "coverage": v.coverage, "trace": res["coverage_trace"]}


def _sec(name, *calls):
    def h(cov, fx):
        with cov.section(name):
            for c in calls:
                c(fx)
    return h


# -- violation mutants: (expected code, case) -------------------------------------------------

def violations() -> dict:
    fx = lambda: sys.modules[FIX]                                   # noqa: E731
    V = {}

    def st(spec, harness, edit=None):
        return lambda tmp: _score_traced(tmp, spec, harness, edit)

    V["never_called"] = ("NOT_EXERCISED", st(_spec(G={"exercises": [T]}),
                                             _sec("G", lambda f: f.other())))
    V["called_only_in_other_section"] = ("NOT_EXERCISED", st(
        _spec(G={"exercises": [T]}, H={"exercises": [O]}),
        lambda cov, f: (_sec("G")(cov, f), _sec("H", lambda f: f.target(),
                                                lambda f: f.other())(cov, f))))
    V["called_only_outside_sections"] = ("NOT_EXERCISED", st(
        _spec(G={"exercises": [T]}), lambda cov, f: (f.target(), _sec("G")(cov, f))))
    V["no_trace"] = ("NO_TRACE", lambda tmp: tmp.exp(_spec(G={"exercises": [T]})).score(
        {"m": 1.0}))
    # isolated: H is fully satisfied, only G's section is missing
    V["section_absent"] = ("SECTION_ABSENT", st(
        _spec(G={"exercises": [T]}, H={"exercises": [O]}), _sec("H", lambda f: f.other())))

    def stale(tmp):
        a = tmp.exp(_spec(G={"exercises": [T]}))
        bs = _spec(G={"exercises": [T]})
        bs["gates"]["G"]["value"] = 0.6
        b = tmp.exp(bs)
        with coverage_trace(a) as cov:
            with cov.section("G"):
                fx().target()
        return b.score({"m": 1.0, "coverage_trace": cov.record()})
    V["stale_gates_sha"] = ("STALE_TRACE", stale)

    def edit_set(key, fn):
        return lambda r: fn(r["coverage_trace"])
    V["trace_target_set_differs"] = ("TARGET_SET", st(
        _spec(G={"exercises": [T]}), _sec("G", lambda f: f.target()),
        edit_set("t", lambda tr: tr["targets"].__setitem__(O, "0" * 64))))
    V["trace_wrong_tracer_id"] = ("WRONG_TRACER", st(
        _spec(G={"exercises": [T]}), _sec("G", lambda f: f.target()),
        edit_set("t", lambda tr: tr.__setitem__("tracer", "handwritten/1"))))
    V["target_unresolvable_attr"] = ("UNRESOLVED", st(_spec(G={"exercises": [f"{FIX}:nope"]}),
                                                      _sec("G")))
    V["target_unresolvable_module"] = ("UNRESOLVED", st(_spec(G={"exercises": ["no_mod_v5c:f"]}),
                                                        _sec("G")))
    V["target_builtin"] = ("NO_CODE", st(_spec(G={"exercises": ["builtins:len"]}),
                                         _sec("G", lambda f: len([]))))
    # isolated: H declares and is satisfied, so only the non-empty check can refuse
    V["exercises_empty_beside_declaring"] = ("DECL", st(
        _spec(G={"exercises": []}, H={"exercises": [O]}),
        lambda cov, f: _sec("H", lambda f: f.other())(cov, f)))
    # isolated: a dict whose keys are valid targets passes every later check but the list check
    V["exercises_not_list"] = ("DECL", st(_spec(G={"exercises": {T: 1}}),
                                          _sec("G", lambda f: f.target())))
    V["exercises_non_string"] = ("DECL", st(_spec(G={"exercises": [1]}), _sec("G")))
    V["exercises_no_colon"] = ("DECL", st(_spec(G={"exercises": ["target"]}), _sec("G")))
    V["exercises_duplicate"] = ("DECL", st(_spec(G={"exercises": [T, T]}),
                                           _sec("G", lambda f: f.target())))
    V["exercises_trailing_newline"] = ("DECL", st(_spec(G={"exercises": [T + "\n"]}),
                                                  _sec("G", lambda f: f.target())))
    V["section_non_string"] = ("SECTION_DECL", st(_spec(G={"exercises": [T], "section": 5}),
                                                  lambda cov, f: f.target()))
    V["section_without_exercises"] = ("SECTION_DECL", lambda tmp: tmp.exp(
        _spec(G={"section": "S"})))
    # isolated: G is also opened and satisfied, so without the check this would score PASS
    V["undeclared_section_opened"] = ("UNDECLARED_SECTION", st(
        _spec(G={"exercises": [T]}),
        lambda cov, f: (_sec("G", lambda f: f.target())(cov, f),
                        _sec("NOT_A_GATE", lambda f: f.target())(cov, f))))

    def nested_sections(cov, f):
        with cov.section("G"):
            with cov.section("H"):
                f.other()
    V["nested_sections"] = ("NESTED_SECTION", st(
        _spec(G={"exercises": [T]}, H={"exercises": [O]}), nested_sections))
    V["nothing_declared"] = ("NOTHING_DECLARED", lambda tmp: coverage_trace(tmp.exp(_spec(G={}))))
    for label, bad in (("bool", True), ("float", 1.0), ("negative", -1), ("zero", 0)):
        V[f"count_{label}"] = ("BAD_COUNT", st(
            _spec(G={"exercises": [T]}), _sec("G", lambda f: f.target()),
            lambda r, bad=bad: r["coverage_trace"]["sections"]["G"].__setitem__(T, bad)))

    def child(cov, f):
        with cov.section("G"):
            env = dict(os.environ, PYTHONPATH=os.pathsep.join(
                [str(Path(f.__file__).parent), os.environ.get("PYTHONPATH", "")]))
            subprocess.run([sys.executable, "-c", f"import {FIX}; {FIX}.target()"],
                           check=True, env=env)
    V["called_only_in_child_process"] = ("NOT_EXERCISED", st(_spec(G={"exercises": [T]}), child))

    # ---- round 1, module red team ----
    V["rt_factory_closure_sibling"] = ("SHARED_CODE", st(
        _spec(G={"exercises": [f"{FIX}:check_low"]}), _sec("G", lambda f: f.check_high(0))))
    V["rt_nowraps_decorator_sibling"] = ("SHARED_CODE", st(
        _spec(G={"exercises": [f"{FIX}:entry_a"]}), _sec("G", lambda f: f.entry_b())))
    V["rt_wraps_decorator_sibling"] = ("NOT_EXERCISED", st(
        _spec(G={"exercises": [f"{FIX}:wrapped"]}), _sec("G", lambda f: f.wrapped_sibling())))
    V["rt_vendored_equal_code_copy"] = ("NOT_EXERCISED", st(
        _spec(G={"exercises": ["_v5c_impl_new:score_null"]}),
        _sec("G", lambda f: sys.modules["_v5c_impl_old"].score_null(1))))

    def pinned_copy(cov, f):
        src = (ROOT / "styxx" / "protocol.py").read_text(encoding="utf-8")
        mod = types.ModuleType("styxx_protocol_pinned_v5c")
        mod.__file__ = "pinned:styxx/protocol.py"
        sys.modules[mod.__name__] = mod
        try:
            exec(compile(src, mod.__file__, "exec"), mod.__dict__)
            with cov.section("G"):
                mod.undeclared_power_gates(HERE / PREREG)
        finally:
            sys.modules.pop(mod.__name__, None)
    V["rt_pinned_exec_copy_of_protocol"] = ("NOT_EXERCISED", st(
        _spec(G={"exercises": ["styxx.protocol:undeclared_power_gates"]}), pinned_copy))
    V["rt_dataclass_equal_init"] = ("NOT_EXERCISED", st(
        _spec(G={"exercises": [f"{FIX}:NullModel.__init__"]}), _sec("G", lambda f: f.AltModel(3))))

    def outlives(cov, f):
        th = threading.Thread(target=lambda: (time.sleep(0.3), f.target()))
        try:
            with cov.section("G"):
                th.start()
        finally:
            th.join()
    V["rt_thread_outlives_section"] = ("THREAD_OUTLIVES", st(_spec(G={"exercises": [T]}),
                                                             outlives))

    def background(cov, f):
        th = threading.Thread(target=lambda: (time.sleep(0.2), f.target()))
        th.start()
        with cov.section("G"):
            th.join()
    V["rt_background_thread_started_outside"] = ("NOT_EXERCISED", st(
        _spec(G={"exercises": [T]}), background))

    def task_from_closed_section(cov, f):
        async def work():
            await asyncio.sleep(0)
            f.target()

        async def main():
            with cov.section("A"):
                f.other()
                task = asyncio.ensure_future(work())
            with cov.section("B"):
                await task
        asyncio.run(main())
    V["rt_asyncio_task_from_closed_section"] = ("NOT_EXERCISED", st(
        _spec(A={"exercises": [O]}, B={"exercises": [T]}), task_from_closed_section))

    def c_profiler_present(tmp):
        import cProfile
        exp = tmp.exp(_spec(G={"exercises": [T]}))
        pr = cProfile.Profile()
        pr.enable()
        try:
            with coverage_trace(exp):
                pass
        finally:
            pr.disable()
    V["rt_c_profiler_present"] = ("FOREIGN_PROFILER", c_profiler_present)

    def cprofile_in_section(cov, f):
        import cProfile
        with cov.section("G"):
            pr = cProfile.Profile()
            pr.enable()
            f.target()
            pr.disable()
    V["rt_cprofile_inside_section"] = ("PROFILER_REPLACED", st(_spec(G={"exercises": [T]}),
                                                               cprofile_in_section))

    def reentry(tmp):
        cov = coverage_trace(tmp.exp(_spec(G={"exercises": [T]})))
        with cov:
            with cov:
                pass
    V["rt_reentry"] = ("REENTRY", reentry)

    def out_of_order(tmp):
        before, before_thr = sys.getprofile(), _thread_profile()
        t1 = coverage_trace(tmp.exp(_spec(G={"exercises": [T]})))
        t2 = coverage_trace(tmp.exp(_spec(H={"exercises": [O]})))
        t1.__enter__()
        t2.__enter__()
        try:
            t1.__exit__(None, None, None)
        finally:
            t2.__exit__(None, None, None)
            if sys.getprofile() is not before or _thread_profile() is not before_thr:
                raise RuntimeError("out-of-order exit leaked a hook")   # a crash, not a pass
    V["rt_out_of_order_exit"] = ("EXIT_ORDER", out_of_order)
    V["rt_import_raises"] = ("UNRESOLVED", st(_spec(G={"exercises": ["_v5c_broken:f"]}), _sec("G")))
    V["rt_import_syntax_error"] = ("UNRESOLVED", st(_spec(G={"exercises": ["_v5c_syntax:f"]}),
                                                    _sec("G")))
    V["rt_unwrap_loop"] = ("UNRESOLVED", st(_spec(G={"exercises": ["_v5c_cycle:f"]}), _sec("G")))
    V["rt_non_string_trace_key"] = ("BAD_TRACE", st(
        _spec(G={"exercises": [T]}), _sec("G", lambda f: f.target()),
        lambda r: r["coverage_trace"]["targets"].__setitem__(1, "x")))

    def check_metrics_bad_key(tmp):
        out = _score_traced_check_metrics(tmp)
        entry = out.get("G:exercises", {})
        if entry.get("usable") is False and str(entry.get("note", "")).startswith("[V5:BAD_TRACE]"):
            raise GateSpecError(entry["note"])      # reported, not raised: counts as the refusal
        return {"check_metrics": out}
    V["rt_check_metrics_non_string_key_reports"] = ("BAD_TRACE", check_metrics_bad_key)
    V["rt_inherited_method"] = ("INHERITED", st(_spec(G={"exercises": [f"{FIX}:Sub.fit"]}),
                                                _sec("G", lambda f: f.Other().fit())))

    # ---- round 2, module red team ----
    SA = f"{FIX}:score_all"
    keep = []

    def runtime_kept(cov, f):
        try:
            with cov.section("G"):
                w = f._timed(f.cheap_path)
                keep.append(w)
                w()
        finally:
            keep.clear()
    V["rt2_runtime_nowraps_kept_alive"] = ("SHARED_CODE", st(_spec(G={"exercises": [SA]}),
                                                             runtime_kept))
    V["rt2_runtime_nowraps_discarded"] = ("NOT_EXERCISED", st(
        _spec(G={"exercises": [SA]}), _sec("G", lambda f: f._timed(f.cheap_path)())))
    V["rt2_clone_with_other_globals"] = ("NOT_EXERCISED", st(
        _spec(G={"exercises": [T]}),
        _sec("G", lambda f: types.FunctionType(f.target.__code__, {"__builtins__": {}})())))

    def shared_pool(cov, f):
        pool = ThreadPoolExecutor(max_workers=1)
        b1, b2 = threading.Barrier(2, timeout=20), threading.Barrier(2, timeout=20)
        errors = []

        def run_a():
            try:
                with cov.section("A"):
                    pool.submit(f.other).result(timeout=20)   # starts the one worker, in A
                    b1.wait()
                    b2.wait()
                    pool.shutdown(wait=True)
            except BaseException as e:                        # noqa: BLE001
                errors.append(e)

        def run_b():
            try:
                with cov.section("B"):
                    b1.wait()
                    f.other()
                    pool.submit(f.target).result(timeout=20)  # B's work, on A's worker
                    b2.wait()
            except BaseException as e:                        # noqa: BLE001
                errors.append(e)
        ths = [threading.Thread(target=run_a), threading.Thread(target=run_b)]
        for th in ths:
            th.start()
        for th in ths:
            th.join(30)
        if errors:
            raise errors[0]
    V["rt2_concurrent_sections_share_pool"] = ("NOT_EXERCISED", st(
        _spec(A={"exercises": [T]}, B={"exercises": [O]}), shared_pool))
    V["rt2_instance_path"] = ("INSTANCE_PATH", st(
        _spec(G={"exercises": [f"{FIX}:default_model.fit"]}), _sec("G", lambda f: f.Other().fit())))
    V["rt2_wraps_siblings_share_inner"] = ("SHARED_CODE", st(
        _spec(G={"exercises": [f"{FIX}:run_fast"]}), _sec("G", lambda f: f.run_safe())))

    def other_context(cov, f):
        import contextvars
        cm = cov.section("G")
        cm.__enter__()
        f.target()
        contextvars.copy_context().run(cm.__exit__, None, None, None)
    V["rt2_section_exited_in_other_context"] = ("SECTION_CONTEXT", st(
        _spec(G={"exercises": [T]}), other_context))

    # ---- round 2, exam mutation audit: every surviving mutant becomes a case ----
    def late_call(cov, f):
        async def work():
            await asyncio.sleep(0)
            f.target()

        async def main():
            with cov.section("G"):
                task = asyncio.ensure_future(work())
            await task
        asyncio.run(main())
    V["x2_call_after_its_section_closed"] = ("NOT_EXERCISED", st(_spec(G={"exercises": [T]}),
                                                                 late_call))
    V["x2_non_string_key_under_sections"] = ("BAD_TRACE", st(
        _spec(G={"exercises": [T]}), _sec("G", lambda f: f.target()),
        lambda r: r["coverage_trace"]["sections"].__setitem__(1, {})))
    V["x2_non_string_key_inside_section"] = ("BAD_TRACE", st(
        _spec(G={"exercises": [T]}), _sec("G", lambda f: f.target()),
        lambda r: r["coverage_trace"]["sections"]["G"].__setitem__(2, 1)))
    V["x2_list_valued_section"] = ("BAD_TRACE", st(
        _spec(G={"exercises": [T]}), _sec("G", lambda f: f.target()),
        lambda r: r["coverage_trace"]["sections"].__setitem__("G", [T])))

    def reports(mutate, code):
        """check_metrics must REPORT: a raise of any kind is a crash here, never a refusal,
        so a check_metrics that raises the right code can no longer pass (round 2: R13d)."""
        def case(tmp):
            fx_ = sys.modules[FIX]
            exp = tmp.exp(_spec(G={"exercises": [T]}))
            with coverage_trace(exp) as cov:
                with cov.section("G"):
                    fx_.target()
            res = {"m": 1.0, "coverage_trace": cov.record()}
            res = mutate(res)
            try:
                out = exp.check_metrics(res)
            except BaseException as e:                         # noqa: BLE001
                raise RuntimeError(f"check_metrics raised {type(e).__name__}: {e}") from None
            if code == "REPORTED":
                raise GateSpecError("[V5:REPORTED] check_metrics returned a report")
            entry = out.get("G:exercises", {})
            if entry.get("usable") is False and str(entry.get("note", "")).startswith(
                    f"[V5:{code}]"):
                raise GateSpecError(entry["note"])
            return {"check_metrics": out}
        return case

    def _set(path_fn):
        def m(res):
            path_fn(res)
            return res
        return m
    V["x2_check_metrics_reports_none_key"] = ("BAD_TRACE", reports(
        _set(lambda r: r["coverage_trace"]["targets"].__setitem__(None, "x")), "BAD_TRACE"))
    V["x2_check_metrics_reports_list_section"] = ("BAD_TRACE", reports(
        _set(lambda r: r["coverage_trace"]["sections"].__setitem__("G", [T])), "BAD_TRACE"))
    V["x2_check_metrics_reports_non_dict_result"] = ("REPORTED", reports(lambda r: [r],
                                                                         "REPORTED"))
    V["x2_alias_targets_one_function"] = ("SHARED_CODE", st(
        _spec(G={"exercises": [T, f"{FIX}:alias"]}), _sec("G", lambda f: f.target())))

    def c_profiler_kept(tmp):
        import cProfile
        exp = tmp.exp(_spec(G={"exercises": [T]}))
        pr = cProfile.Profile()
        pr.enable()
        try:
            with coverage_trace(exp):
                pass
        except GateSpecError:
            if sys.getprofile() is not pr:
                raise RuntimeError("the user's C profiler was destroyed by the refusal") from None
            raise
        finally:
            pr.disable()
    V["x2_c_profiler_refused_and_kept"] = ("FOREIGN_PROFILER", c_profiler_kept)

    def c_profiler_threading_side(tmp):
        import cProfile
        exp = tmp.exp(_spec(G={"exercises": [T]}))
        threading.setprofile(cProfile.Profile())
        with coverage_trace(exp):
            pass
    V["x2_foreign_threading_profiler"] = ("FOREIGN_PROFILER", c_profiler_threading_side)

    def reenter_exited(tmp):
        cov = coverage_trace(tmp.exp(_spec(G={"exercises": [T]})))
        with cov:
            pass
        with cov:
            pass
    V["x2_reenter_exited_tracer"] = ("REENTRY", reenter_exited)
    V["x2_forged_undeclared_key_in_section"] = ("BAD_COUNT", st(
        _spec(G={"exercises": [T]}), _sec("G", lambda f: f.target()),
        lambda r: r["coverage_trace"]["sections"]["G"].__setitem__(O, 1)))
    V["x2_non_ascii_target"] = ("DECL", st(_spec(G={"exercises": [f"{FIX}:t\u0430rget"]}),
                                           _sec("G", lambda f: f.target())))
    return V


def _score_traced_check_metrics(tmp):
    fx = sys.modules[FIX]
    exp = tmp.exp(_spec(G={"exercises": [T]}))
    with coverage_trace(exp) as cov:
        with cov.section("G"):
            fx.target()
    res = {"m": 1.0, "coverage_trace": cov.record()}
    res["coverage_trace"]["targets"][None] = "x"
    return exp.check_metrics(res)


# -- valid cases: (expected coverage on the verdict, case) ------------------------------------

def valids() -> dict:
    V = {}

    def st(spec, harness):
        return lambda tmp: _score_traced(tmp, spec, harness)

    V["direct_call"] = ({"G": {T: 1}}, st(_spec(G={"exercises": [T]}),
                                          _sec("G", lambda f: f.target())))
    V["transitive_call"] = ({"G": {T: 1}}, st(_spec(G={"exercises": [T]}),
                                              _sec("G", lambda f: f.helper())))
    W = f"{FIX}:wrapped"
    V["wraps_decorated"] = ({"G": {W: 1}}, st(_spec(G={"exercises": [W]}),
                                              _sec("G", lambda f: f.wrapped())))
    for label, tgt, call in (("method", "K.meth", lambda f: f.K().meth()),
                             ("staticmethod", "K.stat", lambda f: f.K.stat()),
                             ("classmethod", "K.cm", lambda f: f.K.cm())):
        V[label] = ({"G": {f"{FIX}:{tgt}": 1}},
                    st(_spec(G={"exercises": [f"{FIX}:{tgt}"]}), _sec("G", call)))

    def in_thread(f):
        th = threading.Thread(target=f.target)
        th.start()
        th.join()
    V["thread_started_in_section"] = ({"G": {T: 1}}, st(_spec(G={"exercises": [T]}),
                                                        _sec("G", in_thread)))

    def pool(f):
        with ThreadPoolExecutor(max_workers=2) as ex:
            list(ex.map(lambda _: f.target(), range(3)))
    V["thread_pool_inside_section"] = ({"G": {T: 3}}, st(_spec(G={"exercises": [T]}),
                                                         _sec("G", pool)))

    def aio(f):
        async def work():
            await asyncio.sleep(0)
            f.target()

        async def main():
            await asyncio.ensure_future(work())
        asyncio.run(main())
    V["asyncio_task_in_one_section"] = ({"G": {T: 1}}, st(_spec(G={"exercises": [T]}),
                                                          _sec("G", aio)))

    def parallel(cov, f):
        # round 2: without a timeout a broken implementation deadlocked here instead of failing
        barrier = threading.Barrier(2, timeout=20)
        errors = []

        def run(sec, fn):
            try:
                with cov.section(sec):
                    barrier.wait()
                    fn()
                    barrier.wait()
            except BaseException as e:                        # noqa: BLE001
                errors.append(e)
                barrier.abort()
        ths = [threading.Thread(target=run, args=("A", f.target)),
               threading.Thread(target=run, args=("B", f.other))]
        for th in ths:
            th.start()
        for th in ths:
            th.join(30)
        if errors:
            raise errors[0]
    V["parallel_sections_in_two_threads"] = ({"A": {T: 1}, "B": {O: 1}}, st(
        _spec(A={"exercises": [T]}, B={"exercises": [O]}), parallel))
    V["two_gates_share_section"] = ({"G": {T: 1}, "H": {O: 1}}, st(
        _spec(G={"exercises": [T], "section": "S"}, H={"exercises": [O], "section": "S"}),
        _sec("S", lambda f: f.target(), lambda f: f.other())))
    V["declaring_beside_undeclaring"] = ({"G": {T: 1}}, st(_spec(G={"exercises": [T]}, H={}),
                                                           _sec("G", lambda f: f.target())))

    def nested(tmp):
        fx = sys.modules[FIX]
        a, b = tmp.exp(_spec(G={"exercises": [T]})), tmp.exp(_spec(H={"exercises": [O]}))
        with coverage_trace(a) as ca:
            with ca.section("G"):
                fx.target()
                with coverage_trace(b) as cb:
                    with cb.section("H"):
                        fx.other()
                        fx.target()
        va = a.score({"m": 1.0, "coverage_trace": ca.record()})
        vb = b.score({"m": 1.0, "coverage_trace": cb.record()})
        return {"verdict": f"{va.verdict}/{vb.verdict}",
                "coverage": {"G": va.coverage["G"], "H": vb.coverage["H"]}}
    # the outer tracer must see BOTH target() calls, including the one made inside the inner
    V["nested_tracers_outer_sees_inner_calls"] = ({"G": {T: 2}, "H": {O: 1}}, nested)

    def under_python_profiler(tmp):
        # Not stdlib profile.runcall: the full-battery dry run showed it asserts 'Bad return'
        # whenever ANY profiler is already installed (reproduced with a no-op function and no
        # styxx involved) -- and inside this exam the self-trace is always installed. The
        # property named in the prereg is a pre-existing Python-level profile function, chained
        # (it keeps seeing events while the tracer runs) and restored.
        fx = sys.modules[FIX]
        outer = sys.getprofile()
        seen = []

        def rec(frame, event, arg):
            if event == "call" and frame.f_code is fx.target.__code__:
                seen.append(1)
            if outer is not None:
                outer(frame, event, arg)
        sys.setprofile(rec)
        try:
            out = _score_traced(tmp, _spec(G={"exercises": [T]}), _sec("G", lambda f: f.target()))
            restored = sys.getprofile() is rec
        finally:
            sys.setprofile(outer)
        if not restored or len(seen) != 1:
            raise RuntimeError(f"pre-existing profiler restored={restored}, saw {len(seen)} of 1 "
                               f"target calls while chained")
        return out
    V["preexisting_python_profiler_chained"] = ({"G": {T: 1}}, under_python_profiler)

    def grandchild(f):
        def child():
            g = threading.Thread(target=f.target)
            g.start()
            g.join()
        c = threading.Thread(target=child)
        c.start()
        c.join()
    V["x2_grandchild_thread_in_section"] = ({"G": {T: 1}}, st(_spec(G={"exercises": [T]}),
                                                             _sec("G", grandchild)))

    def thread_hook_released(tmp):
        from styxx.protocol import _Hook
        fx_ = sys.modules[FIX]
        exp = tmp.exp(_spec(G={"exercises": [T]}))
        go, seen = threading.Event(), {}

        def worker():
            go.wait(20)
            fx_.other()                   # an event after exit, where a stale hook would run
            h, chain = sys.getprofile(), []
            while isinstance(h, _Hook):
                chain.append(h.tracer)
                h = h.prev
            seen["ours"] = any(t is cov for t in chain)
        th = threading.Thread(target=worker)
        with coverage_trace(exp) as cov:
            th.start()
            with cov.section("G"):
                fx_.target()
        go.set()
        th.join(30)
        if seen.get("ours", True):
            raise RuntimeError("a thread started during the trace kept its hook after exit")
        v = exp.score({"m": 1.0, "coverage_trace": cov.record()})
        return {"verdict": v.verdict, "coverage": v.coverage}
    V["rt2_thread_hook_released_after_exit"] = ({"G": {T: 1}}, thread_hook_released)
    return V


# -- the P1 retro-case ------------------------------------------------------------------------

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
    return run_p1


P1_PUBLIC = [f"styxx.power:{n}" for n in ("effective_n", "order_stat_bar", "false_positive_rate",
                                           "min_detectable_bar", "reachable")]


def p1_retro(run_p1) -> dict:
    import numpy as np
    committed = json.loads((HERE / "p1_result.json").read_text(encoding="utf-8"))
    gates = json.loads(_select_gates_block(
        (HERE / "PREREG_p1_power_refusal_2026_08_08.md").read_text(encoding="utf-8")))
    gates["gates"]["G4_refuses_degenerate"]["exercises"] = P1_PUBLIC
    tmp = _Tmp()
    out = {"declared": P1_PUBLIC}
    try:
        exp = tmp.exp(json.dumps(gates))
        res = dict(committed)
        with coverage_trace(exp) as cov:
            with cov.section("G4_refuses_degenerate"):
                deg = run_p1.degenerate(np.random.default_rng(run_p1.SEED))
        res["coverage_trace"] = cov.record()
        res["degenerate_refusal_rate"] = round(float(np.mean([c["refused"] for c in deg])), 4)
        sec = res["coverage_trace"]["sections"]["G4_refuses_degenerate"]
        out["calls"] = sec
        out["unexercised"] = sorted(set(P1_PUBLIC) - set(sec))
        try:
            v = exp.score(res)
            out["outcome"] = f"scored {v.verdict}"
        except GateSpecError as e:
            out["outcome"] = str(e)
    finally:
        tmp.close()
    out["exact"] = (out.get("outcome", "").startswith("[V5:NOT_EXERCISED]")
                    and out.get("calls") == {"styxx.power:reachable": 12}
                    and out.get("unexercised") == sorted(set(P1_PUBLIC) - {"styxx.power:reachable"}))
    return out


def main() -> int:
    fixdir = Path(tempfile.mkdtemp(prefix="v5dfix_"))
    for name, src in FIXTURES.items():
        (fixdir / f"{name}.py").write_text(src, encoding="utf-8")
    sys.path.insert(0, str(fixdir))
    for name in (FIX, "_v5c_impl_new", "_v5c_impl_old"):
        __import__(name)
    run_p1 = _load_p1()          # before the self-trace: G2 declares run_p1:degenerate

    import run_protocol_v5 as attempt_b     # the committed differential, reused unchanged
    attempt_b.OWN_PREREGS.update({PREREG, "PREREG_protocol_v5c_repair_2026_09_24.md"})

    self_exp = Experiment(HERE / PREREG, require_power_basis=True, require_nonvacuous_gates=True)
    viol, vals = violations(), valids()
    if SMOKE and "--full-battery" not in sys.argv:   # a full-battery smoke is still INVALID
        viol = dict(list(viol.items())[:6])
        vals = dict(list(vals.items())[:4])
    vres, gres = {}, {}
    with coverage_trace(self_exp) as cov:
        with cov.section("G0_mutants_refused_for_their_reason"):
            for k, (code, fn) in viol.items():
                kind, payload, leaked = _guarded(fn)
                ok = kind == "refused" and payload.startswith(f"[V5:{code}]")
                vres[k] = {"expected": code, "outcome": kind, "ok": ok,
                           "detail": str(payload)[:220], "leaked_profiler": leaked}
        with cov.section("G1_valid_cases_score_with_their_property"):
            for k, (want, fn) in vals.items():
                kind, payload, leaked = _guarded(fn)
                got = payload.get("coverage") if kind == "scored" else None
                ok = (kind == "scored" and str(payload.get("verdict", "")).startswith("PASS")
                      and got == want and not leaked)
                gres[k] = {"expected_coverage": want, "outcome": kind, "ok": ok,
                           "coverage": got, "leaked_profiler": leaked,
                           "detail": None if kind == "scored" else str(payload)[:220]}
        with cov.section("G2_p1_retro_refused_as_coverage_violation"):
            retro = p1_retro(run_p1)
    diff = attempt_b.differential()

    res = {"prereg": PREREG, "smoke": SMOKE,
           "violation_cases": vres, "valid_cases": gres, "p1_retro": retro,
           "n_violation_mutants": len(vres),
           "frac_violation_mutants_refused_with_expected_code": round(
               sum(v["ok"] for v in vres.values()) / len(vres), 4),
           "n_valid_cases": len(gres),
           "frac_valid_cases_scored_with_property": round(
               sum(v["ok"] for v in gres.values()) / len(gres), 4),
           "p1_retro_exact": 1.0 if retro["exact"] else 0.0,
           "n_crashes": sum(v["outcome"] == "crash" for v in list(vres.values()) + list(gres.values())),
           "n_v4_v5_outcome_disagreements": diff["n_v4_v5_outcome_disagreements"],
           "v4_v5_disagreements": diff["v4_v5_disagreements"],
           "n_pairable_results": diff["n_pairable_results"],
           "n_results_v5_scored": diff["n_pairable_results"] - diff["n_v5_raised_on"],
           "n_v5_raised_on": diff["n_v5_raised_on"],
           "ungated_n_v5_differs_from_committed_verdict":
               diff["ungated_n_v5_differs_from_committed_verdict"],
           "ungated_v5_differs_from_committed_verdict":
               diff["ungated_v5_differs_from_committed_verdict"],
           "v4_pin": diff["v4_pin"],
           "coverage_trace": cov.record()}
    import hashlib
    import re as _re
    own = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    m = _re.search(r"FROZEN_RUNNER_SHA256: ([0-9a-f]{64})",
                   (HERE / PREREG).read_text(encoding="utf-8"))
    res["runner_sha256"] = own
    res["exam_runner_frozen"] = 1.0 if (m and m.group(1) == own) else 0.0
    res["impl_sha256"] = hashlib.sha256((ROOT / "styxx" / "protocol.py").read_bytes()).hexdigest()

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

    (HERE / f"protocol_v5d_result{'_smoke' if SMOKE else ''}.json").write_text(
        json.dumps(res, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"violations refused with their own code: "
          f"{res['frac_violation_mutants_refused_with_expected_code']} of {len(vres)}")
    for k, v in vres.items():
        if not v["ok"]:
            print(f"  MUTANT FAILED {k}: expected {v['expected']}, got {v['outcome']}: "
                  f"{v['detail'][:140]}")
    print(f"valid scored with property: {res['frac_valid_cases_scored_with_property']} "
          f"of {len(gres)}")
    for k, v in gres.items():
        if not v["ok"]:
            print(f"  VALID FAILED {k}: {v['outcome']} coverage={v['coverage']} "
                  f"leaked={v['leaked_profiler']} {v['detail']}")
    print(f"P1 retro exact={retro['exact']} calls={retro.get('calls')} "
          f"outcome={str(retro.get('outcome'))[:90]}")
    print(f"crashes {res['n_crashes']} | differential {res['n_pairable_results']} pairable, "
          f"{res['n_v4_v5_outcome_disagreements']} disagreements, "
          f"v5 scored {res['n_results_v5_scored']}")
    print(f"VERDICT: {res['verdict']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
