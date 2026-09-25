import sys, dis, types
sys.path.insert(0, '.')
import mech2 as mech
M=sys.monitoring; E=M.events
c = mech._outcome.__code__
n=[0]; offs=set()
def cb(code, off): n[0]+=1; offs.add(off)
M.use_tool_id(5,'inj'); M.register_callback(5, E.INSTRUCTION, cb); M.set_local_events(5, c, E.INSTRUCTION)
def deep(k, fn):
    if k == 0: return fn()
    return deep(k-1, fn)
out = deep(5, lambda: types.FunctionType(c, vars(mech))(sys._getframe(), c, ()))
print(sys.version.split()[0], 'direct call, no tracer: instruction events', n[0], 'backedges hit', sorted(offs & {i.offset for i in dis.get_instructions(c) if i.opname.startswith('JUMP_BACKWARD')}))
n[0]=0; offs.clear()
def f(): return 1
with mech.Tracer(f) as tr:
    deep(5, lambda: types.FunctionType(c, vars(mech))(sys._getframe(), c, ()))
print(sys.version.split()[0], 'direct call, tracer entered (tool 4 active): instruction events', n[0])
