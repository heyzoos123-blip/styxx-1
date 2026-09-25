# N1: per-hit cost in the rev-2 model (two cut bindings checked per hit, section-scoped PY_UNWIND), against an
# untraced trivial call, at stack depths 5 and 60; the cost of the second binding check; and the global PY_UNWIND
# cost on non-target code inside an open section (rev 2 sets it only there) and outside any section (rev 2: none).
import sys, time, timeit
sys.path.insert(0, '.')
import mech2 as mech
def f(): return 1
N = 200_000
def deep(n, fn):
    if n == 0: return fn()
    return deep(n - 1, fn)
def body():
    for _ in range(N): f()
def per_call(depth):
    t0 = time.perf_counter(); deep(depth, body); return (time.perf_counter() - t0) / N * 1e9
ver = sys.version.split()[0]
for d in (5, 60):
    base = min(per_call(d) for _ in range(3))
    res = {}
    for ro in (False, True):
        mech.CUT_RUN_ONCE[0] = ro
        with mech.Tracer(f) as tr:
            res[ro] = min(tr.run('A', per_call, d) for _ in range(3))
    print(ver, 'depth %2d: untraced %.0f ns/call; traced hit %.0f ns (x%.0f); second binding check adds %.0f ns/hit' % (
        d, base, res[True], res[True] / base, res[True] - res[False]))
def raiser(): raise KeyError('x')
def deepr(n):
    if n == 0: raise KeyError('x')
    return deepr(n - 1)
def one():
    try: raiser()
    except KeyError: pass
def six():
    try: deepr(5)
    except KeyError: pass
for name, fn in (('raise through 1 frame', one), ('raise through 6 frames', six)):
    a = min(timeit.repeat(fn, number=200_000, repeat=5))
    with mech.Tracer(f) as tr:
        b = min(timeit.repeat(fn, number=200_000, repeat=5))
        c = tr.run('A', lambda: min(timeit.repeat(fn, number=200_000, repeat=5)))
    print(ver, '%s: trace active, no section open x%.2f; inside a section x%.2f' % (name, b / a, c / a))
