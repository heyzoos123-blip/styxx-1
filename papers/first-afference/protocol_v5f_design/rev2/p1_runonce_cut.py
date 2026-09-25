# M1, M10, N3, N4: BaseEventLoop._run_once's code in the cut, with _cut_ok() checking both bindings.
# Runs every route for rev 1 (Handle._run only) and rev 2 (plus _run_once), and the regression cases.
import sys, asyncio, asyncio.events as ev, asyncio.base_events as be, operator, threading, signal
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech2 as mech

def f(): return 1
def g(): return 2
H = ev.Handle; ORIG = vars(H)['_run']; BEL = be.BaseEventLoop; RO = vars(BEL)['_run_once']

def reimpl(self): self._context.run(self._callback, *self._args)
def W17(self):                                    # old R17: restores Handle._run from inside its own frame
    H._run = ORIG; self._context.run(self._callback, *self._args)
def W61(self): return ORIG(self)                  # V61: a plain module-level wrapper
class MyHandle(ev.Handle):
    __slots__ = ()
    def _run(self): self._context.run(self._callback, *self._args)
class CDispatchLoop(asyncio.SelectorEventLoop):
    def _run_once(self):
        ready = list(self._ready); self._ready.clear()
        list(map(operator.call, [lambda h=h: h._context.run(h._callback, *h._args) for h in ready]))
        if not ready: super()._run_once()
def RO_restoring(self):                           # A3': a _run_once rebinding that restores itself and
    BEL._run_once = RO                            # dispatches without Handle._run
    ready = list(self._ready); self._ready.clear()
    for h in ready: h._context.run(h._callback, *h._args)

def res(tr):
    r = tr.result()
    return ('CUT_MOVED ' if r['CUT_MOVED'] else '') + (str(r['calls']) if r['calls'] else 'dispatched %s' % r['dispatched'])

def reentrant(sched, pre=lambda: None, post=lambda: None, factory=None, bind_before=None, unbind=None):
    if bind_before: bind_before()
    with mech.Tracer(f) as tr:
        async def main():
            loop = asyncio.get_running_loop(); pre(); sched(loop)
            tr.run('A', loop._run_once)
        if factory: l = factory(); l.run_until_complete(main()); l.close()
        else: asyncio.run(main())
    post()
    if unbind: unbind()
    return res(tr)

def in_task():
    with mech.Tracer(f) as tr:
        async def sec(): await asyncio.sleep(0); f()
        async def main(): await tr.run_async('A', sec)
        asyncio.run(main())
    return res(tr)

def plain():
    with mech.Tracer(f) as tr: tr.run('A', f)
    return res(tr)

def x65d():
    with mech.Tracer(f) as tr:
        def section():
            loop = CDispatchLoop()
            async def serve():
                threading.Thread(target=lambda: loop.call_soon_threadsafe(f)).start()
                await asyncio.sleep(0.05)
            loop.run_until_complete(serve()); loop.close()
        tr.run('A', section)
    return res(tr)

def v19b():
    with mech.Tracer(g) as tr:
        async def main():
            loop = asyncio.get_running_loop()
            loop.call_soon(lambda: tr.run('B', g))
            tr.run('A', loop._run_once)
        asyncio.run(main())
    return res(tr)

def v63():
    with mech.Tracer(g) as tr:
        loop = CDispatchLoop()
        async def _g(): g()
        async def main(): await tr.run_async('B', _g)
        tr.run('A', loop.run_until_complete, main()); loop.close()
    return res(tr)

def v61():
    H._run = W61
    try:
        with mech.Tracer(f) as tr:
            async def main(): await tr.run_async('A', _af)
            async def _af(): f()
            asyncio.run(main())
    except mech.CutUnavailable as e: H._run = ORIG; return 'CUT_UNAVAILABLE ' + str(e)
    H._run = ORIG
    return res(tr)

def v64():
    """N4 witness for 'monotone cut replaced': outer entered; Handle._run rebound to a module-level
    wrapper; inner tracer entered and exited (its E2 sees the wrapper); binding restored; outer calls f."""
    with mech.Tracer(f) as outer:
        H._run = W61
        with mech.Tracer(g): pass
        H._run = ORIG
        outer.run('A', f)
    return res(outer)

def n3_signal_in_reentered_run_once():
    """N3: a signal handler landing in a re-entered _run_once, outside Handle._run, calls f."""
    fired = []
    def handler(*a):
        if not fired: fired.append(1); f()
    with mech.Tracer(f) as tr:
        async def main():
            loop = asyncio.get_running_loop()
            loop.call_later(0.05, lambda: None)        # makes the re-entered _run_once block in select
            signal.signal(signal.SIGALRM, handler); signal.setitimer(signal.ITIMER_REAL, 0.01)
            tr.run('A', loop._run_once)
        asyncio.run(main())
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    return res(tr) + (' (handler ran)' if fired else ' (handler did not run)')

cases = {
  'plain (valid)': plain,
  'section inside a task (valid)': in_task,
  'X65c stdlib re-entry': lambda: reentrant(lambda L: L.call_soon(f)),
  'X65d loop started in section': x65d,
  'V19b B opens across the cut': v19b,
  'V63 boundary in NESTED': v63,
  'V61 module-level wrapper before enter': v61,
  'V64 (N4) nested enter with a rebind between': v64,
  'A1 TimerHandle._run reimpl (X65e)': lambda: reentrant(lambda L: L.call_later(0, f), lambda: setattr(ev.TimerHandle, '_run', reimpl), lambda: delattr(ev.TimerHandle, '_run')),
  'A2 events.Handle -> subclass (X65f)': lambda: reentrant(lambda L: L.call_soon(f), lambda: setattr(ev, 'Handle', MyHandle), lambda: setattr(ev, 'Handle', H)),
  'old R17, W bound after enter (X65g)': lambda: reentrant(lambda L: L.call_soon(f), lambda: setattr(H, '_run', W17), lambda: setattr(H, '_run', ORIG)),
  'old R17, W bound before enter (M10)': lambda: reentrant(lambda L: L.call_soon(f), bind_before=lambda: setattr(H, '_run', W17), unbind=lambda: setattr(H, '_run', ORIG)),
  'A3 own _run_once, no Handle._run (R18)': lambda: reentrant(lambda L: L.call_soon(f), factory=CDispatchLoop),
  "A3' _run_once rebound, self-restoring (R18)": lambda: reentrant(lambda L: L.call_soon(f), lambda: setattr(BEL, '_run_once', RO_restoring), lambda: setattr(BEL, '_run_once', RO)),
  'N3 signal handler in re-entered _run_once': n3_signal_in_reentered_run_once,
}
ver = sys.version.split()[0]
for label, ro, mode in (('rev1 cut (Handle._run)', False, 'monotone'), ('rev2 cut (+_run_once)', True, 'monotone'),
                        ('rev2 + N4 mutant: cut replaced at E2', True, 'replaced')):
    mech._CUT.clear(); mech.CUT_RUN_ONCE[0] = ro; mech.CUT_MODE[0] = mode
    print('==', ver, label)
    for k, fn in cases.items():
        if mode == 'replaced' and not k.startswith(('V64', 'plain', 'V61')): continue
        print('   %-46s %s' % (k, fn()))
