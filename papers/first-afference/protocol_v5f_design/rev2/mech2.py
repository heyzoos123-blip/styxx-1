# Revision-2 model of v5f's event path. Starts from critic2/mech.py (written from the rev-1 spec text) and adds
# the rev-2 changes behind switches, so each probe can compare rev 1 with rev 2:
#   CUT_RUN_ONCE  - BaseEventLoop._run_once's code is a cut code too, and _cut_ok() checks both bindings (M1)
#   SHARE_CHECK   - E2 refuses CUT_UNAVAILABLE for a binding whose code is shared or can be shared (M2)
#   UNWIND_SCOPE  - 'mint' (rev 1: global PY_UNWIND while any mint exists) or 'section' (rev 2: only while an
#                   anchor is registered, set before the anchor commit, cleared after the last anchor pops) (M4)
#   RECLAIM       - exit re-takes a freed, unowned tool id and clears its events (M3)
#   CUT_MODE      - 'monotone' (spec) or 'replaced' (the N4 mutant: E2 resets the cut to the current codes)
# No try/finally or with-exit guards any machinery state here except _run's single try/finally around fn.
import sys, types, gc, asyncio, asyncio.events as ev, asyncio.base_events as be
M = sys.monitoring
E = M.events
TOOL = [4]
NAME = 'styxx.protocol/model-rev2'
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
STATS = {'toggles_on': 0, 'toggles_off': 0}

class CutUnavailable(Exception): pass

class Opening:
    __slots__ = ('section', 'frame', 'loop', 'calls', 'ambiguous', 'fin')
    def __init__(self, section, frame, loop):
        self.section, self.frame, self.loop = section, frame, loop
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
    return M.get_tool(TOOL[0]) == NAME

def _unwind_on():                                   # _open, before the anchor commit, and again after it
    if _ours() and not (M.get_events(TOOL[0]) & E.PY_UNWIND):
        M.set_events(TOOL[0], E.PY_UNWIND); STATS['toggles_on'] += 1

def _unwind_off():                                  # after an anchor pop: clear, then re-check and re-set
    if _ANCHORS or not _ours() or not (M.get_events(TOOL[0]) & E.PY_UNWIND): return
    M.set_events(TOOL[0], 0); STATS['toggles_off'] += 1
    if _ANCHORS: M.set_events(TOOL[0], E.PY_UNWIND); STATS['toggles_on'] += 1

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
        if _ours() and not _MINTED and not _ANCHORS: M.set_events(t, 0)
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
        if UNWIND_SCOPE[0] == 'section': _unwind_on()
        _ANCHORS[frame] = o
        if UNWIND_SCOPE[0] == 'section': _unwind_on()
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
    fr = o.frame
    if fr is not None:
        if UNWIND_SCOPE[0] == 'section' and _ours() and not (M.get_events(TOOL[0]) & E.PY_UNWIND):
            CORE_OF[id(o)].flags['UNWIND_LOST'] = True
        _ANCHORS.pop(fr, None)
    o.frame = None
    if UNWIND_SCOPE[0] == 'section': _unwind_off()

def _run(tr, section, fn, args, kwargs):
    o = tr._open(section, sys._getframe())
    try:
        return fn(*args, **kwargs)
    finally:
        _detach(o)

async def _run_async(tr, section, afn, args, kwargs):
    o = tr._open(section, sys._getframe())
    try:
        return await afn(*args, **kwargs)
    finally:
        _detach(o)

def state():
    t = TOOL[0]
    return {'tool_name': M.get_tool(t), 'global_events': M.get_events(t), 'anchors': len(_ANCHORS), 'mints': len(_MINTED)}
