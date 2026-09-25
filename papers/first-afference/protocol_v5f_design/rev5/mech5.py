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
TOOL = [4]
NAME = 'styxx.protocol/model-rev5'
_get_running_loop = ev._get_running_loop
_TYPE_DICT = type.__dict__['__dict__']
_HANDLE_DICT = [_TYPE_DICT.__get__(ev.Handle)]
_LOOP_DICT = [_TYPE_DICT.__get__(be.BaseEventLoop)]
_CUT = {}
_ANCHORS = {}
_MINTED = {}
MUT = set()
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
_get_tool, _get_events, _set_events = M.get_tool, M.get_events, M.set_events
_set_local_events, _register_callback = M.set_local_events, M.register_callback
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
    if not _ANCHORS: return
    out = _outcome(f, code, m.holders)
    if out: m.pend[id(f)] = (f, offset, out)

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
    if p is not None and p[0] is f: _publish(code, p[2])

def _on_unwind(code, offset, exc):
    m = _MINTED.get(id(code))
    if m is None or m.code is not code: return
    f = sys._getframe(1); p = m.pend.pop(id(f), None)
    if p is not None and p[0] is f and offset != p[1]: _publish(code, p[2])

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
    return not (_get_events(t) & PYU)

_use_tool_id = M.use_tool_id
def _take(t):
    """One call: use_tool_id(t, NAME) iff the id is unowned at that instant, so another tool taking it between a test
    and the call cannot make styxx raise ValueError; then report whether the id carries this copy's name."""
    if 'take_split' in MUT:
        free = M.get_tool(t) is None
        _hk('take:tested')
        if free: _use_tool_id(t, NAME)
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
    """One call: re-register our five callbacks iff the id is named; returns the previous callbacks ([] if not)."""
    if 'no_gate' in MUT: return [_register_callback(t, e, f) for e, f in CALLBACKS]
    if 'gate_split' in MUT:
        ok = _named(t); _hk('reg:named')
        return [_register_callback(t, e, f) for e, f in CALLBACKS] if ok else []
    return list(_map(_register_callback, _chain.from_iterable(_map(_repeat, _compress((t,), _named_it(t)), (5,))),
                     _EVS5, _FNS5))

# ------------------------------------------------------------------------------------------------ the mutex (N3)
class Tok:
    __slots__ = ('tid', 'frame', 'succ')
    def __init__(self, frame): self.tid, self.frame, self.succ = threading.get_ident(), frame, {}   # a fresh dict (N6)
_GUARD = {'hint': None}
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

RECLAIMED = [0]
def _reclaim():                                      # M3 step 0: a freed, unowned id is re-taken (clobbers nobody)
    t = TOOL[0]
    if M.get_tool(t) is None:
        if _take(t): _register_named(t); RECLAIMED[0] += 1

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
    if 'no_rec_off' not in MUT: _unwind_off(None)    # last: one call, clears the event iff nothing is registered

_EVER = [False]                                      # stands in for `_TOOL[0] is not None` (the model's id is fixed)
def install_tool():                                  # _ensure_tool
    t = TOOL[0]
    if _EVER[0] and 'ensure_nocount' not in MUT:     # our own id: a freed one is re-taken through _reclaim (counted)
        _reclaim()
    else:
        _take(t)
    _EVER[0] = True
    _register_named(t)

def _retire(m):
    if m.fn.__code__ is m.code: m.fn.__code__ = m.original
    _set_local_named(TOOL[0], m.code, 0)            # one call, name-gated
    m.pend.clear()
    _MINTED.pop(id(m.code), None)
    # revision 5: no step 6 (reconciliation's last OFF, and OFF with every pop, leave nothing to clear)

class Tracer:
    def __init__(self, *fns):
        self.core = Core(); self.fns = fns; self.mints = []
    def __enter__(self):
        cut_refresh()
        def txn():
            reconcile(); _hk('enter:reconciled'); install_tool()
            self.lost0 = RECLAIMED[0]
        _locked(txn)
        for fn in self.fns:
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
        t = TOOL[0]
        def txn():
            reconcile()
            if RECLAIMED[0] != self.lost0: self.core.lost = True
            if not _named(t):                           # the id is another tool's: never touched again
                self.core.lost = True
                for m in self.mints:
                    if m.fn.__code__ is m.code: m.fn.__code__ = m.original
                    _MINTED.pop(id(m.code), None)
                return
            prev = _register_named(t)
            if any(p is not f for p, f in zip(prev, _FNS5)): self.core.lost = True
            for m in self.mints:
                _retire(m)
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
    o = tr._open(section, sys._getframe())
    try:
        _commit(o)
        return fn(*args, **kwargs)
    finally:
        _detach(o)
        o.frame = None

async def _run_async(tr, section, afn, args, kwargs):
    o = tr._open(section, sys._getframe())
    try:
        _commit(o)
        return await afn(*args, **kwargs)
    finally:
        _detach(o)
        o.frame = None

def state():
    t = TOOL[0]
    name = M.get_tool(t)
    return {'tool_name': name, 'global_events': M.get_events(t) if name is not None else None, 'anchors': len(_ANCHORS),
            'mints': len(_MINTED)}

def events_set():
    return bool(M.get_tool(TOOL[0]) is not None and M.get_events(TOOL[0]) & PYU)

def reset():
    _ANCHORS.clear(); _HOOK[0] = None; MUT.clear(); _GUARD['hint'] = None
    t = TOOL[0]
    if M.get_tool(t) is not None and M.get_tool(t) is not NAME:
        for e in _EVS5: M.register_callback(t, e, None)
        M.free_tool_id(t)
    if M.get_tool(t) is None: M.use_tool_id(t, NAME)
    _EVER[0] = False; install_tool(); M.set_events(t, 0)
