# rev9 verifier: CPython facts behind the 164 sentences new in revision 9 (rev9_new_sentences.json).
# Pure CPython probes; imports nothing from styxx or v5f_exam. Each line prints CLAIM-id: result.
# Run: <venv3.12|venv3.13>/bin/python p_cpython_rev9.py
import sys, os, types, sysconfig, inspect, asyncio, collections, importlib, tempfile, gc

def out(tag, ok, detail=''):
    print('%-44s %s %s' % (tag, 'OK  ' if ok else 'FAIL', detail))

print(sys.version.split()[0], sys.implementation.name)
sm = sys.monitoring

# #223 / GAP-01: event masks are literal 1,2,4,8,4096
ev = sm.events
vals = (ev.PY_START, ev.PY_RESUME, ev.PY_RETURN, ev.PY_YIELD, ev.PY_UNWIND)
out('#223 event masks 1,2,4,8,4096', vals == (1, 2, 4, 8, 4096), vals)

# #181 GIL test: Py_GIL_DISABLED falsy; _is_gil_enabled None or true
g = getattr(sys, '_is_gil_enabled', None)
out('#181 Py_GIL_DISABLED falsy', not sysconfig.get_config_var('Py_GIL_DISABLED'), repr(sysconfig.get_config_var('Py_GIL_DISABLED')))
out('#181 g is None or g()', g is None or g(), 'g=%r' % (g,))

# #119/#194: asyncio.events._get_running_loop is the builtin of _asyncio
grl = asyncio.events._get_running_loop
out('#194 type BuiltinFunctionType', type(grl) is types.BuiltinFunctionType, type(grl).__name__)
out('#194 __name__', grl.__name__ == '_get_running_loop')
out('#194 __self__ is _asyncio', grl.__self__ is sys.modules.get('_asyncio'), repr(grl.__self__))

# #369/#493/#958: audit events of the sys.monitoring functions; get_local_events on unused/freed/foreign ids
seen = []
armed = [False]
def hook(e, a):
    if armed[0]:
        seen.append(e)
sys.addaudithook(hook)
def code(): pass
CODE = code.__code__   # read once: a function's __code__ read itself raises object.__getattr__
T = 5
calls = {
    'get_tool': lambda: sm.get_tool(T),
    'get_events': lambda: sm.get_events(T),
    'get_local_events': lambda: sm.get_local_events(T, CODE),
}
sm.use_tool_id(T, 'probe')
calls['set_events'] = lambda: sm.set_events(T, 0)
calls['set_local_events'] = lambda: sm.set_local_events(T, CODE, 0)
for n, f in calls.items():
    seen.clear(); armed[0] = True; f(); armed[0] = False
    out('#369 %s raises no audit event' % n, seen == [], seen)
sm.free_tool_id(T)
seen.clear(); armed[0] = True; sm.use_tool_id(T, 'probe'); armed[0] = False
out('#369 use_tool_id raises no audit event', seen == [], seen)
sm.free_tool_id(T)
seen.clear(); armed[0] = True; sm.register_callback(1, ev.PY_START, None); armed[0] = False
out('#958 register_callback raises one audit event', seen == ['sys.monitoring.register_callback'], seen)
# exchange and restore: 5 events x 2 calls = 10 audit events
sm.use_tool_id(T, 'probe')
cbs = [ev.PY_START, ev.PY_RESUME, ev.PY_RETURN, ev.PY_YIELD, ev.PY_UNWIND]
mine = lambda *a: None
for e in cbs: sm.register_callback(T, e, mine)
seen.clear(); armed[0] = True
got = []
for e in cbs:
    c = sm.register_callback(T, e, None); got.append(c); sm.register_callback(T, e, c)
armed[0] = False
out('#958 exchange-and-restore: 10 events', len(seen) == 10 and all(c is mine for c in got), len(seen))
out('#958 no callback getter in sys.monitoring', not any('get_callback' in n for n in dir(sm)), [n for n in dir(sm) if 'callback' in n])
sm.free_tool_id(T)
def never_raises(tid, label):
    try:
        v = sm.get_local_events(tid, CODE); out('#493 get_local_events %s' % label, True, v)
    except Exception as e:
        out('#493 get_local_events %s' % label, False, repr(e))
never_raises(T, 'unused id')
sm.use_tool_id(T, 'x'); sm.set_local_events(T, CODE, ev.PY_RETURN); sm.free_tool_id(T)
never_raises(T, 'freed id')
sm.use_tool_id(T, 'other'); sm.set_local_events(T, CODE, ev.PY_RETURN)
never_raises(T, 'foreign-held id'); sm.set_local_events(T, CODE, 0); sm.free_tool_id(T)

# #548: builtins.id and object.__getattr__ (f_code read) raise audit events; sys._getframe too
f = sys._getframe()
for label, fn, want in (('id()', lambda: id(f), 'builtins.id'),
                        ('frame.f_code', lambda: f.f_code, 'object.__getattr__'),
                        ('sys._getframe', lambda: sys._getframe(), 'sys._getframe')):
    seen.clear(); armed[0] = True; fn(); armed[0] = False
    out('#548 %s raises %s' % (label, want), want in seen, seen)

# #193: deque(maxlen=0).extend is a builtin method; __self__ type is collections.deque
d = collections.deque(maxlen=0)
out('#193 deque(maxlen=0).extend builtin method', type(d.extend) is types.BuiltinMethodType and d.extend.__self__ is d and d.maxlen == 0)
d.extend(iter([1, 2, 3])); out('#193 extend consumes and keeps nothing', len(d) == 0)

# #528/#91/#128: _TYPE_QUAL.__get__(cls) runs no metaclass property
_TYPE_QUAL = type.__dict__['__qualname__']
ran = []
# a metaclass cannot hold a __qualname__ property (type.__new__ requires a str), so the metaclass code
# that an attribute read would run is a __getattribute__ override
class Meta(type):
    def __getattribute__(cls, n):
        if n == '__qualname__':
            ran.append(1); return 'LIE'
        return type.__getattribute__(cls, n)
class X(metaclass=Meta): pass
q1 = _TYPE_QUAL.__get__(X)
out('#528 descriptor read runs no metaclass code', q1 == 'X' and ran == [], (q1, ran))
q2 = X.__qualname__
out('#528 (control) attribute read runs it', q2 == 'LIE' and ran == [1], q2)
out('#91 NoneType / function qualnames', _TYPE_QUAL.__get__(type(None)) == 'NoneType' and _TYPE_QUAL.__get__(types.FunctionType) == 'function')
from collections import OrderedDict
out('#898 OrderedDict qualname', _TYPE_QUAL.__get__(OrderedDict) == 'OrderedDict')

# #169: the CREATED test == inspect's CREATED state, per lazy type; attributes exist
def gen(): yield 1
async def co(): pass
async def agen(): yield 1
def created(o):
    for p in ('gi_', 'cr_', 'ag_'):
        if hasattr(o, p + 'frame'):
            return getattr(o, p + 'frame') is not None and not getattr(o, p + 'running') and not getattr(o, p + 'suspended')
def istate(o):
    if isinstance(o, types.GeneratorType): return inspect.getgeneratorstate(o)
    if isinstance(o, types.CoroutineType): return inspect.getcoroutinestate(o)
    return inspect.getasyncgenstate(o)
for mk in (gen, co, agen):
    o = mk()
    out('#169 %s fresh: CREATED test == inspect' % mk.__name__, created(o) is True and istate(o).endswith('CREATED'), istate(o))
    if isinstance(o, types.GeneratorType): next(o)
    elif isinstance(o, types.CoroutineType):
        try: o.send(None)
        except StopIteration: pass
    out('#169 %s started/other: test == inspect' % mk.__name__, created(o) == istate(o).endswith('CREATED'), istate(o))
    o.close() if hasattr(o, 'close') else None
# the cross-version shape: aclose() awaitable created and closed unawaited
a = agen(); aw = a.aclose(); aw.close()
out('#169 F34 shape (aclose unawaited): state', True, 'created_test=%s inspect=%s ag_frame_is_None=%s' % (created(a), istate(a), a.ag_frame is None))

# #484/#485: register_at_fork after_in_child runs in registration order; reload re-runs in same dict
tmp = tempfile.mkdtemp(); sys.path.insert(0, tmp)
open(os.path.join(tmp, 'rl_mod.py'), 'w').write('import os\nN = globals().get("N", 0) + 1\n_ME = N\nos.register_at_fork(after_in_child=lambda k=_ME: print("child handler registered by load", k, "reads _ME =", _ME, flush=True))\n')
import rl_mod
d0 = rl_mod.__dict__
importlib.reload(rl_mod)
out('#485 reload re-runs module in the same dict', rl_mod.__dict__ is d0 and rl_mod.N == 2, rl_mod.N)
sys.stdout.flush()
pid = os.fork()
if pid == 0:
    os._exit(0)
os.waitpid(pid, 0)
print('#484 expect above: load 1 then load 2 (oldest first), each reading _ME = 2 (same globals)')
