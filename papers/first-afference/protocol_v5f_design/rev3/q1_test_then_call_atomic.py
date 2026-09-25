# Revision 3 (MF1) rests on one CPython property: between a test of a dict's emptiness and the next C call, with
# only loads in between, no other thread can run and no asynchronous exception can land. 3.12/3.13 check the eval
# breaker (thread switch, signal handlers, gc, async exceptions) at RESUME, backward jumps and *after* C calls, never
# between a plain load/test and the call that follows it.
# Method: thread B toggles a shared dict D between empty and non-empty, and can be switched out in either state (a C
# call after each change), with a 1 us switch interval. Thread A evaluates `if not D: r = len(D)`. len(D) reads D when it is called, before the CALL's own
# eval-breaker check. If a switch could happen between the test and the call, A would sometimes read r == 1.
# Control: the same with one C call (abs(0)) between the test and len(D): switches do happen there.
import sys, threading, time
sys.setswitchinterval(1e-6)
D = {}
stop = [False]
def toggler():
    k = object()
    while not stop[0]:
        D[k] = 1
        abs(0)                   # a C call while D is non-empty: B can be switched out here, leaving D non-empty
        D.pop(k, None)
        abs(0)                   # and here, leaving D empty
def atomic(n):
    bad = tests = 0
    i = 0
    while i < n:
        i += 1
        if not D: r = len(D); tests += 1; bad += r
    return bad, tests
def control(n):
    bad = tests = 0
    i = 0
    while i < n:
        i += 1
        if not D:
            abs(0)
            r = len(D); tests += 1; bad += r
    return bad, tests
def spec_shape(n):               # the exact shape used in mech3._unwind_off: a return on non-empty, then the call
    bad = tests = 0
    i = 0
    while i < n:
        i += 1
        r = _off_shape()
        if r is not None: tests += 1; bad += r
    return bad, tests
def _off_shape():
    if D: return None
    return len(D)
def or_shape(n):                 # mech3/spec _unwind_off: `if _ANCHORS or set_events(tool, 0): return` on one line
    bad = tests = 0
    i = 0
    while i < n:
        i += 1
        r = D or len(D)
        if type(r) is int: tests += 1; bad += r
    return bad, tests
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3_000_000
th = threading.Thread(target=toggler); th.start()
try:
    v = sys.version.split()[0]
    for name, fn in (('test; call                  ', atomic), ('test; return-if; call        ', spec_shape), ('test or call (spec, one line)', or_shape), ('test; C call; call (control)', control)):
        t0 = time.perf_counter(); bad, tests = fn(N)
        print(v, name, ': non-empty seen at the call %d times in %d empty tests (%.1f s)' % (bad, tests, time.perf_counter() - t0))
finally:
    stop[0] = True; th.join()
