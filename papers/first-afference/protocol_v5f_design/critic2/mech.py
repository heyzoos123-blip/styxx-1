# Minimal model of v5f's M6 event path, written from the spec text (Attribution, M1, M6, M7):
# minted code with local PY_START|PY_RESUME|PY_RETURN|PY_YIELD, global PY_UNWIND, pending entries
# holding frames, the monotone identity cut, the per-hit _cut_ok() check and the loop boundary.
# Single tracer; enough to attack the two revision-1 mechanisms.
import sys, types, asyncio, asyncio.events as ev
M = sys.monitoring
E = M.events
TOOL = 4
_get_running_loop = ev._get_running_loop
_TYPE_DICT = type.__dict__['__dict__']
_HANDLE_DICT = [_TYPE_DICT.__get__(ev.Handle)]
_CUT = {}
_ANCHORS = {}
_MINTED = {}

class Opening:
    __slots__ = ('section', 'frame', 'loop', 'calls', 'ambiguous', 'fin')
    def __init__(self, section, frame, loop):
        self.section, self.frame, self.loop = section, frame, loop
        self.calls, self.ambiguous, self.fin = {}, {}, {}

class Core:
    def __init__(self):
        self.by_code, self.openings, self.flags = {}, [], {}
        self.unc = [{}, {}]

class Mint:
    def __init__(self, fn, core):
        self.fn, self.original = fn, fn.__code__
        self.code = fn.__code__.replace()
        self.globals = fn.__globals__
        self.holders = (core,)
        self.pend = {}

CHECK_CUT_OK = [True]      # toggles for cost measurement
CHECK_LOOP = [True]

def cut_refresh():
    h = _HANDLE_DICT[0].get('_run')
    if type(h) is not types.FunctionType: raise RuntimeError('CUT_UNAVAILABLE')
    _CUT.setdefault(id(h.__code__), h.__code__)

def _cut_ok():
    h = _HANDLE_DICT[0].get('_run')
    return type(h) is types.FunctionType and _CUT.get(id(h.__code__)) is h.__code__

def _outcome(f, code, holders):
    loop = _get_running_loop() if CHECK_LOOP[0] else None
    found = []
    stop = 'u'
    g = f.f_back
    while g is not None:
        c = g.f_code
        if _CUT.get(id(c)) is c: stop = 'd'; break
        o = _ANCHORS.get(g)
        if o is not None:
            if CHECK_LOOP[0] and o.loop is not loop: stop = 'd'; break
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
    if CHECK_CUT_OK[0] and not _cut_ok():
        for h in holders: h.flags['CUT_MOVED'] = True
    if f.f_globals is not m.globals: return
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

def install_tool():
    if M.get_tool(TOOL) is None: M.use_tool_id(TOOL, 'critic2-mech')
    M.register_callback(TOOL, E.PY_START, _on_entry)
    M.register_callback(TOOL, E.PY_RESUME, _on_entry)
    M.register_callback(TOOL, E.PY_RETURN, _on_exit)
    M.register_callback(TOOL, E.PY_YIELD, _on_exit)
    M.register_callback(TOOL, E.PY_UNWIND, _on_unwind)

class Tracer:
    def __init__(self, *fns):
        self.core = Core(); self.fns = fns; self.mints = []
    def __enter__(self):
        install_tool(); cut_refresh()
        for fn in self.fns:
            m = Mint(fn, self.core)
            _MINTED[id(m.code)] = m
            M.set_local_events(TOOL, m.code, LOCAL)
            M.set_events(TOOL, M.get_events(TOOL) | E.PY_UNWIND)
            fn.__code__ = m.code
            self.core.by_code[id(m.code)] = fn.__name__
            self.mints.append(m)
        return self
    def __exit__(self, *a):
        self.core.by_code = {}
        for o in list(self.core.openings):
            if o.frame is not None: _ANCHORS.pop(o.frame, None); o.frame = None
        if not _cut_ok(): self.core.flags['CUT_MOVED'] = True
        for m in self.mints:
            if m.fn.__code__ is m.code: m.fn.__code__ = m.original
            M.set_local_events(TOOL, m.code, 0)
            _MINTED.pop(id(m.code), None); m.pend.clear()
        if not _MINTED: M.set_events(TOOL, 0)
        return False
    def _open(self, section, frame):
        loop = _get_running_loop()
        # NESTED walk: same core's opening on the anchor's chain before the cut, same loop
        g = frame.f_back
        while g is not None:
            c = g.f_code
            if _CUT.get(id(c)) is c: break
            o = _ANCHORS.get(g)
            if o is not None and o in self.core.openings and o.loop is loop:
                raise RuntimeError('[V5:NESTED_SECTION]')
            g = g.f_back
        o = Opening(section, frame, loop)
        self.core.openings.append(o); _ANCHORS[frame] = o
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
                'CUT_MOVED': bool(self.core.flags.get('CUT_MOVED'))}

def _run(tr, section, fn, args, kwargs):
    o = tr._open(section, sys._getframe())
    try:
        return fn(*args, **kwargs)
    finally:
        o.fin.setdefault('fin', 1); _ANCHORS.pop(o.frame, None); o.frame = None

async def _run_async(tr, section, afn, args, kwargs):
    o = tr._open(section, sys._getframe())
    try:
        return await afn(*args, **kwargs)
    finally:
        o.fin.setdefault('fin', 1); _ANCHORS.pop(o.frame, None); o.frame = None
