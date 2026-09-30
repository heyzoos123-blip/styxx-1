"""crash_sweep_v5f.py: G_FI's frozen crash sweep, written by the exam author from G_FI's text (revision 3,
MF5 and later): the fault injector (sys.monitoring INSTRUCTION events, tool id 5, targets from
_v5_faultpoints()), invariants C1-C9 as written there, and the scenarios it names.

Scenarios (frozen enumeration order: scenario, faulted thread, key, offset, k):
  single      one tracer; gate A declares f and g, sentinel S declares h (called inside A, outside S);
  two_thread  one tracer; A (f) on the scenario thread and B (g) on a worker, ordered by frozen barriers so
              no machinery call on one thread overlaps one on the other; swept twice (faulted: scenario,
              then worker);
  run_async   one tracer; A as a run_async section under asyncio.run (f, a suspension, g, h);
  generator   one tracer; A declares the generator function gen, iterated inside A;
  hop         one tracer; run_async section B sent once on a worker thread, resumed inside A on the
              scenario thread (V28b's hop);
  background  the single scenario while a background tracer on another thread, entered before the sweep and
              declaring f, holds one open section of its own (which called f) across each point (C4, C5's
              exclusion);
  callbacks   the five callback-only functions under cover_driver_v5f.py's direct-call trampoline;
  fork        in a fresh subprocess per point that starts no thread before the fork: a trace with a mint, an
              open section and a pending entry forks; in the child the injector faults _forget_in_child at
              each of its instructions; a second variant installs an audit hook refusing __code__ writes. C9.

A fault point is (key, offset, k), k <= K = 2, from a discovery run made twice at the start of each
scenario's sweep (the two sets must be identical, or the sweep is void and fails).

Usage: python crash_sweep_v5f.py [--impl PATH] [--scenario NAME[,NAME]] [--stride N] [--out RESULT.json] [--discover-only]
"""
import collections, gc, json, os, sys, threading, time, types

HERE = os.path.dirname(os.path.abspath(__file__))
K = 2
WATCH = 30.0


ARGV = list(sys.argv)


def _opt(n, d=None):
    a = ARGV[1:]
    return a[a.index(n) + 1] if n in a else d


IMPL = os.path.abspath(_opt("--impl", os.path.join(HERE, "ref_v5f.py")))
ONLY = _opt("--scenario")
STRIDE = int(_opt("--stride", "1"))
OUT = _opt("--out")
DISCOVER_ONLY = "--discover-only" in ARGV   # the freeze-time record of the point sets (corpus_v5f/)


def load_runner():
    sys.argv = [os.path.join(HERE, "run_protocol_v5f_exam.py"), "--impl", IMPL]
    sys.path.insert(0, HERE)
    import importlib
    return importlib.import_module("run_protocol_v5f_exam")


R = None
P = EXP = fx = None
_CODE = None


class Injected(Exception):
    pass


# ---------------------------------------------------------------------------------------------------
# the injector (harness rules: code read at arming, a live-ident filter, restart_events() first)
# ---------------------------------------------------------------------------------------------------
class Arm:
    """Armed on the faulted thread by the scenario itself (arm(ident)), before that thread's first
    machinery call. mode 'count' records (key, offset) executions; mode 'raise' raises exc at the k-th
    execution of offset in key."""
    def __init__(self, keys, mode, point=None, exc=None):
        self.keys, self.mode, self.point, self.exc = keys, mode, point, exc
        self.counts = collections.Counter()
        self.fired = False
        self.inj = None

    def __call__(self, ident):
        fp = P._v5_faultpoints()
        keyof = {id(fp[k]): k for k in self.keys}
        def on_instr(code, off):
            k = keyof.get(id(code))
            if k is None:
                return
            self.counts[(k, off)] += 1
            if self.mode == "raise" and not self.fired and (k, off) == self.point[:2] and self.counts[(k, off)] == self.point[2]:
                self.fired = True
                raise self.exc
        self.inj = R.Injector(list(self.keys), ident, on_instr)

    def close(self):
        if self.inj is not None:
            self.inj.close()
            self.inj = None


# ---------------------------------------------------------------------------------------------------
# scenarios: each constructs tracers only through coverage_trace(), catches nothing (but the StopIteration
# that ends a driven coroutine), and joins every thread it started before any tracer's __exit__
# ---------------------------------------------------------------------------------------------------
def _wait(ev, th=None, limit=10.0):
    end = time.monotonic() + limit
    while not ev.is_set() and time.monotonic() < end:
        if th is not None and not th.is_alive():
            return
        ev.wait(0.005)


def sc_single(box, faulted, arm):
    arm(threading.get_ident())
    exp = EXP("GFI")
    cov = P.coverage_trace(exp)
    box["tracers"].append(("T", cov, exp))
    with cov:
        cov.run("A", fx.body)


def sc_two_thread(box, faulted, arm):
    if faulted == "scenario":
        arm(threading.get_ident())
    exp = EXP("CS_TWO")
    cov = P.coverage_trace(exp)
    box["tracers"].append(("T", cov, exp))
    a_open, b_open, a_done, b_done = (threading.Event() for _ in range(4))
    def worker():
        if faulted == "worker":
            arm(threading.get_ident())
        _wait(a_open)
        def bbody():
            b_open.set()
            fx.g()
            _wait(a_done)
        cov.run("B", bbody)
        b_done.set()
    box["worker"] = worker
    with cov:
        w = threading.Thread(target=worker, name="cs-worker")
        box["threads"].append(w)
        w.start()
        try:
            def abody():
                a_open.set()
                _wait(b_open, w)
                fx.f()
                fx.h()
            cov.run("A", abody)
            a_done.set()
            _wait(b_done, w)
        finally:
            a_open.set(); a_done.set()
            w.join(WATCH)


def sc_run_async(box, faulted, arm):
    import asyncio
    arm(threading.get_ident())
    exp = EXP("GFI")
    cov = P.coverage_trace(exp)
    box["tracers"].append(("T", cov, exp))
    async def co():
        fx.f()
        await asyncio.sleep(0)
        fx.g()
        fx.h()
    async def main():
        await cov.run_async("A", co)
    with cov:
        asyncio.run(main())


def sc_generator(box, faulted, arm):
    arm(threading.get_ident())
    exp = EXP("CS_GEN")
    cov = P.coverage_trace(exp)
    box["tracers"].append(("T", cov, exp))
    with cov:
        cov.run("A", lambda: (list(fx.gen()), fx.h()))


class _Once:
    def __await__(self):
        yield


def sc_hop(box, faulted, arm):
    arm(threading.get_ident())
    exp = EXP("CS_TWO")
    cov = P.coverage_trace(exp)
    box["tracers"].append(("T", cov, exp))
    async def bfn():
        fx.g()
        await _Once()
        fx.g()
    with cov:
        co = cov.run_async("B", bfn)
        th = threading.Thread(target=co.send, args=(None,), name="cs-hop")
        box["threads"].append(th)
        th.start()
        th.join(WATCH)
        def abody():
            try:
                co.send(None)
            except StopIteration:
                pass
            fx.f()
            fx.h()
        cov.run("A", abody)


def sc_callbacks(box, faulted, arm):
    """R._driver_scenario's direct calls; the `d` call runs as a stdlib loop callback, whose exception the
    loop hands to its exception handler: that handler is set to record it (C2: the driver's call raised it)."""
    import asyncio
    arm(threading.get_ident())
    box["loop_exc"] = []
    real_new = asyncio.new_event_loop
    def new_loop():
        L = real_new()
        L.set_exception_handler(lambda loop, ctx: box["loop_exc"].append(ctx.get("exception")))
        return L
    asyncio.new_event_loop = new_loop
    try:
        cov = R._driver_scenario(box)
    finally:
        asyncio.new_event_loop = real_new
    box["tracers"].append(("T", cov, EXP("DRV")))


SCENARIOS = {
    "single": (sc_single, ("scenario",), None),
    "two_thread": (sc_two_thread, ("scenario", "worker"), None),
    "run_async": (sc_run_async, ("scenario",), None),
    "generator": (sc_generator, ("scenario",), None),
    "hop": (sc_hop, ("scenario",), None),
    "background": (sc_single, ("scenario",), "bg"),
    "callbacks": (sc_callbacks, ("scenario",), None),
}


# ---------------------------------------------------------------------------------------------------
# the background tracer (C4)
# ---------------------------------------------------------------------------------------------------
class Background:
    def __init__(self):
        self.exp = EXP("CS_BG")
        self.q = []
        self.cmd = threading.Event()
        self.ack = threading.Event()
        self.calls = 0
        self.th = threading.Thread(target=self._loop, daemon=True, name="cs-background")
        self.th.start()
        self._do("enter")

    def _loop(self):
        self.cov = P.coverage_trace(self.exp)
        while True:
            self.cmd.wait()
            self.cmd.clear()
            op = self.q.pop(0)
            if op == "enter":
                self.cov.__enter__()
                self.ack.set()
            elif op == "open":
                self.release = threading.Event()
                def body():
                    fx.f()
                    self.calls += 1
                    self.ack.set()                   # parked inside its section while the point runs
                    self.release.wait(WATCH)
                self.cov.run("BG", body)
                self.ack.set()
            elif op == "exit":
                self.cov.__exit__(None, None, None)
                self.ack.set()
                return

    def _do(self, op):
        self.ack.clear()
        self.q.append(op)
        self.cmd.set()
        self.ack.wait(WATCH)

    def open(self):
        self._do("open")

    def close(self):
        self.ack.clear()
        self.release.set()
        self.ack.wait(WATCH)                         # parked at the barrier outside its sections

    def finish(self):
        self._do("exit")
        self.th.join(WATCH)
        rec = self.cov.record()
        return rec


# ---------------------------------------------------------------------------------------------------
# one run and one point
# ---------------------------------------------------------------------------------------------------
def run_once(name, faulted, arm):
    fn = SCENARIOS[name][0]
    box = {"tracers": [], "threads": []}
    raised, unraisable, hooked = [], [], []
    old_u, old_e = sys.unraisablehook, threading.excepthook
    sys.unraisablehook = lambda u: unraisable.append(u.exc_value)
    threading.excepthook = lambda a: hooked.append((a.thread, a.exc_value))
    def t():
        try:
            fn(box, faulted, arm)
        except BaseException as e:                     # noqa: BLE001  (C2 and C6 read it)
            raised.append(e)
    th = threading.Thread(target=t, daemon=True, name="cs-scenario")
    th.start()
    th.join(WATCH)
    for w in box["threads"]:
        w.join(1.0)
    sys.unraisablehook, threading.excepthook = old_u, old_e
    return box, th.is_alive(), (raised[0] if raised else None), unraisable, hooked


def records(box):
    out = {}
    for name, cov, exp in box["tracers"]:
        try:
            out[name] = ("rec", cov.record())
        except Exception as e:                        # noqa: BLE001
            c = R.code_of(e)
            out[name] = ("refused", c, str(e))
    return out


def discovery(name, faulted, keys):
    a = Arm(keys, "count")
    try:
        box, hung, raised, _, _ = run_once(name, faulted, a)
    finally:
        a.close()
    if hung or raised is not None:
        raise RuntimeError(f"discovery run of {name}/{faulted} failed: hung={hung} raised={raised!r}")
    return {(k, off, n) for (k, off), c in a.counts.items() for n in range(1, K + 1) if c >= n}


def over_credit(rec, base):
    for sec, ops in rec["sections"].items():
        b = collections.Counter()
        for o in base["sections"].get(sec, []):
            b.update(o["calls"])
        c = collections.Counter()
        for o in ops:
            c.update(o["calls"])
        if any(v > b.get(k, 0) for k, v in c.items()):
            return f"{sec}: {dict(c)} > baseline {dict(b)}"
    return None


def sentinel_pass(exp, rec):
    """C1's sentinel: every gate named S scores NOT_EXERCISED or a refusal, never PASS."""
    try:
        v = exp.score({"m": 1.0, "coverage_trace": rec})
        return "S" in (v.coverage or {})
    except Exception:                                 # noqa: BLE001
        return False


def i6(rec, base):
    ok, why = R.envelope_ok(rec, base)
    if not ok:
        return why
    if sorted(rec["problems"]) != sorted(base["problems"]):
        return f"problems {rec['problems']} != baseline {base['problems']}"
    return None


def check_point(name, faulted, point, base, S0, bg):
    exc = Injected(f"{name}/{faulted}/{point}")
    a = Arm(FAULT_KEYS[name], "raise", point, exc)
    if bg is not None:
        bg.open()
    try:
        box, hung, raised, unraisable, hooked = run_once(name, faulted, a)
    finally:
        a.close()
    if not a.fired:
        if bg is not None:
            bg.close()
        return "UNREACHED", []
    bad = []
    # step 1: C2, C6
    worker_threads = set(box["threads"])
    c2 = (raised is exc or any(x is exc for x in unraisable)
          or (raised is not None and R.code_of(raised) == "UNRESOLVED" and raised.__cause__ is exc)
          or (faulted == "worker" and any(t in worker_threads and x is exc for t, x in hooked)))
    if name == "callbacks" and any(x is exc for x in box.get("loop_exc", [])):
        c2 = True
    if not c2:
        bad.append(f"C2: the injected exception was not seen (raised {raised!r})")
    if raised is not None and raised is not exc and not (R.code_of(raised) == "UNRESOLVED" and raised.__cause__ is exc):
        bad.append(f"C6: another exception left the scenario: {raised!r}"[:200])
    if any(x is not exc for _, x in hooked):
        bad.append(f"C6: a thread ended with another exception: {[repr(x)[:80] for _, x in hooked]}")
    if hung:
        bad.append("C3: the scenario hung")
    # step 2: C1, C8
    recs = records(box)
    zombies = set()
    for tname, r in recs.items():
        b = base.get(tname)
        exp = [e for n, c, e in box["tracers"] if n == tname][0]
        if r[0] == "rec":
            oc = over_credit(r[1], b)
            if oc:
                bad.append("C1: over-credit " + oc)
            if sentinel_pass(exp, r[1]):
                bad.append("C1: the sentinel gate S passed")
            why = i6(r[1], b)
            if why:
                bad.append("C8: " + why)
        else:
            if r[1] == "TRACE_ACTIVE" and "the tracer is active" in r[2]:
                zombies.add(tname)
            elif r[1] not in ("TRACE_INCOMPLETE", "TRACE_ACTIVE"):
                bad.append(f"C8: record() refused {r[1]}")
    # step 3: C3
    if not R.probe_cycle():
        bad.append("C3: the probe cycle did not complete")
    # step 4: C7
    st = P._v5_state()
    live_decl = collections.Counter()
    for n, c, e in box["tracers"]:
        if n in zombies:
            for t in e.coverage_targets:
                live_decl[t] += 1
    if bg is not None:
        for t in bg.exp.coverage_targets:
            live_decl[t] += 1
    for m in st["mints"]:
        if m["holders"] != live_decl.get(m["target"], 0) or m["holders"] == 0 or not m["installed"]:
            bad.append(f"C7: mint {m} (live holders {live_decl.get(m['target'], 0)})")
    # step 5: C1, C8 again for zombies
    for n, cov, e in box["tracers"]:
        if n in zombies:
            if not R._bounded_exit(cov):
                bad.append("C3: the extra __exit__ of a zombie did not return")
                continue
            try:
                r2 = cov.record()
                oc = over_credit(r2, base[n])
                if oc:
                    bad.append("C1 (step 5): " + oc)
                why = i6(r2, base[n])
                if why:
                    bad.append("C8 (step 5): " + why)
            except Exception as ex:                   # noqa: BLE001
                if R.code_of(ex) != "TRACE_INCOMPLETE":
                    bad.append(f"C8 (step 5): record() refused {R.code_of(ex)}")
    if bg is not None:
        bg.close()
    # step 6: C5
    box.clear(); del recs, raised, exc, unraisable, hooked
    gc.collect()
    if not R.probe_cycle():
        bad.append("C5: the second probe cycle did not complete")
    S1 = dict(P._v5_state()); S1.pop("pid", None)
    s0, s1 = dict(S0), dict(S1)
    if bg is not None:
        for s in (s0, s1):
            s["mints"] = [dict(m, pending=None) for m in s["mints"]]
    diff = R.snapshot_diff(s0, s1)
    if diff:
        bad.append(f"C5: _v5_state() differs from S0 in {diff}")
    if S1["anchors"] or S1["guard"] != "free" or S1["global_events"] or not S1["cut_current"]:
        bad.append(f"C5: anchors {S1['anchors']}, guard {S1['guard']}, global_events {S1['global_events']}")
    for kk, (fn, code) in R.ORIG.items():
        if fn.__code__ is not code and not (bg is not None and fn is fx.f):
            bad.append(f"C5: {kk} not restored")
            fn.__code__ = code
    if (sys.getprofile(), sys.gettrace()) != PROF0:
        bad.append("C5: profile or trace function changed")
    return ("UNCLEAN" if bad else "CLEAN"), bad[:4]


FAULT_KEYS = {}
PROF0 = (None, None)


def sweep(name):
    fn, roles, variant = SCENARIOS[name]
    fp = P._v5_faultpoints()
    keys = tuple(R.CALLBACK_ONLY) if name == "callbacks" else tuple(k for k in fp if k not in R.CALLBACK_ONLY)
    FAULT_KEYS[name] = keys
    out = {}
    bg = Background() if variant == "bg" else None
    for faulted in roles:
        if bg is not None:
            bg.open()
        # the baseline (fault-free, once per version), then the snapshot
        noarm = lambda ident: None
        box, hung, raised, _, _ = run_once(name, faulted, noarm)
        if hung or raised is not None:
            out[faulted] = {"void": f"baseline failed: {raised!r}"}
            if bg is not None:
                bg.close()
            continue
        base = {n: r[1] for n, r in records(box).items() if r[0] == "rec"}
        box.clear()
        if bg is not None:
            bg.close()
        gc.collect()
        S0 = dict(P._v5_state()); S0.pop("pid", None)
        if bg is not None:
            bg.open()
        d1 = discovery(name, faulted, keys)
        if bg is not None:
            bg.close(); bg.open()
        d2 = discovery(name, faulted, keys)
        if bg is not None:
            bg.close()
        if d1 != d2:
            out[faulted] = {"void": f"the two discovery runs differ ({len(d1)} vs {len(d2)})"}
            continue
        order = {k: i for i, k in enumerate(keys)}
        points = sorted(d1, key=lambda p: (order[p[0]], p[1], p[2]))
        if DISCOVER_ONLY:
            out[faulted] = {"points": len(points), "point_list": [list(p) for p in points]}
            continue
        verdicts = collections.Counter()
        unclean = []
        for i, pt in enumerate(points):
            if i % STRIDE:
                continue
            v, bad = check_point(name, faulted, pt, base, S0, bg)
            verdicts[v] += 1
            if bad:
                unclean.append((pt, bad))
                if any(b.startswith("C3") for b in bad) or len(unclean) >= 25:
                    out.setdefault("stopped_early", f"{name}/{faulted} at {pt}")
                    break
        out[faulted] = {"points": len(points), "run": sum(verdicts.values()), "verdicts": dict(verdicts),
                        "unclean": [[list(p), b] for p, b in unclean[:10]], "n_unclean": len(unclean)}
    if bg is not None:
        rec = bg.finish()
        u = R.union_of(rec, "BG")
        c4 = (u == {"fx_gfi:f": bg.calls} and not rec["problems"]
              and not any(n for ops in rec["sections"].values() for o in ops for n in o["notes"]))
        gc.collect()
        c4 = c4 and P._v5_state()["mints"] == []
        out["C4"] = {"ok": c4, "calls": bg.calls, "union": u, "problems": rec["problems"][:3]}
    return out


# ---------------------------------------------------------------------------------------------------
# the fork scenario (C9), one fresh subprocess per point
# ---------------------------------------------------------------------------------------------------
def fork_child_run(point, variant):
    """Runs in a fresh subprocess that started no thread. Returns the parent's view and the child's C9."""
    import json as _json
    exp = EXP("CS_FORK")
    cov = P.coverage_trace(exp)
    out = {}
    r, w = os.pipe()
    fired = {"n": 0}
    exc = Injected(f"fork/{point}")
    def do_fork():
        fp = P._v5_faultpoints()
        code = fp["_forget_in_child"]
        counts = collections.Counter()
        def on_instr(c, off):
            counts[off] += 1
            if point == "count":
                return
            if point[0] != "write" and off == point[1] and counts[off] == point[2] and not fired["n"]:
                fired["n"] = 1
                raise exc
        parent = os.getpid()
        writes = {"n": 0, "armed": variant == "audit"}
        if variant == "audit":
            # the second variant: an audit hook, armed only while the at-fork handler runs in the child,
            # refuses the k-th __code__ write (point = ["write", k]) or counts them (point "count")
            def hook(ev, args):
                if (writes["armed"] and os.getpid() != parent and ev == "object.__setattr__"
                        and len(args) > 1 and args[1] == "__code__"):
                    writes["n"] += 1
                    if point != "count" and point[0] == "write" and writes["n"] == point[1] and not fired["n"]:
                        fired["n"] = 1
                        raise RuntimeError("the audit hook refuses a __code__ write")
            sys.addaudithook(hook)
        inj = R.Injector(["_forget_in_child"], threading.get_ident(), on_instr) if variant != "audit" else None
        pid = os.fork()
        if pid == 0:                                   # the child
            writes["armed"] = False
            res = {}
            try:
                if inj is not None:
                    inj.close()
                res["writes"] = writes["n"]
                res["counts"] = {str(k): v for k, v in counts.items()}
                res["fired"] = fired["n"]
                try:
                    res["run"] = cov.run("A", fx.g)      # passes through, returning fn's value
                except BaseException as e:            # noqa: BLE001
                    res["run"] = f"raised {type(e).__name__}"
                res["probe"] = R.probe_cycle()
                st = P._v5_state()
                res["state"] = {"anchors": st["anchors"], "mints": st["mints"], "global_events": st["global_events"]}
                t = st["tool"]
                fixbad = []
                for kk, (fn, code) in R.ORIG.items():
                    if fn.__code__ is code:
                        continue
                    le = sys.monitoring.get_local_events(t, fn.__code__) if (t is not None and sys.monitoring.get_tool(t)) else 0
                    if not (fn.__code__ == code and not le):
                        fixbad.append(str(kk))
                res["fixtures"] = fixbad
            finally:
                os.write(w, _json.dumps(res, default=str).encode())
                os._exit(0)
        if inj is not None:
            inj.close()
        os.close(w)
        data = b""
        while True:
            chunk = os.read(r, 65536)
            if not chunk:
                break
            data += chunk
        os.waitpid(pid, 0)
        out["child"] = _json.loads(data.decode() or "{}")
        return 1
    with cov:
        cov.run("A", fx.forker, do_fork)
    out["parent"] = cov.record()
    return out


def fork_main(point_s, variant):
    point = "count" if point_s == "count" else tuple(json.loads(point_s))
    res = fork_child_run(point, variant)
    print("FORK_RESULT " + json.dumps(res, default=str))


def sweep_fork():
    import subprocess
    def run(point, variant):
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "--impl", IMPL, "--fork-point",
                            json.dumps(point) if point != "count" else "count", "--variant", variant],
                           capture_output=True, text=True, timeout=120)
        lines = [x for x in r.stdout.splitlines() if x.startswith("FORK_RESULT ")]
        if not lines:
            return {"error": f"rc {r.returncode}: {r.stderr[-400:]}"}
        return json.loads(lines[-1].split(" ", 1)[1])
    out = {}
    base = run("count", "plain")
    if "error" in base:
        return {"void": base["error"]}
    base2 = run("count", "plain")
    counts = base["child"]["counts"]
    if counts != base2["child"]["counts"]:
        return {"void": "the two discovery runs differ"}
    points = sorted((["_forget_in_child", int(off), n] for off, c in counts.items() for n in range(1, K + 1) if c >= n),
                    key=lambda p: (p[1], p[2]))
    abase = run("count", "audit")
    if "error" in abase:
        return {"void": abase["error"]}
    apoints = [["write", k] for k in range(1, abase["child"].get("writes", 0) + 1)]
    if DISCOVER_ONLY:
        return {"plain": {"points": len(points), "point_list": points}, "audit": {"points": len(apoints), "point_list": apoints}}
    for variant, pts in (("plain", points), ("audit", apoints)):
        verdicts, unclean = collections.Counter(), []
        for i, pt in enumerate(pts):
            if i % STRIDE:
                continue
            r = run(pt, variant)
            bad = []
            if "error" in r:
                bad.append("C9: " + r["error"][:200])
            else:
                c = r["child"]
                if not c.get("fired"):
                    verdicts["UNREACHED"] += 1
                    continue
                if c.get("run") != 2:
                    bad.append(f"C9: run() did not pass through: {c.get('run')}")
                if not c.get("probe"):
                    bad.append("C9: the child's probe cycle did not complete")
                s = c.get("state", {})
                if s.get("anchors") or s.get("mints") or s.get("global_events"):
                    bad.append(f"C9: child state {s}")
                if c.get("fixtures"):
                    bad.append(f"C9: fixtures {c['fixtures']}")
                keys = ("sections", "problems", "uncredited")    # targets and gates_sha256 carry the process's paths
                if {k: r["parent"].get(k) for k in keys} != {k: base["parent"].get(k) for k in keys}:
                    bad.append("C9: the parent's trace differs from its baseline record")
            verdicts["UNCLEAN" if bad else "CLEAN"] += 1
            if bad:
                unclean.append((pt, bad))
        out[variant] = {"points": len(pts), "verdicts": dict(verdicts), "unclean": unclean[:10],
                        "n_unclean": len(unclean)}
    return out


def main():
    global R, P, EXP, fx, PROF0
    R = load_runner()
    P, EXP, fx = R.P, R.EXP, R.fx_gfi
    PROF0 = (sys.getprofile(), sys.gettrace())
    if "--fork-point" in ARGV:
        fork_main(_opt("--fork-point"), _opt("--variant", "plain"))
        return 0
    t0 = time.monotonic()
    names = ONLY.split(",") if ONLY else list(SCENARIOS) + ["fork"]
    res = {"impl": IMPL, "python": sys.version.split()[0], "stride": STRIDE, "K": K, "scenarios": {}}
    for n in names:
        res["scenarios"][n] = sweep_fork() if n == "fork" else sweep(n)
        print(n, json.dumps(res["scenarios"][n], default=str)[:600], flush=True)
    clean = True
    for n, v in res["scenarios"].items():
        for role, x in v.items():
            if role == "C4":
                clean &= x["ok"]
            elif role == "stopped_early":
                clean = False
            elif isinstance(x, dict) and ("void" in x or x.get("n_unclean")):
                clean = False
    res["G_FI"] = "PASS" if clean else "FAIL"
    res["seconds"] = round(time.monotonic() - t0, 1)
    if OUT:
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    print("G_FI:", res["G_FI"], res["seconds"], "s")
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
