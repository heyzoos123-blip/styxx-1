# A real library: aiodebug 2.3.0 log_slow_callbacks.enable() rebinds Handle._run to a closure
# (enable.<locals>.instrumented) that calls the original Handle._run. Rev 2's '<locals>' clause refuses
# CUT_UNAVAILABLE for every coverage_trace() in the process while it is enabled, although dispatch still passes
# the original Handle._run code (a cut code) and _run_once (a cut code): the refusal buys no soundness here.
import sys, asyncio, asyncio.events as ev
sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/critic3_dl/x_aiodebug-2.3.0-py3-none-any')
sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/rev2')
import mech2 as mech
from aiodebug import log_slow_callbacks
ORIG = vars(ev.Handle)['_run']
def f(): return 1
def trial(label):
    try:
        with mech.Tracer(f) as tr:
            async def main():
                L = asyncio.get_running_loop(); L.call_soon(f); tr.run('A', L._run_once)   # X65c shape
            asyncio.run(main())
            async def main2(): await tr.run_async('B', asyncio.sleep, 0); tr.run('B', f)
            asyncio.run(main2())
        r = tr.result(); print(v, '%-40s' % label, 'calls', r['calls'], 'dispatched', r['dispatched'], 'CUT_MOVED', r['CUT_MOVED'])
    except mech.CutUnavailable as e:
        print(v, '%-40s' % label, 'CUT_UNAVAILABLE:', e)
v = sys.version.split()[0]
mech._CUT.clear(); mech.cut_refresh()
log_slow_callbacks.enable(10.0, on_slow_callback=lambda n, d: None)
print(v, 'Handle._run is now', ev.Handle._run.__qualname__)
mech.SHARE_CHECK[0] = True;  trial('rev2 (share check on)')
mech.SHARE_CHECK[0] = False; trial('share check off (rev1 behaviour)')
ev.Handle._run = ORIG
