# R19 says the same-thread-clearer loss needs a run_async coroutine left suspended by the interrupting code
# "and resumed on another thread". Here everything runs on ONE thread: the main thread closes B (the last anchor);
# inside its _unwind_off window, after the test found _ANCHORS empty and before the clear (mech4 hook 'off:tested',
# standing in for a signal handler / finalizer / lower-id tool callback landing there), code opens
# run_async('A', af) and leaves it suspended at its first await. The window then clears PY_UNWIND. The coroutine is
# resumed later on the SAME thread; af calls t, which raises inside its body and is caught.
import sys, threading, types
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
def t(): raise KeyError
@types.coroutine
def suspend(): yield
async def af():
    await suspend()
    try: t()
    except KeyError: pass
    return 'done'
def reset():
    mech._ANCHORS.clear(); mech._CLEARING.clear(); mech._HOOK[0] = None
    if mech.M.get_tool(4) is not None: mech.M.set_events(4, 0)

def run(point):
    reset()
    box = {}
    with mech.Tracer(t) as tr:
        def hook(p):
            if p == point and 'co' not in box:
                co = tr.run_async('A', af); box['co'] = co; co.send(None)     # opened, armed, suspended
                box['S_after_open'] = mech.events_set()
        mech._HOOK[0] = hook
        tr.run('B', lambda: None)                                           # B's close runs the window
        mech._HOOK[0] = None
        box['S_before_resume'] = mech.events_set(); box['anchors_before_resume'] = len(mech._ANCHORS)
        try: box['co'].send(None)
        except StopIteration as e: box['ret'] = e.value
    r = tr.result()
    return dict(point=point, S_after_open=box['S_after_open'], S_before_resume=box['S_before_resume'],
                anchors_before_resume=box['anchors_before_resume'], ret=box.get('ret'),
                calls_A=r['calls'].get('A'), MONITOR_LOST=r['MONITOR_LOST'])
v = sys.version.split()[0]
for point in ('off:announced', 'off:tested', 'off:cleared'):
    print(v, run(point))
