"""round3_module/t03_signal_timeout_swallowed.py and t03b_signal_timeout_hang.py, rewritten: the SIGALRM timeout
idiom (handler raises an Exception subclass) around a tight loop calling the declared target inside a section.
t03: a 3 000 000-iteration loop, untraced once and traced 5 times (the repro's 20); t03b: a loop bounded at 2 s
(the repro's 5 s) standing in for `while True`, 3 trials (the repro's 10). Each trial records whether the timeout
reached the harness or the loop ran out. Requires SIGALRM (POSIX)."""
import os, signal, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r3m_fx import SIMPLE


class Timeout(Exception):
    pass


def handler(signum, frame):
    raise Timeout()


def main(api):
    fs = api.fixture("rp_fx_simple", SIMPLE)
    old = signal.signal(signal.SIGALRM, handler)
    out = {}

    def busy(n):
        s = 0
        for _ in range(n):
            s += fs.f()
        return s

    def trial(traced):
        try:
            if traced:
                res = api.trace(api.exp({"G": ["rp_fx_simple:f"]}),
                                lambda c: c.run("G", lambda: (signal.setitimer(signal.ITIMER_REAL, 0.05), busy(3_000_000))))
                return {"timeout_reached": any(s.get("raised") == "Timeout" for s in res.get("steps", [])),
                        "record_problems": res.get("record", {}).get("problems") if isinstance(res.get("record"), dict) else None}
            signal.setitimer(signal.ITIMER_REAL, 0.05)
            busy(3_000_000)
            return {"timeout_reached": False}
        except Timeout:
            return {"timeout_reached": True}
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    try:
        out["t03_untraced"] = trial(False)
        out["t03_traced"] = [trial(True) for _ in range(5)]

        def loop():
            t0 = time.monotonic()
            signal.setitimer(signal.ITIMER_REAL, 0.05)
            while time.monotonic() - t0 < 2.0:
                fs.f()
            return "ran_out"
        out["t03b"] = []
        for _ in range(3):
            res = api.trace(api.exp({"G": ["rp_fx_simple:f"]}), lambda c: c.run("G", loop))
            signal.setitimer(signal.ITIMER_REAL, 0)
            out["t03b"].append({"steps": res.get("steps"), "exit": res.get("exit")})
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    return out
