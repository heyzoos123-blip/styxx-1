# G_COVER runs the crash sweep (id-5 INSTRUCTION injector) under "a LINE-event tool". coverage.py's sysmon core
# returns sys.monitoring.DISABLE from its LINE callback after the first hit. Does a LINE tool returning DISABLE
# silence another tool's INSTRUCTION events on the same code (as settrace did in rev2/p5b)?
import sys
M = sys.monitoring; E = M.events
def loop(n):
    i = 0
    while i < n:
        i += 1
    return i
offs = []
def icb(code, off): offs.append(off)
def lcb_disable(code, line): return M.DISABLE
def lcb_keep(code, line): return None
v = sys.version.split()[0]
for label, lcb in (('LINE tool returns None   ', lcb_keep), ('LINE tool returns DISABLE', lcb_disable)):
    M.use_tool_id(1, 'line'); M.register_callback(1, E.LINE, lcb); M.set_local_events(1, loop.__code__, E.LINE)
    M.use_tool_id(5, 'inj'); M.register_callback(5, E.INSTRUCTION, icb); M.set_local_events(5, loop.__code__, E.INSTRUCTION)
    M.restart_events()
    offs.clear(); loop(3); first = len(set(offs))
    offs.clear(); loop(3); second = len(set(offs))
    print(v, label, '| distinct injector offsets, 1st call:', first, ' 2nd call:', second)
    for t in (1, 5): M.set_local_events(t, loop.__code__, 0); M.register_callback(t, E.LINE if t == 1 else E.INSTRUCTION, None); M.free_tool_id(t)
