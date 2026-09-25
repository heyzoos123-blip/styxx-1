# M1 fix check: add BaseEventLoop._run_once's code to the cut. A1, A2 and R17 become dispatched;
# plain credit and a section opened inside a task (credited in v5f) are unchanged; A3 stays open.
import sys, asyncio, asyncio.events as ev, asyncio.base_events as be, operator
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech
RO = vars(be.BaseEventLoop)['_run_once'].__code__
def f(): return 1
H = ev.Handle; ORIG = vars(H)['_run']
def reimpl(self): self._context.run(self._callback, *self._args)
def W(self):
    H._run = ORIG; self._context.run(self._callback, *self._args)
class MyHandle(ev.Handle):
    __slots__ = ()
    def _run(self): self._context.run(self._callback, *self._args)
class CDispatchLoop(asyncio.SelectorEventLoop):
    def _run_once(self):
        ready = list(self._ready); self._ready.clear()
        list(map(operator.call, [lambda h=h: h._context.run(h._callback, *h._args) for h in ready]))
        if not ready: super()._run_once()
def reentrant(sched, pre=lambda: None, post=lambda: None, factory=None):
    with mech.Tracer(f) as tr:
        async def main():
            loop = asyncio.get_running_loop(); pre(); sched(loop)
            tr.run('A', loop._run_once)
        if factory: l = factory(); l.run_until_complete(main()); l.close()
        else: asyncio.run(main())
    post(); return tr.result()['calls'] or 'dispatched'
def in_task():
    with mech.Tracer(f) as tr:
        async def sec(): await asyncio.sleep(0); f()
        async def main(): await tr.run_async('A', sec)
        asyncio.run(main())
    return tr.result()['calls'] or 'dispatched'
cases = {
  'A1': lambda: reentrant(lambda L: L.call_later(0, f), lambda: setattr(ev.TimerHandle, '_run', reimpl), lambda: delattr(ev.TimerHandle, '_run')),
  'A2': lambda: reentrant(lambda L: L.call_soon(f), lambda: setattr(ev, 'Handle', MyHandle), lambda: setattr(ev, 'Handle', H)),
  'R17': lambda: reentrant(lambda L: L.call_soon(f), lambda: setattr(H, '_run', W), lambda: setattr(H, '_run', ORIG)),
  'A3': lambda: reentrant(lambda L: L.call_soon(f), factory=CDispatchLoop),
  'section inside a task (valid)': in_task,
}
for with_fix in (False, True):
    if with_fix: mech._CUT.setdefault(id(RO), RO)
    print(sys.version.split()[0], 'cut + _run_once' if with_fix else 'cut as specified', {k: v() for k, v in cases.items()})
