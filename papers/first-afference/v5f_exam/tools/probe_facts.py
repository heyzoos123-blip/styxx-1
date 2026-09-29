import sys, gc, functools, types
E = sys.monitoring.events
print("ev", E.PY_START, E.PY_RESUME, E.PY_RETURN, E.PY_YIELD, E.PY_UNWIND)
def f(): return 1
c = f.__code__.replace()
print("replace fresh", c is not f.__code__, c == f.__code__)
def g(): yield 1
async def co(): pass
async def ag(): yield 1
x=g(); y=co(); z=ag()
print("gi_susp", hasattr(x,'gi_suspended'), hasattr(y,'cr_suspended'), hasattr(z,'ag_suspended'), hasattr(z, 'ag_running'))
y.close()
m = sys.monitoring
m.use_tool_id(4, "t"); m.free_tool_id(4)
try: print("gle freed", m.get_local_events(4, f.__code__))
except Exception as e: print("gle freed raises", type(e), e)
try: print("ge freed", m.get_events(4))
except Exception as e: print("ge raises", e)
w = functools.lru_cache(None)(f)
print("referents", [type(r).__name__ for r in gc.get_referents(w)])
import itertools, operator, collections
for t in (map, filter, list, itertools.chain, itertools.compress, itertools.repeat, collections.deque, operator.attrgetter):
    print(t.__module__, t.__qualname__, bool(t.__flags__ & (1<<8)))
print(operator.is_.__self__, itertools.tee.__self__ is itertools, type(dict.values), dict.values.__objclass__)
import asyncio.events
print(asyncio.events._get_running_loop, type(asyncio.events._get_running_loop))
seen=[]
def cb(code, off): seen.append(sys._getframe(1).f_code is code)
m.use_tool_id(3,"x"); m.register_callback(3, E.PY_START, cb); m.set_local_events(3, f.__code__, E.PY_START); f(); m.set_local_events(3, f.__code__, 0); m.register_callback(3, E.PY_START, None); m.free_tool_id(3)
print("getframe1", seen)
print("gc freeze count", gc.get_freeze_count())
print(type(type.__dict__['__dict__']), type(staticmethod.__dict__['__func__']))
