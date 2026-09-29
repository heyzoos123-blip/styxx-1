import sys, types
M = sys.monitoring
E = M.events
print(sys.version.split()[0], "events", E.PY_START, E.PY_RESUME, E.PY_RETURN, E.PY_YIELD, E.PY_UNWIND)
f = M.get_local_events
print("gle", type(f) is types.BuiltinFunctionType, f.__self__ is M, f.__name__)
aud = []
def hook(ev, args):
    if ev.startswith("sys.monitoring"): aud.append(ev)
sys.addaudithook(hook)
def g(): pass
code = g.__code__
# unused id
for label, prep in (("unused", lambda: None),):
    try: print(label, M.get_local_events(4, code))
    except Exception as e: print(label, "raises", type(e).__name__, e)
M.use_tool_id(4, "x"); M.set_local_events(4, code, 1)
print("owned", M.get_local_events(4, code))
M.free_tool_id(4)
try: print("freed", M.get_local_events(4, code))
except Exception as e: print("freed raises", type(e).__name__, e)
M.use_tool_id(4, "other")
print("taken by other", M.get_local_events(4, code))
print("audit events from get_local_events:", aud)
import asyncio, asyncio.events as ev
r = ev._get_running_loop
print("grl", type(r), type(r) is types.BuiltinFunctionType, r.__name__, getattr(r,'__self__',None), getattr(r,'__module__',None), r.__self__ is sys.modules.get('_asyncio'))
print("same as asyncio._get_running_loop", r is asyncio._get_running_loop, "is events.get_running_loop's c?", ev.get_running_loop)
