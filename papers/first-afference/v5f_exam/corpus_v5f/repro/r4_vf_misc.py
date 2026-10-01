"""round4/verify/ (the remaining verifiers' repros), rewritten:
stale-stop-after-mint-of-handle-run/v_repro.py, v_repro2.py, v_repro2_ctl.py: tracer A on f, perturbed by an
inner tracer declaring asyncio.events:Handle._run (none, LIFO inside A, non-LIFO around A, on another thread),
then the X73 shape (asyncio.run inside section A) and the X65 shape (run_coroutine_threadsafe and
call_soon_threadsafe from another thread into a loop run inside A); _v5_state()'s cut_current before the run;
v_repro2: tracer B entered inside a task step of a loop run in A; its control without B.
fork-pool-child-nested-refusal-and-hook/v_fork_pool.py: C1 a default ProcessPoolExecutor created inside section A,
jobs opening section B; C2 workers forked inside the trace before A; C3 a ThreadPoolExecutor inside A; C4 a pool
worker forked inside the trace, probed after the parent's exit (its profiler, _v5_state()) and a clean worker
(the verifier's timing comparison is a cost, not observed); C5 multiprocessing.Pool inside A. Per-gate outcomes
through check_metrics (the verifier used the private _check_coverage). POSIX only (fork).
py310-hook-reverts-closure-writes/own_repro.py: A a finalizer observed by a helper after `del` (untraced, in a
section, under a bare Python profiler), B a worker counting into a nonlocal while the opener only reads, C a
done-flag set once by a worker (30 trials, the verifier's 100), switch interval 0.005.
recursion-walk-quadratic/own_repro.py: the declared recursive target at n 1000..8000 and the declared leaf under
undeclared padding at depths 30, 300, 3000 (outcomes and counts; the verifier's timings are costs).
exam-mut-section-decl-clauses/verify_repro.py: its harness (a declared section 'S', 'sección' and ''); the mutant
and frozen-exam half is v5e exam tooling (NOT_APPLICABLE.json). check-metrics-overflow-raises/repro.py is round 4's
f8, in r4_sc_scoring."""
import asyncio, asyncio.events, multiprocessing as mp, os, sys, threading, time, warnings
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

JOBS = '''
import os, sys
import rp_vf_fp
COV = None
def job(i):
    try:
        COV.run("B", rp_vf_fp.g)
        return ["ok"]
    except BaseException as ex:
        msg = str(ex)
        return [type(ex).__name__, msg[4:msg.index("]")] if msg.startswith("[V5:") else ""]
def probe(_):
    st = {}
    try:
        st = dict(COV and __import__("sys").modules.get("v5f_repro_impl")._v5_state() or {})
        st.pop("pid", None)
    except BaseException as ex:
        st = {"raised": type(ex).__name__}
    return {"getprofile_none": sys.getprofile() is None, "state": st}
'''


def main(api):
    out = {}
    vm = api.fixture("rp_vf_stale", "def f(x=0):\n    return x\n")
    EA, EB = api.exp({"A": ["rp_vf_stale:f"]}), api.exp({"B": ["asyncio.events:Handle._run"]})

    def x73_main():
        async def child():
            vm.f(1)

        async def m():
            await asyncio.gather(child(), child())
        return m()

    def x65_body():
        async def job():
            vm.f(2)

        async def m():
            loop = asyncio.get_running_loop()
            done = asyncio.Event()

            def submitter():
                asyncio.run_coroutine_threadsafe(job(), loop).result(10)
                loop.call_soon_threadsafe(vm.f, 3)
                loop.call_soon_threadsafe(done.set)
            t = threading.Thread(target=submitter)
            t.start()
            await done.wait()
            t.join()
        asyncio.run(m())

    def inner():
        return api.trace(EB)
    for shape in ("x73", "x65"):
        for perturb in ("none", "lifo", "nonlifo", "thread"):
            r = {}
            try:
                if perturb == "nonlifo":
                    b = api.coverage_trace(EB)
                    r["b_enter"] = api.attempt(lambda: b.__enter__() is b)
                    a = api.coverage_trace(EA)
                    a.__enter__()
                    r["b_exit"] = api.attempt(lambda: bool(b.__exit__(None, None, None)))
                else:
                    a = api.coverage_trace(EA)
                    a.__enter__()
                    if perturb == "lifo":
                        r["inner"] = inner()
                    elif perturb == "thread":
                        box = {}
                        t = threading.Thread(target=lambda: box.__setitem__("inner", inner()))
                        t.start()
                        t.join()
                        r["inner"] = box.get("inner")
                r["cut_current"] = api.state().get("cut_current")
                if shape == "x73":
                    r["run"] = api.attempt(a.run, "A", asyncio.run, x73_main())
                else:
                    r["run"] = api.attempt(a.run, "A", x65_body)
                a.__exit__(None, None, None)
                r["score"] = api.score(EA, a.record())
            except BaseException as ex:                # noqa: BLE001
                r["escaped"] = type(ex).__name__
            out[f"stale_{shape}_{perturb}"] = r
    out["stale_handle_run_state"] = api.state()

    async def main_task():
        r = api.trace(EB, lambda c: vm.f(9))
        return r

    async def main_ctl():
        vm.f(9)
    out["stale_v_repro2"] = api.trace(EA, lambda c: str(c.run("A", asyncio.run, main_task())))
    out["stale_v_repro2_ctl"] = api.trace(EA, lambda c: c.run("A", asyncio.run, main_ctl()))
    # fork pool
    warnings.simplefilter("ignore", DeprecationWarning)
    fp = api.fixture("rp_vf_fp", "def f():\n    return 1\n\ndef g():\n    return 2\n")
    jobs = api.fixture("rp_vf_fp_jobs", JOBS)
    s = api.spec({"A": ["rp_vf_fp:f"], "B": ["rp_vf_fp:g"]})
    s["gates"]["A"]["metric"], s["gates"]["B"]["metric"] = "a", "b"
    exp = api.Experiment(api.prereg(s))
    ctx = mp.get_context("fork")

    def collect(futs):
        res = []
        for fu in futs:
            try:
                res.append(fu.result(timeout=30))
            except BaseException as ex:                # noqa: BLE001
                res.append([type(ex).__name__])
        return res

    def per_gate(cov):
        try:
            cm = exp.check_metrics({"a": 1.0, "b": 1.0, "coverage_trace": cov.record()})
            return {k: v for k, v in api.metrics(exp, {"a": 1.0, "b": 1.0, "coverage_trace": cov.record()}).items() if k.endswith(":exercises")} if cm else None
        except BaseException as ex:                    # noqa: BLE001
            return {"raised": type(ex).__name__}
    for case in ("C1", "C2", "C3", "C5"):
        box = {}
        cov = api.coverage_trace(exp)
        jobs.COV = cov
        try:
            with cov:
                if case == "C1":
                    def a():
                        fp.f()
                        with ProcessPoolExecutor(2, mp_context=ctx) as ex:
                            box["jobs"] = collect([ex.submit(jobs.job, i) for i in range(2)])
                    cov.run("A", a)
                elif case == "C2":
                    with ProcessPoolExecutor(2, mp_context=ctx) as ex:
                        ex.submit(int, 0).result(timeout=30)

                        def a():
                            fp.f()
                            box["jobs"] = collect([ex.submit(jobs.job, i) for i in range(2)])
                        cov.run("A", a)
                elif case == "C3":
                    def a():
                        fp.f()
                        with ThreadPoolExecutor(2) as ex:
                            box["jobs"] = collect([ex.submit(jobs.job, i) for i in range(2)])
                    cov.run("A", a)
                else:
                    def a():
                        fp.f()
                        with ctx.Pool(2) as pool:
                            ars = [pool.apply_async(jobs.job, (i,)) for i in range(2)]
                            res = []
                            for ar in ars:
                                try:
                                    res.append(ar.get(timeout=30))
                                except BaseException as ex:  # noqa: BLE001
                                    res.append([type(ex).__name__])
                            box["jobs"] = res
                    cov.run("A", a)
        except BaseException as ex:                    # noqa: BLE001
            box["with"] = type(ex).__name__
        box["record"] = api.record(cov)
        box["gates"] = per_gate(cov)
        out[f"forkpool_{case}"] = box
    ex = ProcessPoolExecutor(1, mp_context=ctx)
    cov = api.coverage_trace(exp)
    jobs.COV = cov
    with cov:
        cov.run("A", lambda: (fp.f(), ex.submit(int, 0).result(timeout=30)) and None)
    out["forkpool_C4_parent_getprofile_none"] = sys.getprofile() is None
    out["forkpool_C4_worker_probe"] = ex.submit(jobs.probe, 0).result(timeout=30)
    ex.shutdown()
    ex2 = ProcessPoolExecutor(1, mp_context=ctx)
    jobs.COV = None
    out["forkpool_C4_clean_probe"] = ex2.submit(jobs.probe, 0).result(timeout=30)
    ex2.shutdown()
    # py310 A/B/C
    m = api.fixture("rp_vf_py310", "def tgt():\n    return 1\n")
    e310 = api.exp({"G": ["rp_vf_py310:tgt"]})
    log = []

    class Res:
        def __del__(self):
            log.append("finalized")

    def observe():
        return list(log)

    def case_a():
        log.clear()
        r = Res()
        len(log)
        del r
        seen = observe()
        m.tgt()
        return len(seen)

    def case_b(N=200_000):
        counter = 0

        def worker():
            nonlocal counter
            for _ in range(N):
                counter += 1
        t = threading.Thread(target=worker)
        t.start()
        while t.is_alive():
            len(log)
        t.join()
        m.tgt()
        return N - counter

    def case_c(trials=30, deadline=0.05):
        reverted = 0
        for _ in range(trials):
            done = False
            go = threading.Event()

            def worker():
                nonlocal done
                go.wait()
                done = True
            t = threading.Thread(target=worker)
            t.start()
            go.set()
            end = time.monotonic() + deadline
            while not done and time.monotonic() < end:
                len(log)
            t.join()
            time.sleep(0)
            if not done:
                reverted += 1
        m.tgt()
        return reverted
    old = sys.getswitchinterval()
    sys.setswitchinterval(0.005)
    try:
        r = {"A_untraced": case_a(), "B_untraced": case_b(), "C_untraced": case_c()}
        r["traced"] = api.trace(e310, lambda c: c.run("G", case_a), lambda c: c.run("G", case_b), lambda c: c.run("G", case_c))
        sys.setprofile(lambda f, e, a: None)
        try:
            r["A_bare_py_profiler"] = case_a()
        finally:
            sys.setprofile(None)
    finally:
        sys.setswitchinterval(old)
    out["py310"] = r
    # recursion
    rq = api.fixture("rp_vf_rq", "def rec(n):\n    return 0 if n == 0 else 1 + rec(n - 1)\n"
                     "def twin(n):\n    return 0 if n == 0 else 1 + twin(n - 1)\ndef leaf():\n    return 1\n"
                     "def leaf2():\n    return 1\ndef pad(d, k):\n    if d == 0:\n        s = 0\n        for _ in range(k):\n"
                     "            s += leaf()\n        return s\n    return pad(d - 1, k)\ndef pad_twin(d, k):\n    if d == 0:\n"
                     "        s = 0\n        for _ in range(k):\n            s += leaf2()\n        return s\n    return pad_twin(d - 1, k)\n")
    er = api.exp({"G": ["rp_vf_rq:rec"], "H": ["rp_vf_rq:leaf"]})
    res = {}
    lim = sys.getrecursionlimit()
    sys.setrecursionlimit(100000)
    st = threading.stack_size(256 * 1024 * 1024)
    try:
        def run():
            for d in (30, 300, 3000):
                res[f"pad_{d}"] = api.trace(er, lambda c: c.run("H", rq.pad, d, 2000), lambda c: c.run("H", rq.pad_twin, d, 2000),
                                            lambda c: c.run("G", rq.rec, 1))
            for n in (1000, 2000, 4000, 8000):
                res[f"rec_{n}"] = api.trace(er, lambda c: c.run("G", rq.twin, n), lambda c: c.run("G", rq.rec, n), lambda c: c.run("H", rq.leaf))
        t = threading.Thread(target=run)
        t.start()
        t.join()
    finally:
        threading.stack_size(st)
        sys.setrecursionlimit(lim)
    out["recursion"] = res
    # exam-mut-section-decl harness
    sd = api.fixture("rp_vf_sd", "def f():\n    return 1\n")
    for sec in ("S", "sección", ""):
        r = {}
        try:
            e = api.exp({"G": ["rp_vf_sd:f"]}, sections={"G": sec})
            r["parse"] = "accepted"
            r["trace"] = api.trace(e, lambda c: c.run(sec, sd.f))
        except api.GateSpecError as ex:
            r["parse"] = api.text(str(ex))
        out[f"section_decl_{sec!r}"] = r
    return out
