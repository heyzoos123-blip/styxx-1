# A wait cycle through user code that revision 4 creates and revision 3 did not have.
# T1 holds a user lock L around cov.run('A', f) (e.g. `with results_lock: cov.run(...)`).
# T2 closes the last section B; inside its _unwind_off window (after the clear, before the withdrawal; mech4 hook
# 'off:cleared', standing in for a finalizer run by the gc or a signal handler landing at an eval-breaker check
# there) user code acquires L. Untraced, and under revision 3, this is not a deadlock: T2's code waits until T1's
# section ends. Under revision 4, T1's opener waits for T2's announcement while T2 waits for L held by T1:
# a guaranteed stall of the busy bound, then MACHINERY_BUSY, which refuses every gate of the trace.
import sys, threading, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
def f(): return 1
def reset():
    mech._ANCHORS.clear(); mech._CLEARING.clear(); mech._HOOK[0] = None
    if mech.M.get_tool(4) is not None: mech.M.set_events(4, 0)
def run(rev4):
    reset(); mech.REV4[0] = rev4; mech.BUSY[0] = 2.0
    L = threading.Lock(); inwin = threading.Event(); out = {}
    with mech.Tracer(f) as tr:
        opened, close = threading.Event(), threading.Event()
        def hook(p):
            if threading.current_thread().name == 'T2' and p == 'off:cleared' and not inwin.is_set():
                inwin.set()
                t0 = time.perf_counter(); got = L.acquire(timeout=30); out['t2_lock_wait'] = round(time.perf_counter() - t0, 2)
                if got: L.release()
        def t2(): tr.run('B', lambda: (opened.set(), close.wait(5)))
        def t1():
            with L:
                close.set(); inwin.wait(5)
                t0 = time.perf_counter()
                try: out['run_A'] = tr.run('A', f)
                except mech.MachineryBusy as e: out['run_A'] = 'MACHINERY_BUSY'
                out['t1_open_wait'] = round(time.perf_counter() - t0, 2)
        th2 = threading.Thread(target=t2, name='T2'); th2.start(); opened.wait(5)
        mech._HOOK[0] = hook
        th1 = threading.Thread(target=t1, name='T1'); th1.start(); th1.join(40); th2.join(40); mech._HOOK[0] = None
    mech.REV4[0] = True; mech.BUSY[0] = 10.0
    return dict(rev=4 if rev4 else 3, **out, problems=tr.core.problems)
v = sys.version.split()[0]
for rev4 in (False, True): print(v, run(rev4))
