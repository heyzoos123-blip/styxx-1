# The operations revision 4 adds to, and removes from, one section, measured alone (no model hooks):
#   added   per clearing close: me = _txn() (a module-level function building a _Txn from the caller's frame),
#           _CLEARING[me] = True, _CLEARING.pop(me, None); per open: the step-8 test and `if _CLEARING:`
#   removed per open: one _unwind_on() call (its _ours() / get_tool / get_events, the event already set)
# best of 7 runs of 1,000,000 iterations each.
import sys, time, threading
M = sys.monitoring; E = M.events
M.use_tool_id(4, 'bench'); M.set_events(4, E.PY_UNWIND)
_TOOL = [4]; _TOOL_NAME = 'bench'; _CLEARING = {}; _ANCHORS = {}
class _Txn:
    __slots__ = ('tid', 'fid', 'code', 'succ')
    def __init__(self, tid, fid, code): self.tid, self.fid, self.code, self.succ = tid, fid, code, {}
def _txn():
    f = sys._getframe(1)
    return _Txn(threading.get_ident(), id(f), f.f_code)
def _named(i):
    n = M.get_tool(i)
    return type(n) is str and n == _TOOL_NAME
def _ours(): return _TOOL[0] is not None and _named(_TOOL[0])
def _unwind_on():
    if _ours() and not (M.get_events(_TOOL[0]) & E.PY_UNWIND): M.set_events(_TOOL[0], E.PY_UNWIND)
def announce_withdraw():
    me = _txn()
    _CLEARING[me] = True
    _CLEARING.pop(me, None)
class O: pass
o = O(); o.fin = {}; o.marks = {'active': True}
def recheck():
    if 'fin' in o.fin or 'exiting' in o.marks: pass
    if _CLEARING: pass
def bench(fn, n=1_000_000):
    best = 1e9
    for _ in range(7):
        t0 = time.perf_counter()
        for _ in range(n): fn()
        best = min(best, (time.perf_counter() - t0) / n * 1e6)
    return best
def nop(): pass
base = bench(nop)
a = bench(announce_withdraw) - base; r = bench(recheck) - base; u = bench(_unwind_on) - base
print(sys.version.split()[0], 'added: announce+withdraw %.3f us, re-check and _CLEARING test %.3f us; removed: one _unwind_on %.3f us; net %+.3f us per section' % (a, r, u, a + r - u))
M.set_events(4, 0); M.free_tool_id(4)
