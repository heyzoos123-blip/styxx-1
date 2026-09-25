# Cost of revision 4's open/close path against revision 3's, in the model: one section calling nothing, single
# thread, best of 5 runs of 100,000 sections. Revision 4 drops the pre-store _unwind_on, adds the re-check after the
# store, the `if _CLEARING` test, and in every close that clears: a token, an announcement and a withdrawal.
import sys, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
def target(): return 1
def noop(): return 0
def bench(n):
    with mech.Tracer(target) as tr:
        t0 = time.perf_counter()
        for _ in range(n): tr.run('A', noop)
        return (time.perf_counter() - t0) / n * 1e6
v = sys.version.split()[0]
res = {}
for rev4 in (False, True, False, True):
    mech.REV4[0] = rev4
    res.setdefault(rev4, []).append(min(bench(100_000) for _ in range(5)))
r3, r4 = min(res[False]), min(res[True])
print(v, 'per section (open, commit, close, clear): rev 3 %.2f us, rev 4 %.2f us (%+.2f us)' % (r3, r4, r4 - r3))
