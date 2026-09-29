"""cover_driver_v5f.py: G_COVER's frozen direct-call driver (revision 2, BF1; revision 3, N7).

Written by the exam author from M6's and M9's text. It builds FunctionType(code, vars(module)) from the
_v5_faultpoints() code object of each named function (_on_entry, _on_exit, _on_unwind, _outcome, _publish,
_forget_in_child) and calls it directly, outside any callback, inside real traces opened through the
public API. _on_entry, _on_exit and _on_unwind are called from one trampoline frame built as
FunctionType(trampoline_code, vars(<target module>)), so that frame is the target's frame for them and the
same invocation makes the entry call and its exit or unwind call.

Frozen scenarios, one per branch of M6 and M9:
  non_minted       a code that is not minted (every callback returns at its first test);
  cut_moved        a CUT_MOVED binding (Handle._run rebound to the driver's fresh wrapper during a hit);
  clone_called     foreign globals (the trampoline built on another dict: CLONE_CALLED);
  no_anchor        a trace entered with no section open anywhere;
  kind_c           outcome c (one opening of the holder on the stack);
  kind_a           outcome a (V28b's manual hop: two openings of one core on the stack);
  kind_d           outcome d (a cut frame: dispatched through a stdlib loop's Handle._run);
  kind_d_loop      outcome d by the loop boundary (an anchor whose loop is not the running loop);
  kind_u           outcome u (no anchor of the holder on the stack, an anchor registered elsewhere);
  two_holders      two tracers declaring the target;
  py_return        PY_RETURN (_on_exit);
  unwind_at_entry  PY_UNWIND at the entry offset (no publication);
  unwind_past      PY_UNWIND past the entry offset (publication);
  after_stop       a publication after the credit stop (the tracer exits between entry and exit);
  forget_noop      _forget_in_child before any tracer (the no-op), in a spawned subprocess;
  forget_ours      _forget_in_child with a mint, an open section and a pending entry, as its last step;
  forget_foreign   _forget_in_child with styxx's id held by another tool and the mint's code swapped.

Usage: python cover_driver_v5f.py [--impl PATH] [--out RESULT.json] [--scenario NAME]
The driver itself runs every scenario under linecov_v5f.py and reports which lines of the named functions
it reached (G_COVER counts it for the named list only).
"""
import json, os, subprocess, sys, types

HERE = os.path.dirname(os.path.abspath(__file__))
NAMED = ("_on_entry", "_on_exit", "_on_unwind", "_outcome", "_publish", "_forget_in_child")
CHILD_SCENARIOS = ("forget_noop", "forget_ours", "forget_foreign")


def _args():
    a = sys.argv[1:]
    def opt(n, d=None):
        return a[a.index(n) + 1] if n in a else d
    return opt("--impl", os.path.join(HERE, "ref_v5f.py")), opt("--out"), opt("--scenario"), opt("--linecov")


IMPL, OUT, ONLY, LINECOV_FILE = _args()


def _load_runner():
    """The frozen runner as a library: fixtures, preregs, the implementation (P)."""
    sys.argv = [os.path.join(HERE, "run_protocol_v5f_exam.py"), "--impl", IMPL]
    sys.path.insert(0, HERE)
    import importlib
    return importlib.import_module("run_protocol_v5f_exam")


def trampoline(on_entry, on_exit, on_unwind, code, exit_off, mode, mid):
    """One frame for the entry call and its exit or unwind call (the target's frame)."""
    on_entry(code, 0)
    if mid is not None:
        mid()
    if mode == "return":
        on_exit(code, exit_off, None)
    elif mode == "unwind_at":
        on_unwind(code, 0, ValueError("driver"))
    elif mode == "unwind_past":
        on_unwind(code, exit_off, ValueError("driver"))


def _fns(R):
    fp = R.P._v5_faultpoints()
    g = vars(R.P)
    return {k: types.FunctionType(fp[k], g, k) for k in NAMED}


def _tramp(R, globals_):
    return types.FunctionType(trampoline.__code__, globals_, "tramp")


def scenarios(R):
    import asyncio, threading
    P, EXP, fx = R.P, R.EXP, R.fx_v5f
    fns = _fns(R)
    T = _tramp(R, vars(fx))
    E, X, U = fns["_on_entry"], fns["_on_exit"], fns["_on_unwind"]

    def hit(mode="return", mid=None, tramp=None, code=None):
        (tramp or T)(E, X, U, code or fx.f.__code__, 2, mode, mid)

    out = {}

    def run(name, fn):
        if ONLY and name != ONLY:
            return
        try:
            out[name] = fn()
        except Exception as e:                            # noqa: BLE001
            out[name] = f"raised {type(e).__name__}: {e}"[:300]

    def rec_of(exp, cov):
        r = cov.record()
        return {"score": R.any_score(exp, r), "problems": [p[:60] for p in r["problems"]],
                "uncredited": r["uncredited"]}

    def non_minted():
        exp = EXP("F")
        with P.coverage_trace(exp) as cov:
            cov.run("G", lambda: (hit(code=fx.g.__code__), fx.f()))
        return rec_of(exp, cov)

    def cut_moved():
        H = asyncio.events.Handle
        run0 = H.__dict__["_run"]
        exp = EXP("F")
        with P.coverage_trace(exp) as cov:
            def body():
                H._run = fx_driver_wrapper()
                try:
                    hit()
                finally:
                    H._run = run0
            cov.run("G", body)
        return rec_of(exp, cov)

    def clone_called():
        exp = EXP("F")
        with P.coverage_trace(exp) as cov:
            cov.run("G", lambda: hit(tramp=_tramp(R, dict(vars(fx)))))
        return rec_of(exp, cov)

    def no_anchor():
        exp = EXP("F")
        with P.coverage_trace(exp) as cov:
            hit()
            cov.run("G", fx.f)
        return rec_of(exp, cov)

    def kind_c():
        exp = EXP("F")
        with P.coverage_trace(exp) as cov:
            cov.run("G", hit)
        return rec_of(exp, cov)

    def kind_a():
        exp = EXP("AB")
        class Once:
            def __await__(self):
                yield
        async def bfn():
            await Once()
            hit()
        with P.coverage_trace(exp) as cov:
            co = cov.run_async("B", bfn)
            th = threading.Thread(target=co.send, args=(None,))
            th.start(); th.join()
            def body():
                try:
                    co.send(None)
                except StopIteration:
                    pass
            cov.run("A", body)
        return rec_of(exp, cov)

    def kind_d():
        exp = EXP("F")
        with P.coverage_trace(exp) as cov:
            L = asyncio.new_event_loop()
            try:
                async def via_loop():
                    L.call_soon(hit)
                    await asyncio.sleep(0)
                cov.run("G", L.run_until_complete, via_loop())
            finally:
                L.close()
        return rec_of(exp, cov)

    def kind_d_loop():
        # the loop boundary: G's anchor was registered with no running loop; the hit runs while a loop is
        # set running (asyncio.events._set_running_loop, a stdlib private name), with no cut frame between
        exp = EXP("F")
        with P.coverage_trace(exp) as cov:
            L = asyncio.new_event_loop()
            def body():
                asyncio.events._set_running_loop(L)
                try:
                    hit()
                finally:
                    asyncio.events._set_running_loop(None)
            try:
                cov.run("G", body)
            finally:
                L.close()
        return rec_of(exp, cov)

    def kind_u():
        exp = EXP("F")
        go, done = threading.Event(), threading.Event()
        with P.coverage_trace(exp) as cov:
            def body():
                go.set()
                done.wait(10)
            th = threading.Thread(target=cov.run, args=("G", body))
            th.start()
            go.wait(10)
            hit()
            done.set()
            th.join()
        return rec_of(exp, cov)

    def two_holders():
        e1, e2 = EXP("F"), EXP("F")
        with P.coverage_trace(e1) as c1, P.coverage_trace(e2) as c2:
            c1.run("G", lambda: c2.run("G", hit))
        return {"1": rec_of(e1, c1), "2": rec_of(e2, c2)}

    def unwind(mode):
        def f():
            exp = EXP("F")
            with P.coverage_trace(exp) as cov:
                cov.run("G", lambda: hit(mode=mode))
            return rec_of(exp, cov)
        return f

    def after_stop():
        exp = EXP("F")
        wexp = EXP("A_G")
        with P.coverage_trace(wexp) as wit:
            cov = P.coverage_trace(exp)
            cov.__enter__()
            def body():
                hit(mid=lambda: cov.__exit__(None, None, None))
            wit.run("A", cov.run, "G", body)
        return rec_of(exp, cov)

    run("non_minted", non_minted)
    run("cut_moved", cut_moved)
    run("clone_called", clone_called)
    run("no_anchor", no_anchor)
    run("kind_c", kind_c)
    run("kind_a", kind_a)
    run("kind_d", kind_d)
    run("kind_d_loop", kind_d_loop)
    run("kind_u", kind_u)
    run("two_holders", two_holders)
    run("py_return", kind_c)
    run("unwind_at_entry", unwind("unwind_at"))
    run("unwind_past", unwind("unwind_past"))
    run("after_stop", after_stop)
    return out


_WRAPPER = {}


def fx_driver_wrapper():
    """The driver's fresh module-level wrapper for Handle._run (harness rules: a top-level def used by no
    other case), written into its own module on first use."""
    if "w" not in _WRAPPER:
        import importlib, tempfile
        d = tempfile.mkdtemp(prefix="v5f_driver_")
        with open(os.path.join(d, "fx_driver_cut.py"), "w") as fh:
            fh.write("import asyncio.events\nORIG = asyncio.events.Handle._run\n"
                     "def driver_run(self):\n    return ORIG(self)\n")
        sys.path.insert(0, d)
        _WRAPPER["w"] = importlib.import_module("fx_driver_cut").driver_run
    return _WRAPPER["w"]


def child(name):
    """_forget_in_child's scenarios, each in its own spawned process, the driven call its last step."""
    R = _load_runner()
    P, EXP, fx = R.P, R.EXP, R.fx_v5f
    fp = P._v5_faultpoints()
    forget = types.FunctionType(fp["_forget_in_child"], vars(P), "_forget_in_child")
    if name == "forget_noop":
        forget()
        return {"ok": True}
    exp = EXP("F")
    cov = P.coverage_trace(exp)
    cov.__enter__()
    if name == "forget_ours":
        T = _tramp(R, vars(fx))
        fns = _fns(R)
        # the trampoline's entry stores a pending entry against its frame; mid is the driven call
        cov.run("G", lambda: T(fns["_on_entry"], None, None, fx.f.__code__, 0, None, forget))
        return {"ok": True}
    t = P._v5_state()["tool"]
    sys.monitoring.free_tool_id(t)
    sys.monitoring.use_tool_id(t, "other")
    fx.f.__code__ = fx.g.__code__.replace(co_name="f")
    forget()
    return {"ok": True}


def main():
    if "--child" in sys.argv:
        name = sys.argv[sys.argv.index("--child") + 1]
        if LINECOV_FILE:
            import linecov_v5f
            linecov_v5f.start(IMPL)
            linecov_v5f.dump_at_exit(LINECOV_FILE)
        print(json.dumps(child(name)))
        return 0
    import tempfile
    import linecov_v5f
    lc_file = tempfile.mktemp(prefix="v5f_linecov_")
    R = _load_runner()
    linecov_v5f.start(IMPL)
    out = scenarios(R)
    seen = linecov_v5f.stop()
    kids = {}
    for name in CHILD_SCENARIOS:
        if ONLY and name != ONLY:
            continue
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--impl", IMPL, "--child", name,
                            "--linecov", lc_file], capture_output=True, text=True, timeout=120)
        lines = [x for x in r.stdout.splitlines() if x.startswith("{")]
        kids[name] = json.loads(lines[-1]) if lines else f"rc {r.returncode}: {r.stderr[-300:]}"
    seen |= linecov_v5f.read(lc_file)
    exe = linecov_v5f.executable_lines(R.P, NAMED)
    missing = {k: [ln for ln in v if ln not in seen] for k, v in exe.items()}
    missing = {k: v for k, v in missing.items() if v}
    res = {"impl": IMPL, "python": sys.version.split()[0], "scenarios": out, "children": kids,
           "executable": {k: len(v) for k, v in exe.items()}, "missing": missing,
           "verdict": "PASS" if not missing and all(v == {"ok": True} for v in kids.values()) else "FAIL"}
    if OUT:
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    print(json.dumps({k: res[k] for k in ("python", "executable", "missing", "children", "verdict")}))
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
