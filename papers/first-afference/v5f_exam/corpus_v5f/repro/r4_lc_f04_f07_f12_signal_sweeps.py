"""round4/lifecycle/r1/f04_interrupted_exit_stays_active.py, f07_resolution_swallows_signal_exception.py and
f12_hook_exception_leaves_lock_held.py, rewritten. Each repro swept a SIGALRM Timeout (an Exception subclass)
over random delays for up to 45 s, resetting v5e's private registries between samples; here each sweep is 25
samples at the repro's seeded delays (random.Random(11), (2), (1); its delay ranges), with no reset (v5f's state
after each sample is part of what is observed, through _v5_state()). f04: enter, one section, exit; per sample
whether the body completed, record()'s outcome, and after the sweep three later clean traces. f07: entering a
tracer whose targets are a functools.wraps wrapper from another module and an lru_cache target (both resolve
without a signal, checked first): per sample entered / Timeout propagated / the refusal code. f12: three sections
per trace each catching Timeout; after the sweep, a worker thread opens a section in a new trace (joined with a
5 s bound) and whether it hung. Timing-dependent (envelope). POSIX only."""
import collections, random, signal, sys, threading

F07_DECO = '''
import functools
def logged(fn):
    @functools.wraps(fn)
    def wrapper(*a, **k):
        return fn(*a, **k)
    return wrapper
'''
F07 = '''
import functools
from rp_lc_f07_deco import logged
@logged
def entry(x=0):
    return x + 1
@functools.lru_cache(None)
def cached(x=0):
    return x * 2
'''


class Timeout(Exception):
    pass


def main(api):
    ARMED = [False]

    def handler(signum, frame):
        if ARMED[0]:
            raise Timeout()
    old = signal.signal(signal.SIGALRM, handler)
    out = {}

    def code_of(ex):
        m = str(ex)
        return m[4:m.index("]")] if m.startswith("[V5:") else type(ex).__name__

    def arm(delay):
        ARMED[0] = True
        signal.setitimer(signal.ITIMER_REAL, delay)

    def disarm():
        signal.setitimer(signal.ITIMER_REAL, 0)
        ARMED[0] = False
    try:
        mod = api.fixture("rp_lc_f04", "def work(x=0):\n    return x + 1\n")
        e = api.exp({"G": ["rp_lc_f04:work"]})
        rnd, seen = random.Random(11), collections.Counter()
        for _ in range(25):
            cov, done = None, [False]
            try:
                try:
                    arm(rnd.uniform(0.00002, 0.0004))
                    cov = api.coverage_trace(e)
                    with cov:
                        cov.run("G", mod.work, 1)
                        done[0] = True
                finally:
                    disarm()
                res = "clean"
            except BaseException as ex:                # noqa: BLE001
                res = code_of(ex)
            rec = api.record(cov) if cov is not None else None
            rcode = rec.get("code") if isinstance(rec, dict) and "raised" in rec else ("record" if rec else None)
            seen[f"{res}|body={done[0]}|record={rcode}"] += 1
        out["f04_samples"] = dict(sorted(seen.items()))
        out["f04_state"] = api.state()
        out["f04_later"] = [api.trace(e, lambda c: c.run("G", mod.work, 1)) for _ in range(3)]
        api.fixture("rp_lc_f07_deco", F07_DECO)
        m7 = api.fixture("rp_lc_f07", F07)
        e7 = api.exp({"G": ["rp_lc_f07:entry", "rp_lc_f07:cached"]})
        out["f07_control"] = api.trace(e7, lambda c: c.run("G", lambda: (m7.cached.cache_clear(), m7.entry(1), m7.cached(1)) and None))
        rnd, seen = random.Random(2), collections.Counter()
        for _ in range(25):
            try:
                try:
                    arm(rnd.uniform(0.000005, 0.00008))
                    with api.coverage_trace(e7):
                        pass
                finally:
                    disarm()
                seen["entered"] += 1
            except Timeout:
                seen["Timeout propagated"] += 1
            except BaseException as ex:                # noqa: BLE001
                seen[code_of(ex)] += 1
        out["f07_samples"] = dict(sorted(seen.items()))
        out["f07_state"] = api.state()
        m12 = api.fixture("rp_lc_f12", "def work(x=0):\n    return x + 1\n")
        e12 = api.exp({"G": ["rp_lc_f12:work"]})
        rnd, seen = random.Random(1), collections.Counter()
        for _ in range(25):
            caught = 0
            try:
                try:
                    arm(rnd.uniform(0.00002, 0.0004))
                    with api.coverage_trace(e12) as cov:
                        for _ in range(3):
                            try:
                                cov.run("G", m12.work, 1)
                            except Timeout:
                                caught += 1
                finally:
                    disarm()
                res = "clean"
            except BaseException as ex:                # noqa: BLE001
                res = code_of(ex)
            seen[f"{res}|caught_in_section={caught > 0}"] += 1
        out["f12_samples"] = dict(sorted(seen.items()))
        out["f12_state"] = api.state()
        done = threading.Event()
        r = {}

        def worker_h(c):
            def job():
                try:
                    c.run("G", m12.work, 2)
                finally:
                    done.set()
            t = threading.Thread(target=job, daemon=True)
            t.start()
            t.join(5.0)
            r["hung"] = t.is_alive()
        r["trace"] = api.trace(e12, worker_h)
        out["f12_worker"] = r
    finally:
        disarm()
        signal.signal(signal.SIGALRM, old)
    return out
