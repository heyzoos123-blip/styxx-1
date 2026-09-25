# The revision-5 event path exactly as the spec's M7 states it (M1's names, stubs for the rest), so that
#  (1) the pseudocode in the spec is checked to be valid, runnable Python on 3.12 and 3.13;
#  (2) G_HYG's #130279 lint can be run on it: no backward jump in _commit, _unwind_on, _unwind_off or _detach;
#  (3) an injector sweep can fault every instruction of _run's try-body path and of its finally.
import sys, itertools, operator, collections
M = sys.monitoring; E = M.events
PY_UNWIND = E.PY_UNWIND

# ---- M1 (revision 5): the one-call vocabulary, bound once at import (G_HYG) ----
_map, _chain, _compress, _filter = map, itertools.chain, itertools.compress, filter
_is, _not, _and, _setitem = operator.is_, operator.not_, operator.and_, operator.setitem
_ARMED = operator.attrgetter('armed')
_FLAGS = operator.attrgetter('core.flags')
_VALUES = dict.values
_CONSUME = collections.deque(maxlen=0).extend
_LOST_KEY, _TRUE = itertools.repeat('UNWIND_LOST'), itertools.repeat(True)
_PYU1, _ZERO1, _NONE1 = (PY_UNWIND,), (0,), (None,)
_MON = [None]      # (get_tool, get_events, set_events, set_local_events, register_callback, use_tool_id): set by coverage_trace()

_ANCHORS = {}
_TOOL = [None]
_TOOL_NAME = 'styxx.protocol/' + 'ab12cd34ef56'
_NAME1 = (_TOOL_NAME,)

class GateSpecError(Exception): pass
TRACE_INACTIVE_TEXT = '[V5:TRACE_INACTIVE] ...'
OPEN_AT_EXIT_TEXT = '[V5:OPEN_AT_EXIT] ...'
class _Core:
    def __init__(self): self.marks, self.flags, self.problems, self.openings = {'active': True}, {}, [], []
class _Opening:
    __slots__ = ('core', 'section', 'frame', 'fin', 'armed', 'lazy')
    def __init__(self, core, section, frame):
        self.core, self.section, self.frame, self.fin, self.armed, self.lazy = core, section, frame, {}, False, None
def _open(core, section, frame):
    o = _Opening(core, section, frame); core.openings.append(o); return o

# ---------------------------------------------------------------------------------------------- M7 (revision 5)
def _run(core, section, fn, args, kwargs):      # module level: its frame is the anchor, its locals hold no facade
    o = _open(core, section, sys._getframe())   # checks and append only (At open, steps 1-6)
    if o is None: return fn(*args, **kwargs)    # forked child: pass-through
    end = "raised"
    try:
        _commit(o)
        result = fn(*args, **kwargs); end = "returned"
    finally:
        _detach(o, (end, ()))                   # no loop in the try body, and none in any function it calls
        o.frame = None                          # the opening's own finally releases the anchor frame (B1)
    return result

def _commit(o):                                 # At open, steps 7-8
    _ANCHORS[o.frame] = o                       # the store
    if 'fin' in o.fin or 'exiting' in o.core.marks:   # step 8: a detacher claimed o, or exit began
        _detach(o, ("open", (OPEN_AT_EXIT_TEXT,)))
        o.core.problems.append(TRACE_INACTIVE_TEXT)
        raise GateSpecError(TRACE_INACTIVE_TEXT)
    _unwind_on(o)                               # one call: after the store, so no clear can follow while o is registered
    o.armed = True                              # last: the body may run now

def _unwind_on(o):
    # ONE CALL { if get_tool(t) is _TOOL_NAME and _ANCHORS.get(o.frame) is o:
    #                if not get_events(t) & PY_UNWIND:
    #                    for p in _ANCHORS.values(): if p.armed: p.core.flags['UNWIND_LOST'] = True
    #                set_events(t, PY_UNWIND) }
    t = _TOOL[0]; get_tool, get_events, set_events = _MON[0][0], _MON[0][1], _MON[0][2]
    _CONSUME(_chain(
        _map(_setitem, _map(_FLAGS, _filter(_ARMED, _chain.from_iterable(_map(_VALUES,
            _compress(_compress(_compress((_ANCHORS,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                                _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),
                      _map(_not, _map(_and, _map(get_events, (t,)), _PYU1))))))), _LOST_KEY, _TRUE),
        _map(set_events,
             _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                       _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),
             _PYU1)))

def _unwind_off(key):
    # ONE CALL { _ANCHORS.pop(key, None); if get_tool(t) is _TOOL_NAME and not _ANCHORS: set_events(t, 0) }
    t = _TOOL[0]; get_tool, set_events = _MON[0][0], _MON[0][2]
    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),
                    _map(set_events, _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                                               _map(_not, (_ANCHORS,))), _ZERO1)))

def _detach(o, fin):
    o.fin.setdefault("fin", fin)                # one claim: first finaliser wins
    fr = o.frame                                # never assigned here: every detacher pops by the anchor's own key
    if fr is not None:
        if o.armed and not (_MON[0][1](_TOOL[0]) & PY_UNWIND) and _ANCHORS.get(fr) is o:
            o.core.flags['UNWIND_LOST'] = True  # the event first, the anchor last: an outside party cleared it
        _unwind_off(fr)                         # one call: pop, then clear iff no anchor is left

FUNCS = (_run, _commit, _unwind_on, _unwind_off, _detach)

# ---------------------------------------------------------------------------------------------- checks
def lint():
    import dis
    out = {}
    for fn in FUNCS:
        back = [i.opname for i in dis.get_instructions(fn) if 'BACKWARD' in i.opname]
        out[fn.__name__] = back
    return out

class KI(BaseException): pass

def inject_sweep(target):
    """Raise KI at the k-th executed instruction of `target` during run(); after each trial, check that _run's
    finally ran (the opening is claimed) and classify what is left."""
    code = target.__code__
    results = collections.Counter(); k = 1
    while True:
        _ANCHORS.clear(); M.set_events(_TOOL[0], 0)
        core = _Core(); st = {'n': 0, 'fired': False}
        def cb(c, off):
            st['n'] += 1
            if st['n'] == k and not st['fired']:
                st['fired'] = True; raise KI
        M.use_tool_id(5, 'inj'); M.register_callback(5, E.INSTRUCTION, cb); M.set_local_events(5, code, E.INSTRUCTION)
        err = None
        try: _run(core, 'A', lambda: 1, (), {})
        except KI: err = 'KI'
        finally:
            M.set_local_events(5, code, 0); M.register_callback(5, E.INSTRUCTION, None); M.free_tool_id(5)
        if not st['fired']: break
        o = core.openings[0] if core.openings else None
        claimed = o is not None and 'fin' in o.fin
        left = (len(_ANCHORS), bool(M.get_events(_TOOL[0]) & PY_UNWIND))
        results[(err, 'finally ran' if claimed else 'NOT CLAIMED', 'anchors=%d event=%d' % left)] += 1
        k += 1
    return k - 1, dict(results)

if __name__ == '__main__':
    v = sys.version.split()[0]
    _MON[0] = (M.get_tool, M.get_events, M.set_events, M.set_local_events, M.register_callback, M.use_tool_id)
    _TOOL[0] = 4; M.use_tool_id(4, _TOOL_NAME); M.register_callback(4, PY_UNWIND, lambda *a: None)
    print(v, 'backward jumps:', lint())
    # a plain section: the event is set in the body and clear after
    seen = {}
    core = _Core()
    print(v, 'plain run:', _run(core, 'A', lambda: seen.setdefault('S', bool(M.get_events(4) & PY_UNWIND)) and 7, (), {}),
          'S in body', seen['S'], 'after', bool(M.get_events(4) & PY_UNWIND), 'anchors', len(_ANCHORS), 'flags', core.flags)
    for tgt in (_run, _commit, _unwind_on, _unwind_off, _detach):
        n, res = inject_sweep(tgt)
        print(v, 'inject %-12s %3d trials:' % (tgt.__name__, n), res)

# ---- the other one-call steps of M7 (revision 5), checked here too ----
_repeat = itertools.repeat
def _on_entry(*a): pass
def _on_exit(*a): pass
def _on_unwind(*a): pass
_EVENTS5 = (E.PY_START, E.PY_RESUME, E.PY_RETURN, E.PY_YIELD, E.PY_UNWIND)
_CALLBACKS5 = (_on_entry, _on_entry, _on_exit, _on_exit, _on_unwind)

def _named(i): return _MON[0][0](i) is _TOOL_NAME      # identity: no __eq__ of any kind runs

def _take(t):
    # ONE CALL { if get_tool(t) is None: use_tool_id(t, _TOOL_NAME) }; afterwards the caller tests _named(t)
    _CONSUME(_map(_MON[0][5], _compress((t,), _map(_is, _map(_MON[0][0], (t,)), _NONE1)), _NAME1))

def _register(t):
    # ONE CALL { if get_tool(t) is _TOOL_NAME: register our five callbacks }; returns the previous callbacks ([] if not)
    return list(_map(_MON[0][4], _chain.from_iterable(_map(_repeat, _compress((t,), _map(_is, _map(_MON[0][0], (t,)), _NAME1)), (5,))),
                     _EVENTS5, _CALLBACKS5))

def _set_local(t, code, events):
    # ONE CALL { if get_tool(t) is _TOOL_NAME: set_local_events(t, code, events) }
    _CONSUME(_map(_MON[0][3], _compress((t,), _map(_is, _map(_MON[0][0], (t,)), _NAME1)), (code,), (events,)))

if __name__ == '__main__':
    import dis
    print(v, 'backward jumps (other steps):', {fn.__name__: [i.opname for i in dis.get_instructions(fn) if 'BACKWARD' in i.opname]
                                               for fn in (_named, _take, _register, _set_local)})
    M.set_events(4, 0)
    for e in _EVENTS5: M.register_callback(4, e, None)
    M.free_tool_id(4)
    _take(4); a = _named(4)
    prev = _register(4); prev2 = _register(4)
    code = (lambda: 0).__code__; _set_local(4, code, E.PY_START); le = M.get_local_events(4, code); _set_local(4, code, 0)
    M.free_tool_id(4); M.use_tool_id(4, 'other')
    _take(4); b = _named(4); prev3 = _register(4); _set_local(4, code, E.PY_START); le2 = M.get_local_events(4, code)
    print(v, 'take->named', a, 'register prev', [p is None for p in prev], 'again', [p is q for p, q in zip(prev2, _CALLBACKS5)],
          'local', le == E.PY_START, '| taken by another: named', b, 'register', prev3, 'local untouched', le2 == 0)
    M.free_tool_id(4)
