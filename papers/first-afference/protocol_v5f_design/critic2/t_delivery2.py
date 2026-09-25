# L-DELIVERY rate: count ValueErrors that reached `raise` and whose `except ValueError` then did not run
# because a signal-handler exception replaced them during unwinding. Untraced, CPython's unwinding has no
# eval-breaker check between `raise` and the handler. With a global PY_UNWIND callback registered (styxx
# sets one process-wide while any mint exists) the Timeout can land inside the callback.
import sys, signal, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech
class Timeout(Exception): pass
armed = [False]
def on_alarm(*a):
    if armed[0]: raise Timeout
state = [0]
def unrelated():
    state[0] = 1
    raise ValueError
def run(n):
    lost = handled = to = 0
    signal.signal(signal.SIGALRM, on_alarm)
    signal.setitimer(signal.ITIMER_REAL, 0.00002, 0.00002)
    i = 0
    while i < n:
        i += 1
        try:
            state[0] = 0
            armed[0] = True
            try:
                unrelated()
            except ValueError:
                armed[0] = False
                handled += 1
            armed[0] = False
        except Timeout as e:
            armed[0] = False
            to += 1
            if state[0] == 1 and type(e.__context__) is not ValueError: lost += 1
    signal.setitimer(signal.ITIMER_REAL, 0, 0)
    return handled, to, lost
def target(): return 1
N = 2_000_000
print(sys.version.split()[0], 'untraced:        handled %d, timeouts %d, ValueError raised then replaced (except skipped) %d' % run(N))
with mech.Tracer(target):
    print(sys.version.split()[0], 'mint registered: handled %d, timeouts %d, ValueError raised then replaced (except skipped) %d' % run(N))
