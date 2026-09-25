# M2: a Handle._run binding whose code is shared (a generic decorator's inner function) poisons the monotone cut.
# Rev 2: E2 refuses CUT_UNAVAILABLE when the binding's code is new to the cut and either its co_qualname contains
# '<locals>' (a factory can make more functions with it) or gc finds another function holding it.
# Also: the one-off cost of that gc scan, and a nest_asyncio-shaped loop (own _run_once calling handle._run()).
import sys, functools, time, types, asyncio, asyncio.events as ev, asyncio.base_events as be
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech2 as mech
def f(): return 1
H = ev.Handle; ORIG = vars(H)['_run']
def logged(fn):
    @functools.wraps(fn)
    def inner(*a, **k): return fn(*a, **k)
    return inner
@logged
def helper(): return f()
def W(self): return ORIG(self)                     # module level, unique: V61's shape

def trace_helper():
    with mech.Tracer(f) as tr: tr.run('A', helper)
    r = tr.result(); return r['calls'] or 'dispatched %s' % r['dispatched']

def attempt(binding):
    mech._CUT.clear(); mech.cut_refresh()          # the stdlib codes first, as a constructor would
    H._run = binding
    try:
        out = trace_helper()
    except mech.CutUnavailable as e:
        out = 'CUT_UNAVAILABLE (%s)' % e
    H._run = ORIG
    later = trace_helper()                          # a later, unrelated trace, binding restored
    return out, later

ver = sys.version.split()[0]
for share in (False, True):
    mech.SHARE_CHECK[0] = share
    print('==', ver, 'rev2 share check' if share else 'rev1 (no share check)')
    out, later = attempt(logged(ORIG))
    print('   %-34s this trace: %-44s later trace: %s' % ('logged(ORIG), decorator inner', out, later))
    out, later = attempt(W)
    print('   %-34s this trace: %-44s later trace: %s' % ('module-level W (V61)', out, later))
    twin = types.FunctionType(W.__code__, globals(), 'W_twin')     # a second live function with W's code
    out, later = attempt(W)
    print('   %-34s this trace: %-44s later trace: %s' % ('W while a twin shares its code', out, later))
    del twin

# nest_asyncio shape: the loop class's own _run_once dispatches through handle._run()
class NestLoop(asyncio.SelectorEventLoop):
    def _run_once(self):
        ready = list(self._ready); self._ready.clear()
        for h in ready: h._run()
mech.SHARE_CHECK[0] = True; mech._CUT.clear()
with mech.Tracer(f) as tr:
    async def main():
        loop = asyncio.get_running_loop(); loop.call_soon(f); tr.run('A', loop._run_once)
    l = NestLoop(); l.run_until_complete(main()); l.close()
print('  ', ver, 'nest_asyncio-shaped loop re-entered:', tr.result()['calls'] or 'dispatched %s' % tr.result()['dispatched'])

# cost of the one-off scan for a code new to the cut, by heap size
for n in (100_000, 1_000_000):
    junk = [[i] for i in range(n)]
    t0 = time.perf_counter(); mech._shared(ORIG); t1 = time.perf_counter()
    print('  ', ver, 'gc scan for one new cut code, %d extra tracked objects: %.1f ms' % (n, (t1 - t0) * 1e3))
    del junk
