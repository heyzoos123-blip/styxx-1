# N8: importlib.reload of a module shaped like styxx.protocol's state (per-copy random tool name, registries at
# module level). Rev 1 rebinds every name: a mint held across the reload is lost, and each reload consumes a tool id
# under a dead name. Rev 2 binds the M1 state with setdefault semantics, so a reload keeps it.
import sys, os, importlib, tempfile, textwrap
d = tempfile.mkdtemp(); sys.path.insert(0, d)
SRC = {
 'rev1': '''
import os, sys
M = sys.monitoring
_TOOL_NAME = "p/" + os.urandom(6).hex()
_MINTED = {}
_TOOL = [None]
''',
 'rev2': '''
import os, sys
M = sys.monitoring
_g = globals()
_TOOL_NAME = _g.get("_TOOL_NAME") or "p/" + os.urandom(6).hex()
_MINTED = _g.get("_MINTED", {})
_TOOL = _g.get("_TOOL", [None])
''' }
COMMON = '''
def ensure_tool():
    t = _TOOL[0]
    if t is not None and M.get_tool(t) == _TOOL_NAME: return t
    for i in (4, 3):
        if M.get_tool(i) == _TOOL_NAME or M.get_tool(i) is None:
            if M.get_tool(i) is None: M.use_tool_id(i, _TOOL_NAME)
            _TOOL[0] = i; return i
    raise RuntimeError("MONITOR_BUSY")
'''
for which in ('rev1', 'rev2'):
    name = 'protomodel_' + which
    open(os.path.join(d, name + '.py'), 'w').write(SRC[which] + COMMON)
    mod = importlib.import_module(name)
    mod.ensure_tool(); mod._MINTED['held-across-reload'] = 1
    out = []
    for k in range(3):
        importlib.reload(mod)
        try: t = mod.ensure_tool(); out.append('reload %d: tool %d, held mint kept %s' % (k + 1, t, 'held-across-reload' in mod._MINTED))
        except RuntimeError as e: out.append('reload %d: %s, held mint kept %s' % (k + 1, e, 'held-across-reload' in mod._MINTED))
    print(sys.version.split()[0], which, '; '.join(out))
    for i in (3, 4):
        if sys.monitoring.get_tool(i) is not None: sys.monitoring.free_tool_id(i)
