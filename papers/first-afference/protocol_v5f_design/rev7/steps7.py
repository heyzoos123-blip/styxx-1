# Revision 7: M7's five step functions, copied from the revision-7 text of M7 (and the M1 block they read), with the
# M1 state they need. This is the "reference" G_ATOM (atom7.py) runs against; mutated copies of THIS FILE are its
# hookup controls. _v5_faultpoints() returns the step functions' code objects, as M10 does. The G_ATOM interface
# (M10, revision 7) is the names this module exposes to the harness: _ANCHORS, _TOOL, _TOOL_NAME, _CONSUME, _list,
# _Opening, _Core, _EVENTS5, _CALLBACKS5, _LOCAL, _LOST, _v5_faultpoints. public_enter_exit() stands for "one enter and exit
# through the public API", which binds _MON, takes the id under _TOOL_NAME and registers _CALLBACKS5.
import os, sys, itertools, operator, collections
M = sys.monitoring
E = M.events
PY_START, PY_RESUME, PY_RETURN, PY_YIELD, PY_UNWIND = E.PY_START, E.PY_RESUME, E.PY_RETURN, E.PY_YIELD, E.PY_UNWIND
_ANCHORS = {}
_TOOL = [None]
_LOST = []                                            # revision 7: a list used as a counter, len(_LOST)
_TOOL_NAME = "styxx.protocol/" + os.urandom(6).hex()
_LOCAL = PY_START | PY_RESUME | PY_RETURN | PY_YIELD
_map, _chain, _compress, _filter = map, itertools.chain, itertools.compress, filter
_is, _not, _and, _setitem = operator.is_, operator.not_, operator.and_, operator.setitem
_ARMED = operator.attrgetter('armed');  _FLAGS = operator.attrgetter('core.flags');  _VALUES = dict.values
_CONSUME = collections.deque(maxlen=0).extend
_LOST_KEY, _TRUE = itertools.repeat('UNWIND_LOST'), itertools.repeat(True)
_PYU1, _ZERO1, _NONE1, _NAME1 = (PY_UNWIND,), (0,), (None,), (_TOOL_NAME,)
_repeat, _list = itertools.repeat, list
_is_not, _LOST_APPEND = operator.is_not, _LOST.append   # revision 7 (B1)
_EVENTS5 = (PY_START, PY_RESUME, PY_RETURN, PY_YIELD, PY_UNWIND)
def _on_entry(code, offset): return None           # data for the steps: never called by them
def _on_exit(code, offset, value): return None
def _on_unwind(code, offset, exc): return None
_CALLBACKS5 = (_on_entry, _on_entry, _on_exit, _on_exit, _on_unwind)
_MON = [None]

class _Opening:
    __slots__ = ('core', 'section', 'frame', 'tid', 'loop', 'calls', 'ambiguous', 'fin', 'lazy', 'armed')
    def __init__(self, core, section, frame, tid, loop):
        self.core, self.section, self.frame, self.tid, self.loop = core, section, frame, tid, loop
        self.calls, self.ambiguous, self.fin, self.lazy, self.armed = {}, {}, {}, None, False

class _Core:
    __slots__ = ('exp', 'marks', 'by_code', 'names', 'sections', 'openings', 'problems', 'clone_called', 'uncredited',
                 'lost_note', 'flags', 'facade', 'pid', 'prov', 'lost0')
    def __init__(self, exp):
        self.exp, self.marks, self.by_code, self.names, self.sections = exp, {}, {}, {}, ()
        self.openings, self.problems, self.clone_called, self.uncredited = [], [], {}, {}
        self.lost_note, self.flags, self.facade, self.pid, self.prov, self.lost0 = None, {}, None, os.getpid(), None, 0

def _unwind_on(o):
    t, get_tool, get_events, set_events = _TOOL[0], _MON[0][0], _MON[0][1], _MON[0][2]
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
    t, get_tool, set_events = _TOOL[0], _MON[0][0], _MON[0][2]
    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),
                    _map(set_events, _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                                               _map(_not, (_ANCHORS,))), _ZERO1)))

def _take(t):
    get_tool, use_tool_id = _MON[0][0], _MON[0][5]
    _CONSUME(_map(use_tool_id, _compress((t,), _map(_is, _map(get_tool, (t,)), _NONE1)), _NAME1))

def _register(t):
    get_tool, register_callback = _MON[0][0], _MON[0][4]
    return _list(_chain(
        _map(_LOST_APPEND, _filter(None, _map(_is_not,
            _map(register_callback,
                 _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
                 _EVENTS5, _CALLBACKS5),
            _CALLBACKS5))),
        _map(get_tool, (t,))))

def _set_local(t, code, events):
    get_tool, set_local_events = _MON[0][0], _MON[0][3]
    _CONSUME(_map(set_local_events, _compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)), (code,), (events,)))

def _v5_faultpoints():
    return {'_unwind_on': _unwind_on.__code__, '_unwind_off': _unwind_off.__code__, '_take': _take.__code__,
            '_register': _register.__code__, '_set_local': _set_local.__code__}

def public_enter_exit():
    """Stands for one `with coverage_trace(EXP): pass` on a fresh id: binds _MON, takes id 4, registers callbacks."""
    if _MON[0] is None:
        _MON[0] = (M.get_tool, M.get_events, M.set_events, M.set_local_events, M.register_callback, M.use_tool_id)
    for t in (4, 3):
        if M.get_tool(t) is None or M.get_tool(t) is _TOOL_NAME:
            if M.get_tool(t) is None: M.use_tool_id(t, _TOOL_NAME)
            for e, f in zip(_EVENTS5, _CALLBACKS5): M.register_callback(t, e, f)
            M.set_events(t, 0); _TOOL[0] = t
            return t
    raise RuntimeError('MONITOR_BUSY')
