# Revision 6, #130279 check: the revision-6 step functions as M7 writes them have no backward jump.
import sys, dis, itertools, operator, collections
_map, _chain, _compress, _filter, _repeat, _list = map, itertools.chain, itertools.compress, filter, itertools.repeat, list
_is, _not, _and, _setitem = operator.is_, operator.not_, operator.and_, operator.setitem
_CONSUME = collections.deque(maxlen=0).extend
_TOOL = [4]; _MON = [None]; _ANCHORS = {}; _TOOL_NAME = 'n'; _NAME1 = (_TOOL_NAME,); _NONE1 = (None,)
_EVENTS5 = (1, 2, 4, 8, 4096); _CALLBACKS5 = (None,) * 5
def _register(t):
    get_tool, register_callback = _MON[0][0], _MON[0][4]
    return _list(_chain(
        _map(register_callback,
             _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
             _EVENTS5, _CALLBACKS5),
        _map(get_tool, (t,))))
def _take(t):
    get_tool, use_tool_id = _MON[0][0], _MON[0][5]
    _CONSUME(_map(use_tool_id, _compress((t,), _map(_is, _map(get_tool, (t,)), _NONE1)), _NAME1))
def _set_local(t, code, events):
    get_tool, set_local_events = _MON[0][0], _MON[0][3]
    _CONSUME(_map(set_local_events, _compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)), (code,), (events,)))
def _unwind_off(key): pass
def _reconcile_tail():
    if _TOOL[0] is not None: _unwind_off(None)
for f in (_register, _take, _set_local, _reconcile_tail):
    back = [i.opname for i in dis.get_instructions(f) if 'BACKWARD' in i.opname]
    print(sys.version.split()[0], f.__name__, 'backward jumps:', back)
