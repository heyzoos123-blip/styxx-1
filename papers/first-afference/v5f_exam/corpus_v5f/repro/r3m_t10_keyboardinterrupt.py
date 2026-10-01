"""round3_module/t10_keyboardinterrupt.py, rewritten: a SIGALRM handler raising KeyboardInterrupt while a section
calls the declared target in a loop bounded at 3 s, with a user Python profiler installed before the trace; 5
trials (the repro's 20). Each records whether the interrupt reached the harness and whether the user profiler is
still installed after. Requires SIGALRM (POSIX)."""
import collections, os, signal, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r3m_fx import SIMPLE


def main(api):
    fs = api.fixture("rp_fx_simple", SIMPLE)
    calls = collections.Counter()

    def userprof(frame, event, arg):
        calls[event] += 1

    def kbi(*a):
        raise KeyboardInterrupt()
    old = signal.signal(signal.SIGALRM, kbi)
    trials = []
    try:
        for _ in range(5):
            sys.setprofile(userprof)

            def loop():
                t0 = time.monotonic()
                signal.setitimer(signal.ITIMER_REAL, 0.03)
                while time.monotonic() - t0 < 3:
                    fs.f()
                return "no_interrupt"
            try:
                res = api.trace(api.exp({"G": ["rp_fx_simple:f"]}), lambda c: c.run("G", loop))
                r = {"steps": res.get("steps"), "exit": res.get("exit"), "escaped": None}
            except KeyboardInterrupt:
                r = {"escaped": "KeyboardInterrupt"}
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            r["user_profiler_kept"] = sys.getprofile() is userprof
            sys.setprofile(None)
            trials.append(r)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    return {"trials": trials, "threading_getprofile_none": threading.getprofile() is None}
