# The same idiom guarding a battery item that never terminates on its own: the harness relies on
# the alarm. Traced, the Timeout is swallowed by the hook -> the item runs forever.
import signal, time, sys
from rtlib import *
import fx_simple
class Timeout(Exception): pass
def handler(signum, frame): raise Timeout()
signal.signal(signal.SIGALRM, handler)
e = exp(spec(G={"exercises": ["fx_simple:f"]}))
for trial in range(10):
    t0 = time.time()
    try:
        with coverage_trace(e) as cov:
            with cov.section("G"):
                signal.setitimer(signal.ITIMER_REAL, 0.05)
                while time.time() - t0 < 5.0:    # stands in for "while True" (bounded for the demo)
                    fx_simple.f()
        print(f"trial {trial}: Timeout SWALLOWED - loop ran its full {time.time()-t0:.1f}s (would hang)")
    except Timeout:
        print(f"trial {trial}: Timeout delivered after {time.time()-t0:.2f}s")
    except GateSpecError as ex:
        print(f"trial {trial}: Timeout SWALLOWED - loop ran {time.time()-t0:.1f}s (would hang), then {str(ex)[:24]}")
    signal.setitimer(signal.ITIMER_REAL, 0)
