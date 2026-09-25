# Revision 6 (M5): rev5/t1_onecall_atomic.py part D did not discriminate. Its two-statement control also showed 0
# violations (the sixth critic's M5). Two reasons, both fixed here:
#   (1) its finalizer and handler registered an anchor only while 'closer' was in A, which is false exactly in the
#       window between the control's pop and its write, so no violation could be registered there;
#   (2) gc and signal handlers run only at eval-breaker checks, and the two-statement control has none between its
#       test and its write.
# Part D2: a `closing` flag set around the call replaces the 'closer' test, and a second control splits the test
# and the write by a Python-level call (a pass-through set_events wrapper, whose RESUME is an eval-breaker check).
# The one-call step must show 0 violations; the Python-call control must show violations, or D2 is void.
import sys, gc, signal, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import t1_onecall_atomic as t1
M, A, T, PYU, S = t1.M, t1.A, t1.T, t1.PYU, t1.S
def py_set_events(tool, ev): return M.set_events(tool, ev)
def off_split_pycall(key):
    A.pop(key, None)
    if not A:
        py_set_events(T, 0)

def part_d2(off, seconds=3.0):
    t1.setup()
    closing = [False]; st = {'fired': 0}; FLAG = [None]
    class Fin:
        def __del__(self):
            if closing[0] and 'late' not in A:
                st['fired'] += 1; FLAG[0] = S(); A['late'] = True
    def handler(sig, frm):
        if closing[0] and 'late' not in A:
            st['fired'] += 1; FLAG[0] = S(); A['late'] = True
    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 0.00002, 0.00002)
    gc.set_threshold(1, 1, 1)
    viol = iters = 0; t0 = time.time()
    while time.time() - t0 < seconds:
        A.clear(); A['closer'] = True; M.set_events(T, PYU); FLAG[0] = None
        a = Fin(); b = Fin(); a.o = b; b.o = a; del a, b
        closing[0] = True
        off('closer')
        closing[0] = False
        if FLAG[0] is True and 'late' in A and not S():
            viol += 1                  # an anchor registered while S was set, and S is clear with it registered
        iters += 1
    signal.setitimer(signal.ITIMER_REAL, 0, 0); signal.signal(signal.SIGALRM, old); gc.set_threshold(700, 10, 10)
    A.clear()
    return dict(iters=iters, interrupts=st['fired'], violations=viol)

if __name__ == '__main__':
    v = sys.version.split()[0]
    for name, off in (('one-call', t1.off_onecall), ('two-statement (rev5 control)', t1.off_split),
                      ('split by a Python call (D2 control)', off_split_pycall)):
        print(v, 'D2 gc+SIGALRM', name, part_d2(off), flush=True)
