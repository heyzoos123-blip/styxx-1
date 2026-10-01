"""round4/attribution/r1/a04_signal_in_close_leak.py, rewritten: a repeating SIGALRM (0.3 ms) whose handler raises
an Exception subclass while a harness runs 3000 short sections per trace, each Timeout caught and skipped; up to 5
traces (the repro retried for up to 35 s until a leak appeared; v5e's private _THREADS is not v5f's, so each
trace's leftovers are read from _v5_state()). Then a fresh tracer with no signals: its trace and _v5_state() after
its exit. Each trace's exit outcome is recorded; timing-dependent (envelope). POSIX only."""
import signal, sys


class Timeout(Exception):
    pass


def handler(signum, frame):
    raise Timeout()


def main(api):
    fx = api.fixture("rp_a04_fix", "def f(): return 1\n")
    e = api.exp({"G": ["rp_a04_fix:f"]})
    old = signal.signal(signal.SIGALRM, handler)
    out = {"traces": []}
    try:
        for _ in range(5):
            cov = api.coverage_trace(e)
            r = {"timeouts_in_sections": 0}
            try:
                with cov:
                    signal.setitimer(signal.ITIMER_REAL, 0.0003, 0.0003)
                    try:
                        for _ in range(3000):
                            try:
                                cov.run("G", fx.f)
                            except Timeout:
                                r["timeouts_in_sections"] += 1
                    finally:
                        signal.setitimer(signal.ITIMER_REAL, 0)
                r["exit"] = "clean"
            except Timeout:
                r["exit"] = "Timeout"
            except BaseException as ex:                # noqa: BLE001
                r["exit"] = type(ex).__name__
            signal.setitimer(signal.ITIMER_REAL, 0)
            r["timeouts_in_sections"] = r["timeouts_in_sections"] > 0
            r["problems"] = api.record(cov).get("problems") if isinstance(api.record(cov), dict) else None
            r["state"] = api.state()
            out["traces"].append(r)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    out["fresh"] = api.trace(e, lambda c: c.run("G", fx.f), lambda c: sys.getprofile() is None)
    out["fresh_state"] = api.state()
    return out
