# #130279 without sys.monitoring: SIGALRM into a tight loop inside try/finally, and inside a with body.
import signal, sys, random
class Boom(Exception): pass
def h(s, f): raise Boom
signal.signal(signal.SIGALRM, h)
FIN = []
class CM:
    def __enter__(self): return self
    def __exit__(self, *a): FIN.append(1); return False
def while_try():
    try:
        i = 0
        while i < 10**9:
            i += 1
    finally:
        FIN.append(1)
def for_if_try():
    try:
        for x in range(10**9):
            if x & 1:
                pass
    finally:
        FIN.append(1)
def while_with():
    with CM():
        i = 0
        while i < 10**9:
            i += 1
for fn in (while_try, for_if_try, while_with):
    skipped = 0; N = 400
    for _ in range(N):
        FIN.clear()
        signal.setitimer(signal.ITIMER_REAL, random.uniform(0.0005, 0.003))
        try: fn()
        except Boom: pass
        if not FIN: skipped += 1
    print(sys.version.split()[0], fn.__name__, f"finally/with-exit skipped in {skipped}/{N} trials")
