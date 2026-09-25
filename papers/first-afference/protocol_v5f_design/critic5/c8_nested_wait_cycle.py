# I5: "A clearer never waits for anything, so no cycle of waits exists inside the machinery." A clearer's window can
# contain an opener on the same thread (a finalizer, profiler or lower-id-tool callback that runs a section: mech4's
# hook at 'off:tested' stands in for it); that opener waits for clearers of OTHER threads, so the clearer below it
# waits too. Two threads in that state at once wait on each other: a cycle inside the machinery, broken only by the
# busy bound (1 s here, 10 s in the spec): one inner open raises MACHINERY_BUSY after the full bound.
import sys, threading, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
def f(): return 1
def reset():
    mech._ANCHORS.clear(); mech._CLEARING.clear(); mech._HOOK[0] = None
    if mech.M.get_tool(4) is not None: mech.M.set_events(4, 0)
def run(rev4):
    reset(); mech.REV4[0] = rev4; mech.BUSY[0] = 1.0
    out = {}; fired = set(); popped = threading.Barrier(2); tested = threading.Barrier(2); opened = threading.Barrier(2)
    with mech.Tracer(f) as tr:
        def hook(p):
            n = threading.current_thread().name
            if n not in ('T1', 'T2') or n in fired: return
            if p == 'detach:popped': popped.wait(5)          # both outer sections popped: each test finds none
            if p in ('off:tested', 'off:read') and (rev4 and p == 'off:tested' or not rev4 and p == 'off:read'):
                fired.add(n); tested.wait(5)                 # both clearers inside their windows
                t0 = time.perf_counter()
                try: out[n] = tr.run('I' + n, f)             # a section run from inside the window
                except mech.MachineryBusy: out[n] = 'MACHINERY_BUSY'
                out[n + '_s'] = round(time.perf_counter() - t0, 2)
        def worker():
            def body(): opened.wait(5)                       # both outer sections open before either closes
            tr.run('S' + threading.current_thread().name, body)
        mech._HOOK[0] = hook
        ths = [threading.Thread(target=worker, name=n) for n in ('T1', 'T2')]
        [t.start() for t in ths]; [t.join(20) for t in ths]; mech._HOOK[0] = None
    mech.BUSY[0] = 10.0; mech.REV4[0] = True
    return dict(rev=4 if rev4 else 3, **out)
v = sys.version.split()[0]
for rev4 in (False, True):
    for i in range(2): print(v, run(rev4))
