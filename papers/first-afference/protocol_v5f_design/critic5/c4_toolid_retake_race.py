# L-MONITOR says an id another tool took is "never touched", and the Tool-acquisition prefix says a free landing
# between _ours() and set_events only makes that call raise ValueError. If the other party frees AND re-takes the
# id inside that window (another thread, or an instrument callback running there), styxx's call succeeds on the
# foreign tool's id: _unwind_off clears the other tool's global events, and _unwind_on replaces its event mask.
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
M = mech.M; E = M.events
def f(): return 1
def other_cb(*a): return None
def reset():
    mech._ANCHORS.clear(); mech._CLEARING.clear(); mech._HOOK[0] = None
    if M.get_tool(4) is not None and M.get_tool(4) != mech.NAME: M.free_tool_id(4)
    if M.get_tool(4) is None: M.use_tool_id(4, mech.NAME); mech.install_tool()
    M.set_events(4, 0)
def steal():
    M.free_tool_id(4); M.use_tool_id(4, 'other-tool')
    M.register_callback(4, E.PY_THROW, other_cb); M.set_events(4, E.PY_THROW | E.RAISE)
def run(point):
    reset(); done = [0]
    with mech.Tracer(f) as tr:
        def hook(p):
            if p == point and not done[0]: done[0] = 1; steal()
        mech._HOOK[0] = hook
        try: r = tr.run('A', f); err = None
        except Exception as e: r = None; err = type(e).__name__ + ': ' + str(e)
        mech._HOOK[0] = None
        ev = M.get_events(4); name = M.get_tool(4)
    out = dict(point=point, run=r, err=err, id4_name=name, id4_events_after=ev, other_tool_had=int(E.PY_THROW | E.RAISE))
    M.free_tool_id(4)
    return out
v = sys.version.split()[0]
for point in ('off:tested', 'on:read'): print(v, run(point))
