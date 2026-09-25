# (a)2: a transient rebind of Handle._run (or a __code__ swap), restored before exit, removes the cut
# frame from a dispatched call's chain; the binding observed AT THE HIT is the moved one.
import asyncio, asyncio.events as ev, sys, types
H = ev.Handle; ORIG = vars(H)['_run']; CUT = {id(ORIG.__code__): ORIG.__code__}
seen = {}
def cut_ok():
    h = vars(H).get('_run')
    return type(h) is types.FunctionType and CUT.get(id(h.__code__)) is h.__code__
def f():
    codes = []; fr = sys._getframe(1)
    while fr is not None: codes.append(fr.f_code); fr = fr.f_back
    before_anchor = codes[:next(i for i, c in enumerate(codes) if c is _run.__code__)]
    seen['cut_frame_before_anchor'] = any(CUT.get(id(c)) is c for c in before_anchor)
    seen['cut_ok_at_hit'] = cut_ok()
def W(self):                                   # a reimplementation, not a wrapper of the original
    self._context.run(self._callback, *self._args)
def section(loop, how):
    if how == 'rebind': H._run = W
    else: ORIG.__code__ = W.__code__
    loop._run_once()
    if how == 'rebind': H._run = ORIG
    else: ORIG.__code__ = CUT[next(iter(CUT))]
def _run(fn, *a): return fn(*a)
async def main(how):
    loop = asyncio.get_running_loop(); loop.call_soon(f); await asyncio.sleep(0) if False else None
    _run(section, loop, how)
for how in ('rebind', 'code-swap'):
    seen.clear(); asyncio.run(main(how))
    print(sys.version.split()[0], how, seen, '| restored before exit:', cut_ok())
