# Revision-8 model of v5f's event path: rev7/mech7.py copied, with revision 8's change (the eighth critic's M1) and
# three probe mutants, each behind MUT:
#   * M1: _register reads its exchanges through itertools.tee, so every previous callback stays referenced by the tee
#     buffer until the consuming call has made every count; a replaced callback's finalizer runs only when the
#     pipeline is released, after the call. MUT 'reg_rev7' restores revision 7's form (the previous callback is dropped
#     by map right after _is_not, before its count).
#   * N4: MUT 'count_excl_none' counts only previous callbacks that are neither styxx's nor None (a Python stand-in).
#   * N2 (A13): MUT 'pend_bare_id' keys a pending entry by id(frame) without holding the frame, and publishes on a
#     matching id without the identity test.
#   * N1 (probe only, not the spec): MUT 'take_count' appends to _LOST inside _take's own consuming call.
# Everything below that is not marked 'revision 8' is revision 7's model.
#
# Revision-7 model of v5f's event path: rev6/mech6.py copied, with revision 7's changes (the seventh critic's B1, M3,
# M5.2, N1, N6), each behind a single-rule mutant:
#   * B1: X5's registration repairs a callback that an outside party replaced on styxx's id. Revision 7 COUNTS every
#     exchange whose previous callback is not styxx's, in C, inside the registration's own consuming call
#     (_filter(None, _map(_is_not, <exchanges>, _FNS5)) feeding _REPL.append), so every trace live then notes
#     MONITOR_LOST and no fault can land between a repair and its count. _LOST is read as lost_count() =
#     RECLAIMED[0] + len(_REPL). MUT 'cbrep_nocount' restores revision 6 (only the exiting trace notes it); MUT
#     'count_after_register' is the seventh critic's proposed form (a Python count after the call; the hook point
#     'exit:registered' lies between the two, where a fault skips the count).
#   * M5.2: _ensure_tool counts every usable id it takes while TOOL[0] is set: a rebinding to the other id AND a
#     re-take of the same id (after a reclaim whose registration was split with owner None). MUT 'retake_nocount'
#     restores revision 6's prototype rule (count only t != i).
#   * M3: bind() runs at EVERY Tracer construction (every coverage_trace()), not only the first: it re-checks the
#     one-call vocabulary as the module now binds it (a reload re-binds it) and the bound _MON items. MUT
#     'check_once' restores revision 6 (check only when _MON is first bound). The registries, the tool id, the name,
#     RECLAIMED and the bound _MON functions are bound through globals().get, as M1's reload paragraph states, so
#     importlib.reload(mech7) behaves as the spec's reload does.
#   * N1: _CONSUME's __self__ must be of the real C deque type (immutable C type collections.deque) with maxlen 0,
#     and _VALUES must be dict's 'values' descriptor. MUT 'deque_by_name' restores revision 6's name-only test.
#   * N5: a Tracer whose function is already minted JOINS that mint (M4's "An existing mint"); an exit drops its
#     holdership and retires the mint only when no holder is left. mech6 re-minted instead, so a second tracer
#     declaring the same function took the function away from the first (X137g's Q half could not be shown).
#   * audit mutants (revision 7's self-audit): 'store_no_anchor' (_on_entry stores a pending entry with no anchor
#     registered), 'open_locks' (an open takes the robust mutex).
#   * N6 / M2: the version gate (_VERIFIED) is read at call time, in bind(), from sys.version_info.
# Everything below this header that is not marked 'revision 7' is revision 6's model, unchanged.
#
# Revision-6 model of v5f's event path: rev5/mech5.py copied, with revision 6's changes (the sixth critic's B1, M1, N1):
#   * _register (here _register_named) gates EACH register_callback on the name, in the same lazy pipeline, and reads
#     the owner once more after the last exchange, still inside the one consuming call. It returns the previous
#     callbacks followed by that owner. CPython raises the audit event 'sys.monitoring.register_callback' inside
#     every register_callback, BEFORE its exchange (critic6/a1, a2), so an audit hook runs between each gate and its
#     exchange. Revision 6 does not claim atomicity for _register; it bounds and detects: exchanges 1..n-1 landed on
#     styxx's id, only exchange n can have landed on another's, and the owner read right after it says whose.
#     MUT 'reg_rev5' restores revision 5's form (one gate before all five exchanges, no owner read).
#   * _MON's functions are bound by bind(), at the first Tracer, and only if each is the C builtin of sys.monitoring;
#     the one-call vocabulary is checked at the same time (immutable C types, C builtin functions). Otherwise bind()
#     raises Unsupported('[V5:UNSUPPORTED_VERSION] ...'). MUT 'no_builtin_check'.
#   * _ensure_tool (install_tool) rebinds TOOL[0] to id 3 when the id it holds was taken by another tool, counts the
#     rebinding in RECLAIMED (the _LOST counter), and sets local events on every registered mint for the new id.
#     MUT 'rebind_no_local' leaves them unset (revision 5's unstated joiner outcome).
#   * a split registration (the owner after it is not NAME) is reported by _register and noted by the exit that made
#     it; every other live trace notes MONITOR_LOST anyway (its own exit's registration on that id cannot be complete
#     until a reclaim or a rebinding, both counted in RECLAIMED).
# Everything below this header that is not marked 'revision 6' is revision 5's model, unchanged.
#
# Revision-5 model of v5f's event path, written from scratch against the revision-5 text (not a patch of mech4.py).
#
# Revision 5 removes revision 4's clearer announcement (_CLEARING) and the opener's wait (_await_clearers). Every
# read-decide-write on styxx's global PY_UNWIND is instead ONE C CALL: a lazy itertools/operator pipeline, built in
# Python (which reads nothing) and consumed by one builtin (collections.deque(maxlen=0).extend, or any), which reads
# and writes everything inside that single call. No Python code runs inside a C call: no other thread, no signal
# handler, no finalizer, no audit hook, no trace/profile function, no sys.monitoring callback, no greenlet switch
# (t1_onecall_atomic.py). So the anchor test and the clear cannot be separated by anything, and nothing waits.
#
# The three one-call steps (and the close's read):
#   ON(o)       in _commit, after the store and step 8:
#               one call { if our id is named and o's anchor is registered:
#                              if the event is clear: note UNWIND_LOST on every armed registered opening's core
#                              set the event }
#   OFF(key)    in _detach (key = the anchor frame) and last in every reconciliation (key = None):
#               one call { pop key; if our id is named and no anchor is left: clear the event }
#   BLIND       in _detach, before OFF: o.armed, then one call { our id is named and the event is clear },
#               then o's anchor is still registered (event first, anchor last, as revision 4)
#   every other sys.monitoring write styxx makes (local events at retire, callback registration) is also one call
#   gated on the name, so a free-and-retake by another tool between a test and a write cannot happen.
#
# Mutants (MUT), one rule each:
#   off_split          OFF's emptiness test and clear as two statements (revision 3's shape, split open)
#   popoff_split       the pop as its own statement before OFF (a window with the event set and no anchor)
#   on_ungated_own     ON sets the event without testing that o's anchor is still registered
#   on_no_capture      ON without the UNWIND_LOST capture
#   on_capture_split   ON reads the event in one call, then captures and sets in a second call
#   on_capture_nogate  ON captures armed openings whether or not the event is clear
#   on_before_store    ON (ungated by o's anchor, revision 3's first set) before the store, none after
#   no_on              _commit without ON
#   blind_anchor_first BLIND tests the anchor before the event
#   blind_no_armed     BLIND without o.armed ; blind_no_anchor  BLIND without the anchor test
#   ensure_nocount     _ensure_tool re-takes its own freed id without counting it (no MONITOR_LOST for that free)
#   take_split         use_tool_id after a separate 'is it free?' test (ValueError if another tool takes it between)
#   no_rec_off         reconciliation does not end with OFF(None)
#   gate_split         name-gated writes as a test then a write (two statements)
#   no_gate            writes without the name gate
#   detach_nulls, no_recheck, no_fin_test, no_exiting_test, no_anchor_prune   (revision 4's B1 rules, kept)
#   time_at_call       the mutex reads time.monotonic / time.sleep through the time module at call time (N3)
# _HOOK is a test hook called with a point name at statement boundaries (never inside a one-call step: there is none).
import sys, types, gc, time, threading, itertools, operator, collections
import asyncio, asyncio.events as ev, asyncio.base_events as be
M = sys.monitoring
E = M.events
PYU = E.PY_UNWIND
TOOL = globals().get('TOOL', [None])                  # revision 7: kept through a reload (M1)
NAME = globals().get('NAME') or 'styxx.protocol/model-rev8'
_get_running_loop = ev._get_running_loop
_TYPE_DICT = type.__dict__['__dict__']
_HANDLE_DICT = [_TYPE_DICT.__get__(ev.Handle)]
_LOOP_DICT = [_TYPE_DICT.__get__(be.BaseEventLoop)]
_CUT = globals().get('_CUT', {})
_ANCHORS = globals().get('_ANCHORS', {})
_MINTED = globals().get('_MINTED', {})
MUT = globals().get('MUT', set())
_HOOK = [None]
BUSY = [10.0]
# ---- bound once (N3: the mutex's clock and sleep are not read through the time module at call time) ----
_monotonic, _sleep = time.monotonic, time.sleep
# ---- the one-call vocabulary ----
_map, _chain, _compress, _filter, _repeat = map, itertools.chain, itertools.compress, filter, itertools.repeat
_is, _not, _and, _setitem = operator.is_, operator.not_, operator.and_, operator.setitem
_ARMED = operator.attrgetter('armed')
_FLAGS = operator.attrgetter('core.flags')
_VALUES = dict.values
_CONSUME = collections.deque(maxlen=0).extend
_any = any
_list = list                                           # revision 6 (M4 v): the registration's consumer, bound once
_is_not = operator.is_not                              # revision 7 (B1)
_tee = itertools.tee                                   # revision 8 (M1)
_REPL = globals().get('_REPL', [])                     # revision 7 (B1): one entry per foreign previous callback, kept through a reload
_REPL_APPEND = _REPL.append                            # the count, made in C inside the registration's consuming call
_MONB = globals().get('_MONB', [None])                # revision 7: the bound sys.monitoring functions (_MON), kept through a reload
_BOUND = globals().get('_BOUND', [False])
_get_tool, _get_events, _set_events, _set_local_events, _register_callback, _use_tool_id = _MONB[0] or (None,) * 6
_VERIFIED = ((3, 12, 3), (3, 13, 12))                 # revision 6 (M5); revision 7 reads sys.version_info at call time
class Unsupported(Exception): pass
_BUILTIN = types.BuiltinFunctionType
_IMMUTABLE = 1 << 8                                    # Py_TPFLAGS_IMMUTABLETYPE: set on C types, never on a Python class
_MON_NAMES = ('get_tool', 'get_events', 'set_events', 'set_local_events', 'register_callback', 'use_tool_id')

def _c_type(x, mod, qual):
    return type(x) is type and bool(x.__flags__ & _IMMUTABLE) and x.__module__ == mod and x.__qualname__ == qual

def _c_func(f, selfname, name):
    s = getattr(f, '__self__', None)
    sn = s.__name__ if type(s) is types.ModuleType else type(s).__name__
    return type(f) is _BUILTIN and f.__name__ == name and sn == selfname

def _vocab_bad():
    """Revision 7 (M3, N1): the one-call vocabulary as the module binds it NOW (a reload re-binds it)."""
    s = getattr(_CONSUME, '__self__', None)
    if 'deque_by_name' in MUT: deq = _c_func(_CONSUME, 'deque', 'extend')                       # revision 6's test
    else: deq = (type(_CONSUME) is _BUILTIN and _CONSUME.__name__ == 'extend' and _c_type(type(s), 'collections', 'deque')
                 and s.maxlen == 0)
    vocab = ((_c_type(_map, 'builtins', 'map'), 'map'), (_c_type(_filter, 'builtins', 'filter'), 'filter'),
             (_c_type(_chain, 'itertools', 'chain'), 'itertools.chain'),
             (_c_type(_compress, 'itertools', 'compress'), 'itertools.compress'),
             (_c_type(_repeat, 'itertools', 'repeat'), 'itertools.repeat'),
             (_c_type(_list, 'builtins', 'list'), 'list'),
             (_c_func(_is, '_operator', 'is_'), 'operator.is_'), (_c_func(_not, '_operator', 'not_'), 'operator.not_'),
             (_c_func(_and, '_operator', 'and_'), 'operator.and_'),
             (_c_func(_setitem, '_operator', 'setitem'), 'operator.setitem'),
             (_c_type(type(_ARMED), 'operator', 'attrgetter'), 'operator.attrgetter'),
             (type(_VALUES) is types.MethodDescriptorType and _VALUES.__objclass__ is type({})
              and (_VALUES.__name__ == 'values' or 'deque_by_name' in MUT), 'dict.values'),
             (deq, 'deque(maxlen=0).extend'),
             (_c_func(_is_not, '_operator', 'is_not'), 'operator.is_not'),
             (_c_func(_tee, 'itertools', 'tee'), 'itertools.tee'),
             (type(_REPL_APPEND) is _BUILTIN and _REPL_APPEND.__self__ is _REPL and type(_REPL) is list
              and _REPL_APPEND.__name__ == 'append', '_LOST.append'))
    return [n for ok, n in vocab if not ok]

def bind():
    """Revision 6 (M1): bind _MON at the first coverage_trace(), only if every function is sys.monitoring's C builtin
    and the one-call vocabulary is C. Revision 7 (M3): the check runs at EVERY coverage_trace(): the vocabulary as the
    module binds it now, and the _MON items as bound (or, before the first binding, sys.monitoring's). Revision 7
    (N6): the version gate is read here, at call time. Refuse UNSUPPORTED_VERSION otherwise; bind nothing."""
    global _get_tool, _get_events, _set_events, _set_local_events, _register_callback, _use_tool_id
    if tuple(sys.version_info[:3]) not in _VERIFIED:
        raise Unsupported('[V5:UNSUPPORTED_VERSION] CPython %s is not a verified patch level' % '.'.join(map(str, tuple(sys.version_info[:3]))))
    if _BOUND[0] and 'check_once' in MUT: return          # revision 6: checked only when _MON is first bound
    mon = sys.monitoring
    fns = _MONB[0] if _MONB[0] is not None else tuple(getattr(mon, n, None) for n in _MON_NAMES)
    if 'no_builtin_check' not in MUT:
        bad = [n for n, f in zip(_MON_NAMES, fns) if not (type(f) is _BUILTIN and f.__self__ is mon and f.__name__ == n)]
        bad += _vocab_bad()
        if bad: raise Unsupported('[V5:UNSUPPORTED_VERSION] not the C builtin: ' + ', '.join(bad))
    if _MONB[0] is None: _MONB[0] = fns
    _get_tool, _get_events, _set_events, _set_local_events, _register_callback, _use_tool_id = _MONB[0]
    _BOUND[0] = True
_NAME1 = (NAME,)
_PYU1, _ZERO1, _NONE1, _TRUE1 = (PYU,), (0,), (None,), (True,)
_LOSTKEY, _ALWAYS = _repeat('UNWIND_LOST'), _repeat(True)

def _hk(point):
    h = _HOOK[0]
    if h is not None: h(point)
STATS = {'toggles_on': 0, 'toggles_off': 0}

class CutUnavailable(Exception): pass
class TraceInactive(Exception): pass
class MachineryBusy(Exception): pass

class Opening:
    __slots__ = ('section', 'frame', 'loop', 'calls', 'ambiguous', 'fin', 'armed', 'core')
    def __init__(self, section, frame, loop, core):
        self.section, self.frame, self.loop, self.core = section, frame, loop, core
        self.armed = False
        self.calls, self.ambiguous, self.fin = {}, {}, {}

class Core:
    __slots__ = ('by_code', 'openings', 'flags', 'unc', 'lost', 'exiting', 'exited', 'facade_dead', 'problems')  # rev 6 (M4 iv)
    def __init__(self):
        self.by_code, self.openings, self.flags = {}, [], {}
        self.unc = [{}, {}]
        self.lost = False
        self.exiting = False
        self.exited = False
        self.facade_dead = False
        self.problems = []

def _core_dead(c): return c.exited or c.facade_dead

class Mint:
    def __init__(self, fn, core):
        self.fn, self.original = fn, fn.__code__
        self.code = fn.__code__.replace()
        self.globals = fn.__globals__
        self.holders = (core,)
        self.pend = {}

def _bindings():
    return [_HANDLE_DICT[0].get('_run'), _LOOP_DICT[0].get('_run_once')]

def cut_refresh():
    for h in _bindings():
        if type(h) is not types.FunctionType: raise CutUnavailable('not a plain function')
        _CUT.setdefault(id(h.__code__), h.__code__)

def _cut_ok():
    for h in _bindings():
        if type(h) is not types.FunctionType or _CUT.get(id(h.__code__)) is not h.__code__: return False
    return True

def _outcome(f, code, holders):
    loop = _get_running_loop()
    found = []; stop = 'u'; g = f.f_back
    while g is not None:
        c = g.f_code
        if _CUT.get(id(c)) is c: stop = 'd'; break
        o = _ANCHORS.get(g)
        if o is not None:
            if o.loop is not loop: stop = 'd'; break
            found.append(o)
        g = g.f_back
    out = []
    for h in holders:
        if id(code) not in h.by_code: continue
        mine = [o for o in found if o in h.openings]
        if len(mine) == 1: out.append((h, 'c', mine[0]))
        elif mine: out.append((h, 'a', tuple(mine)))
        else: out.append((h, stop, None))
    return out

def _on_entry(code, offset):
    m = _MINTED.get(id(code))
    if m is None or m.code is not code: return
    f = sys._getframe(1)
    if f.f_globals is not m.globals: return
    if not _ANCHORS and 'store_no_anchor' not in MUT: return   # revision 7 audit: MUT stores even with no anchor
    out = _outcome(f, code, m.holders)
    if out: m.pend[id(f)] = (None if 'pend_bare_id' in MUT else f, offset, out)   # revision 8 probe: MUT holds no frame

def _publish(code, outs):
    for h, kind, o in outs:
        if id(code) not in h.by_code: continue
        if kind == 'c': o.calls[code.co_name] = o.calls.get(code.co_name, 0) + 1
        elif kind == 'a':
            for x in o: x.ambiguous[code.co_name] = x.ambiguous.get(code.co_name, 0) + 1
        else:
            d = h.unc[0 if kind == 'd' else 1]; d[code.co_name] = d.get(code.co_name, 0) + 1

def _on_exit(code, offset, value):
    m = _MINTED.get(id(code))
    if m is None or m.code is not code: return
    f = sys._getframe(1); p = m.pend.pop(id(f), None)
    if p is not None and (p[0] is f or 'pend_bare_id' in MUT): _publish(code, p[2])

def _on_unwind(code, offset, exc):
    m = _MINTED.get(id(code))
    if m is None or m.code is not code: return
    f = sys._getframe(1); p = m.pend.pop(id(f), None)
    if p is not None and (p[0] is f or 'pend_bare_id' in MUT) and offset != p[1]: _publish(code, p[2])

LOCAL = E.PY_START | E.PY_RESUME | E.PY_RETURN | E.PY_YIELD
CALLBACKS = ((E.PY_START, _on_entry), (E.PY_RESUME, _on_entry), (E.PY_RETURN, _on_exit), (E.PY_YIELD, _on_exit),
             (E.PY_UNWIND, _on_unwind))
_EVS5 = tuple(e for e, _ in CALLBACKS); _FNS5 = tuple(f for _, f in CALLBACKS)

def _named_it(t):
    """Lazily: True iff tool t carries this copy's name (an `is` test: no foreign __eq__ can run)."""
    return _map(_is, _map(_get_tool, (t,)), _NAME1)

def _named(t):                                      # a plain test, for reads only (never before a write)
    return _get_tool(t) is NAME

# ------------------------------------------------------------------------------------------------ the three steps
def _unwind_on(o):
    t = TOOL[0]
    _hk('on:enter')
    if 'no_gate' in MUT:                            # no name test (own-anchor gate kept)
        if _ANCHORS.get(o.frame) is o and not (_get_events(t) & PYU): _set_events(t, PYU); STATS['toggles_on'] += 1
        _hk('on:return'); return
    if 'on_capture_split' in MUT:                   # read in one call, capture and set in a second
        clear = _any(_map(_not, _map(_and, _map(_get_events, _compress((t,), _named_it(t))), _PYU1)))
        _hk('on:read')
        if clear and _ANCHORS.get(o.frame) is o:
            for p in list(_ANCHORS.values()):
                if p.armed: p.core.flags['UNWIND_LOST'] = True
            _set_events(t, PYU); STATS['toggles_on'] += 1
        _hk('on:return'); return
    if 'gate_split' in MUT:                         # the name test, then (separately) the rest
        ok = _named(t)
        _hk('on:named')
        if not ok: _hk('on:return'); return
        _CONSUME(_chain(
            _map(_setitem, _map(_FLAGS, _filter(_ARMED, _chain.from_iterable(_map(_VALUES,
                 _compress(_compress((_ANCHORS,), _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),
                           _map(_not, _map(_and, _map(_get_events, (t,)), _PYU1))))))), _LOSTKEY, _ALWAYS),
            _map(_set_events, _compress(_compress((t,), _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),
                                        _map(_not, _map(_and, _map(_get_events, (t,)), _PYU1))), _PYU1)))
        _hk('on:return'); return
    own = _TRUE1 if 'on_ungated_own' in MUT else _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))
    own2 = _TRUE1 if 'on_ungated_own' in MUT else _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))
    clear_gate = _TRUE1 if 'on_capture_nogate' in MUT else _map(_not, _map(_and, _map(_get_events, (t,)), _PYU1))
    capture = () if 'on_no_capture' in MUT else _map(_setitem, _map(_FLAGS, _filter(_ARMED, _chain.from_iterable(
        _map(_VALUES, _compress(_compress(_compress((_ANCHORS,), _named_it(t)), own), clear_gate))))), _LOSTKEY, _ALWAYS)
    # ONE CALL: capture (if the event is clear), then set; both under the name and own-anchor gates
    _CONSUME(_chain(capture,
                    _map(_set_events,
                         _compress(_compress(_compress((t,), _named_it(t)), own2),
                                   _map(_not, _map(_and, _map(_get_events, (t,)), _PYU1))),
                         _PYU1)))
    STATS['toggles_on'] += 1
    _hk('on:return')

def _unwind_off(key):
    t = TOOL[0]
    _hk('off:enter')
    if 'popoff_split' in MUT and key is not None:
        _ANCHORS.pop(key, None); _hk('off:popped'); key = None
    if 'off_split' in MUT:                          # the test, then the clear: revision 3's shape, split open
        _ANCHORS.pop(key, None)
        empty = not _ANCHORS and _named(t)
        _hk('off:tested')
        if empty: _set_events(t, 0); STATS['toggles_off'] += 1
        _hk('off:return'); return
    if 'no_gate' in MUT:
        _ANCHORS.pop(key, None)
        if not _ANCHORS: _set_events(t, 0)
        _hk('off:return'); return
    if 'gate_split' in MUT:
        ok = _named(t)
        _hk('off:named')
        if ok: _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1), _map(_set_events, _compress((t,), _map(_not, (_ANCHORS,))), _ZERO1)))
        else: _ANCHORS.pop(key, None)
        _hk('off:return'); return
    # ONE CALL: pop the key, then clear iff the id is named and no anchor is left
    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),
                    _map(_set_events,
                         _compress(_compress((t,), _named_it(t)), _map(_not, (_ANCHORS,))),
                         _ZERO1)))
    STATS['toggles_off'] += 1
    _hk('off:return')

def _blind_event(t):
    """The event is clear. get_events never raises, even on a freed id (out_freed_id_calls.txt), so no gate."""
    if 'blind_read_gated' in MUT: return _named(t) and not (_get_events(t) & PYU)   # revision 4's form (F14)
    return not (_get_events(t) & PYU)

def _take(t):
    """One call: use_tool_id(t, NAME) iff the id is unowned at that instant, so another tool taking it between a test
    and the call cannot make styxx raise ValueError; then report whether the id carries this copy's name."""
    if 'take_split' in MUT:
        free = _get_tool(t) is None
        _hk('take:tested')
        if free: _use_tool_id(t, NAME)
        return _named(t)
    if 'take_count' in MUT:                          # revision 8 probe (N1): each take appends inside the same call
        _CONSUME(_map(_REPL_APPEND, _map(_use_tool_id, _compress((t,), _map(_is, _map(_get_tool, (t,)), _NONE1)), _NAME1)))
        return _named(t)
    _CONSUME(_map(_use_tool_id, _compress((t,), _map(_is, _map(_get_tool, (t,)), _NONE1)), _NAME1))
    return _named(t)

def _set_local_named(t, code, evs):
    if 'no_gate' in MUT: _set_local_events(t, code, evs); return
    if 'gate_split' in MUT:
        ok = _named(t); _hk('local:named')
        if ok: _set_local_events(t, code, evs)
        return
    _CONSUME(_map(_set_local_events, _compress((t,), _named_it(t)), (code,), (evs,)))

def _register_named(t):
    """Revision 6: one statement, one consuming call. Each register_callback is gated on the name, evaluated right
    before it; the owner is read once more after the last exchange. Returns [prev_1 .. prev_n, owner_after].
    An audit hook runs INSIDE each register_callback, before its exchange (B1): this is not an atomic step."""
    if 'no_gate' in MUT: return [_register_callback(t, e, f) for e, f in CALLBACKS] + [_get_tool(t)]
    if 'gate_split' in MUT:
        ok = _named(t); _hk('reg:named')
        return ([_register_callback(t, e, f) for e, f in CALLBACKS] if ok else []) + [_get_tool(t)]
    if 'reg_rev5' in MUT:                            # revision 5: one gate before all five exchanges, no owner read
        return list(_map(_register_callback, _chain.from_iterable(_map(_repeat, _compress((t,), _named_it(t)), (5,))),
                         _EVS5, _FNS5)) + [None]
    if 'reg_no_owner' in MUT:                        # mutant: per-exchange gates, but no owner read after the last
        return _list(_map(_register_callback,
                          _compress(_repeat(t), _map(_is, _map(_get_tool, _repeat(t, 5)), _repeat(NAME))),
                          _EVS5, _FNS5)) + [NAME]
    if 'cbrep_nocount' in MUT or 'count_after_register' in MUT:   # revision 6's form: returns the previous callbacks
        return _list(_chain(
            _map(_register_callback,
                 _compress(_repeat(t), _map(_is, _map(_get_tool, _repeat(t, 5)), _repeat(NAME))),
                 _EVS5, _FNS5),
            _map(_get_tool, (t,))))
    if 'count_excl_none' in MUT:                     # revision 8 probe (N4): None previous callbacks not counted
        out = []
        for e, f in zip(_EVS5, _FNS5):
            if _get_tool(t) is not NAME: break
            p = _register_callback(t, e, f)
            if p is not f and p is not None: _REPL_APPEND(True); out.append(None)
        return out + [_get_tool(t)]
    if 'reg_rev7' not in MUT:                        # revision 8 (M1): the exchanges read through tee, so each previous
        a, b = _tee(_map(_register_callback,        # callback stays referenced until every count is made
                         _compress(_repeat(t), _map(_is, _map(_get_tool, _repeat(t, 5)), _repeat(NAME))),
                         _EVS5, _FNS5))
        return _list(_chain(
            _map(_REPL_APPEND, _map(_is_not, _compress(a, _map(_is_not, b, _FNS5)), _repeat(None))),
            _map(_get_tool, (t,))))
    # revision 7 (B1): each exchange whose previous callback is not styxx's is counted (a C list.append) inside the
    # same consuming call, before the next exchange's audit hook can run. Returns [None]*k + [owner].
    return _list(_chain(
        _map(_REPL_APPEND, _filter(None, _map(_is_not,
             _map(_register_callback,
                  _compress(_repeat(t), _map(_is, _map(_get_tool, _repeat(t, 5)), _repeat(NAME))),
                  _EVS5, _FNS5),
             _FNS5))),
        _map(_get_tool, (t,))))

def lost_count():                                    # revision 7: _LOST as the spec now reads it (len of a list)
    return RECLAIMED[0] + len(_REPL)

REV7_FORM = lambda: not ({'cbrep_nocount', 'count_after_register', 'no_gate', 'gate_split', 'reg_rev5', 'reg_no_owner'} & MUT)

def reg_verdict(r):
    """Revision 6: ('ok' | 'none' | 'split'), n exchanges made, the owner right after the last one."""
    n, owner = len(r) - 1, r[-1]
    if n == 0: return 'none', 0, owner
    if n == 5 and owner is NAME: return 'ok', 5, owner
    return 'split', n, owner

REG_LOG = []                                         # (site, verdict, n, owner) of every registration, for the probes
def _register_checked(t, site):
    """Returns (ok, replaced): complete registration; some previous callback was not styxx's."""
    rev7 = REV7_FORM()
    r = _register_named(t)
    if rev7:                                         # [None]*k + [owner]: complete iff owner is NAME (all gates passed)
        ok = r[-1] is NAME
        REG_LOG.append((site, 'ok' if ok else 'incomplete', len(r) - 1, r[-1]))
        return ok, len(r) > 1
    if 'reg_rev5' in MUT:
        REG_LOG.append((site, 'rev5', len(r) - 1, None))
        return True, any(p is not f for p, f in zip(r[:-1], _FNS5))
    v, n, owner = reg_verdict(r)
    REG_LOG.append((site, v, n, owner))
    return v == 'ok', any(p is not f for p, f in zip(r[:-1], _FNS5))

# ------------------------------------------------------------------------------------------------ the mutex (N3)
class Tok:
    __slots__ = ('tid', 'frame', 'succ')
    def __init__(self, frame): self.tid, self.frame, self.succ = threading.get_ident(), frame, {}   # a fresh dict (N6)
_GUARD = globals().get('_GUARD', {'hint': None})
def _tok_alive(t):
    f = sys._current_frames().get(t.tid)
    while f is not None:
        if f is t.frame: return True
        f = f.f_back
    return False

def _acquire(me):
    mono = time.monotonic if 'time_at_call' in MUT else _monotonic
    t0 = mono()
    while True:
        r = _GUARD['hint']
        if r is None or not _tok_alive(r):
            _GUARD['hint'] = me; return
        if r.tid == me.tid: raise MachineryBusy('[V5:REENTRANT]')
        mono = time.monotonic if 'time_at_call' in MUT else _monotonic
        if mono() - t0 > BUSY[0]: raise MachineryBusy('[V5:MACHINERY_BUSY]')
        (time.sleep if 'time_at_call' in MUT else _sleep)(0.0002)

def _release(me):
    if _GUARD['hint'] is me: _GUARD['hint'] = None

def _locked(fn, *a):
    me = Tok(sys._getframe()); _acquire(me); out = fn(*a); _release(me); return out

# ------------------------------------------------------------------------------------------------ transitions
def _prune(core):                                    # revision 5: no credit stop (a dead core's record is never read)
    for o in list(core.openings): _detach(o)

RECLAIMED = globals().get('RECLAIMED', [0])
def _reclaim():                                      # M3 step 0: a freed, unowned id is re-taken (clobbers nobody)
    t = TOOL[0]
    if t is None: return
    if _get_tool(t) is None:
        if _take(t):
            ok, _r = _register_checked(t, 'reclaim')
            if ok or 'reg_rev5' in MUT: RECLAIMED[0] += 1

def reconcile():
    _reclaim()
    for m in list(_MINTED.values()):
        for h in m.holders:
            if _core_dead(h) and not h.exited: _prune(h)
        keep = tuple([h for h in m.holders if not _core_dead(h)])
        m.holders = keep
        if not keep: _retire(m)
    if 'no_anchor_prune' not in MUT:                 # every dead core reachable from a registered anchor
        for k, o in list(_ANCHORS.items()):
            if _core_dead(o.core): _prune(o.core); _ANCHORS.pop(k, None)
    if 'no_rec_off' not in MUT and TOOL[0] is not None: _unwind_off(None)   # last (revision 6, F20: only once an id is held)

class MonitorBusy(Exception): pass
def install_tool():                                  # _ensure_tool (revision 6: rebinding stated and done)
    t = TOOL[0]
    if t is not None:
        if 'ensure_nocount' not in MUT: _reclaim()   # our own id: a freed one is re-taken through _reclaim (counted)
        elif _get_tool(t) is None: _take(t); _register_checked(t, 'ensure')
        if _named(t): return
    for i in (4, 3):                                 # first acquisition, or rebinding away from a taken id
        if not _named(i):
            _take(i)
            if not _named(i): continue
        ok, _r = _register_checked(i, 'ensure')
        if not ok: continue
        if t is not None and (t != i or 'retake_nocount' not in MUT):   # revision 6 (N1) rebinding; revision 7 (M5.2): or a re-take
            if 'rebind_count_none' not in MUT: RECLAIMED[0] += 1
            if 'rebind_no_local' not in MUT:
                for m in list(_MINTED.values()): _set_local_named(i, m.code, LOCAL)
        TOOL[0] = i
        return
    raise MonitorBusy('[V5:MONITOR_BUSY]')

def _retire(m):
    if m.fn.__code__ is m.code: m.fn.__code__ = m.original
    _set_local_named(TOOL[0], m.code, 0)            # one call, name-gated
    m.pend.clear()
    _MINTED.pop(id(m.code), None)
    # revision 5: no step 6 (reconciliation's last OFF, and OFF with every pop, leave nothing to clear)

class Tracer:
    def __init__(self, *fns):                       # coverage_trace(): revision 7 (M3) checks the binding every time
        bind()
        self.core = Core(); self.fns = fns; self.mints = []
    def __enter__(self):
        bind()
        cut_refresh()
        def txn():
            reconcile(); _hk('enter:reconciled'); install_tool()
            self.lost0 = lost_count()
        _locked(txn)
        for fn in self.fns:
            m = _MINTED.get(id(fn.__code__))
            if m is not None and m.code is fn.__code__:  # revision 7 (N5): join an existing mint (Minting, "An existing mint")
                m.holders = m.holders + (self.core,)
            else:
                m = Mint(fn, self.core)
                _MINTED[id(m.code)] = m
                _set_local_named(TOOL[0], m.code, LOCAL)
                fn.__code__ = m.code
            self.core.by_code[id(m.code)] = fn.__name__
            self.mints.append(m)
        return self
    def __exit__(self, *a):
        if self.core.exiting: return False
        self.core.exiting = True
        self.core.by_code = {}
        for o in list(self.core.openings): _detach(o)
        def txn():
            reconcile()
            if lost_count() != self.lost0: self.core.lost = True
            t = TOOL[0]
            if 'reg_rev5' in MUT and not _named(t):     # revision 5: name test, then (separately) the registration
                self.core.lost = True
                for m in self.mints:
                    m.holders = tuple([h for h in m.holders if h is not self.core])
                    if not m.holders:
                        if m.fn.__code__ is m.code: m.fn.__code__ = m.original
                        _MINTED.pop(id(m.code), None)
                return
            ok, replaced = _register_checked(t, 'exit')   # revision 6: gated per exchange, owner read after the last
            _hk('exit:registered')                      # revision 7: a fault point between the registration and the rest
            if 'count_after_register' in MUT and ok and replaced: RECLAIMED[0] += 1   # the critic's form: a count after the call
            if lost_count() != self.lost0: self.core.lost = True   # revision 7: includes this registration's own count
            if not ok and 'reg_rev5' not in MUT:        # the id is not (or no longer) ours: never touched again
                self.core.lost = True
                for m in self.mints:                     # step 3 still drops the holder; _retire's local write is gated
                    m.holders = tuple([h for h in m.holders if h is not self.core])
                    if not m.holders:
                        if m.fn.__code__ is m.code: m.fn.__code__ = m.original
                        _MINTED.pop(id(m.code), None)
                return
            if replaced: self.core.lost = True
            for m in self.mints:
                if _get_local(t, m.code) != LOCAL: self.core.lost = True
                m.holders = tuple([h for h in m.holders if h is not self.core])   # revision 7: other holders keep the mint
                if not m.holders: _retire(m)
        try: _locked(txn)
        except MachineryBusy as e: self.core.problems.append(str(e))
        self.core.exited = True
        return False
    def _open(self, section, frame):
        if self.core.exiting or self.core.exited:
            self.core.problems.append('[V5:TRACE_INACTIVE]'); raise TraceInactive('[V5:TRACE_INACTIVE]')
        _hk('open:checked')
        loop = _get_running_loop()
        g = frame.f_back
        while g is not None:
            c = g.f_code
            if _CUT.get(id(c)) is c: break
            o = _ANCHORS.get(g)
            if o is not None and o in self.core.openings and o.loop is loop: raise RuntimeError('[V5:NESTED_SECTION]')
            g = g.f_back
        o = Opening(section, frame, loop, self.core)
        self.core.openings.append(o)
        return o
    def run(self, section, fn, *a, **k):            # MF4: a plain def that returns _run(...)
        return _run(self, section, fn, a, k)
    def run_async(self, section, afn, *a, **k):     # a plain def: the coroutine is _run_async's
        return _run_async(self, section, afn, a, k)
    def result(self):
        r = {}
        for o in self.core.openings:
            for k, v in o.calls.items(): r.setdefault(o.section, {})[k] = r.get(o.section, {}).get(k, 0) + v
        return {'calls': r, 'dispatched': self.core.unc[0], 'unattributed': self.core.unc[1],
                'MONITOR_LOST': self.core.lost or bool(self.core.flags.get('UNWIND_LOST')),
                'problems': list(self.core.problems)}

def _commit(o):
    _hk('commit:0')
    if 'on_before_store' in MUT:                    # revision 3's first set: before the store, no own-anchor gate
        t = TOOL[0]
        if _named(t) and not (_get_events(t) & PYU): _set_events(t, PYU)
        _hk('commit:on-early')
    _ANCHORS[o.frame] = o
    _hk('commit:stored')
    if 'no_recheck' not in MUT:
        claimed = 'fin' in o.fin and 'no_fin_test' not in MUT
        exiting = o.core.exiting and 'no_exiting_test' not in MUT
        if claimed or exiting:
            _detach(o)
            o.core.problems.append('[V5:TRACE_INACTIVE]')
            raise TraceInactive('[V5:TRACE_INACTIVE]')
    _hk('commit:checked')
    if 'no_on' not in MUT and 'on_before_store' not in MUT: _unwind_on(o)
    _hk('commit:on')
    o.armed = True
    _hk('commit:armed')

def _detach(o):
    o.fin.setdefault('fin', 1)
    _hk('detach:claimed')
    fr = o.frame
    if fr is not None:
        t = TOOL[0]
        if 'blind_anchor_first' in MUT:
            reg = _ANCHORS.get(fr) is o
            _hk('detach:anchor-read')
            if (o.armed or 'blind_no_armed' in MUT) and reg and _blind_event(t): o.core.flags['UNWIND_LOST'] = True
        else:
            if ((o.armed or 'blind_no_armed' in MUT) and _blind_event(t)
                    and (_hk('detach:event-read') or True)
                    and (_ANCHORS.get(fr) is o or 'blind_no_anchor' in MUT)):
                o.core.flags['UNWIND_LOST'] = True
        _hk('detach:checked')
        if 'detach_nulls' in MUT: o.frame = None
        _unwind_off(fr)                             # one call: pop, then clear iff nothing is left
        _hk('detach:done')

def _run(tr, section, fn, args, kwargs):
    if 'open_locks' in MUT: return _locked(_run_locked_mutant, tr, section, fn, args, kwargs)   # revision 7 audit mutant
    o = tr._open(section, sys._getframe())
    try:
        _commit(o)
        return fn(*args, **kwargs)
    finally:
        _detach(o)
        o.frame = None

def _run_locked_mutant(tr, section, fn, args, kwargs):
    MUT.discard('open_locks')
    try: return _run(tr, section, fn, args, kwargs)
    finally: MUT.add('open_locks')

async def _run_async(tr, section, afn, args, kwargs):
    o = tr._open(section, sys._getframe())
    try:
        _commit(o)
        return await afn(*args, **kwargs)
    finally:
        _detach(o)
        o.frame = None

def _get_local(t, code):
    try: return M.get_local_events(t, code)
    except ValueError: return None

def state():
    t = TOOL[0]
    name = M.get_tool(t) if t is not None else None
    return {'tool_name': name, 'global_events': M.get_events(t) if name is not None else None, 'anchors': len(_ANCHORS),
            'mints': len(_MINTED)}

def events_set():
    return bool(TOOL[0] is not None and M.get_tool(TOOL[0]) is not None and M.get_events(TOOL[0]) & PYU)

def reset():
    _ANCHORS.clear(); _HOOK[0] = None; MUT.clear(); _GUARD['hint'] = None
    bind()
    for t in (3, 4):
        if M.get_tool(t) is not None:
            for e in _EVS5: M.register_callback(t, e, None)
            try: M.set_events(t, 0)
            except ValueError: pass
            M.free_tool_id(t)
    TOOL[0] = None; REG_LOG.clear(); install_tool(); M.set_events(TOOL[0], 0)
