"""Lifecycle / hang: an exception raised inside the hook can leave styxx's _LOCK held for ever, after
which every OTHER thread that opens or closes a section, or enters/exits a tracer, blocks for ever.

In _open, `sys.setprofile(_hook)` runs INSIDE `with _LOCK:`.  The with statement's exit then calls
the C method `_LOCK.__exit__`, which fires a 'c_call' profile event, so _hook runs right there.
The spec deliberately lets an exception raised in the hook (a signal handler's exception,
KeyboardInterrupt, RecursionError) propagate "as CPython defines" -- and CPython defines that when
the profile function fails on a c_call event, the C function is NOT called.  So the RLock release
is skipped: the exception leaves _open with _LOCK still acquired by this thread.  The thread itself
never notices (the lock is re-entrant), but no other thread can ever take _LOCK again.

Harness shape: the main thread runs traced cases under a per-case SIGALRM budget (the exam's own
H2 `Timeout(Exception)` pattern, pytest-timeout's signal method, or a Ctrl-C in a notebook) and
carries on after a timeout; later it fans cases out to worker threads that each open their own
section -- the spec's remedy for pools ("each job opens its own section, with cov.run inside the
submitted function").  The sweep varies only when the timer fires; it stops at the first cycle
after which the main thread still owns _LOCK, then runs ONE worker-thread section.

Spec: "The hook: ... no try/except, no lock, and no handler ... An exception raised in the hook
... propagates as CPython defines. ... CPython then drops the hook on that thread. The loss is
recorded as a PROFILER_LOST note at close, and afterwards that thread only under-counts."
"Re-entry through finalizers or signal handlers ... the RLock serializes it. The worst case is
lost counts plus a spurious note."  R3-D3 finalizer deadlock: CLOSED_S.  H3: "KeyboardInterrupt
raised from a signal ... Expect it to propagate and leave no hook behind."

Run: PYTHONPATH=/home/user/styxx-1 python f12_hook_exception_leaves_lock_held.py
"""
import importlib
import json
import random
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import traceback
from pathlib import Path

from styxx.protocol import Experiment, GateSpecError, coverage_trace
import styxx.protocol as P


def make_exp(gates):
    td = Path(tempfile.mkdtemp(prefix="rt4lc_"))
    g = {k: {"metric": "m", "op": ">=", "value": 0.5, **v} for k, v in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {k: True for k in g}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True)
    return Experiment(p)


def make_mod(name, src):
    td = tempfile.mkdtemp(prefix="rt4lcmod_")
    Path(td, name + ".py").write_text(textwrap.dedent(src), encoding="utf-8")
    sys.path.insert(0, td)
    return importlib.import_module(name)


mod = make_mod("rt4lc_f12", """
    def work(x=0):
        return x + 1
""")
exp = make_exp({"G": {"exercises": ["rt4lc_f12:work"]}})


class Timeout(Exception):
    pass


ARMED = [False]


def handler(signum, frame):
    if ARMED[0]:
        raise Timeout()


def reset():                      # between samples only, so the sweep can keep looking
    P._THREADS.clear(); P._ANCHORS.clear(); P._MINTED.clear(); P._BY_FN.clear()
    P._ACTIVE = 0
    sys.setprofile(None)


def main(budget=45.0):
    signal.signal(signal.SIGALRM, handler)
    rnd = random.Random(1)
    end = time.monotonic() + budget
    cycles = 0
    where = ""
    while time.monotonic() < end:
        cycles += 1
        last = None
        try:
            try:
                ARMED[0] = True
                signal.setitimer(signal.ITIMER_REAL, rnd.uniform(0.00002, 0.0004))
                with coverage_trace(exp) as cov:
                    for _ in range(3):
                        try:
                            cov.run("G", mod.work, 1)
                        except Timeout as e:          # the case's budget ran out: next case
                            last = e
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                ARMED[0] = False
        except (Timeout, GateSpecError) as e:
            last = e
        if P._LOCK._is_owned():
            if last is not None:
                tb = traceback.extract_tb(last.__traceback__)[-3:]
                where = " <- ".join(f"{fr.name}:{fr.lineno}" for fr in reversed(tb))
            break
        reset()
    else:
        print(f"no finding: {cycles} cycles, _LOCK never left held")
        return
    reset()
    # later in the same run: fan cases out to a worker thread that opens its own section
    done = threading.Event()
    with coverage_trace(exp) as cov2:            # the main thread still gets in (RLock)
        def job():
            cov2.run("G", mod.work, 2)
            done.set()
        t = threading.Thread(target=job, daemon=True)
        t.start()
        t.join(5.0)
        hung = t.is_alive()
        if hung:
            while P._LOCK._is_owned():           # let the worker go, so this script can end
                P._LOCK.release()
            t.join(5.0)
    if hung:
        print(f"FINDING-REPRODUCED: after cycle {cycles} a Timeout raised inside _hook "
              f"({where}) left styxx.protocol._LOCK owned by the main thread; a later worker-thread "
              f"section (cov.run) then blocked for 5 s in _open until the lock was force-released")
    else:
        print(f"no finding: _LOCK was left owned after cycle {cycles} but the worker got through")


if __name__ == "__main__":
    main()
