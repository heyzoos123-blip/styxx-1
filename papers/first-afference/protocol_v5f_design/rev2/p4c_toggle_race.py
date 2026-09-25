# M4: rev 2's set/clear protocol under concurrency. Two or four threads open and close sections as fast as they can;
# in each section the declared target raises inside its body (V54's shape), so its call is confirmed only by
# PY_UNWIND. Every call must be counted: a section's own anchor is registered while its target unwinds.
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech2 as mech
sys.setswitchinterval(1e-6)                          # force frequent thread switches
def t(): raise KeyError
def body():
    try: t()
    except KeyError: pass
mech.UNWIND_SCOPE[0] = 'section'
for nthreads in ((int(sys.argv[1]),) if len(sys.argv) > 1 else (2, 4)):
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 50_000
    with mech.Tracer(t) as tr:
        def worker():
            for _ in range(N): tr.run('A', body)
        ths = [threading.Thread(target=worker) for _ in range(nthreads)]
        for x in ths: x.start()
        for x in ths: x.join()
    got = tr.result()['calls'].get('A', {}).get('t', 0)
    print(sys.version.split()[0], '%d threads x %d sections: counted %d of %d raising calls; false MONITOR_LOST %s; toggles on/off %d/%d' % (
        nthreads, N, got, nthreads * N, tr.result()['MONITOR_LOST'], mech.STATS['toggles_on'], mech.STATS['toggles_off']))
    mech.STATS['toggles_on'] = mech.STATS['toggles_off'] = 0
