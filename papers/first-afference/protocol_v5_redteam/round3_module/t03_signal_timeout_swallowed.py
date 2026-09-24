# A harness with the common SIGALRM timeout idiom. The handler raises an Exception subclass. If the
# signal is delivered while the eval loop is inside the hook's Python code (_on_call), the hook's
# `except Exception` swallows it: the timeout never fires.
import signal, time, sys
from rtlib import *
import fx_simple
class Timeout(Exception): pass
def handler(signum, frame): raise Timeout()
def busy(n):
    s = 0
    for i in range(n):
        s += fx_simple.f()       # declared target, called in a tight loop
    return s
def trial(traced):
    signal.signal(signal.SIGALRM, handler)
    got = None
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    t0 = time.time()
    try:
        if traced:
            with coverage_trace(e) as cov:
                with cov.section("G"):
                    signal.setitimer(signal.ITIMER_REAL, 0.05)
                    busy(3_000_000)
        else:
            signal.setitimer(signal.ITIMER_REAL, 0.05)
            busy(3_000_000)
        got = "no timeout (ran to completion in %.2fs)" % (time.time() - t0)
    except Timeout:
        got = "Timeout after %.2fs" % (time.time() - t0)
    except GateSpecError as ex:
        got = "GateSpecError " + str(ex)[:60] + " after %.2fs" % (time.time() - t0)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    return got
print("untraced:", trial(False))
from collections import Counter
print("traced x20:", Counter(trial(True).split(" after")[0] for _ in range(20)))
print("sys.getprofile after:", sys.getprofile())
