"""round4/verify-exam/ (the verifiers' witnesses for the exam mutants and exam holes), rewritten: each witness's
API program; the mutant-vs-original drivers (b6drive.py, each witness's both()/mutant.patch) are exam tooling for
v5e (NOT_APPLICABLE.json). Where a witness read v5e's private state (P._STOP, P._hook, P._resolve_target,
P._MINTED...), the rewrite reads _v5_state() or enters a tracer. Per-gate outcomes are check_metrics' notes.
b3wit: w_cache_body (class-held and PEP 562-held cache wrappers whose module-level body is called; the wrapper
called as control), w_class_step (ABC, Enum, user metaclass, typing.Protocol module, plain class, ABC-inherited,
missing), w_inherited (grandparent, second base after a mixin, object dunder, direct base, missing), w_module_step
(a ModuleType-subclass module's PEP 562 and direct targets, a subclassed submodule after the colon, a LazyLoader
module). exam-mut witnesses: bad-trace-end-type (str-subclass and a lying __eq__ end), double-exit, foreign-
profiler-first-open-only (i, ii, iii), hop-close-drops-closer-hook, problems-before-bad-count (three bad counts on
a trace with recorded problems), profiler-lost-only-if-none (setprofile and cProfile mid-section),
target-set-before-stale (old prereg, edited prereg, same targets in a new block), uncredited-last-thread-wins
(two threads alive together). examhole witnesses: clone-alive / clone-called (with the reverse-nesting control) /
code-swapped across nested tracers, declared-section (W2a shared, W2b renamed, W2c cross-named),
dispatch-cut-by-name (W3a helper, W3b method, W3c real cut), stop-read-before-mint, union (W1a-W1d), walk-bound
(W4a three stacked wraps; W4b chain depths 1-17 entered). witness_b5.py: nested_same_name, restore_swapped,
close_foreign_prof, exit_foreign_prof_inside, exit_foreign_prof_preexisting."""
import asyncio, asyncio.events, copy, importlib, importlib.util, sys, textwrap, threading, types


def main(api):
    out = {}
    T = lambda gates, *steps, sections=None: api.trace(api.exp(gates, sections=sections), *steps)

    def gate(e, rec, name):
        mm = api.metrics(e, {"m": 1.0, "coverage_trace": rec})
        return mm.get(name + ":exercises", mm) if isinstance(mm, dict) else mm

    def trace_of(e, h):
        cov = api.coverage_trace(e)
        with cov:
            h(cov)
        return cov.record()
    # b3wit
    api.fixture("rp_vx_cache", "import functools\ndef _impl(x): return x * 2\nclass Scorer:\n"
                "    fast = staticmethod(functools.lru_cache(None)(_impl))\n    fast2 = functools.lru_cache(None)(_impl)\n"
                "def _impl3(x): return x + 3\n_LAZY = {'lazy_fast': functools.lru_cache(None)(_impl3)}\n"
                "def __getattr__(name):\n    if name in _LAZY:\n        return _LAZY[name]\n    raise AttributeError(name)\n")
    mc = importlib.import_module("rp_vx_cache")
    out["b3_cache_static_body"] = T({"G": ["rp_vx_cache:Scorer.fast"]}, lambda c: c.run("G", mc._impl, 1))
    out["b3_cache_bare_body"] = T({"G": ["rp_vx_cache:Scorer.fast2"]}, lambda c: c.run("G", mc._impl, 2))
    out["b3_cache_pep562_body"] = T({"G": ["rp_vx_cache:lazy_fast"]}, lambda c: c.run("G", mc._impl3, 3))
    mc.Scorer.fast.cache_clear()
    out["b3_cache_wrapper_called"] = T({"G": ["rp_vx_cache:Scorer.fast"]}, lambda c: c.run("G", mc.Scorer.fast, 5))
    mcls = api.fixture("rp_vx_cls", "import abc, enum, typing\nclass Model(abc.ABC):\n    def fit(self): return 1\n"
                       "class Color(enum.Enum):\n    RED = 1\n    def describe(self): return self.name\nclass Meta(type): pass\n"
                       "class Custom(metaclass=Meta):\n    def go(self): return 3\nclass Proto(typing.Protocol):\n"
                       "    def need(self) -> int: ...\nclass Plain:\n    def run(self): return 5\nclass ABase(abc.ABC):\n"
                       "    def inh(self): return 6\nclass ASub(ABase): pass\n")
    out["b3_class_abc"] = T({"G": ["rp_vx_cls:Model.fit"]}, lambda c: c.run("G", lambda: type("Lin", (mcls.Model,), {})().fit()))
    out["b3_class_enum"] = T({"G": ["rp_vx_cls:Color.describe"]}, lambda c: c.run("G", lambda: mcls.Color.RED.describe()))
    out["b3_class_custom_meta"] = T({"G": ["rp_vx_cls:Custom.go"]}, lambda c: c.run("G", lambda: mcls.Custom().go()))
    out["b3_class_plain"] = T({"G": ["rp_vx_cls:Plain.run"]}, lambda c: c.run("G", lambda: mcls.Plain().run()))
    out["b3_class_abc_inherited"] = T({"G": ["rp_vx_cls:ASub.inh"]}, lambda c: c.run("G", lambda: mcls.ASub().inh()))
    out["b3_class_abc_missing"] = T({"G": ["rp_vx_cls:Model.nope"]}, lambda c: c.run("G", lambda: None))
    mi = api.fixture("rp_vx_inh", "class Base:\n    def fit(self): return 1\nclass Mid(Base): pass\nclass Leaf(Mid): pass\n"
                     "class LoggingMixin:\n    def log(self): return 0\nclass Model(LoggingMixin, Base): pass\nclass Direct(Base): pass\n")
    out["b3_inh_grandparent"] = T({"G": ["rp_vx_inh:Leaf.fit"]}, lambda c: c.run("G", lambda: mi.Leaf().fit()))
    out["b3_inh_mixin_second_base"] = T({"G": ["rp_vx_inh:Model.fit"]}, lambda c: c.run("G", lambda: mi.Model().fit()))
    out["b3_inh_object_dunder"] = T({"G": ["rp_vx_inh:Leaf.__init__"]}, lambda c: c.run("G", lambda: mi.Leaf() and None))
    out["b3_inh_direct_base"] = T({"G": ["rp_vx_inh:Direct.fit"]}, lambda c: c.run("G", lambda: mi.Direct().fit()))
    out["b3_inh_missing"] = T({"G": ["rp_vx_inh:Leaf.nope"]}, lambda c: c.run("G", lambda: None))
    ms = api.fixture("rp_vx_modsub", "import sys, types\ndef direct(): return 1\ndef _helper(): return 5\n"
                     "def __getattr__(name):\n    if name == 'helper':\n        return _helper\n    raise AttributeError(name)\n"
                     "class _Mod(types.ModuleType):\n    @property\n    def version(self): return '1.0'\n"
                     "sys.modules[__name__].__class__ = _Mod\n")
    out["b3_mod_type_a"] = type(ms).__name__ != "module"
    out["b3_mod_pep562"] = T({"G": ["rp_vx_modsub:helper"]}, lambda c: c.run("G", lambda: ms.helper()))
    out["b3_mod_direct"] = T({"G": ["rp_vx_modsub:direct"]}, lambda c: c.run("G", lambda: ms.direct()))
    api.write("rp_vx_pkg.sub", "import sys, types\nclass _Mod(types.ModuleType):\n    pass\nsys.modules[__name__].__class__ = _Mod\n")
    api.write("rp_vx_pkg.__init__", "from rp_vx_pkg import sub\ndef fn(): return 1\nsub.fn = fn\n")
    pkg = importlib.import_module("rp_vx_pkg")
    out["b3_mod_after_colon"] = T({"G": ["rp_vx_pkg:sub.fn"]}, lambda c: c.run("G", lambda: pkg.sub.fn()))
    api.write("rp_vx_lazy", "def work(): return 9\n")
    spec = importlib.util.find_spec("rp_vx_lazy")
    loader = importlib.util.LazyLoader(spec.loader)
    spec.loader = loader
    lm = importlib.util.module_from_spec(spec)
    sys.modules["rp_vx_lazy"] = lm
    loader.exec_module(lm)
    out["b3_mod_lazyloader"] = T({"G": ["rp_vx_lazy:work"]}, lambda c: c.run("G", lambda: sys.modules["rp_vx_lazy"].work()))
    # exam-mut witnesses
    m7 = api.fixture("rp_vx_et", "def f():\n    return 1\n")
    e = api.exp({"G": ["rp_vx_et:f"]})
    rec = trace_of(e, lambda c: c.run("G", m7.f))

    class Tagged(str):
        pass

    class Liar(str):
        def __eq__(self, other): return True
        def __ne__(self, other): return False
        def __hash__(self): return hash("returned")
    r1, r2 = copy.deepcopy(rec), copy.deepcopy(rec)
    r1["sections"]["G"][0]["end"] = Tagged("returned")
    r2["sections"]["G"][0]["end"] = Liar("finished")
    out["xm_end_type"] = {"plain": api.score(e, copy.deepcopy(rec)), "subclass": api.score(e, r1), "liar": api.score(e, r2),
                          "metrics_subclass": gate(e, r1, "G")}
    mde = api.fixture("rp_vx_de", "def f():\n    return 1\n")
    e = api.exp({"G": ["rp_vx_de:f"]})
    cov = api.coverage_trace(e)
    cov.__enter__()
    try:
        cov.run("G", mde.f)
        cov.__exit__(None, None, None)
    finally:
        second_exit = api.attempt(lambda: bool(cov.__exit__(None, None, None)))
    out["xm_double_exit"] = {"second_exit": second_exit, "first": api.score(e, cov.record()), "state_after": api.state(),
                             "later": T({"H": ["rp_vx_de:f"]}, lambda c: c.run("H", mde.f)).get("score"), "state_end": api.state()}
    mfp = api.fixture("rp_vx_fp", "def f():\n    return 1\ndef g():\n    return 2\n")

    def foreign(frame, event, arg):
        return None

    def attempt_open(cov, section, fn):
        try:
            cov.run(section, fn)
            return "opened"
        except api.GateSpecError as ex:
            return api.text(str(ex)).get("code")
    r = {}
    e1, e2 = api.exp({"S1": ["rp_vx_fp:g"]}), api.exp({"S2": ["rp_vx_fp:f"]})
    t2 = api.coverage_trace(e2)

    def s1():
        mfp.g()
        with t2:
            sys.setprofile(foreign)
            try:
                return attempt_open(t2, "S2", mfp.f)
            finally:
                sys.setprofile(None)
    t1 = api.coverage_trace(e1)
    with t1:
        r["i_open_S2"] = t1.run("S1", s1)
    r["i_inner_score"] = api.score(e2, t2.record())
    e3, e4 = api.exp({"S1": ["rp_vx_fp:g"]}), api.exp({"S2": ["rp_vx_fp:f"]})
    t4 = api.coverage_trace(e4)
    with t4:
        t4.run("S2", mfp.f)
        t3 = api.coverage_trace(e3)
        with t3:
            def s1b():
                mfp.g()
                sys.setprofile(foreign)
                try:
                    return attempt_open(t4, "S2", mfp.f)
                finally:
                    sys.setprofile(None)
            r["ii_open_S2_again"] = t3.run("S1", s1b)
    r["ii_inner_score"] = api.score(e4, t4.record())
    e5 = api.exp({"A": ["rp_vx_fp:g"], "B": ["rp_vx_fp:f"]})
    errs = []

    def iii(cov):
        async def a():
            mfp.g()
            sys.setprofile(foreign)
            await asyncio.sleep(0)
            await asyncio.sleep(0)

        async def b():
            mfp.f()

        async def safe(c):
            try:
                await c
            except api.GateSpecError as ex:
                errs.append(api.text(str(ex)).get("code"))

        async def amain():
            await asyncio.gather(safe(cov.run_async("A", a)), safe(cov.run_async("B", b)))
        try:
            asyncio.run(amain())
        finally:
            sys.setprofile(None)
    r["iii"] = api.norm(trace_of(e5, iii))
    r["iii_errors"] = errs
    out["xm_foreign_profiler"] = r
    mh = api.fixture("rp_vx_hop", "def f():\n    return 1\ndef g():\n    return 2\n")
    e = api.exp({"A": ["rp_vx_hop:f"], "B": ["rp_vx_hop:g"]})

    class Once:
        def __await__(self):
            yield

    async def bbody():
        mh.g()
        await Once()
        return "b-done"
    probe = {}

    def hop(cov):
        coro = cov.run_async("B", bbody)
        t = threading.Thread(target=lambda: coro.send(None))
        t.start()
        t.join()

        def abody():
            probe["profile_none_before"] = sys.getprofile() is None
            try:
                coro.send(None)
            except StopIteration as ex:
                probe["b_result"] = ex.value
            probe["profile_none_after"] = sys.getprofile() is None
            return mh.f()
        cov.run("A", abody)
    rec = trace_of(e, hop)
    out["xm_hop_close"] = {"probe": probe, "record": api.norm(rec), "score": api.score(e, rec), "state": api.state()}
    mp_ = api.fixture("rp_vx_pb", "def f():\n    return 1\n")
    e = api.exp({"G": ["rp_vx_pb:f"]})

    def pb(cov):
        try:
            cov.run("NOT_DECLARED", mp_.f)
        except api.GateSpecError:
            pass
        cov.run("G", lambda: (mp_.f(), exec(mp_.f.__code__, {})) and None)
    rec = trace_of(e, pb)
    v = {}
    for label, edit in (("count_0", lambda r: r["sections"]["G"][0]["calls"].__setitem__("rp_vx_pb:f", 0)),
                        ("count_True", lambda r: r["sections"]["G"][0]["calls"].__setitem__("rp_vx_pb:f", True)),
                        ("undeclared_key", lambda r: r["sections"]["G"][0]["ambiguous"].__setitem__("rp_vx_pb:zz", 1))):
        rr = copy.deepcopy(rec)
        edit(rr)
        v[label] = api.score(e, rr)
    out["xm_problems_before_bad_count"] = {"problems": api.norm(rec)["problems"], "unedited": api.score(e, copy.deepcopy(rec)), "variants": v}
    import cProfile
    mpl = api.fixture("rp_vx_pl", "def f():\n    return 1\ndef g():\n    return 2\n")
    e = api.exp({"G": ["rp_vx_pl:f", "rp_vx_pl:g"]})
    prof = cProfile.Profile()

    def pl(cov):
        def body_a():
            mpl.f()
            sys.setprofile(foreign)
            mpl.g()
        try:
            cov.run("G", body_a)
        finally:
            sys.setprofile(None)

        def body_b():
            mpl.f()
            prof.enable()
            mpl.g()
        try:
            cov.run("G", body_b)
        finally:
            prof.disable()
    rec = trace_of(e, pl)
    out["xm_profiler_lost"] = {"record": api.norm(rec), "score": api.score(e, rec), "profile_none": sys.getprofile() is None}
    mst = api.fixture("rp_vx_st", "def f():\n    return 1\ndef g():\n    return 2\n")
    old = api.exp({"G": ["rp_vx_st:f"]})
    rec = trace_of(old, lambda c: c.run("G", mst.f))
    new = api.exp({"G": ["rp_vx_st:f", "rp_vx_st:g"]})
    s2 = api.spec({"G": ["rp_vx_st:f"]})
    s2["gates"]["G"]["value"] = 0.25
    only_stale = api.Experiment(api.prereg(s2))
    out["xm_target_set_before_stale"] = {"old": api.score(old, rec), "edited": api.score(new, rec), "only_stale": api.score(only_stale, rec),
                                         "metrics_edited": gate(new, rec, "G")}
    mul = api.fixture("rp_vx_ul", "def f():\n    return 1\ndef g():\n    return 2\n")
    e = api.exp({"G": ["rp_vx_ul:g"], "S": ["rp_vx_ul:f"]})
    bar, idents = threading.Barrier(2), []

    def ul(cov):
        def shard():
            idents.append(threading.get_ident())

            def body():
                mul.f()
                loop = asyncio.new_event_loop()
                try:
                    loop.call_soon(mul.g)
                    loop.call_soon(loop.stop)
                    loop.run_forever()
                finally:
                    loop.close()
                bar.wait(timeout=10)
            cov.run("S", body)
        ts = [threading.Thread(target=shard) for _ in range(2)]
        [t.start() for t in ts]
        [t.join(timeout=20) for t in ts]
        cov.run("G", lambda: None)
    rec = trace_of(e, ul)
    out["xm_uncredited_threads"] = {"distinct_threads": len(set(idents)), "uncredited": rec["uncredited"], "score": api.score(e, rec)}
    # examhole witnesses
    FX = api.fixture("rp_vx_eh", "def f(x=0): return x\ndef u(x=0): return -x\n")
    orig = FX.f.__code__
    keep = []
    e_out, e_in = api.exp({"G": ["rp_vx_eh:f"]}), api.exp({"H": ["rp_vx_eh:f"]})
    box = {}

    def ca(outer):
        def body():
            clone = types.FunctionType(FX.f.__code__, FX.f.__globals__)
            keep.append(clone)
            return clone(1)
        box["inner"] = trace_of(e_in, lambda inner: inner.run("H", body))
        keep.clear()
    rec_out = trace_of(e_out, ca)
    out["xh_clone_alive"] = {"inner": api.score(e_in, box["inner"]), "outer": api.score(e_out, rec_out), "code_restored": FX.f.__code__ is orig}

    def cc(outer):
        box["inner"] = trace_of(e_in, lambda inner: inner.run("H", lambda: (types.FunctionType(FX.f.__code__, {})(1), FX.f(1)) and None))
        outer.run("G", FX.f, 2)
    rec_out = trace_of(e_out, cc)
    r = {"inner": api.score(e_in, box["inner"]), "outer": api.score(e_out, rec_out)}
    e3, e4 = api.exp({"G": ["rp_vx_eh:f"]}), api.exp({"H": ["rp_vx_eh:f"]})

    def ccr(o3):
        def inner(i4):
            o3.run("G", lambda: (types.FunctionType(FX.f.__code__, {})(1), FX.f(1)) and None)
            i4.run("H", FX.f, 1)
        box["i4"] = trace_of(e4, inner)
    rec3 = trace_of(e3, ccr)
    r["ctrl_outer"], r["ctrl_inner"] = api.score(e3, rec3), api.score(e4, box["i4"])
    r["code_restored"] = FX.f.__code__ is orig
    out["xh_clone_called"] = r

    def cs(outer):
        minted = FX.f.__code__

        def body():
            FX.f(1)
            FX.f.__code__ = FX.u.__code__
            FX.f(1)
        box["inner"] = trace_of(e_in, lambda inner: inner.run("H", body))
        FX.f.__code__ = minted
        outer.run("G", FX.f, 2)
    rec_out = trace_of(e_out, cs)
    out["xh_code_swapped"] = {"inner": api.score(e_in, box["inner"]), "outer": api.score(e_out, rec_out), "code_restored": FX.f.__code__ is orig}
    FX.f.__code__ = orig
    ws = api.fixture("rp_vx_ws", "def f(): return 1\ndef g(): return 2\n")
    out["xh_W2a_shared"] = T({"G_fast": ["rp_vx_ws:f"], "G_slow": ["rp_vx_ws:g"]}, lambda c: c.run("run", lambda: (ws.f(), ws.g()) and None),
                             sections={"G_fast": "run", "G_slow": "run"})
    out["xh_W2b_renamed"] = T({"G": ["rp_vx_ws:f"]}, lambda c: c.run("harness", ws.f), sections={"G": "harness"})
    out["xh_W2c_cross"] = T({"X": ["rp_vx_ws:f"], "Y": ["rp_vx_ws:g"]}, lambda c: c.run("X", ws.f), lambda c: c.run("Y", ws.g),
                            sections={"X": "Y", "Y": "X"})
    wd = api.fixture("rp_vx_wd", "def f(): return 1\n")

    def _run(cfg):
        return wd.f() + cfg

    class Job:
        def _run(self):
            return wd.f()
    out["xh_W3a_helper"] = T({"G": ["rp_vx_wd:f"]}, lambda c: c.run("G", _run, 1))
    out["xh_W3b_method"] = T({"G": ["rp_vx_wd:f"]}, lambda c: c.run("G", Job()._run))

    async def _acall():
        wd.f()

    async def w3c():
        await asyncio.get_running_loop().create_task(_acall())
    out["xh_W3c_real_cut"] = T({"G": ["rp_vx_wd:f"]}, lambda c: c.run("G", asyncio.run, w3c()))
    msr = api.fixture("rp_vx_sr", "def f(x=0): return x\n")

    async def amain():
        async def child():
            msr.f(1)
        await asyncio.gather(child(), child())
    h_orig = asyncio.events.Handle._run.__code__
    st = {}
    out["xh_stop_read_before_mint"] = T({"A": ["asyncio.events:Handle._run", "rp_vx_sr:f"]},
                                        lambda c: st.__setitem__("cut_current", api.state().get("cut_current")),
                                        lambda c: c.run("A", asyncio.run, amain()))
    out["xh_stop_read_before_mint_cut"] = st
    out["xh_stop_handle_restored"] = asyncio.events.Handle._run.__code__ is h_orig
    wu = api.fixture("rp_vx_wu", "def f(): return 1\ndef g(): return 2\n")
    out["xh_W1a_swapped"] = T({"A": ["rp_vx_wu:f"], "B": ["rp_vx_wu:g"]}, lambda c: c.run("A", wu.g), lambda c: c.run("B", wu.f))
    out["xh_W1b_A_forgot"] = T({"A": ["rp_vx_wu:f"], "B": ["rp_vx_wu:g"]}, lambda c: c.run("A", wu.g),
                               lambda c: c.run("B", lambda: (wu.f(), wu.g()) and None))
    out["xh_W1c_counts"] = T({"A": ["rp_vx_wu:f"], "B": ["rp_vx_wu:f"]}, lambda c: c.run("A", wu.f), lambda c: c.run("B", wu.f))
    e = api.exp({"A": ["rp_vx_wu:f"], "B": ["rp_vx_wu:g"]})
    out["xh_W1d_metrics"] = gate(e, trace_of(e, lambda c: (c.run("A", wu.g), c.run("B", wu.f))), "A")
    api.fixture("rp_vx_wwdeco", "import functools\ndef retry(fn):\n    @functools.wraps(fn)\n    def w(*a, **k): return fn(*a, **k)\n"
                "    return w\ndef log_calls(fn):\n    @functools.wraps(fn)\n    def w(*a, **k): return fn(*a, **k)\n    return w\n"
                "def timed(fn):\n    @functools.wraps(fn)\n    def w(*a, **k): return fn(*a, **k)\n    return w\n"
                "def wraps_n(fn, n):\n    for _ in range(n):\n        fn = retry(fn)\n    return fn\n")
    wsv = api.fixture("rp_vx_wwsvc", "from rp_vx_wwdeco import retry, log_calls, timed, wraps_n\n@retry\n@log_calls\n@timed\n"
                      "def fetch(x): return x\ndef _inner(x): return x\n" + "".join(f"chain{n} = wraps_n(_inner, {n})\n" for n in range(1, 18)))
    out["xh_W4a"] = T({"G": ["rp_vx_wwsvc:fetch"]}, lambda c: c.run("G", wsv.fetch, 1))
    acc = {}
    for n in range(1, 18):
        r = T({"G": [f"rp_vx_wwsvc:chain{n}"]})
        acc[n] = r["enter"]["code"] if "enter" in r else "entered"
    out["xh_W4b_depths"] = acc
    # witness_b5
    M = api.fixture("rp_vx_w5", "def f(): return 'v1'\ndef g(): return 'g'\ndef f_v2(): return 'v2'\n")
    e_out, e_in = api.exp({"G1": ["rp_vx_w5:f"]}), api.exp({"G1": ["rp_vx_w5:f"]})
    box = {}

    def nsn(outer):
        def body():
            inner = api.coverage_trace(e_in)
            with inner:
                box["inner_run"] = api.attempt(inner.run, "G1", M.f)
            box["inner"] = inner.record()
        outer.run("G1", body)
    rec = trace_of(e_out, nsn)
    out["b5_nested_same_name"] = {"inner_run": box["inner_run"], "outer": api.score(e_out, rec), "inner": api.score(e_in, box["inner"])}
    orig = M.f.__code__
    e = api.exp({"G": ["rp_vx_w5:f"]})

    def rs(cov):
        def body():
            M.f()
            M.f.__code__ = M.f_v2.__code__
        cov.run("G", body)
    rec = trace_of(e, rs)
    out["b5_restore_swapped"] = {"score": api.score(e, rec), "f_after": M.f(), "is_v2": M.f.__code__ is M.f_v2.__code__,
                                 "is_pre": M.f.__code__ is orig}
    M.f.__code__ = orig
    hits = [0]

    def my_prof(frame, event, arg):
        hits[0] += 1
    r = {}

    def cfp(cov):
        def body():
            M.f()
            sys.setprofile(my_prof)
        cov.run("G", body)
        r["mine_after_close"] = sys.getprofile() is my_prof
        h0 = hits[0]
        M.g()
        r["called_after_close"] = hits[0] > h0
    rec = trace_of(e, cfp)
    r["mine_after_exit"] = sys.getprofile() is my_prof
    sys.setprofile(None)
    r["record"], r["score"] = api.norm(rec), api.score(e, rec)
    out["b5_close_foreign_prof"] = r

    def efi(cov):
        cov.run("G", M.f)
        sys.setprofile(my_prof)
    rec = trace_of(e, efi)
    out["b5_exit_foreign_prof_inside"] = {"mine_after_exit": sys.getprofile() is my_prof, "score": api.score(e, rec)}
    sys.setprofile(None)
    sys.setprofile(my_prof)
    try:
        def efp(cov):
            t = threading.Thread(target=cov.run, args=("G", M.f))
            t.start()
            t.join()
        rec = trace_of(e, efp)
        r = {"mine_after_exit": sys.getprofile() is my_prof}
        h0 = hits[0]
        M.g()
        r["called_after_exit"] = hits[0] > h0
    finally:
        sys.setprofile(None)
    r["score"] = api.score(e, rec)
    out["b5_exit_foreign_prof_preexisting"] = r
    return out
