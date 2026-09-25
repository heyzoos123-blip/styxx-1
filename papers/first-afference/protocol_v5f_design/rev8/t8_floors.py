# Revision 8 (the eighth critic's M4): G_ATOM's part E and part D2 made count-bounded. Each form runs until its floor
# is reached, and stops there; T_MAX = 60 s is a failure bound, not a measurement window. A control runs until its
# first violation, and fails if it reaches its floor (or T_MAX) with none. No outcome is "void": each part passes or
# fails, and nothing is re-run. Reuses rev5/t1_onecall_atomic.py's pipelines and rev6/t1d2_discriminating.py's.
import sys, os, time, threading, gc, signal
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'rev5')); sys.path.insert(0, os.path.join(HERE, '..', 'rev6'))
import t1_onecall_atomic as t1
import t1d2_discriminating as d2
M, A, T, PYU, S = t1.M, t1.A, t1.T, t1.PYU, t1.S
T_MAX = 60.0
E_FLOOR, D2_FLOOR = 50_000, 5_000

def part_e(off, control, nthreads=4):
    t1.setup()
    stop = [False]; samples = [0] * nthreads; clear = [0] * nthreads
    offc = (t1.off_onecall.__code__, t1.off_split.__code__)
    def prof(f, ev, a):
        if ev == 'c_call' and f.f_code in offc: time.sleep(0)
    def worker(i):
        sys.setprofile(prof); n = 0
        while not stop[0]:
            key = (i, n); n += 1
            A[key] = True; t1.on_onecall(key)
            for _ in range(3):
                samples[i] += 1; clear[i] += not S(); time.sleep(0)
            off(key); time.sleep(0)
        sys.setprofile(None)
    ths = [threading.Thread(target=worker, args=(i,)) for i in range(nthreads)]
    old = sys.getswitchinterval(); sys.setswitchinterval(1e-6)
    t0 = time.monotonic(); [t.start() for t in ths]
    while True:
        time.sleep(0.01)
        el = time.monotonic() - t0
        if sum(samples) >= E_FLOOR or el >= T_MAX or (control and sum(clear) > 0): break
    stop[0] = True; [t.join() for t in ths]; el = time.monotonic() - t0
    sys.setswitchinterval(old)
    s, c = sum(samples), sum(clear)
    ok = (c > 0) if control else (c == 0 and s >= E_FLOOR)
    return dict(samples=s, clear=c, seconds=round(el, 2), result='PASS' if ok else 'FAIL')

def part_d2(off, control):
    t1.setup()
    closing = [False]; st = {'fired': 0}; FLAG = [None]
    class Fin:
        def __del__(self):
            if closing[0] and 'late' not in A: st['fired'] += 1; FLAG[0] = S(); A['late'] = True
    def handler(sig, frm):
        if closing[0] and 'late' not in A: st['fired'] += 1; FLAG[0] = S(); A['late'] = True
    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 0.00002, 0.00002)
    gc.set_threshold(1, 1, 1)
    viol = iters = 0; t0 = time.monotonic()
    while True:
        A.clear(); A['closer'] = True; M.set_events(T, PYU); FLAG[0] = None
        a = Fin(); b = Fin(); a.o = b; b.o = a; del a, b
        closing[0] = True; off('closer'); closing[0] = False
        if FLAG[0] is True and 'late' in A and not S(): viol += 1
        iters += 1
        if control and viol: break
        if iters >= D2_FLOOR and st['fired'] >= D2_FLOOR: break
        if time.monotonic() - t0 >= T_MAX: break
    el = time.monotonic() - t0
    signal.setitimer(signal.ITIMER_REAL, 0, 0); signal.signal(signal.SIGALRM, old); gc.set_threshold(700, 10, 10)
    A.clear()
    ok = (viol > 0) if control else (viol == 0 and iters >= D2_FLOOR and st['fired'] >= D2_FLOOR)
    return dict(closes=iters, interrupts=st['fired'], violations=viol, seconds=round(el, 2), result='PASS' if ok else 'FAIL')

if __name__ == '__main__':
    v = sys.version.split()[0]
    print(v, 'E  one-call (floor %d samples, 0 clear)' % E_FLOOR, part_e(t1.off_onecall, False), flush=True)
    print(v, 'E  two-statement control (>= 1 clear)', part_e(t1.off_split, True), flush=True)
    print(v, 'D2 one-call (floor %d closes and %d interrupts, 0 violations)' % (D2_FLOOR, D2_FLOOR), part_d2(t1.off_onecall, False), flush=True)
    print(v, 'D2 Python-call control (>= 1 violation)', part_d2(d2.off_split_pycall, True), flush=True)
