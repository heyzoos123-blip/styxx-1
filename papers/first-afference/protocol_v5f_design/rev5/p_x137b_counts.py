# X137b (taken variant), revision 5 form, on mech5: another tool takes the freed id mid-section; then the same
# section runs again. Counts, MONITOR_LOST, and whether styxx touched the other tool's events or callback.
import sys; sys.path.insert(0, __file__.rsplit('/', 1)[0]); import mech5 as mech
M = mech.M; E = M.events
mech.reset()
def f(): return 1
def g(): return 2
def other_cb(*a): return None
with mech.Tracer(f, g) as tr:
    def body():
        f(); M.free_tool_id(4); M.use_tool_id(4, 'other-tool'); M.register_callback(4, E.RAISE, other_cb); M.set_events(4, E.RAISE); g()
    tr.run('G', body); tr.run('G', f)
r = tr.result()
print(sys.version.split()[0], r['calls'], 'ML', r['MONITOR_LOST'], 'id4 events', M.get_events(4), 'raise cb other', M.register_callback(4, E.RAISE, None) is other_cb)
M.set_events(4, 0); M.free_tool_id(4)
