# Revision 8 (the eighth critic's M1, M2, M3): atom7.py run against rev8/steps8.py (the tee registration), with
#   * criterion (c) extended by the CALL events G_ATOM already arms on the step's code: every CALL made from the
#     step's code is of a vocabulary constructor (_map, _filter, _chain, _compress, _repeat, _tee),
#     _chain.from_iterable or the consumer, and none is made after the interval closes (M2);
#   * _tee allowed as a c_call from the step's frame (it is a builtin function; it builds, and reads nothing);
#   * three more _register cases (67 in all): held by styxx with the global event SET, with and without one callback
#     replaced (M3), and held by styxx with its PY_START and PY_UNWIND callbacks replaced by callables whose only
#     reference is the slot and whose finalizers record whether the interval is open and len(_LOST) (M1): both
#     finalizers must run after the interval has closed, each seeing len(_LOST) + 2;
#   * hookup controls K11 (count after the call through a method-wrapper), K13 (_register clears S), K14
#     (_register in revision 7's form, no tee); K12 (a bytecode gate read in _unwind_on) is run and reported: G_ATOM
#     cannot see it, and G_HYG must reject it (rev8/hyg8.py). K4 and K10 are re-based on steps8.py's _register.
# Revision 7 (the seventh critic's M1): a prototype of the frozen premise gate G_ATOM as the revision-7 text specifies
# it, run against rev7/steps7.py (M7's step functions as written in the spec) and against single-step mutants of it.
#
# The harness reads ONLY the G_ATOM interface (M10, revision 7): _v5_faultpoints(), _ANCHORS, _TOOL, _TOOL_NAME,
# _CONSUME, _list, _Opening, _Core, _EVENTS5, _CALLBACKS5, _LOCAL, _LOST; plus public_enter_exit(), which stands for one
# enter and exit through the public API. Openings and cores are built with __new__ and slot assignment.
# Each step is called through FunctionType(code, vars(module)) with code from _v5_faultpoints().
#
# Instruments, armed around each step call: tool id 5 with global PY_START and local CALL / C_RETURN / C_RAISE on the
# step's code; an audit hook; a sys.setprofile function. Per case, all of these must hold:
#   (a) INTERVAL   the step's code CALLs its consumer (the object that IS _CONSUME, or _list for _register) exactly
#                  once, and that call returns (C_RETURN or C_RAISE) exactly once;
#   (b) INSIDE     no PY_START on the step's thread inside the interval, and no audit event, except for _register:
#                  exactly one 'sys.monitoring.register_callback' per exchange made (= len(r) - 1);
#   (c) OUTSIDE    between the step's start and its return, outside the interval: no PY_START of any function on the
#                  step's thread, and no C call from the step's frame except the consumer and chain.from_iterable
#                  (seen by the profile function);
#   (d) STATE      the observable state read at the consumer's CALL equals the state before the step (nothing was
#                  done before the one call), and the state after the step equals the case's expected effect, which
#                  the harness computes from the spec's rule for that gate outcome, not from the implementation.
# Plus the slot check: armed, core, frame of _Opening and flags of _Core are member descriptors.
# CASE MATRIX (frozen; 64 cases): _unwind_on  named{y,n} x own anchor{reg,unreg} x event{set,clear} x
#   other opening{none,armed,unarmed} = 24; _unwind_off  named{y,n} x key{registered,unregistered,None} x
#   other anchor left{no,yes} x event{set,clear} = 24; _take  owner{unowned,other,styxx} = 3; _set_local
#   named{y,n} x events{_LOCAL,0} = 4; _register  owner{styxx, styxx with one callback replaced, other, unowned} = 4,
#   plus the split cases k = 1..5 (an audit hook at the k-th register_callback event frees the id and another tool
#   takes it) = 9. The expected effect includes len(_LOST) (revision 7: the registration's in-call count).
# CONTROLS, which must be detected or the run is void:
#   instrument controls (on the harness's own pipelines): K1 a Python set_events wrapper, K2 attrgetter over a Python
#   __getattribute__, K3 sys._getframe (audited) in a pipeline;
#   hookup controls (G_ATOM run on a single-step mutant of the reference; the run must FAIL): K4 _register in revision
#   5's form; K5 _unwind_off through a Python helper; K6 _unwind_off consumed by a deque built at call time; K7
#   _unwind_off with the pop as its own statement; K8 _unwind_on without the own-anchor gate on its set; K9 _take
#   with the unowned test as its own statement; K10 _register counting after its consuming call (the critic's form).
import sys, os, json, types, threading, subprocess, itertools, operator, importlib.util, platform
HERE = os.path.dirname(os.path.abspath(__file__))
M = sys.monitoring; E = M.events
ATOM = 5
OTHER = 'atom-other'
MD = types.MemberDescriptorType
FROM_ITERABLE = itertools.chain.from_iterable
def is_from_iterable(c):     # a bound classmethod is created at each access: compare its self and name
    return type(c) is types.BuiltinMethodType and getattr(c, '__self__', None) is itertools.chain and c.__name__ == 'from_iterable'

REG8 = '''    a, b = _tee(_map(register_callback,
                     _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
                     _EVENTS5, _CALLBACKS5))
    return _list(_chain(
        _map(_LOST_APPEND, _map(_is_not, _compress(a, _map(_is_not, b, _CALLBACKS5)), _repeat(None))),
        _map(get_tool, (t,))))'''
REG7 = '''    return _list(_chain(
        _map(_LOST_APPEND, _filter(None, _map(_is_not,
            _map(register_callback,
                 _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
                 _EVENTS5, _CALLBACKS5),
            _CALLBACKS5))),
        _map(get_tool, (t,))))'''
PATCHES = {
    'K4': (REG8, '''    return _list(_map(register_callback, _chain.from_iterable(_map(_repeat,
        _compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)), (5,))), _EVENTS5, _CALLBACKS5))'''),
    'K5': ('''def _unwind_off(key):
    t, get_tool, set_events = _TOOL[0], _MON[0][0], _MON[0][2]
    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),
                    _map(set_events, _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                                               _map(_not, (_ANCHORS,))), _ZERO1)))''', '''def _unwind_off(key):
    _off_helper(key)
def _off_helper(key):
    t, get_tool, set_events = _TOOL[0], _MON[0][0], _MON[0][2]
    _ANCHORS.pop(key, None)
    if not _ANCHORS and get_tool(t) is _TOOL_NAME: set_events(t, 0)'''),
    'K6': ('''    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),''', '''    collections.deque(_chain(_map(_ANCHORS.pop, (key,), _NONE1),'''),
    'K7': ('''    t, get_tool, set_events = _TOOL[0], _MON[0][0], _MON[0][2]
    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),''', '''    t, get_tool, set_events = _TOOL[0], _MON[0][0], _MON[0][2]
    _ANCHORS.pop(key, None)
    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),'''),
    'K8': ('''        _map(set_events,
             _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                       _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),
             _PYU1)))''', '''        _map(set_events,
             _compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),
             _PYU1)))'''),
    'K10': (REG8, '''    r = _list(_chain(
        _map(register_callback,
             _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
             _EVENTS5, _CALLBACKS5),
        _map(get_tool, (t,))))
    _LOST.extend(_filter(None, _map(_is_not, r[:-1], _CALLBACKS5)))
    return r[-1:]'''),
    'K9': ('''    _CONSUME(_map(use_tool_id, _compress((t,), _map(_is, _map(get_tool, (t,)), _NONE1)), _NAME1))''',
           '''    free = get_tool(t) is None
    _CONSUME(_map(use_tool_id, _compress((t,), (free,)), _NAME1))'''),
}
PATCHES['K11'] = (REG8, '''    r = _list(_chain(
        _map(register_callback,
             _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
             _EVENTS5, _CALLBACKS5),
        _map(get_tool, (t,))))
    _LOST.__iadd__([True for x in _filter(None, _map(_is_not, r[:-1], _CALLBACKS5))])
    return [None for x in _filter(None, _map(_is_not, r[:-1], _CALLBACKS5))] + r[-1:]''')     # critic8/c2's K11
PATCHES['K12'] = ('''def _unwind_on(o):
    t, get_tool, get_events, set_events = _TOOL[0], _MON[0][0], _MON[0][1], _MON[0][2]''', '''def _unwind_on(o):
    t, get_tool, get_events, set_events, own = _TOOL[0], _MON[0][0], _MON[0][1], _MON[0][2], (o.frame in _ANCHORS and _ANCHORS[o.frame] is o)''')
K12_GATE = ('_map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))', '(own,)')                                  # critic8/c2's K12
PATCHES['K13'] = ('''    get_tool, register_callback = _MON[0][0], _MON[0][4]
    a, b = _tee(''', '''    get_tool, register_callback, set_events = _MON[0][0], _MON[0][4], _MON[0][2]
    a, b = _tee(''')                                                                              # critic8/c5's K13
K13_CHAIN = ('''    return _list(_chain(
        _map(_LOST_APPEND''', '''    return _list(_chain(
        _filter(None, _map(set_events, _compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)), _ZERO1)),
        _map(_LOST_APPEND''')
PATCHES['K12b'] = ('''                       _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),
             _PYU1)))''', '''                       (o.frame in _ANCHORS,)),
             _PYU1)))''')          # revision 8: K12's read moved into the pipeline statement (a CONTAINS_OP at build time)
PATCHES['K14'] = (REG8, REG7)                                                                     # revision 7's _register
K6_FIX = ('''_ZERO1)))

def _take''', '''_ZERO1)), 0)

def _take''')

def load(variant):
    src = open(os.path.join(HERE, 'steps8.py')).read()
    if variant != 'ref':
        old, new = PATCHES[variant]
        assert src.count(old) == 1, variant
        src = src.replace(old, new)
        if variant == 'K12':
            assert src.count(K12_GATE[0]) == 2; src = src.replace(K12_GATE[0], K12_GATE[1])
        if variant == 'K13':
            assert src.count(K13_CHAIN[0]) == 1; src = src.replace(K13_CHAIN[0], K13_CHAIN[1])
        if variant == 'K6':
            assert src.count(K6_FIX[0]) == 1; src = src.replace(K6_FIX[0], K6_FIX[1])
    mod = types.ModuleType('steps8_' + variant); mod.__file__ = os.path.join(HERE, 'steps8.py')
    exec(compile(src, mod.__file__, 'exec'), vars(mod))
    return mod

# ------------------------------------------------------------------ instruments
st = dict(active=False, tid=None, stepcode=None, consumer=None, inside=0, opened=0, closed=0, ps_in=[], ps_out=[],
          au_in=[], cc_out=[], snapfn=None, snap_at_call=None, calls=[])
HARNESS = set()
def on_call(code, off, callee, arg0):
    if st['active'] and code is st['stepcode']:                  # revision 8 (M2): every CALL from the step's code
        st['calls'].append((callee, st['closed'] > 0))
    if st['active'] and code is st['stepcode'] and callee is st['consumer']:
        if st['opened'] == 0 and st['snapfn'] is not None: st['snap_at_call'] = st['snapfn']()
        st['opened'] += 1; st['inside'] += 1
def on_cret(code, off, callee, arg0):
    if st['active'] and code is st['stepcode'] and callee is st['consumer'] and st['inside']:
        st['inside'] -= 1; st['closed'] += 1
def on_pystart(code, off):
    if not st['active'] or code in HARNESS or code is st['stepcode'] or threading.get_ident() != st['tid']: return
    (st['ps_in'] if st['inside'] else st['ps_out']).append(code.co_qualname)
def audit(ev, args):                                   # the split cases' own interference is the harness's, not the step's
    if st['active'] and st['inside'] and threading.get_ident() == st['tid'] and not SPLIT['busy']: st['au_in'].append(ev)
def prof(frame, ev, arg):
    if ev == 'c_call' and st['active'] and not st['inside'] and frame.f_code is st['stepcode']:
        st['cc_out'].append(arg)
SPLIT = {'k': 0, 'n': 0, 't': None, 'mod': None, 'busy': False}
def other_cb(*a): return None
def take_by_other(t, mod):
    M.free_tool_id(t); M.use_tool_id(t, OTHER)
    for e in mod._EVENTS5: M.register_callback(t, e, other_cb)
def split_hook(ev, args):
    if ev == 'sys.monitoring.register_callback' and SPLIT['k'] and threading.get_ident() == st['tid'] and st['inside']:
        SPLIT['n'] += 1
        if SPLIT['n'] == SPLIT['k']:
            SPLIT['k'] = 0; SPLIT['busy'] = True
            th = threading.Thread(target=take_by_other, args=(SPLIT['t'], SPLIT['mod'])); th.start(); th.join()
            SPLIT['busy'] = False
for f in (on_call, on_cret, on_pystart, audit, prof, split_hook, other_cb, take_by_other): HARNESS.add(f.__code__)
sys.addaudithook(audit); sys.addaudithook(split_hook)

def measure(fn, consumer, snapfn, *args):
    st.update(active=False, tid=threading.get_ident(), stepcode=fn.__code__, consumer=consumer, inside=0, opened=0,
              closed=0, ps_in=[], ps_out=[], au_in=[], cc_out=[], snapfn=snapfn, snap_at_call=None, calls=[])
    M.use_tool_id(ATOM, 'atom-gate')
    for e, cb in ((E.CALL, on_call), (E.C_RETURN, on_cret), (E.C_RAISE, on_cret), (E.PY_START, on_pystart)):
        M.register_callback(ATOM, e, cb)
    M.set_events(ATOM, E.PY_START); M.set_local_events(ATOM, fn.__code__, E.CALL | E.C_RETURN | E.C_RAISE)
    sys.setprofile(prof)
    st['active'] = True
    try: out = fn(*args); err = None
    except Exception as e: out = None; err = repr(e)
    finally:
        st['active'] = False
        sys.setprofile(None)
        M.set_local_events(ATOM, fn.__code__, 0); M.set_events(ATOM, 0)
        for e in (E.CALL, E.C_RETURN, E.C_RAISE, E.PY_START): M.register_callback(ATOM, e, None)
        M.free_tool_id(ATOM)
    return out, err

# ------------------------------------------------------------------ helpers over the G_ATOM interface only
def core(mod):
    c = mod._Core.__new__(mod._Core); c.flags = {}; return c
def opening(mod, c, armed):
    o = mod._Opening.__new__(mod._Opening); o.core = c; o.frame = object(); o.armed = armed; return o
def prep_other(mod, t, events=0):
    for e in mod._EVENTS5: M.register_callback(t, e, None)
    if M.get_tool(t) is not None: M.set_events(t, 0); M.free_tool_id(t)
    M.use_tool_id(t, OTHER)
    for e in mod._EVENTS5: M.register_callback(t, e, other_cb)
    M.set_events(t, events)
def give_back(mod, t):
    for e in mod._EVENTS5: M.register_callback(t, e, None)
    if M.get_tool(t) is not None: M.set_events(t, 0); M.free_tool_id(t)
    M.use_tool_id(t, mod._TOOL_NAME)
    for e, f in zip(mod._EVENTS5, mod._CALLBACKS5): M.register_callback(t, e, f)
    M.set_events(t, 0)
def read_cbs(mod, t):                                  # exchange-and-restore (sys.monitoring has no getter)
    out = []
    for e in mod._EVENTS5:
        c = M.register_callback(t, e, None); M.register_callback(t, e, c); out.append(c)
    return out
def snap(mod, t, cores, code=None):
    owner = M.get_tool(t)
    return (tuple((id(k), id(v)) for k, v in mod._ANCHORS.items()), owner,
            M.get_events(t) if owner is not None else None,
            M.get_local_events(t, code) if (owner is not None and code is not None) else None,
            tuple(tuple(sorted(c.flags.items())) for c in cores), len(mod._LOST))
def fx(): return None
FIN = {}; FIN_WHY = []
class FinCb:                                           # revision 8 (M1): a replacement whose finalizer records when it ran
    def __init__(self, ev): self.ev = ev
    def __call__(self, *a): return None
    def __del__(self):
        if st['active']: FIN[self.ev] = (st['inside'], st['opened'], st['closed'], len(MODREF[0]._LOST))
MODREF = [None]

def verdict(fn_name, mod, expected, post, n_exch=None, extra_ok=True):
    reg = fn_name == '_register'
    why = []
    if not (st['opened'] == 1 and st['closed'] == 1): why.append('interval opened %d closed %d' % (st['opened'], st['closed']))
    if st['ps_in']: why.append('PY_START inside %s' % st['ps_in'])
    if reg:
        if st['au_in'] != ['sys.monitoring.register_callback'] * (n_exch or 0): why.append('audit inside %s for %s exchanges' % (st['au_in'], n_exch))
    elif st['au_in']: why.append('audit inside %s' % st['au_in'])
    if st['ps_out']: why.append('PY_START outside the interval %s' % st['ps_out'])
    bad_cc = [getattr(c, '__qualname__', repr(c)) for c in st['cc_out']
              if not (c is st['consumer'] or is_from_iterable(c) or c is getattr(mod, '_tee', None))]
    if bad_cc: why.append('C calls outside the interval %s' % bad_cc)
    ctors = (mod._map, mod._filter, mod._chain, mod._compress, mod._repeat, getattr(mod, '_tee', None))
    bad_calls = [getattr(c, '__qualname__', repr(c)) for c, after in st['calls']
                 if not (c is st['consumer'] or is_from_iterable(c) or any(c is k for k in ctors if k is not None))]
    if bad_calls: why.append('CALL of a non-vocabulary callable from the step %s' % bad_calls)
    late = [getattr(c, '__qualname__', repr(c)) for c, after in st['calls'] if after]
    if late: why.append('CALL after the interval closed %s' % late)
    if st['snap_at_call'] is not None and st['snap_at_call'] != st['pre']: why.append('state changed before the one call')
    if post != expected: why.append('effect %r != expected %r' % (post, expected))
    if not extra_ok: why.append('registration result or callbacks wrong')
    return why

def cases(mod):
    fp = mod._v5_faultpoints()
    F = {k: types.FunctionType(c, vars(mod)) for k, c in fp.items()}
    t = mod._TOOL[0]; PYU = E.PY_UNWIND
    res = []
    # ---- _unwind_on: named x own x event x other opening ----
    for named in (True, False):
        for own in (True, False):
            for ev in ('set', 'clear'):
                for other in ('none', 'armed', 'unarmed'):
                    mod._ANCHORS.clear()
                    c0 = core(mod); o = opening(mod, c0, False); cores = [c0]
                    if other != 'none':
                        c1 = core(mod); p = opening(mod, c1, other == 'armed'); cores.append(c1); mod._ANCHORS[p.frame] = p
                    if own: mod._ANCHORS[o.frame] = o
                    evv = PYU if ev == 'set' else 0
                    if named: M.set_events(t, evv)
                    else: prep_other(mod, t, evv)
                    sf = lambda: snap(mod, t, cores)
                    st['pre'] = pre = sf()
                    # the spec's rule: iff named and own registered: if the event is clear, flag every armed registered
                    # opening's core, then set the event
                    flags = [dict(c.flags) for c in cores]
                    evafter = evv
                    if named and own:
                        if ev == 'clear':
                            for i, c in enumerate(cores):
                                if any(q.core is c and q.armed for q in mod._ANCHORS.values()): flags[i]['UNWIND_LOST'] = True
                        evafter = PYU
                    exp = (pre[0], pre[1], evafter, None, tuple(tuple(sorted(f.items())) for f in flags), pre[5])
                    measure(F['_unwind_on'], mod._CONSUME, sf, o)
                    post = sf()
                    res.append(('_unwind_on', 'named=%s own=%s event=%s other=%s' % (named, own, ev, other), verdict('_unwind_on', mod, exp, post)))
                    if not named: give_back(mod, t)
    # ---- _unwind_off: named x key x other anchor left x event ----
    for named in (True, False):
        for key in ('registered', 'unregistered', 'None'):
            for left in (False, True):
                for ev in ('set', 'clear'):
                    mod._ANCHORS.clear()
                    c0 = core(mod); o = opening(mod, c0, True)
                    if key == 'registered': mod._ANCHORS[o.frame] = o
                    if left:
                        p = opening(mod, core(mod), True); mod._ANCHORS[p.frame] = p
                    k = o.frame if key != 'None' else None
                    evv = PYU if ev == 'set' else 0
                    if named: M.set_events(t, evv)
                    else: prep_other(mod, t, evv)
                    sf = lambda: snap(mod, t, [])
                    st['pre'] = pre = sf()
                    anchors_after = tuple(x for x in pre[0] if not (key == 'registered' and x[0] == id(o.frame)))
                    evafter = 0 if (named and not anchors_after) else evv
                    exp = (anchors_after, pre[1], evafter, None, (), pre[5])
                    measure(F['_unwind_off'], mod._CONSUME, sf, k)
                    post = sf()
                    res.append(('_unwind_off', 'named=%s key=%s left=%s event=%s' % (named, key, left, ev), verdict('_unwind_off', mod, exp, post)))
                    if not named: give_back(mod, t)
    mod._ANCHORS.clear()
    # ---- _take: owner ----
    for who in ('unowned', 'other', 'styxx'):
        if who == 'unowned':
            M.set_events(t, 0); M.free_tool_id(t)
        if who == 'other': prep_other(mod, t)
        sf = lambda: snap(mod, t, [])
        st['pre'] = pre = sf()
        exp = (pre[0], mod._TOOL_NAME if who == 'unowned' else pre[1], pre[2] if who != 'unowned' else 0, None, (), pre[5])
        measure(F['_take'], mod._CONSUME, sf, t)
        post = sf()
        res.append(('_take', 'owner=%s' % who, verdict('_take', mod, exp, post)))
        give_back(mod, t)
    # ---- _set_local: named x events ----
    for named in (True, False):
        for evs in ('_LOCAL', '0'):
            e_new = mod._LOCAL if evs == '_LOCAL' else 0
            if named: M.set_local_events(t, fx.__code__, 0 if e_new else mod._LOCAL)
            else:
                prep_other(mod, t); M.set_local_events(t, fx.__code__, E.LINE)
            sf = lambda: snap(mod, t, [], fx.__code__)
            st['pre'] = pre = sf()
            exp = (pre[0], pre[1], pre[2], e_new if named else pre[3], (), pre[5])
            measure(F['_set_local'], mod._CONSUME, sf, t, fx.__code__, e_new)
            post = sf()
            res.append(('_set_local', 'named=%s events=%s' % (named, evs), verdict('_set_local', mod, exp, post)))
            M.set_local_events(t, fx.__code__, 0)
            if not named: give_back(mod, t)
    # ---- _register: owner, a replaced callback, and the split cases (revision 7: the in-call count) ----
    for who in ('styxx', 'styxx-replaced', 'styxx-set', 'styxx-replaced-set', 'styxx-fin', 'other', 'unowned',
                'split1', 'split2', 'split3', 'split4', 'split5'):
        FIN.clear()
        if who == 'other': prep_other(mod, t)
        if who.endswith('-set'): M.set_events(t, E.PY_UNWIND)                        # revision 8 (M3): S set
        if who == 'styxx-replaced-set': M.register_callback(t, E.PY_UNWIND, other_cb)
        if who == 'styxx-fin':                                                       # revision 8 (M1): the slot holds the
            M.register_callback(t, E.PY_START, FinCb('PY_START'))                    # only reference to each replacement
            M.register_callback(t, E.PY_UNWIND, FinCb('PY_UNWIND'))
        if who == 'unowned': M.set_events(t, 0); M.free_tool_id(t)
        if who == 'styxx-replaced': M.register_callback(t, E.PY_UNWIND, other_cb)   # an outside party's replacement
        if who.startswith('split'): SPLIT.update(k=int(who[-1]), n=0, t=t, mod=mod)
        sf = lambda: snap(mod, t, [])
        st['pre'] = pre = sf()
        r, err = measure(F['_register'], mod._list, sf, t)
        SPLIT['k'] = 0
        post = sf()
        ok = isinstance(r, list) and err is None
        # the spec's rule: [None] per exchange whose previous callback was not styxx's (each counted in _LOST inside the
        # call), then the owner; exchanges made: 5 on styxx's id, 0 on another's or an unowned id, k in split case k
        fin_ok = True
        if who in ('styxx', 'styxx-set'):
            n_ex, want_r, dl, exp_owner = 5, [mod._TOOL_NAME], 0, pre[1]
        elif who in ('styxx-replaced', 'styxx-replaced-set'):
            n_ex, want_r, dl, exp_owner = 5, [None, mod._TOOL_NAME], 1, pre[1]
        elif who == 'styxx-fin':                    # both finalizers ran after the interval closed, each after both counts
            n_ex, want_r, dl, exp_owner = 5, [None, None, mod._TOOL_NAME], 2, pre[1]
            fin_ok = sorted(FIN) == ['PY_START', 'PY_UNWIND'] and all(v == (0, 1, 1, pre[5] + 2) for v in FIN.values())
        elif who == 'other':
            n_ex, want_r, dl, exp_owner = 0, [OTHER], 0, pre[1]
        elif who == 'unowned':
            n_ex, want_r, dl, exp_owner = 0, [None], 0, pre[1]
        else:
            k = int(who[-1]); n_ex, want_r, dl, exp_owner = k, [None, OTHER], 1, OTHER
        exp = (pre[0], exp_owner, pre[2] if not who.startswith('split') else 0, None, (), pre[5] + dl)
        ok = ok and r == want_r
        if who.startswith('styxx'): ok = ok and read_cbs(mod, t) == list(mod._CALLBACKS5)
        if not fin_ok: ok = False; FIN_WHY.append((who, dict(FIN), pre[5]))
        if who == 'other': ok = ok and all(c is other_cb for c in read_cbs(mod, t))
        if who.startswith('split'):
            want = [other_cb] * 5; want[k - 1] = mod._CALLBACKS5[k - 1]
            ok = ok and read_cbs(mod, t) == want
        res.append(('_register', 'owner=%s' % who, verdict('_register', mod, exp, post, n_ex, ok) + (['finalizers %r (want (inside 0, opened 1, closed 1, len(_LOST) %d) for both)' % (dict(FIN), pre[5] + 2)] if not fin_ok else [])))
        give_back(mod, t)
    return res

# ------------------------------------------------------------------ instrument controls
_real_set = M.set_events
def py_set_events(tool, ev): return _real_set(tool, ev)
class Slow:
    def __getattribute__(self, n): return object.__getattribute__(self, n)
def instrument_controls(mod):
    t = mod._TOOL[0]; out = []
    s = Slow(); object.__setattr__(s, 'armed', True); ag = operator.attrgetter('armed')
    def K1(): mod._CONSUME(map(py_set_events, (t,), (0,)))
    def K2(): mod._CONSUME(map(ag, (s,)))
    def K3(): mod._CONSUME(map(sys._getframe, (0,)))
    for name, fn in (('K1 Python set_events wrapper', K1), ('K2 attrgetter over a Python __getattribute__', K2),
                     ('K3 sys._getframe in the pipeline', K3)):
        measure(fn, mod._CONSUME, None)
        out.append((name, bool(st['ps_in'] or st['au_in']) and st['opened'] == 1))
    return out

def run_variant(variant):
    mod = load(variant); MODREF[0] = mod
    for f in (FinCb.__init__, FinCb.__call__, FinCb.__del__): HARNESS.add(f.__code__)
    mod.public_enter_exit()
    slots = all(type(mod._Opening.__dict__[n]) is MD for n in ('armed', 'core', 'frame')) and type(mod._Core.__dict__['flags']) is MD
    res = cases(mod)
    fails = [(f, c, w) for f, c, w in res if w]
    out = dict(variant=variant, cases=len(res), failed=len(fails), slots=slots, first_failures=fails[:40],
               build=[sys.version.split()[0], platform.python_build(), platform.python_compiler()])
    if variant == 'ref': out['instrument_controls'] = instrument_controls(mod)
    return out

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'run':
        print(json.dumps(run_variant(sys.argv[2]), default=repr)); sys.exit(0)
    v = sys.version.split()[0]
    ok_all = True
    for variant in ('ref', 'K4', 'K5', 'K6', 'K7', 'K8', 'K9', 'K10', 'K11', 'K13', 'K14', 'K12', 'K12b'):
        p = subprocess.run([sys.executable, __file__, 'run', variant], capture_output=True, text=True, timeout=300)
        if not p.stdout.strip():
            print(v, variant, 'ERROR', p.stderr.strip().splitlines()[-3:]); ok_all = False; continue
        r = json.loads(p.stdout.strip().splitlines()[-1])
        if variant == 'ref':
            print(v, 'build', r['build'])
            print(v, 'reference: %d cases, %d failed, slots %s' % (r['cases'], r['failed'], r['slots']))
            for f in r['first_failures']: print(v, '   FAIL', f)
            for name, det in r['instrument_controls']: print(v, 'instrument control %-46s %s' % (name, 'DETECTED' if det else 'NOT DETECTED (void)'))
            ok_all &= r['failed'] == 0 and r['slots'] and all(d for _, d in r['instrument_controls'])
        elif variant in ('K12', 'K12b'):                       # revision 8: reported; G_ATOM cannot see it, G_HYG rejects it
            print(v, 'static-only control %s: %d of %d cases fail (expected 0: a bytecode read is G_HYG\'s; rev8/hyg8.py)' % (variant, r['failed'], r['cases']))
        else:
            det = r['failed'] > 0
            print(v, 'hookup control %s: %d of %d cases fail -> %s; first: %s' % (variant, r['failed'], r['cases'],
                  'DETECTED' if det else 'NOT DETECTED (FAIL)', r['first_failures'][:1]))
            ok_all &= det
    print(v, 'G_ATOM (revision 8 prototype)', 'PASS' if ok_all else 'FAIL')
