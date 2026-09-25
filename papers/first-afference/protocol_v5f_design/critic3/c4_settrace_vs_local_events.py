# F1's mechanism (a settrace function silencing another tool's INSTRUCTION events) -- does it also reach the
# event set styxx uses (local PY_START/PY_RETURN on minted code, global PY_UNWIND)? Trace function returns None
# (the p5b shape) or itself (ctrace-like).
import sys
M = sys.monitoring; E = M.events
def f(): return 1
def g():
    try: raise KeyError
    except KeyError: pass
    return 2
def h(): raise ValueError
hits = {'start': 0, 'ret': 0, 'unwind': 0}
M.use_tool_id(4, 'styxx-like')
M.register_callback(4, E.PY_START, lambda c, o: hits.__setitem__('start', hits['start'] + 1))
M.register_callback(4, E.PY_RETURN, lambda c, o, r: hits.__setitem__('ret', hits['ret'] + 1))
M.register_callback(4, E.PY_UNWIND, lambda c, o, e: hits.__setitem__('unwind', hits['unwind'] + (c is h.__code__)))
for fn in (f, g, h): M.set_local_events(4, fn.__code__, E.PY_START | E.PY_RETURN)
M.set_events(4, E.PY_UNWIND)
def body():
    f(); g()
    try: h()
    except ValueError: pass
def none_tracer(frame, ev, arg): return None
def self_tracer(frame, ev, arg): return self_tracer
v = sys.version.split()[0]
for label, tr in (('no settrace', None), ('settrace returning None', none_tracer), ('settrace returning itself', self_tracer), ('after settrace(None)', None)):
    for k in hits: hits[k] = 0
    sys.settrace(tr); body(); sys.settrace(None)
    print(v, '%-28s' % label, dict(hits), '(expect start 3, ret 2, unwind 1)')
