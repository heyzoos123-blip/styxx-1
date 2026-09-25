# MF1 (critic3/c5_retire_step6_race.py, extended to every switch point). Tracer X's exit runs _retire step 6 on
# thread X, which is paused at the points where CPython can switch threads (after a C call) on its step-6 path.
# During the first pause, section C (open when X started, so the event was set) closes on thread Z. During the last
# pause, tracer Y, still active, opens section B on thread TB. Then X resumes and finishes, and B's body calls t,
# which raises inside its body. Revision 2's step 6 tests _ANCHORS, calls get_tool, then clears (the critic's race).
# Revision 3's step 6 is _unwind_off(): its calls come first, and it tests _ANCHORS immediately before the clear.
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech3 as mech
def t(): raise KeyError
def body(ready, go):
    ready.set(); go.wait(5)
    try: t()
    except KeyError: pass
def trial(rev3, points, with_c):
    mech.REV3[0] = rev3
    reached = [threading.Event() for _ in points]; resume = [threading.Event() for _ in points]
    def hook(p):
        if threading.current_thread().name == 'X' and p in points:
            i = points.index(p); reached[i].set(); resume[i].wait(5)
    with mech.Tracer(t) as Y:
        c_open, c_close = threading.Event(), threading.Event()
        z = threading.Thread(target=lambda: Y.run('C', lambda: (c_open.set(), c_close.wait(5))), name='Z')
        if with_c: z.start(); c_open.wait(5)
        mech._HOOK[0] = hook
        x = threading.Thread(target=mech.retire_step6, name='X'); x.start()
        got = [False] * len(points)
        got[0] = reached[0].wait(0.5)
        if with_c: c_close.set(); z.join(5)
        for i in range(1, len(points)):
            resume[i - 1].set(); got[i] = reached[i].wait(0.5)
        ready, go = threading.Event(), threading.Event()
        tb = threading.Thread(target=lambda: Y.run('B', body, ready, go), name='TB'); tb.start(); ready.wait(5)
        resume[-1].set(); x.join(5); mech._HOOK[0] = None
        ev_during = mech.events_set()
        go.set(); tb.join(5)
    r = Y.result()
    return all(got), {'B calls': r['calls'].get('B', {}), 'MONITOR_LOST': r['MONITOR_LOST'],
                      'PY_UNWIND set while B open': ev_during, 'global_events after exit': mech.state()['global_events']}
v = sys.version.split()[0]
CASES = ((False, False, ('retire:tested',)),                 # the critic's interleaving
         (True, False, ('off:read',)), (True, True, ('off:read',)), (True, True, ('off:read', 'off:cleared')))
for rev3, with_c, points in CASES:
    ok, r = trial(rev3, points, with_c)
    print(v, 'rev %d, C open at start %-5s, X paused at %-24s:' % (3 if rev3 else 2, with_c, '+'.join(points)),
          r if ok else 'pause point not reached (step 6 returned before it: nothing to clear)')
mech.REV3[0] = True
