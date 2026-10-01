"""round4/py313_signal_backedge.py, rewritten: its second check, against v5f. A tracer with 300 openings is exited
under a SIGALRM whose handler raises KeyboardInterrupt, armed at 30%, 40%, 50% and 60% of a clean exit's duration
(measured first); after each trial: whether the exit was interrupted, record(), _v5_state(), and whether another
thread can complete a trace within 5 s. Its first check (four loop shapes interrupted by SIGALRM, whether finally
runs) exercises only the interpreter, not the API (NOT_APPLICABLE.json); X140's sweep covers v5f's back-edges.
Timing-dependent (envelope). POSIX only."""
import signal, threading, time


def main(api):
    m = api.fixture("rp_py313_fx", "def f(x=0):\n    return x\n")
    e = api.exp({"G": ["rp_py313_fx:f"]})

    def build():
        cov = api.coverage_trace(e)
        cov.__enter__()
        for _ in range(300):
            cov.run("G", m.f, 1)
        return cov
    cov = build()
    t0 = time.perf_counter()
    cov.__exit__(None, None, None)
    dt = time.perf_counter() - t0

    def h(s, fr):
        raise KeyboardInterrupt
    old = signal.signal(signal.SIGALRM, h)
    trials = []
    try:
        for k in range(4):
            cov = build()
            r = {}
            signal.setitimer(signal.ITIMER_REAL, max(dt * (0.3 + 0.1 * k), 1e-6))
            try:
                cov.__exit__(None, None, None)
                r["interrupted"] = False
            except KeyboardInterrupt:
                r["interrupted"] = True
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            r["record"] = api.record(cov)
            r["state"] = api.state()
            done, box = threading.Event(), {}

            def other():
                box["trace"] = api.trace(e, lambda c: c.run("G", m.f, 2)).get("score")
                done.set()
            t = threading.Thread(target=other, daemon=True)
            t.start()
            t.join(5.0)
            r["other_thread_completed"] = done.is_set()
            r["other_thread_score"] = box.get("trace")
            r["interrupted"] = None
            trials.append(r)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    return {"trials": trials}
