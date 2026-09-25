# Cost of revision 3's open path against revision 2's, in the model: one section calling nothing, best of 5 runs of
# 100,000 sections, single thread. Revision 3 adds one Python call (_commit) and the o.armed store per section.
import sys, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech3 as mech
def target(): return 1
def noop(): return 0
def bench(n):
    with mech.Tracer(target) as tr:
        t0 = time.perf_counter()
        for _ in range(n): tr.run('A', noop)
        return (time.perf_counter() - t0) / n * 1e6
v = sys.version.split()[0]
res = {}
for rev3 in (False, True, False, True):
    mech.REV3[0] = rev3
    res.setdefault(rev3, []).append(min(bench(100_000) for _ in range(5)))
r2, r3 = min(res[False]), min(res[True])
print(v, 'per section: rev 2 %.2f us, rev 3 %.2f us (%+.2f us)' % (r2, r3, r3 - r2))
