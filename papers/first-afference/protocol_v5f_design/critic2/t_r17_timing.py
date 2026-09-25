# R17's pinned outcome (PASS, credited to A) depends on when W is bound: "Beforehand" is ambiguous.
import sys, asyncio, asyncio.events as ev
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech
def f(): return 1
H = ev.Handle; ORIG = vars(H)['_run']
def W(self):
    H._run = ORIG
    self._context.run(self._callback, *self._args)
def r17(bind_before_enter):
    if bind_before_enter: H._run = W
    with mech.Tracer(f) as tr:
        async def main():
            loop = asyncio.get_running_loop(); loop.call_soon(f)
            if not bind_before_enter: H._run = W
            tr.run('A', loop._run_once)
        asyncio.run(main())
    H._run = ORIG
    return tr.result()
print(sys.version.split()[0], 'W bound after __enter__ :', r17(False))
print(sys.version.split()[0], 'W bound before __enter__:', r17(True))
