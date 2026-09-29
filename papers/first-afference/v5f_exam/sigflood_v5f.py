"""sigflood_v5f.py: G_SIG (signal floods, frozen, 60 s per cell on each verified interpreter).

Written by the exam author from G_SIG's text and the Stated limits' "G_SIG (frozen decision)". Required: 0
user-lock leaks, 0 hangs, 0 poison, 0 wrong results, and credited <= body runs. A wrong result is a skipped
with/finally cleanup; a result value that differs on an iteration in which no asynchronous exception was
delivered; or a later trace whose record differs from its fault-free record (poison, checked one fixed way:
after each cell, with the flood disarmed, the cell's tracers dropped, gc.collect(), one probe cycle; the
cell is poisoned if the probe cycle does not complete or _v5_state() differs from the pre-cell snapshot
outside the common exemptions). L-DELIVERY is not a wrong result; its three cells have fixed rules.

Cells (the text names the quantities; the flows other than the three L-DELIVERY cells are the exam author's,
Revision 12 follow-ups GAP-56):
  lock      `with lock:` inside an open section under a 0.5 ms SIGALRM flood: 0 leaks (lock held after a
            delivered Timeout), 0 hangs;
  credit    one section per call, each call counting its body runs, under a 0.2 ms flood: credited <= runs;
  result    one section per call returning f(x); the value checked only on iterations with no delivery;
  ldel_a    L-DELIVERY (a): an `except ValueError` flow outside every section with a trace active: 0 lost;
  ldel_b    L-DELIVERY (b): the same inside an open section: reported;
  ldel_c    L-DELIVERY (c): with-lock and try/finally flows inside an open section: 0 skipped, 0 leaks.

Usage: python sigflood_v5f.py [--impl PATH] [--seconds 60] [--cells a,b] [--out RESULT.json]
"""
import gc, json, os, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
ARGV = list(sys.argv)


def _opt(n, d=None):
    return ARGV[ARGV.index(n) + 1] if n in ARGV else d


IMPL = os.path.abspath(_opt("--impl", os.path.join(HERE, "ref_v5f.py")))
SECONDS = float(_opt("--seconds", "60"))
CELLS = _opt("--cells")
OUT = _opt("--out")


def load_runner():
    sys.argv = [os.path.join(HERE, "run_protocol_v5f_exam.py"), "--impl", IMPL]
    sys.path.insert(0, HERE)
    import importlib
    return importlib.import_module("run_protocol_v5f_exam")


R = load_runner()
P, EXP, fx, fxb = R.P, R.EXP, R.fx_v5f, R.fx_b1
ARMED, Timeout = R.ARMED, R.Timeout
DELIVERED = [0]


def flood(interval):
    import signal
    def handler(signum, frame):
        if ARMED[0]:
            DELIVERED[0] += 1
            raise Timeout()
    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, interval, interval)
    return old


def unflood(old):
    import signal
    signal.setitimer(signal.ITIMER_REAL, 0, 0)
    signal.signal(signal.SIGALRM, old)


def cell_lock(box, deadline):
    lock = threading.Lock()
    with P.coverage_trace(EXP("F")) as cov:
        def body():
            fx.f()
            while time.monotonic() < deadline:
                try:
                    ARMED[0] = True
                    with lock:
                        box["work"] += 1
                    ARMED[0] = False
                except Timeout:
                    ARMED[0] = False
                    if lock.locked():
                        box["leaks"] += 1
                        lock.release()
        old = flood(0.0005)
        try:
            while time.monotonic() < deadline:
                try:
                    ARMED[0] = True
                    cov.run("G", body)
                    ARMED[0] = False
                except Timeout:
                    ARMED[0] = False
        finally:
            ARMED[0] = False
            unflood(old)
    box["held_at_end"] = lock.locked()


def cell_credit(box, deadline):
    exp = EXP("HB")
    fxb.BODY[0] = 0
    with P.coverage_trace(exp) as cov:
        old = flood(0.0002)
        try:
            while time.monotonic() < deadline:
                try:
                    ARMED[0] = True
                    cov.run("G", fxb.hbody)
                    ARMED[0] = False
                except Timeout:
                    ARMED[0] = False
        finally:
            ARMED[0] = False
            unflood(old)
    rec = cov.record()
    box["credited"] = sum(o["calls"].get("fx_b1:hbody", 0) for o in rec["sections"].get("G", []))
    box["body_runs"] = fxb.BODY[0]


def cell_result(box, deadline):
    with P.coverage_trace(EXP("F")) as cov:
        old = flood(0.0005)
        try:
            x = 0
            while time.monotonic() < deadline:
                x += 1
                d0 = DELIVERED[0]
                try:
                    ARMED[0] = True
                    v = cov.run("G", fx.f, x)
                    ARMED[0] = False
                except Timeout:
                    ARMED[0] = False
                    continue
                if DELIVERED[0] == d0:
                    box["checked"] += 1
                    if v != x + 1:
                        box["wrong"] += 1
        finally:
            ARMED[0] = False
            unflood(old)


def cell_ldel(which):
    def cell(box, deadline):
        exp = EXP("F")
        lock = threading.Lock()
        with P.coverage_trace(exp) as cov:
            if which == "a":
                cov.run("G", fx.f)                    # one section, fault-free, before the flood
                box["global_events_before"] = P._v5_state()["global_events"]
            old = flood(0.00002)
            try:
                if which == "a":
                    R._except_flow(deadline, box)
                elif which == "b":
                    cov.run("G", lambda: (fx.f(), R._except_flow(deadline, box)))
                else:
                    cov.run("G", R._cleanup_flow, deadline, box, lock)
            finally:
                ARMED[0] = False
                unflood(old)
                ARMED[0] = True
        box["lock_left_held"] = lock.locked()
    return cell


CELL_FNS = {"lock": cell_lock, "credit": cell_credit, "result": cell_result,
            "ldel_a": cell_ldel("a"), "ldel_b": cell_ldel("b"), "ldel_c": cell_ldel("c")}


def run_cell(name):
    before = dict(P._v5_state()); before.pop("pid", None)
    box = {"leaks": 0, "work": 0, "checked": 0, "wrong": 0, "inflight": False, "handled": 0, "lost": 0,
           "entered": 0, "cleaned": 0}
    err = []
    def t():
        try:
            CELL_FNS[name](box, time.monotonic() + SECONDS)
        except BaseException as e:                     # noqa: BLE001
            err.append(repr(e)[:200])
    ARMED[0] = False
    # the flood is a process signal delivered to the main thread, so the cell runs on it; a hang is caught
    # by faulthandler, which ends the process (no result is written: G_SIG fails)
    import faulthandler
    faulthandler.dump_traceback_later(SECONDS + 120, exit=True)
    t_ = time.monotonic()
    t()
    faulthandler.cancel_dump_traceback_later()
    hung = time.monotonic() - t_ > SECONDS + 60
    ARMED[0] = False
    poisoned, diff = R._poisoned(before)
    box.update(hung=hung, error=err, poisoned=poisoned, diff=diff)
    fails = []
    if hung:
        fails.append("hang")
    if err:
        fails.append("an exception left the cell: " + err[0])
    if poisoned:
        fails.append(f"poison {diff}")
    if name == "lock" and (box["leaks"] or box.get("held_at_end")):
        fails.append(f"user-lock leaks {box['leaks']}")
    if name == "credit" and box["credited"] > box["body_runs"]:
        fails.append(f"credited {box['credited']} > body runs {box['body_runs']}")
    if name == "result" and box["wrong"]:
        fails.append(f"wrong results {box['wrong']}")
    if name == "ldel_a" and (box["lost"] or box.get("global_events_before")):
        fails.append(f"L-DELIVERY (a) lost {box['lost']} (global_events before arming {box.get('global_events_before')})")
    if name == "ldel_c" and (box["entered"] != box["cleaned"] or box["lock_left_held"]):
        fails.append(f"L-DELIVERY (c) skipped {box['entered'] - box['cleaned']}, lock held {box['lock_left_held']}")
    return box, fails


def main():
    names = CELLS.split(",") if CELLS else list(CELL_FNS)
    res = {"impl": IMPL, "python": sys.version.split()[0], "seconds_per_cell": SECONDS, "cells": {}}
    ok = True
    for n in names:
        box, fails = run_cell(n)
        res["cells"][n] = {"fails": fails, **{k: v for k, v in box.items() if not callable(v)}}
        ok &= not fails
        print(n, json.dumps(res["cells"][n], default=str)[:400], flush=True)
    res["G_SIG"] = "PASS" if ok else "FAIL"
    if OUT:
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    print("G_SIG:", res["G_SIG"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
