# M1 witness X141c: BaseEventLoop._run_once rebound during the trace (after __enter__) to W that dispatches ready
# callbacks without Handle._run and does NOT restore itself; restored after exit. Section A, opened in a task,
# re-enters loop._run_once(). Spec (rev 2): the hit sees the moved _run_once binding -> CUT_MOVED. Mutant: _cut_ok()
# checks only Handle._run (the _run_once code is still a cut code, but W is not) -> credited, no CUT_MOVED.
import sys, asyncio, asyncio.base_events as be
sys.path.insert(0, '.')
import mech2 as mech
def f(): return 1
BEL = be.BaseEventLoop; RO = vars(BEL)['_run_once']
def W(self):
    ready = list(self._ready); self._ready.clear()
    for h in ready: h._context.run(h._callback, *h._args)
def case():
    with mech.Tracer(f) as tr:
        async def main():
            loop = asyncio.get_running_loop(); BEL._run_once = W; loop.call_soon(f)
            tr.run('A', loop._run_once)
            BEL._run_once = RO
        asyncio.run(main())
    r = tr.result()
    return ('CUT_MOVED ' if r['CUT_MOVED'] else 'no CUT_MOVED ') + str(r['calls'] or 'dispatched %s' % r['dispatched'])
spec = case()
orig_bindings = mech._bindings
mech._bindings = lambda: [mech._HANDLE_DICT[0].get('_run')]     # mutant: _cut_ok() ignores the _run_once binding
mut = case()
print(sys.version.split()[0], 'X141c spec:', spec, '| mutant (no _run_once binding check):', mut)
