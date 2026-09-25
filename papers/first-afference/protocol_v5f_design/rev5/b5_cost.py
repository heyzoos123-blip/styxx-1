# Per-section cost of revision 5's open and close (one-call ON, one-call pop+OFF, no announcement, no wait) against
# revision 4's (announcement, wait test, _unwind_on, _unwind_off with _txn()), in the two models, test hooks unset.
# Two workloads: (a) no other section open (every open sets the event, every close clears it: the toggling path);
# (b) another section held open on another thread (the event stays set: the pre-checks' path).
import sys, time, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4, mech5
def f(): return 1
def bench(mech, n, other_open):
    if mech is mech5: mech.reset()
    else:
        mech._ANCHORS.clear(); mech._CLEARING.clear(); mech._HOOK[0] = None
        if mech.M.get_tool(4) is None: mech.M.use_tool_id(4, mech.NAME)
        mech.install_tool(); mech.M.set_events(4, 0)
    tr = mech.Tracer(f); tr.__enter__()
    hold, go = threading.Event(), threading.Event()
    th = None
    if other_open:
        th = threading.Thread(target=lambda: tr.run('B', lambda: (hold.set(), go.wait(60)))); th.start(); hold.wait(5)
    body = lambda: None
    best = None
    for rep in range(5):
        t0 = time.perf_counter()
        for _ in range(n): tr.run('A', body)
        dt = (time.perf_counter() - t0) / n * 1e6
        best = dt if best is None else min(best, dt)
    go.set()
    if th: th.join()
    tr.__exit__(None, None, None)
    # free the model's tool id so the other model can take id 4 with its own name
    for e in (mech.E.PY_START, mech.E.PY_RESUME, mech.E.PY_RETURN, mech.E.PY_YIELD, mech.E.PY_UNWIND): mech.M.register_callback(4, e, None)
    mech.M.set_events(4, 0); mech.M.free_tool_id(4)
    return best
v = sys.version.split()[0]
for other in (False, True):
    r4 = bench(mech4, 20000, other); r5 = bench(mech5, 20000, other)
    print(v, 'other section open' if other else 'no other section  ', 'rev4 %.2f us  rev5 %.2f us  (%+.2f us per section)' % (r4, r5, r5 - r4))
