"""round4/verify/ (the verifiers' repros of the lifecycle findings), rewritten. Where a verifier injected at a
named line of v5e's private source (v_inject.py's windows in _close/_open, v_det.py's line after the restore in
__exit__, verify_repro.py's try-body line of _own_dict, own_repro.py's c_call of sys.getrefcount in __exit__), v5f's
text defines the fault points instead (_v5_faultpoints(), the harness rules' id-5 injector): the exception is
raised by the injector at instruction n (1, 3, 10, 30) of the named v5f fault-point code objects.
hook-self-removal-uninstalls-chaining-profiler/own_repro.py: a user profiler started inside the section (plain,
chain_all, chain_py), installed after the close and after the exit, later calls it saw.
interrupted-exit-stays-active/own_repro.py: entry-profiler (a profile function raising at the call event of
v5f's _CoverageTracer.__exit__ code), mid (the injector in the exit's fault points), entry-signal (SIGALRM
repeating every 50 us, the handler raising when its frame is the __exit__ code; 200 iterations); each followed by
record(), _v5_state(), three later clean traces and a run on the dead tracer.
async-exception-in-close-leaks-threads-registry/v_inject.py: a Timeout injected in the second of three sections
(fault points _open, _commit, _detach, _run); the hook state after the last close, the record, a second tracer.
interrupted-exit-poisons-later-entries/v_det.py: a Timeout injected in the exit (_exit, _exit_txn, _retire); later
traces with the same prereg, another prereg, and an unrelated target.
resolution-swallows-signal-exception/verify_repro.py: part A, a Timeout injected in _own_dict / _resolve_target
during the enter for a wraps wrapper from another module and an lru_cache target (controls before and after);
part B, a real SIGALRM at random.Random(7) delays, 40 enters per target.
hook-exception-leaves-lock-held/own_repro.py: 200 cycles of cov.run under a random (Random(7)) SIGALRM raising
Timeout, then the same raising KeyboardInterrupt; the guard after each raised cycle; a worker-thread section
joined with a 3 s bound.
reentry-race-double-entry/own_repro.py: A (sequential second enter), B (two threads, the declared module's import
sleeps 0.3 s), C (module pre-imported, 30 races; the verifier's 300), D (a PEP 562 lazy export sleeping 0.2 s while
an outer tracer holds the mint), E (one thread waits inside resolution while the other enters, runs and exits).
Timing-dependent parts are envelope. POSIX only."""
import collections, functools, importlib, random, signal, sys, threading, time


class Timeout(Exception):
    pass


def main(api):
    out = {}
    fp = api.P._v5_faultpoints()
    GSE = api.GateSpecError

    def code_of(ex):
        m = str(ex)
        return m[4:m.index("]")] if m.startswith("[V5:") and "]" in m else type(ex).__name__
    # hook-self-removal
    cm = api.fixture("rp_vf_chain", "def target():\n    return 1\ndef after():\n    return 2\n")
    e = api.exp({"G": ["rp_vf_chain:target"]})
    for mode in ("plain", "chain_all", "chain_py"):
        st = {"seen_after": 0, "prev": None}

        def prof(frame, event, arg, st=st, mode=mode):
            if event == "call" and frame.f_code.co_name == "after":
                st["seen_after"] += 1
            prev = st["prev"]
            if prev is None or mode == "plain":
                return
            if mode == "chain_py" and event not in ("call", "return"):
                return
            prev(frame, event, arg)

        def body(st=st, prof=prof):
            st["prev"] = sys.getprofile()
            sys.setprofile(prof)
            cm.target()
        r = {}

        def after(c, prof=prof, r=r):
            r["installed_after_close"] = sys.getprofile() is prof
            for _ in range(5):
                cm.after()
        try:
            r["trace"] = api.trace(e, lambda c: c.run("G", body), after)
            r["installed_after_exit"] = sys.getprofile() is prof
        finally:
            sys.setprofile(None)
        r["found_profiler"] = st["prev"] is not None
        r["after_seen"] = st["seen_after"]
        out[f"chain_{mode}"] = r
    # interrupted-exit-stays-active
    wm = api.fixture("rp_vf_iesa", "def work(x=0):\n    return x + 1\n")
    ew = api.exp({"G": ["rp_vf_iesa:work"]})
    EXIT = fp.get("_CoverageTracer.__exit__")

    def report(cov):
        r = {"record": api.record(cov), "state": api.state()}
        r["later"] = [api.trace(ew, lambda c: c.run("G", wm.work, 1)).get("score") for _ in range(3)]
        r["state_after_later"] = api.state()
        r["dead_tracer_run"] = api.attempt(cov.run, "G", wm.work, 5)
        return r

    def fault(frame, event, arg):
        if event == "call" and frame.f_code is EXIT:
            raise Timeout("fault at __exit__'s call event")
    cov = api.coverage_trace(ew)
    try:
        with cov:
            cov.run("G", wm.work, 1)
            sys.setprofile(fault)
        res = "exit completed"
    except Timeout:
        res = "Timeout"
    finally:
        sys.setprofile(None)
    out["iesa_entry_profiler"] = {"raised": res, **report(cov)}
    for n in (1, 3, 10, 30):
        cov = api.coverage_trace(ew)
        cov.__enter__()
        cov.run("G", wm.work, 1)
        dis = api.inject(("_CoverageTracer.__exit__", "_exit", "_exit_txn"), n, Timeout)
        try:
            cov.__exit__(None, None, None)
            res = "exit completed"
        except Timeout:
            res = "Timeout"
        finally:
            inj = dis()
        out[f"iesa_mid_{n}"] = {"raised": res, "injector": inj, **report(cov)}
    hits = {"n": 0}

    def h_entry(signum, frame):
        if frame is not None and frame.f_code is EXIT and hits["n"] == 0:
            hits["n"] += 1
            raise Timeout("SIGALRM at __exit__ entry")
    old = signal.signal(signal.SIGALRM, h_entry)
    signal.setitimer(signal.ITIMER_REAL, 0.00005, 0.00005)
    sig = {"iterations": 0, "hit": False}
    try:
        for _ in range(200):
            sig["iterations"] += 1
            cov = api.coverage_trace(ew)
            try:
                with cov:
                    cov.run("G", wm.work, 1)
            except Timeout:
                sig["hit"] = True
                break
            except GSE:
                pass
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0, 0)
        signal.signal(signal.SIGALRM, old)
    if sig["hit"]:
        sig.update(report(cov))
    sig["iterations"] = None
    out["iesa_entry_signal"] = sig
    # v_inject
    vi = api.fixture("rp_vf_inj", "def f():\n    return 1\n")
    ei = api.exp({"G": ["rp_vf_inj:f"]})
    for keys in (("_open",), ("_commit",), ("_detach",), ("_run",)):
        for n in (1, 3, 10, 30):
            cov = api.coverage_trace(ei)
            r = {}
            with cov:
                cov.run("G", vi.f)
                dis = api.inject(keys, n, Timeout)
                try:
                    cov.run("G", vi.f)
                    r["second"] = "returned"
                except Timeout:
                    r["second"] = "Timeout"
                except BaseException as ex:            # noqa: BLE001
                    r["second"] = code_of(ex)
                finally:
                    r["injector"] = dis()
                r["third"] = api.attempt(cov.run, "G", vi.f)
                r["profile_after_last_close_none"] = sys.getprofile() is None
            r["record"] = api.record(cov)
            r["state"] = api.state()
            r["tracer2"] = api.trace(api.exp({"G": ["rp_vf_inj:f"]}), lambda c: c.run("G", vi.f))
            out[f"inject_{keys[0]}_{n}"] = r
    # v_det
    tm = api.fixture("rp_vf_det", "def g(x):\n    return x + 1\n")
    oth = api.fixture("rp_vf_det_other", "def h(x):\n    return x\n")
    ed = api.exp({"G": ["rp_vf_det:g"]})
    for n in (1, 3, 10, 30):
        cov = api.coverage_trace(ed)
        cov.__enter__()
        cov.run("G", tm.g, 1)
        dis = api.inject(("_exit", "_exit_txn", "_retire"), n, Timeout)
        try:
            cov.__exit__(None, None, None)
            res = "exit completed"
        except Timeout:
            res = "Timeout"
        finally:
            inj = dis()
        out[f"vdet_{n}"] = {"raised": res, "injector": inj, "record": api.record(cov), "state": api.state(),
                            "same_prereg": api.trace(ed, lambda c: c.run("G", tm.g, 2)).get("score"),
                            "other_prereg": api.trace(api.exp({"H": ["rp_vf_det:g"]}), lambda c: c.run("H", tm.g, 2)).get("score"),
                            "unrelated": api.trace(api.exp({"G": ["rp_vf_det_other:h"]}), lambda c: c.run("G", oth.h, 1)).get("score")}
    # resolution-swallows
    api.fixture("rp_vf_rsig_deco", "import functools\ndef logged(fn):\n    @functools.wraps(fn)\n    def wrapper(*a, **k):\n"
                                   "        return fn(*a, **k)\n    return wrapper\n")
    rm = api.fixture("rp_vf_rsig", "import functools\nfrom rp_vf_rsig_deco import logged\n@logged\ndef entry(x=0):\n"
                                   "    return x + 1\n@functools.lru_cache(None)\ndef cached(x=0):\n    return x * 2\n")
    EXP = {t: api.exp({"G": [t]}) for t in ("rp_vf_rsig:entry", "rp_vf_rsig:cached")}

    def control(t):
        return api.trace(EXP[t], lambda c: c.run("G", lambda: (rm.cached.cache_clear(), rm.entry(1), rm.cached(1)) and None)).get("score")
    for t in EXP:
        out[f"rsig_control_before_{t}"] = control(t)
        for keys in (("_own_dict",), ("_resolve_target",)):
            for n in (1, 3, 10):
                dis = api.inject(keys, n, Timeout)
                try:
                    with api.coverage_trace(EXP[t]):
                        pass
                    res = "entered"
                except Timeout:
                    res = "Timeout propagated"
                except GSE as ex:
                    chain, x = [], ex
                    while x is not None:
                        chain.append(type(x).__name__)
                        x = x.__cause__ or x.__context__
                    res = code_of(ex) + " chain=" + ">".join(chain)
                finally:
                    inj = dis()
                out[f"rsig_A_{t}_{keys[0]}_{n}"] = {"outcome": res, "injector": inj}
        out[f"rsig_control_after_{t}"] = control(t)

    def raise_timeout(signum, frame):
        raise Timeout("SIGALRM budget")
    old = signal.signal(signal.SIGALRM, raise_timeout)
    try:
        for t in EXP:
            rnd, seen = random.Random(7), collections.Counter()
            for _ in range(40):
                try:
                    try:
                        signal.setitimer(signal.ITIMER_REAL, rnd.uniform(0.000003, 0.00008))
                        with api.coverage_trace(EXP[t]):
                            pass
                    finally:
                        signal.setitimer(signal.ITIMER_REAL, 0)
                    seen["no signal inside"] += 1
                except Timeout:
                    seen["Timeout propagated"] += 1
                except GSE as ex:
                    has, x = False, ex
                    while x is not None:
                        has |= isinstance(x, Timeout)
                        x = x.__cause__ or x.__context__
                    seen[f"{code_of(ex)} ({'Timeout chained' if has else 'Timeout LOST'})"] += 1
            out[f"rsig_B_{t}"] = dict(sorted(seen.items()))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    # hook-exception-leaves-lock-held
    lm = api.fixture("rp_vf_lock", "def work(x=0):\n    return x + 1\n")
    el = api.exp({"G": ["rp_vf_lock:work"]})
    for kind, EXC in (("timeout", Timeout), ("kbi", KeyboardInterrupt)):
        ARMED = [False]

        def h(signum, frame, ARMED=ARMED, EXC=EXC):
            if ARMED[0]:
                ARMED[0] = False
                raise EXC()
        old = signal.signal(signal.SIGALRM, h)
        rnd = random.Random(7)
        r = {"raised": 0, "guard_not_free_after_raise": 0}
        try:
            with api.coverage_trace(el) as cov:
                for _ in range(200):
                    try:
                        try:
                            ARMED[0] = True
                            signal.setitimer(signal.ITIMER_REAL, rnd.uniform(0.00001, 0.0003))
                            cov.run("G", lm.work, 1)
                        finally:
                            signal.setitimer(signal.ITIMER_REAL, 0)
                            ARMED[0] = False
                    except EXC:
                        r["raised"] += 1
                        if api.state().get("guard") != "free":
                            r["guard_not_free_after_raise"] += 1
                    except GSE:
                        pass
                done = threading.Event()

                def job():
                    try:
                        cov.run("G", lm.work, 2)
                    finally:
                        done.set()
                w = threading.Thread(target=job, daemon=True)
                w.start()
                w.join(3.0)
                r["worker_finished"] = done.is_set()
        except BaseException as ex:                    # noqa: BLE001
            r["with"] = code_of(ex)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
        r["raised"] = r["raised"] > 0
        r["state"] = api.state()
        out[f"lock_{kind}"] = r
    # reentry-race
    ra = api.fixture("rp_vf_ra", "def f(): return 1\n")
    ea = api.exp({"G": ["rp_vf_ra:f"]})
    cov = api.coverage_trace(ea)
    with cov:
        out["reentry_A_second"] = api.attempt(lambda: cov.__enter__() is cov)
        cov.run("G", ra.f)
    out["reentry_A_record"] = api.record(cov)

    def race(cov, body):
        start, inside, res = threading.Barrier(2), threading.Barrier(2, timeout=3), {}

        def worker(i):
            start.wait()
            try:
                with cov:
                    cov.run("G", body)
                    try:
                        inside.wait()
                    except threading.BrokenBarrierError:
                        pass
                res[i] = "entered"
            except BaseException as ex:                # noqa: BLE001
                res[i] = code_of(ex)
                try:
                    inside.abort()
                except Exception:                      # noqa: BLE001
                    pass
        ts = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        [t.start() for t in ts]
        [t.join(10) for t in ts]
        return "|".join(sorted(res.values()))
    api.write("rp_vf_rb", "import time\ntime.sleep(0.3)\ndef f(): return 1\n")
    eb = api.exp({"G": ["rp_vf_rb:f"]})
    cov = api.coverage_trace(eb)
    out["reentry_B"] = {"workers": race(cov, lambda: sys.modules["rp_vf_rb"].f()), "record": api.record(cov), "state": api.state()}
    rc = api.fixture("rp_vf_rc", "def f(): return 1\ndef g(): return 2\n")
    ec = api.exp({"G": ["rp_vf_rc:f", "rp_vf_rc:g"]})
    seen = collections.Counter()
    for _ in range(30):
        seen[race(api.coverage_trace(ec), lambda: (rc.f(), rc.g()) and None)] += 1
    out["reentry_C"] = dict(sorted(seen.items()))
    rd = api.fixture("rp_vf_rd", "import time\ndef _lazy_f(): return 1\ndef __getattr__(name):\n    if name == 'f':\n"
                                 "        time.sleep(0.2)\n        return _lazy_f\n    raise AttributeError(name)\n")
    edd = api.exp({"G": ["rp_vf_rd:f"]})
    outer = api.coverage_trace(api.exp({"H": ["rp_vf_rd:f"]}))
    r = {}
    try:
        with outer:
            cov = api.coverage_trace(edd)
            r["workers"] = race(cov, lambda: rd._lazy_f())
    except BaseException as ex:                        # noqa: BLE001
        r["outer"] = code_of(ex)
    r["record"] = api.record(cov)
    r["state"] = api.state()
    out["reentry_D"] = r
    re_ = api.fixture("rp_vf_re", "import threading\nGATE = threading.Event()\nSLOW = set()\ndef _lazy_f(): return 1\n"
                                  "def __getattr__(name):\n    if name == 'f':\n        if threading.get_ident() in SLOW:\n"
                                  "            GATE.wait(5)\n        return _lazy_f\n    raise AttributeError(name)\n")
    ee = api.exp({"G": ["rp_vf_re:f"]})
    cov = api.coverage_trace(ee)
    res = {}

    def slow():
        re_.SLOW.add(threading.get_ident())
        try:
            with cov:
                cov.run("G", re_._lazy_f)
            res["t2"] = "entered"
        except BaseException as ex:                    # noqa: BLE001
            res["t2"] = code_of(ex)
    t2 = threading.Thread(target=slow)
    t2.start()
    time.sleep(0.2)
    try:
        with cov:
            cov.run("G", re_._lazy_f)
        res["t1"] = "entered"
    except BaseException as ex:                        # noqa: BLE001
        res["t1"] = code_of(ex)
    re_.GATE.set()
    t2.join(10)
    res["record"] = api.record(cov)
    res["state"] = api.state()
    out["reentry_E"] = res
    return out
