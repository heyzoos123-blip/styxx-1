# Revision 6 (M4, M5): a prototype of the frozen DYNAMIC premise gate G_ATOM, run here against rev6/mech6.py.
#
# For each one-call function, in each of its gate outcomes, the step is invoked with three instruments armed:
#   * sys.monitoring tool id 5: global PY_START (every Python function that starts), and CALL / C_RETURN / C_RAISE as
#     local events on the step function's own code, which mark the interval between the consumer's CALL and its
#     C_RETURN or C_RAISE (the consumer is the step's outermost call: deque.extend or list);
#   * an audit hook that records every audit event;
#   * a sys.setprofile function (an instrument that runs Python code at every C call made from Python code).
# Inside that interval it counts PY_START events of code that is not the harness's own, and audit events.
# Pass criteria (frozen with G_ATOM): _unwind_on, _unwind_off, _take, _set_local: 0 and 0. _register: 0 PY_START,
# and exactly one audit event per exchange, all 'sys.monitoring.register_callback' (B1: disclosed, not atomic).
# Discriminating controls, which MUST show violations or the gate run is void:
#   K1 a pipeline calling a pure-Python pass-through of set_events (the M1 shape)       -> PY_START inside
#   K2 an attrgetter over a class whose __getattribute__ is Python                       -> PY_START inside
#   K3 a pipeline calling sys._getframe (an audited C function)                          -> an audit event inside
#   K4 revision 5's _register form                                                       -> 5 audit events, as _register
import sys, operator, itertools, collections, types
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech6 as mech
M = sys.monitoring; E = M.events
ATOM = 5
st = {'inside': 0, 'consumer': None, 'pystart': [], 'audit': []}
HARNESS = set()

def on_call(code, off, callee, arg0):
    if callee is st['consumer']: st['inside'] += 1
def on_cret(code, off, callee, arg0):
    if callee is st['consumer'] and st['inside']: st['inside'] -= 1
def on_pystart(code, off):
    if st['inside'] and code not in HARNESS: st['pystart'].append(code.co_qualname)
def audit(ev, args):
    if st['inside']: st['audit'].append(ev)
def prof(frame, ev, arg): return None
for f in (on_call, on_cret, on_pystart, audit, prof): HARNESS.add(f.__code__)
sys.addaudithook(audit)

def measure(fn, consumer, *args):
    """Run fn(*args) with the instruments armed; return (pystart_codes, audit_events)."""
    st.update(inside=0, consumer=consumer, pystart=[], audit=[])
    M.use_tool_id(ATOM, 'atom-gate')
    M.register_callback(ATOM, E.CALL, on_call); M.register_callback(ATOM, E.C_RETURN, on_cret)
    M.register_callback(ATOM, E.C_RAISE, on_cret); M.register_callback(ATOM, E.PY_START, on_pystart)
    M.set_events(ATOM, E.PY_START); M.set_local_events(ATOM, fn.__code__, E.CALL | E.C_RETURN | E.C_RAISE)
    sys.setprofile(prof)
    try:
        out = fn(*args)
    finally:
        sys.setprofile(None)
        M.set_local_events(ATOM, fn.__code__, 0); M.set_events(ATOM, 0)
        for e in (E.CALL, E.C_RETURN, E.C_RAISE, E.PY_START): M.register_callback(ATOM, e, None)
        M.free_tool_id(ATOM)
    return list(st['pystart']), list(st['audit']), out

CONSUME = mech._CONSUME
def other_tool_holds(t):
    for e in mech._EVS5: M.register_callback(t, e, None)
    M.free_tool_id(t); M.use_tool_id(t, 'other')
def give_back(t):
    M.free_tool_id(t); M.use_tool_id(t, mech.NAME)
    for e, f in mech.CALLBACKS: M.register_callback(t, e, f)

def cases():
    mech.reset(); t = mech.TOOL[0]
    def f(): pass
    code = f.__code__
    class Core:
        __slots__ = ('flags',)
        def __init__(self): self.flags = {}
    out = []
    # ---- _unwind_on: (named, own anchor registered, event clear) ----
    for named, own, clear in ((True, True, True), (True, True, False), (True, False, True), (False, True, True)):
        mech._ANCHORS.clear()
        o = mech.Opening('A', sys._getframe(), None, Core()); o.armed = True
        p = mech.Opening('B', f, None, Core()); p.armed = True; mech._ANCHORS[f] = p
        if own: mech._ANCHORS[o.frame] = o
        M.set_events(t, 0 if clear else E.PY_UNWIND)
        if not named: other_tool_holds(t)
        ps, au, _ = measure(mech._unwind_on, CONSUME, o)
        if not named: give_back(t)
        out.append(('_unwind_on', 'named=%s own=%s clear=%s' % (named, own, clear), ps, au, 0))
    # ---- _unwind_off: (named, key registered, last anchor), and key None ----
    for named, last, key in ((True, True, 'k'), (True, False, 'k'), (False, True, 'k'), (True, True, None)):
        mech._ANCHORS.clear(); mech._ANCHORS['k'] = 1
        if not last: mech._ANCHORS['other'] = 2
        M.set_events(t, E.PY_UNWIND)
        if not named: other_tool_holds(t)
        ps, au, _ = measure(mech._unwind_off, CONSUME, key)
        if not named: give_back(t)
        out.append(('_unwind_off', 'named=%s last=%s key=%s' % (named, last, key), ps, au, 0))
    mech._ANCHORS.clear()
    # ---- _take: unowned, other, ours ----
    for who in ('unowned', 'other', 'ours'):
        if who == 'unowned': M.free_tool_id(t)
        if who == 'other': other_tool_holds(t)
        ps, au, _ = measure(mech._take, CONSUME, t)
        if who == 'other': give_back(t)
        if who == 'unowned' and M.get_tool(t) is not mech.NAME:
            M.use_tool_id(t, mech.NAME)
        out.append(('_take', who, ps, au, 0))
    # ---- _set_local: named, not named ----
    for named in (True, False):
        if not named: other_tool_holds(t)
        ps, au, _ = measure(mech._set_local_named, CONSUME, t, code, mech.LOCAL)
        if not named: give_back(t)
        else: M.set_local_events(t, code, 0)
        out.append(('_set_local', 'named=%s' % named, ps, au, 0))
    # ---- _register: named, not named (audit events expected: one per exchange) ----
    for named in (True, False):
        if not named: other_tool_holds(t)
        ps, au, r = measure(mech._register_named, mech._list, t)
        if not named: give_back(t)
        out.append(('_register', 'named=%s' % named, ps, au, len(r) - 1))
    return out

# ---------------- controls ----------------
_real_set = M.set_events
def py_set_events(tool, ev): return _real_set(tool, ev)
class Slow:
    def __getattribute__(self, n): return object.__getattribute__(self, n)
_armed = operator.attrgetter('armed')
def K1(t): CONSUME(mech._map(py_set_events, (t,), (0,)))
def K2(objs): CONSUME(mech._map(_armed, objs))
def K3(): CONSUME(mech._map(sys._getframe, (0,)))
def controls():
    mech.reset(); t = mech.TOOL[0]
    s = Slow(); object.__setattr__(s, 'armed', True)
    out = []
    ps, au, _ = measure(K1, CONSUME, t); out.append(('K1 python set_events wrapper', ps, au))
    ps, au, _ = measure(K2, CONSUME, (s,)); out.append(('K2 attrgetter, Python __getattribute__', ps, au))
    ps, au, _ = measure(K3, CONSUME); out.append(('K3 sys._getframe in the pipeline', ps, au))
    mech.MUT.add('reg_rev5')
    ps, au, _ = measure(mech._register_named, list, t); out.append(('K4 revision 5 _register', ps, au))
    mech.MUT.clear()
    return out

def slots_ok():
    MD = types.MemberDescriptorType
    return all(type(mech.Opening.__dict__[n]) is MD for n in ('armed', 'core', 'frame')) and type(mech.Core.__dict__['flags']) is MD

if __name__ == '__main__':
    v = sys.version.split()[0]
    ok_all = slots_ok()
    print(v, 'member descriptors (armed, core, frame; flags):', ok_all)
    for fn, case, ps, au, n in cases():
        if fn == '_register':
            ok = not ps and au == ['sys.monitoring.register_callback'] * n
        else:
            ok = not ps and not au
        ok_all &= ok
        print(v, '%-12s %-32s PY_START inside %-24s audit inside %-3d %s' % (fn, case, ps or '-', len(au),
              'PASS' if ok else 'FAIL'), ('(exchanges %d)' % n) if fn == '_register' else '')
    kill = True
    for name, ps, au in controls():
        caught = bool(ps or au); kill &= caught
        print(v, 'control %-40s PY_START inside %-28s audit inside %-40s %s' % (name, ps or '-', sorted(set(au)) or '-',
              'DETECTED' if caught else 'NOT DETECTED (gate void)'))
    print(v, 'G_ATOM', 'PASS' if ok_all and kill else 'FAIL', '(steps %s, controls %s)' % (ok_all, kill))
