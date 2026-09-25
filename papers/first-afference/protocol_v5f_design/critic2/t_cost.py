# Per-hit cost of the revision-1 additions (_cut_ok() and one _get_running_loop()), against the whole
# modelled event path, at stack depths 5 and 60, in plain code and inside an asyncio task.
import sys, time, asyncio, timeit
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech
def f(): return 1
N = 200_000
def deep(n, fn):
    if n == 0: return fn()
    return deep(n - 1, fn)
def body():
    for _ in range(N): f()
def per_call(depth):
    t0 = time.perf_counter(); deep(depth, body); return (time.perf_counter() - t0) / N * 1e9
def measure(label, depth):
    base = per_call(depth)
    res = {}
    for name, cut, loop in (('full', True, True), ('no_cut_ok', False, True), ('no_loop', True, False), ('neither', False, False)):
        mech.CHECK_CUT_OK[0], mech.CHECK_LOOP[0] = cut, loop
        with mech.Tracer(f) as tr:
            res[name] = min(tr.run('A', per_call, depth) for _ in range(3))
    mech.CHECK_CUT_OK[0] = mech.CHECK_LOOP[0] = True
    print(f"{sys.version.split()[0]} {label} depth={depth}: untraced {base:.0f} ns/call; traced full {res['full']:.0f}, "
          f"no _cut_ok {res['no_cut_ok']:.0f}, no loop read {res['no_loop']:.0f}, neither {res['neither']:.0f} ns/call; "
          f"rev1 additions = {res['full']-res['neither']:.0f} ns/hit ({(res['full']-res['neither'])/res['full']*100:.1f}% of the traced cost)")
for d in (5, 60):
    measure('sync', d)
print('isolated: _cut_ok() %.0f ns, _get_running_loop() %.0f ns' % (
    min(timeit.repeat(mech._cut_ok, number=1_000_000, repeat=5)) * 1e3,
    min(timeit.repeat(mech._get_running_loop, number=1_000_000, repeat=5)) * 1e3))
