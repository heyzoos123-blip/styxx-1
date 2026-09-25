# critic7 c3: G_ATOM's pass criterion (0 PY_START and 0 audit events "inside the interval") is met vacuously when the
# consumer's CALL never happens in the step's own code, so the interval never opens. Two mutant step bodies:
#   V1 _unwind_off split into two statements through a Python helper (the classic U3 split; runs Python code between
#      the pop and the clear): the interval never opens, G_ATOM's criterion reports PASS.
#   V2 _unwind_off consuming with a deque built at call time (not the bound _CONSUME): same.
# atom6.py's own measure() is used unchanged; the verdict is its criterion (not ps and not au).
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run'))
import atom6
mech = atom6.mech
M = atom6.M; E = atom6.E
def _helper(key):
    mech._ANCHORS.pop(key, None)
    if not mech._ANCHORS and M.get_tool(mech.TOOL[0]) is mech.NAME: M.set_events(mech.TOOL[0], 0)
def V1(key): _helper(key)
def V2(key):
    collections.deque(mech._chain(mech._map(mech._ANCHORS.pop, (key,), (None,)),
        mech._map(mech._set_events, mech._compress((mech.TOOL[0],), mech._map(mech._not, (mech._ANCHORS,))), (0,))), 0)
seen = {'opened': 0}
_orig_on_call = atom6.on_call
def on_call(code, off, callee, arg0):
    if callee is atom6.st['consumer']: seen['opened'] += 1
    return _orig_on_call(code, off, callee, arg0)
atom6.on_call = on_call; atom6.HARNESS.add(on_call.__code__)
v = sys.version.split()[0]
for name, fn in (('spec _unwind_off', mech._unwind_off), ('V1 python-helper split', V1), ('V2 call-time deque', V2)):
    mech.reset(); mech._ANCHORS.clear(); mech._ANCHORS['k'] = 1
    M.set_events(mech.TOOL[0], E.PY_UNWIND)
    seen['opened'] = 0
    ps, au, _ = atom6.measure(fn, atom6.CONSUME, 'k')
    print(v, '%-24s PY_START inside %-6s audit inside %-4d interval opened %d  -> G_ATOM criterion %s' % (
        name, ps or '-', len(au), seen['opened'], 'PASS' if not ps and not au else 'FAIL'), flush=True)
