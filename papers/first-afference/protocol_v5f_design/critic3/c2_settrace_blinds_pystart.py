# F1 found that a settrace function silences tool 5's INSTRUCTION events on code it traced, until
# restart_events(). Does it also silence a *local PY_START / PY_RETURN* event of another tool (the exam's id-3
# fault tool used by X92c, X135, X138, X139, X143, R16)? Order: V50/V51-style settrace over f first, then the tool.
import sys
M = sys.monitoring; E = M.events
def f(): return 1
def g(): return 2
hits = {'start': 0, 'ret': 0, 'instr': 0}
def st(frame, ev, arg): return st
v = sys.version.split()[0]
for label, pre in (('no prior settrace', None), ('settrace ran over f, then removed', st)):
    if pre: sys.settrace(pre); f(); sys.settrace(None)
    M.use_tool_id(3, 'fault'); 
    M.register_callback(3, E.PY_START, lambda c, o: hits.__setitem__('start', hits['start'] + 1))
    M.register_callback(3, E.PY_RETURN, lambda c, o, r: hits.__setitem__('ret', hits['ret'] + 1))
    M.register_callback(3, E.INSTRUCTION, lambda c, o: hits.__setitem__('instr', hits['instr'] + 1))
    M.set_local_events(3, f.__code__, E.PY_START | E.PY_RETURN | E.INSTRUCTION)
    for k in hits: hits[k] = 0
    f(); f()
    print(v, '%-36s' % label, dict(hits))
    M.set_local_events(3, f.__code__, 0); M.free_tool_id(3)
