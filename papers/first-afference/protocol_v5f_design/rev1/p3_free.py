# (a)6 / L-MONITOR: what free_tool_id leaves in place on 3.12 / 3.13
import sys
M = sys.monitoring; E = M.events
hits = []
def f(): return 1
def g(): raise ValueError
M.use_tool_id(4, 'styxx.protocol')
M.register_callback(4, E.PY_START, lambda c, o: hits.append(('start', c.co_name)))
M.register_callback(4, E.PY_UNWIND, lambda c, o, e: hits.append(('unwind', c.co_name)))
M.set_local_events(4, f.__code__, E.PY_START)
M.set_events(4, E.PY_UNWIND)
f()
try: g()
except ValueError: pass
print(sys.version.split()[0], 'before free', hits); hits.clear()
M.free_tool_id(4)
f()
try: g()
except ValueError: pass
print('after free: hits', hits, 'get_tool', M.get_tool(4), 'local', M.get_local_events(4, f.__code__), 'global', M.get_events(4))
hits.clear()
print('has clear_tool_id:', hasattr(M, 'clear_tool_id'))
# another tool takes the freed id and registers only PY_START
M.use_tool_id(4, 'other')
other = []
prev = M.register_callback(4, E.PY_START, lambda c, o: other.append(c.co_name))
print('other took id 4; register_callback returned the previous (styxx) callback:', prev is not None)
f()
try: g()
except ValueError: pass
print('after reuse: styxx hits', hits, 'other hits', other, 'global events on id 4 still', M.get_events(4))
