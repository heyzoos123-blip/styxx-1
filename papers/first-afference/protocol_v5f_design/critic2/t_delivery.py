# L-DELIVERY rate: a program that raises and handles ValueError in a loop, under a SIGALRM flood whose
# handler raises Timeout. Count ValueErrors that were raised but whose `except ValueError` did not run.
# Untraced, CPython unwinds without an eval-breaker check, so the count is 0; with a global PY_UNWIND
# callback (styxx sets one while any mint exists, process-wide) the Timeout can land inside the callback.
import sys, signal, time, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech
class Timeout(Exception): pass
def on_alarm(*a): raise Timeout
def unrelated():                  # not a declared target; plain library code anywhere in the process
    raise ValueError
def run(seconds):
    raised = handled = timeouts = 0; lock = threading.Lock(); leaks = 0
    signal.signal(signal.SIGALRM, on_alarm)
    signal.setitimer(signal.ITIMER_REAL, 0.00005, 0.00005)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            try:
                raised += 1
                lock.acquire()
                unrelated()
            except ValueError:
                handled += 1
                lock.release()
        except Timeout:
            timeouts += 1
            if lock.locked(): leaks += 1; lock.release()
    signal.setitimer(signal.ITIMER_REAL, 0, 0)
    return raised, handled, timeouts, leaks
def target(): return 1
for label in ('untraced', 'mint registered'):
    if label == 'untraced':
        r = run(3)
    else:
        with mech.Tracer(target):          # a mint exists: global PY_UNWIND is set
            r = run(3)
    raised, handled, timeouts, leaks = r
    # a Timeout landing before `raise` legitimately skips the handler too; isolate "raised then replaced"
    print(f"{sys.version.split()[0]} {label}: iterations {raised}, handlers run {handled}, timeouts {timeouts}, "
          f"lock left held after a Timeout {leaks}")
