# A2: asyncio.events.Handle rebound to a subclass with its own _run, before the callback is scheduled.
# Handle._run itself is untouched, so _cut_ok() stays true and no CUT_MOVED is recorded.
import sys, asyncio, asyncio.events as ev
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech
def f(): return 1
H = ev.Handle
class MyHandle(ev.Handle):
    __slots__ = ()
    def _run(self): self._context.run(self._callback, *self._args)
with mech.Tracer(f) as tr:
    async def main():
        loop = asyncio.get_running_loop()
        ev.Handle = MyHandle
        loop.call_soon(f)                  # scheduled by the harness's other code, not by A
        tr.run('A', loop._run_once)
        ev.Handle = H
    asyncio.run(main())
print(sys.version.split()[0], 'A2 events.Handle rebound during the trace, restored before exit:', tr.result())
