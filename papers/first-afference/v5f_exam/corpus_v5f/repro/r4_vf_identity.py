"""round4/verify/ (the verifiers' repros of the identity and resolution findings), rewritten:
cache-wrapper-body-from-writable-wrapped/verify_repro.py: an lru_cache wrapper re-stamped by functools.wraps(power_ref)
inside a builder (counters in both bodies), only the reference called, only the declared wrapper called; a plain
lru_cache control called and never called; a module-level reference (the refusal, and declaring the reference
while calling the wrapper). two-cache-wrappers-share-one-mint/own_repro.py: two lru_cache wrappers of one unnamed
body in both orders, the small one declared and only the big one called; both declared in two sections; a
cache hit; two functools.wraps wrappers of one body. enter-failure-after-mint-leaks/verify_repro.py: A an audit
hook refusing the second declared function's __code__ write at enter, a later trace, the same tracer retried; C a
BaseException (pytest-timeout's shape) from SIGALRM at 60 delays across the enter (B, an exception at a line of
v5e's __enter__, is r4_id_a04_a08's injector sweep). gc-freeze-hides-live-clone/own_repro.py: a same-globals clone
kept alive and a __code__ swap onto another function, each with no freeze, gc.freeze() in the section, and after
the section. pep562-fresh-product-false-refusal/verify.py: shims A fresh, B stable, C cached, D wraps, E the callee
declared, F __getattr__ declared. pep562-message-no-module/repro.py: lazy re-exports from a submodule and from an
exec'd submodule (each refusal's code and names; the defining module's declaration accepted).
pretrace-code-swap-stub-passes-provenance/own_repro.py: baseline, a stub bound at the name, a pre-trace __code__
swap, a FunctionType(stub code, vars(mod)). pretrace-generator-objects-never-credited/verify_pretrace_gen.py:
generator and coroutine objects created before the trace, in the trace outside sections, and inside the sections.
resolution-isinstance-runs-user-code/repro.py: registries raising KeyError / AttributeError, lazy proxies whose
__class__ property has a side effect or raises, and the registries themselves declared.
wraps-over-class-wrapper-overblock/v_repro.py: variants A-F (wraps over a class-based update_wrapper decorator, and
its controls). unstarted-generator-credited-py310-311/my_repro.py: drop, close_explicit, throw_in, consumed,
never, and close at a bare yield. profile-module-refuses-on-312/repro.py: none, profile.Profile().runcall,
cProfile.Profile().runcall around the section. POSIX only (part C)."""
import asyncio, gc, random, signal, sys, types


class Alarm(BaseException):
    pass


def main(api):
    out = {}
    GSE = api.GateSpecError
    T = lambda tgt, *steps: api.trace(api.exp({"G": [tgt]}), *steps)
    # cache-wrapper
    m = api.fixture("rp_vf_restamp", "import functools\nCALLS = {'ref': 0, 'fast': 0}\nREG = {}\ndef _build():\n"
                    "    def power_ref(n):\n        CALLS['ref'] += 1\n        return sum(range(n))\n"
                    "    @functools.wraps(power_ref)\n    @functools.lru_cache(maxsize=None)\n    def power(n):\n"
                    "        CALLS['fast'] += 1\n        return n * (n - 1) // 2\n    return power, power_ref\n"
                    "power, REG['ref'] = _build()\n")
    out["restamp_ref_only"] = T("rp_vf_restamp:power", lambda c: c.run("G", m.REG["ref"], 10))
    out["restamp_ref_only_calls"] = dict(m.CALLS)
    m.power.cache_clear()
    m.CALLS.update(ref=0, fast=0)
    out["restamp_declared_only"] = T("rp_vf_restamp:power", lambda c: c.run("G", m.power, 10))
    out["restamp_declared_only_calls"] = dict(m.CALLS)
    pm = api.fixture("rp_vf_plain", "import functools\nCALLS = {'fast': 0}\n@functools.lru_cache(maxsize=None)\n"
                     "def power(n):\n    CALLS['fast'] += 1\n    return n * (n - 1) // 2\n")
    out["plain_called"] = T("rp_vf_plain:power", lambda c: c.run("G", pm.power, 10))
    out["plain_never"] = T("rp_vf_plain:power", lambda c: c.run("G", lambda: None))
    nm = api.fixture("rp_vf_named", "import functools\nCALLS = {'ref': 0, 'fast': 0}\ndef reference(n):\n"
                     "    CALLS['ref'] += 1\n    return sum(range(n))\n@functools.wraps(reference)\n"
                     "@functools.lru_cache(maxsize=None)\ndef fast(n):\n    CALLS['fast'] += 1\n    return n * (n - 1) // 2\n")
    out["named_fast"] = T("rp_vf_named:fast")
    out["named_remedy_reference_call_fast"] = T("rp_vf_named:reference", lambda c: c.run("G", nm.fast, 10))
    # two-cache
    SRC = ("import functools\ndef _mk(fn, order):\n    a = functools.lru_cache(maxsize=None)(fn); b = functools.lru_cache(maxsize=4)(fn)\n"
           "    return (a, b) if order == 0 else (b, a)\ndef _body(x):\n    return x + 1\nORDER = {order}\nif ORDER == 0:\n"
           "    big, small = _mk(_body, 0)\nelse:\n    small, big = _mk(_body, 1)\ndel _body\n")
    for order in (0, 1):
        mm = api.fixture(f"rp_vf_2c{order}", SRC.replace("{order}", str(order)))
        out[f"twocache_order{order}"] = api.trace(api.exp({"G": [f"rp_vf_2c{order}:small"]}, sections={"G": "S"}),
                                                  lambda c: c.run("S", mm.big, 7))
        out[f"twocache_order{order}_small_calls"] = mm.small.cache_info().hits + mm.small.cache_info().misses
    mb = api.fixture("rp_vf_2cboth", SRC.replace("{order}", "0"))
    out["twocache_both"] = api.trace(api.exp({"GB": ["rp_vf_2cboth:big"], "GS": ["rp_vf_2cboth:small"]}, sections={"GB": "B", "GS": "S"}),
                                     lambda c: c.run("B", mb.big, 1), lambda c: c.run("S", mb.big, 2))
    mh = api.fixture("rp_vf_2chit", SRC.replace("{order}", "0"))
    mh.big(3)
    out["twocache_hit"] = api.trace(api.exp({"G": ["rp_vf_2chit:small"]}, sections={"G": "S"}), lambda c: c.run("S", mh.big, 3))
    mw = api.fixture("rp_vf_2cwraps", "import functools\ndef _mk(fn):\n    @functools.wraps(fn)\n    def w1(*a): return fn(*a)\n"
                     "    @functools.wraps(fn)\n    def w2(*a): return fn(*a)\n    return w1, w2\ndef _body(x):\n    return x + 1\n"
                     "big, small = _mk(_body)\ndel _body\n")
    out["twocache_wraps"] = api.trace(api.exp({"G": ["rp_vf_2cwraps:small"]}, sections={"G": "S"}), lambda c: c.run("S", mw.big, 1))
    # enter-failure
    mA = api.fixture("rp_vf_ea", "def f(x=0):\n    return x\n\ndef g(x=0):\n    return x\n")
    FA, GA = mA.f.__code__, mA.g.__code__
    armed = [False]

    def audit(ev, args):
        if armed[0] and ev == "object.__setattr__" and len(args) >= 2 and args[1] == "__code__" and args[0] is mA.g:
            raise PermissionError("policy: no __code__ writes on g")
    sys.addaudithook(audit)
    expA = api.exp({"G": ["rp_vf_ea:f", "rp_vf_ea:g"]})
    trA = api.coverage_trace(expA)
    armed[0] = True
    r = {"enter": api.attempt(lambda: trA.__enter__() is trA)}
    armed[0] = False
    r["exit_after_failed_enter"] = api.attempt(lambda: bool(trA.__exit__(None, None, None)))
    r["after_failed_enter"] = {"f_restored": mA.f.__code__ is FA, "g_restored": mA.g.__code__ is GA, "state": api.state()}
    r["later"] = T("rp_vf_ea:f", lambda c: c.run("G", mA.f, 1))
    r["after_later"] = {"f_restored": mA.f.__code__ is FA, "state": api.state()}
    r["retry_enter"] = api.attempt(lambda: trA.__enter__() is trA)
    if r["retry_enter"].get("returned") is True:
        r["retry_run"] = api.attempt(trA.run, "G", lambda: (mA.f(1), mA.g(1)) and None)
        r["retry_exit"] = api.attempt(lambda: bool(trA.__exit__(None, None, None)))
    r["retry_record"] = api.record(trA)
    r["after_retry"] = {"f_restored": mA.f.__code__ is FA, "g_restored": mA.g.__code__ is GA, "state": api.state()}
    out["enter_failure_A"] = r
    mC = api.fixture("rp_vf_ec", "def f(x=0):\n    return x\n\ndef g(x=0):\n    return x\n")
    FC, GC = mC.f.__code__, mC.g.__code__
    expC = api.exp({"G": ["rp_vf_ec:f", "rp_vf_ec:g"]})

    def on_alarm(signum, frame):
        raise Alarm()
    old = signal.signal(signal.SIGALRM, on_alarm)
    seen = {"entered": 0, "alarm": 0, "leak": 0}
    try:
        for trial in range(60):
            t = api.coverage_trace(expC)
            entered = False
            try:
                signal.setitimer(signal.ITIMER_REAL, 0.00002 + (trial % 97) * 0.000003)
                with t:
                    entered = True
                signal.setitimer(signal.ITIMER_REAL, 0)
            except Alarm:
                seen["alarm"] += 1
            except GSE:
                pass
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            seen["entered"] += entered
            if mC.f.__code__ is not FC or mC.g.__code__ is not GC or api.state().get("mints"):
                seen["leak"] += 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    out["enter_failure_C"] = {"leaks": seen["leak"], "state": api.state(),
                              "later": T("rp_vf_ec:f", lambda c: c.run("G", mC.f, 1)).get("score")}
    # gc-freeze
    M = api.fixture("rp_vf_frz", "def f(x=0): return x + 1\ndef u(x=0): return -1\n")
    orig_f, orig_u = M.f.__code__, M.u.__code__
    for kind in ("clone", "uswap"):
        for fw in ("none", "in_section", "after_section"):
            keep = []

            def body(kind=kind, fw=fw, keep=keep):
                if kind == "clone":
                    c = types.FunctionType(M.f.__code__, M.f.__globals__, "f_clone")
                    keep.append(c)
                    c(1)
                else:
                    M.u.__code__ = M.f.__code__
                    M.u(1)
                if fw == "in_section":
                    gc.freeze()

            def after(c, fw=fw):
                if fw == "after_section":
                    gc.freeze()
            try:
                out[f"freeze_{kind}_{fw}"] = T("rp_vf_frz:f", lambda c: c.run("G", body), after)
            finally:
                gc.unfreeze()
                M.u.__code__ = orig_u
                keep.clear()
            out[f"freeze_{kind}_{fw}_f_restored"] = M.f.__code__ is orig_f
    # pep562 fresh
    SH = {"FRESH": "def new_api(x):\n    return x + 1\ndef __getattr__(name):\n    if name == 'old_api':\n"
                   "        def old_api(x):\n            return new_api(x)\n        return old_api\n    raise AttributeError(name)\n",
          "STABLE": "def new_api(x):\n    return x + 1\ndef _old_api(x):\n    return new_api(x)\ndef __getattr__(name):\n"
                    "    if name == 'old_api':\n        return _old_api\n    raise AttributeError(name)\n",
          "CACHED": "def new_api(x):\n    return x + 1\ndef __getattr__(name):\n    if name == 'old_api':\n        def old_api(x):\n"
                    "            return new_api(x)\n        globals()[name] = old_api\n        return old_api\n    raise AttributeError(name)\n",
          "WRAPS": "import functools\ndef new_api(x):\n    return x + 1\ndef __getattr__(name):\n    if name == 'old_api':\n"
                   "        @functools.wraps(new_api)\n        def old_api(*a, **k):\n            return new_api(*a, **k)\n"
                   "        return old_api\n    raise AttributeError(name)\n"}
    for label, src, decl in (("A_fresh", "FRESH", "old_api"), ("B_stable", "STABLE", "old_api"), ("C_cached", "CACHED", "old_api"),
                             ("D_wraps", "WRAPS", "old_api"), ("E_callee", "FRESH", "new_api"), ("F_getattr", "FRESH", "__getattr__")):
        name = f"rp_vf_pep_{label.lower()}"
        mm = api.fixture(name, SH[src])
        out[f"pep562_{label}"] = T(f"{name}:{decl}", lambda c: c.run("G", lambda: mm.old_api(1)))
    # pep562 message
    api.write("rp_vf_vpkg.__init__", "def __getattr__(name):\n    if name == 'solve':\n        from rp_vf_vpkg._impl import solve\n"
              "        return solve\n    if name == 'solve2':\n        from rp_vf_vpkg._gen import solve2\n        return solve2\n"
              "    raise AttributeError(name)\n")
    api.write("rp_vf_vpkg._impl", "def solve(x=0):\n    return x\n")
    api.write("rp_vf_vpkg._gen", "exec(compile('def solve2(x=0):\\n    return x\\n', '<string>', 'exec'), globals())\n")
    for tgt, defmod in (("rp_vf_vpkg:solve", "rp_vf_vpkg._impl:solve"), ("rp_vf_vpkg:solve2", "rp_vf_vpkg._gen:solve2")):
        out[f"pep562msg_{tgt}"] = T(tgt)
        out[f"pep562msg_{tgt}_defining"] = T(defmod)
    # pretrace code swap
    vm = api.fixture("rp_vf_vmod", "RAN = []\ndef real(x):\n    RAN.append(x)\n    return x * 2\n")
    vs = api.fixture("rp_vf_vstubs", "def stub(x):\n    return 42\n")
    captured = vm.real
    orig_fn, orig_code = vm.real, vm.real.__code__
    out["swap_0_baseline"] = T("rp_vf_vmod:real", lambda c: c.run("G", lambda: captured(1)))
    vm.real = vs.stub
    out["swap_A_stub_bound"] = T("rp_vf_vmod:real", lambda c: c.run("G", lambda: vm.real(1)))
    vm.real = orig_fn
    vm.real.__code__ = vs.stub.__code__
    out["swap_B_code_swap"] = T("rp_vf_vmod:real", lambda c: c.run("G", lambda: captured(1)))
    vm.real.__code__ = orig_code
    vm.real = types.FunctionType(vs.stub.__code__, vars(vm), "real")
    out["swap_C_functiontype"] = T("rp_vf_vmod:real", lambda c: c.run("G", lambda: vm.real(1)))
    vm.real = orig_fn
    out["swap_code_restored"] = vm.real.__code__ is orig_code
    # pretrace generator
    vg = api.fixture("rp_vf_vgen", "def stream(n):\n    for i in range(n):\n        yield i\nasync def fetch(x):\n    return x * 2\n")
    eg = api.exp({"G": ["rp_vf_vgen:stream"], "H": ["rp_vf_vgen:fetch"]})
    for when in ("pre", "in_trace", "in_section"):
        box = {}
        if when == "pre":
            box["g"], box["c"] = vg.stream(3), vg.fetch(10)

        def mk(c, when=when, box=box):
            if when == "in_trace":
                box["g"], box["c"] = vg.stream(3), vg.fetch(10)

        def g_step(c, when=when, box=box):
            return len(list(c.run("G", (lambda: list(vg.stream(3))) if when == "in_section" else (lambda: list(box["g"])))))

        def h_step(c, when=when, box=box):
            async def drive():
                return await (vg.fetch(10) if when == "in_section" else box["c"])
            return asyncio.run(c.run_async("H", drive))
        out[f"pregen_{when}"] = api.trace(eg, mk, g_step, h_step)
    # resolution isinstance
    fx = api.fixture("rp_vf_isinst", "SIDE_EFFECTS = []\ndef handler(x=0): return x\nclass _Base:\n"
                     "    def __init__(self, **kw): object.__getattribute__(self, '__dict__').update(kw)\n"
                     "class StrictKeyError(_Base):\n    def __getattribute__(self, name):\n        d = object.__getattribute__(self, '__dict__')\n"
                     "        if name in d: return d[name]\n        raise KeyError(name)\nclass StrictAttrError(_Base):\n"
                     "    def __getattribute__(self, name):\n        d = object.__getattribute__(self, '__dict__')\n"
                     "        if name in d: return d[name]\n        raise AttributeError(name)\nclass LazyOK(_Base):\n    @property\n"
                     "    def __class__(self):\n        SIDE_EFFECTS.append('setup ran')\n        return type(self)\n"
                     "class LazyUnconfigured(_Base):\n    @property\n    def __class__(self):\n        raise RuntimeError('settings are not configured')\n"
                     "strict_ke = StrictKeyError(handler=handler)\nstrict_ae = StrictAttrError(handler=handler)\n"
                     "lazy_ok = LazyOK(handler=handler)\nlazy_bad = LazyUnconfigured(handler=handler)\n")
    for path in ("strict_ae.handler", "strict_ke.handler", "lazy_ok.handler", "lazy_bad.handler", "strict_ke", "strict_ae"):
        before = len(fx.SIDE_EFFECTS)
        out[f"isinst_{path}"] = T(f"rp_vf_isinst:{path}", lambda c: c.run("G", fx.handler, 1))
        out[f"isinst_{path}_side_effects"] = len(fx.SIDE_EFFECTS) - before
    # wraps over class wrapper
    api.fixture("rp_vf_vdecos", "import functools\nclass memoize:\n    def __init__(self, fn):\n        functools.update_wrapper(self, fn)\n"
                "        self.fn, self.cache = fn, {}\n    def __call__(self, *a):\n        if a not in self.cache:\n"
                "            self.cache[a] = self.fn(*a)\n        return self.cache[a]\ndef logged(fn):\n    @functools.wraps(fn)\n"
                "    def wrapper(*a, **k):\n        return fn(*a, **k)\n    return wrapper\n")
    head = "import functools\nfrom rp_vf_vdecos import memoize, logged\n"
    VAR = {"A_logged_over_memoize": ("@logged\n@memoize\ndef fit(x):\n    return x + 1\n", "fit", "fit"),
           "B_memoize_alone": ("@memoize\ndef fit(x):\n    return x + 1\n", "fit", "fit"),
           "C_logged_alone": ("@logged\ndef fit(x):\n    return x + 1\n", "fit", "fit"),
           "D_logged_over_lru_cache": ("@logged\n@functools.lru_cache(None)\ndef fit(x):\n    return x + 1\n", "fit", "fit"),
           "E_workaround_declare_raw": ("def _fit(x):\n    return x + 1\nfit = logged(memoize(_fit))\n", "_fit", "fit"),
           "F_logged_over_local_class_wrapper": ("class localmemo:\n    def __init__(self, fn):\n        functools.update_wrapper(self, fn)\n"
                                                 "        self.fn = fn\n    def __call__(self, *a):\n        return self.fn(*a)\n"
                                                 "@logged\n@localmemo\ndef fit(x):\n    return x + 1\n", "fit", "fit")}
    for i, (vname, (src, qual, callname)) in enumerate(VAR.items()):
        mm = api.fixture(f"rp_vf_vmod{i}", head + src)
        out[f"wraps_{vname}"] = T(f"rp_vf_vmod{i}:{qual}", lambda c: c.run("G", getattr(mm, callname), 1))
    # unstarted generators
    ug = api.fixture("rp_vf_ugc", "RAN = []\ndef scan(rows):\n    RAN.append('scan')\n    for r in rows:\n        yield r\n"
                     "async def fetch(x):\n    RAN.append('fetch')\n    return x\n")
    eu = api.exp({"G": ["rp_vf_ugc:scan", "rp_vf_ugc:fetch"]})

    def drop():
        ug.scan([1])
        c = ug.fetch(1)
        c.close()

    def close_explicit():
        g = ug.scan([1])
        g.close()
        c = ug.fetch(1)
        c.close()

    def throw_in():
        g = ug.scan([1])
        try:
            g.throw(ValueError)
        except ValueError:
            pass
        c = ug.fetch(1)
        try:
            c.throw(ValueError)
        except ValueError:
            pass

    def consumed():
        list(ug.scan([1]))
        c = ug.fetch(1)
        try:
            c.send(None)
        except StopIteration:
            pass
    for lab, fn in (("drop", drop), ("close_explicit", close_explicit), ("throw_in", throw_in), ("ctrl_consumed", consumed), ("ctrl_never", lambda: None)):
        del ug.RAN[:]
        out[f"unstarted_{lab}"] = api.trace(eu, lambda c: c.run("G", fn))
        out[f"unstarted_{lab}_ran"] = list(ug.RAN)
    del ug.RAN[:]
    box = {}

    def prime(c):
        box["g"] = ug.scan([1, 2])
        next(box["g"])
        box["c"] = ug.fetch(1)
        box["n0"] = len(ug.RAN)

    def close_bare():
        box["g"].close()
        try:
            box["c"].send(None)
        except StopIteration:
            pass
    out["unstarted_close_bare_yield"] = api.trace(eu, prime, lambda c: c.run("G", close_bare))
    out["unstarted_close_bare_yield_scan_in_section"] = [x for x in ug.RAN[box.get("n0", 0):] if x == "scan"]
    # profile module
    import cProfile, profile
    pf = api.fixture("rp_vf_prof", "def g():\n    return 7\n")
    ep = api.exp({"G": ["rp_vf_prof:g"]})
    for kind in ("none", "profile", "cprofile"):
        seen = {}

        def body(seen=seen):
            seen["getprofile"] = type(sys.getprofile()).__name__
            return pf.g()

        def h(c, kind=kind, seen=seen, body=body):
            try:
                if kind == "none":
                    return c.run("G", body)
                p = (profile.Profile if kind == "profile" else cProfile.Profile)()

                def outer():
                    seen["pre_open_getprofile"] = type(sys.getprofile()).__name__
                    return c.run("G", body)
                return p.runcall(outer)
            finally:
                sys.setprofile(None)
        out[f"profile_{kind}"] = {"trace": api.trace(ep, h), **seen}
    return out
