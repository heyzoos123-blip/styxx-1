# Revision 8 (the eighth critic's N3): critic8/c4 frozen as G_ATOM part R, run on rev8/steps8.py, with _take and
# _set_local added. Otherwise c4 unchanged.
# critic8/c4: A14 ("RecursionError cannot land after a step's first write") is probe-only. Can a frozen, deterministic
# check be written cheaply? Sweep the C recursion depth at which _unwind_off (key registered, last anchor, event set,
# id named) and _unwind_on (own anchor registered, event clear, one armed other opening) are called, from far below
# the limit up past it, and classify each trial: 'none' (RecursionError before any effect), 'all' (full effect) or
# 'PARTIAL' (some effect, then RecursionError). Uses rev7/steps7.py (M7's steps as written).
import sys, types, operator
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import steps8 as S
M = sys.monitoring; PYU = M.events.PY_UNWIND
S.public_enter_exit(); t = S._TOOL[0]
F = {k: types.FunctionType(c, vars(S)) for k, c in S._v5_faultpoints().items()}
def rec(n, fn):
    if n == 0: return fn()
    return next(map(rec, (n - 1,), (fn,)))       # one C-level call (next) per level
def core():
    c = S._Core.__new__(S._Core); c.flags = {}; return c
def opening(c, armed):
    o = S._Opening.__new__(S._Opening); o.core = c; o.frame = object(); o.armed = armed; return o
def trial_off(n):
    S._ANCHORS.clear(); o = opening(core(), True); S._ANCHORS[o.frame] = o; M.set_events(t, PYU)
    try: rec(n, lambda: F['_unwind_off'](o.frame)); err = None
    except RecursionError: err = 'RecursionError'
    popped = o.frame not in S._ANCHORS; cleared = M.get_events(t) == 0
    return err, ('all' if popped and cleared else 'none' if not popped and not cleared else 'PARTIAL')
def trial_on(n):
    S._ANCHORS.clear(); c0 = core(); o = opening(c0, False); S._ANCHORS[o.frame] = o
    c1 = core(); p = opening(c1, True); S._ANCHORS[p.frame] = p; M.set_events(t, 0)
    try: rec(n, lambda: F['_unwind_on'](o)); err = None
    except RecursionError: err = 'RecursionError'
    flagged = bool(c1.flags.get('UNWIND_LOST')); setev = M.get_events(t) == PYU
    return err, ('all' if flagged and setev else 'none' if not flagged and not setev else 'PARTIAL')
def trial_take(n):                                   # revision 8: the id unowned; the effect is the take
    M.set_events(t, 0); M.free_tool_id(t)
    try: rec(n, lambda: F['_take'](t)); err = None
    except RecursionError: err = 'RecursionError'
    took = M.get_tool(t) is S._TOOL_NAME
    if not took: M.use_tool_id(t, S._TOOL_NAME)
    return err, ('all' if took else 'none')
def fx(): return None
def trial_local(n):                                  # revision 8: named; the effect is the local-events write
    M.set_local_events(t, fx.__code__, 0)
    try: rec(n, lambda: F['_set_local'](t, fx.__code__, S._LOCAL)); err = None
    except RecursionError: err = 'RecursionError'
    w = M.get_local_events(t, fx.__code__) == S._LOCAL
    M.set_local_events(t, fx.__code__, 0)
    return err, ('all' if w else 'none')
sys.setrecursionlimit(100000)
res = {}
for name, tr in (('_unwind_off', trial_off), ('_unwind_on', trial_on), ('_take', trial_take), ('_set_local', trial_local)):
    # find the largest n that completes, then sweep n-30 .. n+30
    lo, hi = 0, 20000
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if tr(mid)[0] is None: lo = mid
        else: hi = mid - 1
    counts = {}
    for n in range(lo - 30, lo + 31):
        k = tr(n); counts[k] = counts.get(k, 0) + 1
    res[name] = (lo, counts)
print(sys.version.split()[0], res)
# control (frozen with part R): K7's _unwind_off (the pop as its own statement before the consuming call) must show
# PARTIAL trials (pop done, then RecursionError before the clear)
src = open(S.__file__).read()
k7o = '''    t, get_tool, set_events = _TOOL[0], _MON[0][0], _MON[0][2]
    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),'''
k7n = '''    t, get_tool, set_events = _TOOL[0], _MON[0][0], _MON[0][2]
    _ANCHORS.pop(key, None)
    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),'''
assert src.count(k7o) == 1
ns = dict(vars(S)); exec(compile(src.replace(k7o, k7n), S.__file__, 'exec'), ns)
F_ref = F['_unwind_off']; F['_unwind_off'] = types.FunctionType(ns['_unwind_off'].__code__, vars(S))
lo, hi = 0, 20000
while lo < hi:
    mid = (lo + hi + 1) // 2
    if trial_off(mid)[0] is None: lo = mid
    else: hi = mid - 1
cc = {}
for n in range(lo - 30, lo + 31):
    k = trial_off(n); cc[k] = cc.get(k, 0) + 1
F['_unwind_off'] = F_ref
print(sys.version.split()[0], 'control K7 _unwind_off', (lo, cc), 'DETECTED' if ('RecursionError', 'PARTIAL') in cc else 'NOT DETECTED')
ok = ('RecursionError', 'PARTIAL') in cc and all(set(c) <= {(None, 'all'), ('RecursionError', 'none')} and (None, 'all') in c and ('RecursionError', 'none') in c
         for _, c in res.values())
print(sys.version.split()[0], 'part R (frozen rule: every trial full-effect-no-error or error-no-effect, both seen, per step):', 'PASS' if ok else 'FAIL')
