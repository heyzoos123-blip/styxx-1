# _await_clearers (spec pseudocode, and mech4) reads time.monotonic and time.sleep through the time module at call
# time. A test harness that freezes time.monotonic (freezegun's documented behaviour; simulated here by a constant)
# removes the busy bound: an opener waiting for a held clearer waits for as long as the clearer is held (3 s here,
# with the bound at 1 s), instead of raising MACHINERY_BUSY at the bound (I5: "at most 10 s").
import sys, threading, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
def f(): return 1
def reset():
    mech._ANCHORS.clear(); mech._CLEARING.clear(); mech._HOOK[0] = None
    if mech.M.get_tool(4) is not None: mech.M.set_events(4, 0)
def run(frozen):
    reset(); mech.BUSY[0] = 1.0; out = {}
    real = time.monotonic
    with mech.Tracer(f) as tr:
        inwin = threading.Event()
        def hook(p):
            if threading.current_thread().name == 'T2' and p == 'off:tested' and not inwin.is_set():
                inwin.set(); time.sleep(3.0)                 # the clearer held in its window by user code
        opened, close = threading.Event(), threading.Event()
        th2 = threading.Thread(target=lambda: tr.run('B', lambda: (opened.set(), close.wait(5))), name='T2'); th2.start(); opened.wait(5)
        mech._HOOK[0] = hook; close.set(); inwin.wait(5)
        if frozen: time.monotonic = lambda: 1000.0
        t0 = time.perf_counter()
        try: out['run_A'] = tr.run('A', f)
        except mech.MachineryBusy: out['run_A'] = 'MACHINERY_BUSY'
        out['waited_s'] = round(time.perf_counter() - t0, 2)
        time.monotonic = real; th2.join(10); mech._HOOK[0] = None
    mech.BUSY[0] = 10.0
    return dict(monotonic_frozen=frozen, **out)
v = sys.version.split()[0]
for fr in (False, True): print(v, run(fr))
