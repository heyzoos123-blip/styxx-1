# Sanity: the model reproduces the spec's expected outcomes for plain credit, X65c (cut),
# X65d (loop boundary), V63 (loop boundary in NESTED) and R17 (the disclosed residual).
import sys, asyncio, asyncio.events as ev, operator, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech

def f(): return 1
def g(): return 2

# plain
with mech.Tracer(f) as tr:
    tr.run('A', f)
print('plain', tr.result())

# X65c: re-entrant same-loop dispatch through stdlib Handle._run
def x65c():
    with mech.Tracer(f) as tr:
        async def other(): asyncio.get_running_loop().call_soon(f)
        async def main():
            loop = asyncio.get_running_loop(); await other()
            tr.run('A', loop._run_once)
        asyncio.run(main())
    return tr.result()
print('X65c', x65c())

class CDispatchLoop(asyncio.SelectorEventLoop):
    def _run_once(self):
        ready = list(self._ready); self._ready.clear()
        list(map(operator.call, [lambda h=h: h._context.run(h._callback, *h._args) for h in ready]))
        if not ready: super()._run_once()

# X65d: loop started inside the section, C dispatch, cross-thread job
def x65d():
    with mech.Tracer(f) as tr:
        def section():
            loop = CDispatchLoop()
            async def serve():
                threading.Thread(target=lambda: loop.call_soon_threadsafe(f)).start()
                await asyncio.sleep(0.05)
            loop.run_until_complete(serve()); loop.close()
        tr.run('A', section)
    return tr.result()
print('X65d', x65d())
mech.CHECK_LOOP[0] = False
print('X65d without loop boundary', x65d())
mech.CHECK_LOOP[0] = True

# V63
def v63():
    with mech.Tracer(g) as tr:
        loop = CDispatchLoop()
        async def main():
            await tr.run_async('B', _g)
        async def _g(): g()
        tr.run('A', loop.run_until_complete, main()); loop.close()
    return tr.result()
print('V63', v63())

# R17
def r17():
    H = ev.Handle; ORIG = vars(H)['_run']
    with mech.Tracer(f) as tr:
        def W(self):
            H._run = ORIG                         # restores first
            self._context.run(self._callback, *self._args)
        async def other(): asyncio.get_running_loop().call_soon(f)
        async def main():
            loop = asyncio.get_running_loop(); await other()
            H._run = W
            tr.run('A', loop._run_once)
        asyncio.run(main())
    H._run = ORIG
    return tr.result()
print('R17', r17())
