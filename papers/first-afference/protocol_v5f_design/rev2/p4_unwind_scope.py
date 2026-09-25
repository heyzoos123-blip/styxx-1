# M4: L-DELIVERY scope. Counts ValueErrors that reached `raise` in undeclared code and whose `except ValueError`
# then did not run, under a 20 us SIGALRM flood whose handler raises Timeout (critic2/t_delivery2.py's method).
# rev 1: global PY_UNWIND while any mint exists. rev 2: only while some section is open (an anchor is registered).
# Also the cost of rev 2's per-section toggling of the global event set.
import sys, signal, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech2 as mech
class Timeout(Exception): pass
armed = [False]
def on_alarm(*a):
    if armed[0]: raise Timeout
state = [0]
def unrelated():
    state[0] = 1
    raise ValueError
def run(n):
    lost = handled = to = 0
    signal.signal(signal.SIGALRM, on_alarm)
    signal.setitimer(signal.ITIMER_REAL, 0.00002, 0.00002)
    i = 0
    while i < n:
        i += 1
        try:
            state[0] = 0
            armed[0] = True
            try:
                unrelated()
            except ValueError:
                armed[0] = False
                handled += 1
            armed[0] = False
        except Timeout as e:
            armed[0] = False
            to += 1
            if state[0] == 1 and type(e.__context__) is not ValueError: lost += 1
    signal.setitimer(signal.ITIMER_REAL, 0, 0)
    return lost, to
def target(): return 1
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000
ver = sys.version.split()[0]
print(ver, 'untraced                                   : lost %d (timeouts %d)' % run(N))
for scope in ('mint', 'section'):
    mech.UNWIND_SCOPE[0] = scope
    with mech.Tracer(target) as tr:
        a = run(N)
        b = tr.run('A', run, N)
    print(ver, 'scope=%-7s trace active, no section open : lost %d (timeouts %d)' % ((scope,) + a))
    print(ver, 'scope=%-7s inside an open section        : lost %d (timeouts %d)' % ((scope,) + b))

# cost: sections per second, and re-instrumentation of other code after each toggle
def noop(): return 0
FUNCS = []
for i in range(100):
    exec('def h%d(): return %d' % (i, i)); FUNCS.append(globals()['h%d' % i])
def many():
    for h in FUNCS: h()
def bench(fn, n):
    with mech.Tracer(target) as tr:
        t0 = time.perf_counter()
        for _ in range(n): tr.run('A', fn)
        return (time.perf_counter() - t0) / n * 1e6
for fn, label, n in ((noop, 'section calling nothing', 100_000), (many, 'section calling 100 distinct functions', 20_000)):
    res = {}
    for scope in ('mint', 'section'):
        mech.UNWIND_SCOPE[0] = scope; mech.STATS['toggles_on'] = mech.STATS['toggles_off'] = 0
        res[scope] = min(bench(fn, n) for _ in range(3))
    print(ver, '%-40s rev1 %.2f us/section, rev2 %.2f us/section (+%.2f us; toggles per section on/off %.0f/%.0f)' % (
        label, res['mint'], res['section'], res['section'] - res['mint'], mech.STATS['toggles_on'] / (3 * n), mech.STATS['toggles_off'] / (3 * n)))
t0 = time.perf_counter(); many(); base = (time.perf_counter() - t0) * 1e6
print(ver, '(untraced call of many(): %.2f us)' % base)
