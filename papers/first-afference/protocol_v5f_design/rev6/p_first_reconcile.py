# Revision 6, F20: revision 5's reconciliation ends with _unwind_off(None) unconditionally. At the process's first
# reconciliation (the first enter's E4 step 1) _TOOL[0] is still None, and the pipeline's get_tool(None) raises
# TypeError. This runs revision 5's _unwind_off pipeline, as M7 writes it, with t = None.
import sys, itertools, operator, collections
M = sys.monitoring
_map, _chain, _compress, _is, _not = map, itertools.chain, itertools.compress, operator.is_, operator.not_
_CONSUME = collections.deque(maxlen=0).extend
_ANCHORS = {}; _NAME1 = ('styxx.protocol/x',); _NONE1, _ZERO1 = (None,), (0,)
def _unwind_off(key, t):
    get_tool, set_events = M.get_tool, M.set_events
    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),
                    _map(set_events, _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                                               _map(_not, (_ANCHORS,))), _ZERO1)))
try: _unwind_off(None, None); print(sys.version.split()[0], 'no error')
except Exception as e: print(sys.version.split()[0], 'first reconciliation raises', type(e).__name__, e)
