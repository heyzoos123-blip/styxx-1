# A witness for the opener's own-thread skip (no SM1 row today). T2 closes B, the last anchor; inside its window
# (mech4 'off:tested', i.e. the id-3 tool's CALL callback at the clear) code on T2 runs cov.run('C', f).
# Spec: the inner open skips T2's own announcement and returns at once. Mutant (wait on every token, own thread
# included): the inner open waits for its own suspended clearer until the bound, then MACHINERY_BUSY.
import sys, threading, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
def f(): return 1
ORIG = mech._await_clearers
def await_all():                                   # the mutant: no `t.tid != me` filter
    w = list(mech._CLEARING); t0 = time.monotonic()
    while w:
        w = [t for t in w if t in mech._CLEARING and mech._tok_alive(t)]
        if not w: break
        if time.monotonic() - t0 > mech.BUSY[0]: raise mech.MachineryBusy('[V5:MACHINERY_BUSY]')
        time.sleep(0.0002)
def reset():
    mech._ANCHORS.clear(); mech._CLEARING.clear(); mech._HOOK[0] = None
    if mech.M.get_tool(4) is not None: mech.M.set_events(4, 0)
def run(mutant):
    reset(); mech.BUSY[0] = 1.0; mech._await_clearers = await_all if mutant else ORIG; out = {}
    with mech.Tracer(f) as tr:
        def hook(p):
            if threading.current_thread().name == 'T2' and p == 'off:tested' and 'inner' not in out:
                out['inner'] = None; t0 = time.perf_counter()
                try: out['inner'] = tr.run('C', f)
                except mech.MachineryBusy: out['inner'] = 'MACHINERY_BUSY'
                out['s'] = round(time.perf_counter() - t0, 2)
        mech._HOOK[0] = hook
        th = threading.Thread(target=lambda: tr.run('B', f), name='T2'); th.start(); th.join(10); mech._HOOK[0] = None
    mech._await_clearers = ORIG; mech.BUSY[0] = 10.0
    return dict(mutant=mutant, **out)
v = sys.version.split()[0]
for mu in (False, True): print(v, run(mu))
