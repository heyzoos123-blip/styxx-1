# Revision-3 model of v5f's event path: rev2/mech2.py (the revision-2 model) copied, with the revision-3 changes to
# the section-scoped PY_UNWIND behind one more switch, REV3, so each probe can compare revision 2 with revision 3:
#   REV3          - True (rev 3): (MF2) the anchor commit and both _unwind_on() calls move out of _open into _commit,
#                   the first statement of _run's / _run_async's try body, so a fault anywhere in them is followed
#                   by _detach's pop and _unwind_off(); (MF1) _unwind_off reads the id and the event first and then
#                   tests _ANCHORS immediately before its clear, with no call in between; _retire step 6 is
#                   _unwind_off(); every reconciliation ends with _unwind_off(); _detach flags UNWIND_LOST only
#                   for an opening that _commit completed (o.armed, its last statement) and whose anchor is still
#                   registered, so neither a fault inside _commit nor exit's X3 re-detaching an opening whose close
#                   was cut short after its pop makes a false MONITOR_LOST. False: revision 2 exactly as mech2.py.
#   _HOOK         - test hook, called with a point name at every statement boundary of _commit, _open (rev 2),
#                   _unwind_on, _unwind_off, _detach and _retire step 6. Every point is either after a C call
#                   (where CPython 3.12/3.13 may switch threads or deliver an asynchronous exception) or a statement
#                   boundary where an injected fault can land. Probes use it to force a switch or raise a fault.
#                   The one place with no hook is between _unwind_off's _ANCHORS test and its clear, which are one
#                   expression on one line: nothing but loads lies between them, so no switch and no delivered
#                   asynchronous exception can separate them (q1_test_then_call_atomic.py). An injected fault there
#                   has the same effect as one just before the test (no clear).
# Revision-2 switches, unchanged:
#   CUT_RUN_ONCE  - BaseEventLoop._run_once's code is a cut code too, and _cut_ok() checks both bindings (M1)
#   SHARE_CHECK   - E2 refuses CUT_UNAVAILABLE for a binding whose code is shared or can be shared (M2)
#   UNWIND_SCOPE  - 'mint' (rev 1: global PY_UNWIND while any mint exists) or 'section' (rev 2: only while an
#                   anchor is registered, set before the anchor commit, cleared after the last anchor pops) (M4)
#   RECLAIM       - exit re-takes a freed, unowned tool id and clears its events (M3)
#   CUT_MODE      - 'monotone' (spec) or 'replaced' (the N4 mutant: E2 resets the cut to the current codes)
# No try/finally or with-exit guards any machinery state here except _run's and _run_async's single try/finally
# (rev 3: around _commit and fn; _run's try body has no loop).
import sys, types, gc, asyncio, asyncio.events as ev, asyncio.base_events as be
M = sys.monitoring
E = M.events
TOOL = [4]
NAME = 'styxx.protocol/model-rev3'
_get_running_loop = ev._get_running_loop
_TYPE_DICT = type.__dict__['__dict__']
_HANDLE_DICT = [_TYPE_DICT.__get__(ev.Handle)]
_LOOP_DICT = [_TYPE_DICT.__get__(be.BaseEventLoop)]
_CUT = {}
_ANCHORS = {}
_MINTED = {}
CUT_RUN_ONCE = [True]
SHARE_CHECK = [True]
UNWIND_SCOPE = ['section']
RECLAIM = [True]
CUT_MODE = ['monotone']
REV3 = [True]
# Single-rule mutants of revision 3, for the SM1 witness probe (w1_rev3_witnesses.py); empty = the spec:
#   commit_outside_try - _open commits and toggles before the try (revision 2's placement)
#   no_armed           - _detach's UNWIND_LOST check without o.armed
#   no_anchor_test     - _detach's UNWIND_LOST check without _ANCHORS.get(fr) is o
#   no_reconcile_off   - reconciliation does not end with _unwind_off()
#   off_rev2_order     - _unwind_off tests _ANCHORS first, then makes its calls (revision 2's order)
#   step6_rev2         - _retire step 6 is revision 2's test-then-clear
MUT = set()
_HOOK = [None]

def _hk(point):
    h = _HOOK[0]
    if h is not None: h(point)
STATS = {'toggles_on': 0, 'toggles_off': 0}

class CutUnavailable(Exception): pass

class Opening:
    __slots__ = ('section', 'frame', 'loop', 'calls', 'ambiguous', 'fin', 'armed')
    def __init__(self, section, frame, loop):
        self.section, self.frame, self.loop = section, frame, loop
        self.armed = False
        self.calls, self.ambiguous, self.fin = {}, {}, {}

class Core:
    def __init__(self):
        self.by_code, self.openings, self.flags = {}, [], {}
        self.unc = [{}, {}]
        self.lost = False

class Mint:
    def __init__(self, fn, core):
        self.fn, self.original = fn, fn.__code__
        self.code = fn.__code__.replace()
        self.globals = fn.__globals__
        self.holders = (core,)
        self.pend = {}

def _bindings():
    out = [_HANDLE_DICT[0].get('_run')]
    if CUT_RUN_ONCE[0]: out.append(_LOOP_DICT[0].get('_run_once'))
    return out

def _shared(h):
    """M2: the binding's code is, or can be, shared by another function."""
    c = h.__code__
    if '<locals>' in c.co_qualname: return True
    for r in gc.get_referrers(c):
        if type(r) is types.FunctionType and r is not h: return True
    return False

def cut_refresh():                                  # E2 (and the constructor)
    hs = _bindings()
    for h in hs:
        if type(h) is not types.FunctionType: raise CutUnavailable('not a plain function')
    if CUT_MODE[0] == 'replaced': _CUT.clear()      # N4 mutant
    for h in hs:
        c = h.__code__
        if _CUT.get(id(c)) is c: continue           # already a cut code: no scan
        if SHARE_CHECK[0] and _shared(h): raise CutUnavailable('shared code: ' + c.co_qualname)
        _CUT.setdefault(id(c), c)

def _cut_ok():
    for h in _bindings():
        if type(h) is not types.FunctionType or _CUT.get(id(h.__code__)) is not h.__code__: return False
    return True

def _outcome(f, code, holders):
    loop = _get_running_loop()
    found = []
    stop = 'u'
    g = f.f_back
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
    holders = m.holders
    if not _cut_ok():
        for h in holders: h.flags['CUT_MOVED'] = True
    if f.f_globals is not m.globals: return
    if UNWIND_SCOPE[0] == 'section' and not _ANCHORS: return   # no section open anywhere: nothing stored
    out = _outcome(f, code, holders)
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

def _ours():
    _hk('ours')                                     # models PY_START of _ours, where an exam fault tool can act
    return M.get_tool(TOOL[0]) == NAME

def _unwind_on():                                   # _commit (rev 3) / _open (rev 2): before the anchor commit and after it
    _hk('on:enter')
    if _ours() and not (M.get_events(TOOL[0]) & E.PY_UNWIND):
        _hk('on:read')
        M.set_events(TOOL[0], E.PY_UNWIND); STATS['toggles_on'] += 1
    _hk('on:return')

def _unwind_off():
    if not REV3[0] or 'off_rev2_order' in MUT: return _unwind_off_rev2()
    # rev 3: every call (C) first, then the emptiness test immediately before the clear
    if not _ours() or not (M.get_events(TOOL[0]) & E.PY_UNWIND): return
    _hk('off:read')
    if _ANCHORS or M.set_events(TOOL[0], 0): return # the test and the clear: one expression, one line
    STATS['toggles_off'] += 1
    _hk('off:cleared')
    if _ANCHORS: M.set_events(TOOL[0], E.PY_UNWIND); STATS['toggles_on'] += 1   # defensive; see the spec

def _unwind_off_rev2():                             # rev 2: test _ANCHORS, then calls, then clear, re-check, re-set
    if _ANCHORS or not _ours() or not (M.get_events(TOOL[0]) & E.PY_UNWIND): return
    _hk('off:read')
    M.set_events(TOOL[0], 0); STATS['toggles_off'] += 1
    _hk('off:cleared')
    if _ANCHORS: M.set_events(TOOL[0], E.PY_UNWIND); STATS['toggles_on'] += 1

def retire_step6():                                 # M3 _retire step 6
    if REV3[0] and 'step6_rev2' not in MUT: return _unwind_off()   # rev 3 (MF1): the closer's own protocol
    if not _ANCHORS and _ours():                    # rev 2: "if _ANCHORS is empty and the id carries the name"
        _hk('retire:tested')
        M.set_events(TOOL[0], 0); STATS['toggles_off'] += 1

def reconcile_end():                                # rev 3 (MF2): every reconciliation ends with _unwind_off()
    if REV3[0] and UNWIND_SCOPE[0] == 'section' and 'no_reconcile_off' not in MUT: _unwind_off()

def _commit(o):                                     # rev 3: the first statement of _run's / _run_async's try body
    _hk('commit:0')
    _unwind_on()
    _hk('commit:1')
    _ANCHORS[o.frame] = o
    _hk('commit:2')
    _unwind_on()
    _hk('commit:3')
    o.armed = True                                  # last: the body may start; _detach flags UNWIND_LOST only now

def install_tool():
    t = TOOL[0]
    if M.get_tool(t) is None: M.use_tool_id(t, NAME)
    M.register_callback(t, E.PY_START, _on_entry)
    M.register_callback(t, E.PY_RESUME, _on_entry)
    M.register_callback(t, E.PY_RETURN, _on_exit)
    M.register_callback(t, E.PY_YIELD, _on_exit)
    M.register_callback(t, E.PY_UNWIND, _on_unwind)

class Tracer:
    def __init__(self, *fns):
        self.core = Core(); self.fns = fns; self.mints = []
    def __enter__(self):
        cut_refresh(); install_tool()
        reconcile_end()                             # the enter transaction's reconciliation
        for fn in self.fns:
            m = Mint(fn, self.core)
            _MINTED[id(m.code)] = m
            M.set_local_events(TOOL[0], m.code, LOCAL)
            if UNWIND_SCOPE[0] == 'mint': M.set_events(TOOL[0], M.get_events(TOOL[0]) | E.PY_UNWIND)
            fn.__code__ = m.code
            self.core.by_code[id(m.code)] = fn.__name__
            self.mints.append(m)
        return self
    def __exit__(self, *a):
        self.core.by_code = {}
        for o in list(self.core.openings):
            _detach(o)
        if not _cut_ok(): self.core.flags['CUT_MOVED'] = True
        t = TOOL[0]
        if M.get_tool(t) != NAME:
            self.core.lost = True                   # MONITOR_LOST
            if RECLAIM[0] and M.get_tool(t) is None:
                M.use_tool_id(t, NAME)              # unowned: re-take it; nobody is clobbered
                install_tool()
        for m in self.mints:
            if m.fn.__code__ is m.code: m.fn.__code__ = m.original
            if _ours(): M.set_local_events(t, m.code, 0)
            _MINTED.pop(id(m.code), None); m.pend.clear()
        if UNWIND_SCOPE[0] == 'section':
            if self.mints: retire_step6()           # each retired mint runs step 6; one call models them
            reconcile_end()
        elif _ours() and not _MINTED and not _ANCHORS: M.set_events(t, 0)   # rev 1 (mint scope)
        return False
    def _open(self, section, frame):
        loop = _get_running_loop()
        g = frame.f_back
        while g is not None:
            c = g.f_code
            if _CUT.get(id(c)) is c: break
            o = _ANCHORS.get(g)
            if o is not None and o in self.core.openings and o.loop is loop:
                raise RuntimeError('[V5:NESTED_SECTION]')
            g = g.f_back
        o = Opening(section, frame, loop)
        CORE_OF[id(o)] = self.core
        self.core.openings.append(o)
        if REV3[0] and UNWIND_SCOPE[0] == 'section' and 'commit_outside_try' not in MUT: return o   # rev 3: _commit in the try
        _hk('open:appended')
        if UNWIND_SCOPE[0] == 'section': _unwind_on()
        _hk('open:on1')
        _ANCHORS[frame] = o
        _hk('open:committed')
        if UNWIND_SCOPE[0] == 'section': _unwind_on()
        _hk('open:on2')
        o.armed = True
        return o
    def run(self, section, fn, *a, **k):
        return _run(self, section, fn, a, k)
    def run_async(self, section, afn, *a, **k):
        return _run_async(self, section, afn, a, k)
    def result(self):
        r = {}
        for o in self.core.openings:
            for k, v in o.calls.items(): r.setdefault(o.section, {})[k] = r.get(o.section, {}).get(k, 0) + v
        return {'calls': r, 'dispatched': self.core.unc[0], 'unattributed': self.core.unc[1],
                'CUT_MOVED': bool(self.core.flags.get('CUT_MOVED')),
                'MONITOR_LOST': self.core.lost or bool(self.core.flags.get('UNWIND_LOST'))}

CORE_OF = {}
def _detach(o):
    o.fin.setdefault('fin', 1)
    _hk('detach:claimed')
    fr = o.frame
    if fr is not None:
        if REV3[0]:
            if (UNWIND_SCOPE[0] == 'section' and (o.armed or 'no_armed' in MUT) and (_ANCHORS.get(fr) is o or 'no_anchor_test' in MUT)
                    and _ours() and not (M.get_events(TOOL[0]) & E.PY_UNWIND)):
                CORE_OF[id(o)].flags['UNWIND_LOST'] = True
        elif UNWIND_SCOPE[0] == 'section' and _ours() and not (M.get_events(TOOL[0]) & E.PY_UNWIND):
            CORE_OF[id(o)].flags['UNWIND_LOST'] = True
        _hk('detach:checked')
        _ANCHORS.pop(fr, None)
        _hk('detach:popped')
    o.frame = None
    if UNWIND_SCOPE[0] == 'section': _unwind_off()

def _run(tr, section, fn, args, kwargs):
    o = tr._open(section, sys._getframe())
    if REV3[0] and UNWIND_SCOPE[0] == 'section' and 'commit_outside_try' not in MUT:
        try:
            _commit(o)
            return fn(*args, **kwargs)
        finally:
            _detach(o)
    try:
        return fn(*args, **kwargs)
    finally:
        _detach(o)

async def _run_async(tr, section, afn, args, kwargs):
    o = tr._open(section, sys._getframe())
    if REV3[0] and UNWIND_SCOPE[0] == 'section' and 'commit_outside_try' not in MUT:
        try:
            _commit(o)
            return await afn(*args, **kwargs)
        finally:
            _detach(o)
    try:
        return await afn(*args, **kwargs)
    finally:
        _detach(o)

def state():
    t = TOOL[0]
    return {'tool_name': M.get_tool(t), 'global_events': M.get_events(t), 'anchors': len(_ANCHORS), 'mints': len(_MINTED)}

def events_set():
    return bool(M.get_tool(TOOL[0]) is not None and M.get_events(TOOL[0]) & E.PY_UNWIND)
