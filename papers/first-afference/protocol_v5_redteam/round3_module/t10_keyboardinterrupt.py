# Ctrl-C (default SIGINT handler -> KeyboardInterrupt, a BaseException) during a traced section:
# does it reach the harness, and what is left installed? Also a user Python profiler installed
# before the trace (chained): does it survive?
import signal, threading, sys, time, collections
from rtlib import *
import fx_simple
calls = collections.Counter()
def userprof(frame, event, arg): calls[event] += 1
out = collections.Counter()
signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
for trial in range(20):
    sys.setprofile(userprof)
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    t0 = time.time()
    try:
        with coverage_trace(e) as cov:
            with cov.section("G"):
                signal.setitimer(signal.ITIMER_REAL, 0.03)
                signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
                while time.time() - t0 < 3: fx_simple.f()
        out["no interrupt"] += 1
    except KeyboardInterrupt:
        out["KeyboardInterrupt reached harness; user profiler after: %s" %
            ("kept" if sys.getprofile() is userprof else repr(sys.getprofile()))] += 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    sys.setprofile(None)
print(dict(out)); print("threading.getprofile:", threading.getprofile())
