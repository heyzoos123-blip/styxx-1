# critic8/c4: A14 ("RecursionError cannot land after a step's first write") is probe-only. Can a frozen, deterministic
# check be written cheaply? Sweep the C recursion depth at which _unwind_off (key registered, last anchor, event set,
# id named) and _unwind_on (own anchor registered, event clear, one armed other opening) are called, from far below
# the limit up past it, and classify each trial: 'none' (RecursionError before any effect), 'all' (full effect) or
# 'PARTIAL' (some effect, then RecursionError). Uses rev7/steps7.py (M7's steps as written).
import sys, types, operator
sys.path.insert(0, '/home/user/styxx-1/papers/first-afference/protocol_v5f_design/rev7')
import steps7 as S
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
sys.setrecursionlimit(100000)
res = {}
for name, tr in (('_unwind_off', trial_off), ('_unwind_on', trial_on)):
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
