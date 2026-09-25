# Attacks on the per-hit cut check and the loop boundary (spec: "One route is left ... R17").
import sys, asyncio, asyncio.events as ev, asyncio.base_events as be, operator, threading, functools
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech

def f(): return 1
def g(): return 2
H = ev.Handle; ORIG = vars(H)['_run']

def reimpl(self):                     # a Handle._run reimplementation: never calls the original
    self._context.run(self._callback, *self._args)

def reentrant_case(schedule, prepare=lambda: None, undo=lambda: None, loop_factory=None):
    """Section A opened in a task of the running loop; A re-enters the loop's dispatch."""
    with mech.Tracer(f) as tr:
        async def other(): schedule(asyncio.get_running_loop())
        async def main():
            loop = asyncio.get_running_loop(); await other()
            prepare()
            tr.run('A', loop._run_once)
        if loop_factory:
            lp = loop_factory(); lp.run_until_complete(main()); lp.close()
        else: asyncio.run(main())
    undo()
    return tr.result()

# A1: TimerHandle._run overridden (Handle._run untouched). Timer callbacks are dispatched by it.
had = '_run' in vars(ev.TimerHandle)
r = reentrant_case(lambda L: L.call_later(0, f),
                   prepare=lambda: setattr(ev.TimerHandle, '_run', reimpl),
                   undo=lambda: delattr(ev.TimerHandle, '_run'))
print('A1 TimerHandle._run reimplemented, left bound through exit:', r)

# A2: asyncio.events.Handle rebound to a subclass with its own _run (base_events looks up events.Handle)
class MyHandle(ev.Handle):
    __slots__ = ()
    def _run(self): self._context.run(self._callback, *self._args)
r = reentrant_case(lambda L: L.call_soon(f),
                   prepare=lambda: setattr(ev, 'Handle', MyHandle),
                   undo=lambda: setattr(ev, 'Handle', H))
print('A2 asyncio.events.Handle rebound to a subclass:', r)
ev.Handle = H

# A3: a loop subclass whose _run_once dispatches without Handle._run, re-entered inside a task-opened section
class CDispatchLoop(asyncio.SelectorEventLoop):
    def _run_once(self):
        ready = list(self._ready); self._ready.clear()
        list(map(operator.call, [lambda h=h: h._context.run(h._callback, *h._args) for h in ready]))
        if not ready: super()._run_once()
r = reentrant_case(lambda L: L.call_soon(f), loop_factory=CDispatchLoop)
print('A3 custom _run_once loop, re-entered in a task-opened section:', r)

# A4: X65b as the named witness for "monotone cut (cleared)". X65b's loop is started inside A,
# so the loop boundary alone already refuses the credit: clearing the cut changes nothing.
def x65b_like(clear_cut):
    with mech.Tracer(f) as tr:
        def section():
            if clear_cut: mech._CUT.clear()          # the E17 weakening (cut lost at an inner exit)
            loop = asyncio.new_event_loop()
            async def serve():
                threading.Thread(target=lambda: loop.call_soon_threadsafe(f)).start()
                async def job(): f()
                threading.Thread(target=lambda: asyncio.run_coroutine_threadsafe(job(), loop)).start()
                await asyncio.sleep(0.05)
            loop.run_until_complete(serve()); loop.close()
        tr.run('A', section)
    mech.cut_refresh()
    return tr.result()
print('A4 X65b, cut intact :', x65b_like(False))
print('A4 X65b, cut cleared:', x65b_like(True))

# A5: Handle._run wrapped by a generic decorator before __enter__ (V61's shape); E2 puts the
# decorator's shared inner code into the monotone cut. A harness helper decorated with the same
# decorator now acts as a cut frame, for the rest of the process.
def logged(fn):
    @functools.wraps(fn)
    def inner(*a, **k): return fn(*a, **k)
    return inner
@logged
def helper(): return f()
ev.Handle._run = logged(ORIG)
with mech.Tracer(f) as tr:
    tr.run('A', helper)
ev.Handle._run = ORIG
print('A5 helper decorated like the Handle._run wrapper:', tr.result(),
      '| shared code in cut:', mech._CUT.get(id(helper.__code__)) is helper.__code__)
with mech.Tracer(f) as tr:                          # a later, unrelated trace in the same process
    tr.run('A', helper)
print('A5 later trace, Handle._run restored long ago:', tr.result())
