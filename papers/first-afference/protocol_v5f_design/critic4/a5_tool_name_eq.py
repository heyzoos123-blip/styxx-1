# _ours() / _ensure_tool compare `get_tool(id) == _TOOL_NAME`. get_tool returns the object another tool passed to
# use_tool_id. If that is a str subclass, its __eq__ runs (reflected-operand rule does not apply: it is the LEFT operand).
import sys
M = sys.monitoring
class N(str):
    def __eq__(self, other): return True
    __hash__ = str.__hash__
try:
    M.use_tool_id(3, N('other-tool'))
    g = M.get_tool(3)
    print(sys.version.split()[0], 'use_tool_id accepted a str subclass:', type(g).__name__, '| get_tool(3) == "styxx.protocol/abc" ->', g == 'styxx.protocol/abc')
    M.free_tool_id(3)
except Exception as e:
    print(sys.version.split()[0], 'refused:', repr(e))
