# critic8/c7: a sketch of one mechanism fix for c1. Keep every previous callback alive until the consuming call has
# made every count, by reading the exchanges through itertools.tee (C): compress yields the previous callback itself
# when it is not styxx's, and the count appends True. Each finalizer then runs only when the pipeline is released,
# after the consuming call returns. Standalone: tool id 2 stands for styxx's id; nothing else is monitored.
import sys, itertools, operator
M = sys.monitoring; E = M.events; T = 2
LOST = []; APP = LOST.append
EV5 = (E.PY_START, E.PY_RESUME, E.PY_RETURN, E.PY_YIELD, E.PY_UNWIND)
def a(*x): pass
def b(*x): pass
CB5 = (a, a, b, b, b)
NAME = 'styxx-sketch'; M.use_tool_id(T, NAME)
for e, f in zip(EV5, CB5): M.register_callback(T, e, f)
seen = []
class Repl:
    def __call__(self, *x): pass
    def __del__(self): seen.append(len(LOST))
def spec_form(t):                      # revision 7 as written
    get_tool, rc = M.get_tool, M.register_callback
    return list(itertools.chain(map(APP, filter(None, map(operator.is_not,
        map(rc, itertools.compress(itertools.repeat(t), map(operator.is_, map(get_tool, itertools.repeat(t, 5)), itertools.repeat(NAME))), EV5, CB5),
        CB5))), map(get_tool, (t,))))
def tee_form(t):                       # the sketch: the exchanges read through tee; counts made before any release
    get_tool, rc = M.get_tool, M.register_callback
    A, B = itertools.tee(map(rc, itertools.compress(itertools.repeat(t), map(operator.is_, map(get_tool, itertools.repeat(t, 5)), itertools.repeat(NAME))), EV5, CB5))
    return list(itertools.chain(map(APP, map(operator.is_not, itertools.compress(A, map(operator.is_not, B, CB5)), (None,) * 5)),
                                map(get_tool, (t,))))
for name, fn in (('spec', spec_form), ('tee', tee_form)):
    LOST.clear(); seen.clear()
    M.register_callback(T, E.PY_START, Repl()); M.register_callback(T, E.PY_UNWIND, Repl())   # two replaced slots
    r = fn(T)
    print(sys.version.split()[0], name, 'r =', ['None' if x is None else x for x in r], 'counts', len(LOST),
          'len(_LOST) seen inside each finalizer', seen)
