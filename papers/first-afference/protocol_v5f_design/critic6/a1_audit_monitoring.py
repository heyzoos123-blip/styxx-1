import sys
M = sys.monitoring
seen = []
def hook(ev, args):
    if 'monitoring' in ev or ev.startswith('sys.'):
        seen.append(ev)
sys.addaudithook(hook)
t = 4
M.use_tool_id(t, "x"); seen.append('--after use_tool_id')
M.get_tool(t); M.get_events(t); seen.append('--after get')
M.set_events(t, M.events.PY_UNWIND); seen.append('--after set_events')
def f(): pass
M.set_local_events(t, f.__code__, M.events.PY_START); seen.append('--after set_local_events')
M.register_callback(t, M.events.PY_START, lambda *a: None); seen.append('--after register_callback')
M.set_events(t, 0); M.free_tool_id(t)
try:
    print('get_events on freed id ->', M.get_events(t))
except Exception as e: print('get_events on freed id raises', type(e).__name__, e)
try:
    print('get_local_events on freed id ->', M.get_local_events(t, f.__code__))
except Exception as e: print('get_local_events on freed id raises', type(e).__name__, e)
print(sys.version.split()[0], seen)
