# R19 and the greenlet bullet say the loss "is never silent": the close's UNWIND_LOST test notes MONITOR_LOST.
# Same shape as c2 (one thread, clearer interrupted at 'off:tested' by code that opens run_async('A') and leaves it
# suspended), but after A's lost raising call, an unrelated section of another tracer opens and closes on another
# thread before A closes. Its _unwind_on re-sets the event; its close does not clear it (A's anchor is registered);
# A's close then finds the event set: the call is lost with no MONITOR_LOST.
import sys, threading, types
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
def t(): raise KeyError
def h(): return 3
@types.coroutine
def suspend(): yield
async def af():
    await suspend()
    try: t()
    except KeyError: pass
    await suspend()
    return 'done'
def reset():
    mech._ANCHORS.clear(); mech._CLEARING.clear(); mech._HOOK[0] = None
    if mech.M.get_tool(4) is not None: mech.M.set_events(4, 0)
def run(other_open):
    reset(); box = {}
    with mech.Tracer(t) as tr, mech.Tracer(h) as other:
        def hook(p):
            if p == 'off:tested' and 'co' not in box:
                co = tr.run_async('A', af); box['co'] = co; co.send(None)
        mech._HOOK[0] = hook
        tr.run('B', lambda: None); mech._HOOK[0] = None
        box['co'].send(None)                         # t raises inside A with the event clear: lost
        if other_open:
            th = threading.Thread(target=lambda: other.run('C', h)); th.start(); th.join()
        try: box['co'].send(None)
        except StopIteration: pass
    r = tr.result()
    return dict(other_section_before_A_closes=other_open, calls_A=r['calls'].get('A'), MONITOR_LOST=r['MONITOR_LOST'])
v = sys.version.split()[0]
for oo in (False, True): print(v, run(oo))
