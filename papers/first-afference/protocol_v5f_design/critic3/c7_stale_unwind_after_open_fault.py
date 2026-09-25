# OPEN prefix "killed after the first set and before the commit": PY_UNWIND is on with no anchor "until the next
# close or reconciliation clears it". But reconciliation clears it only inside _retire (M3 step 6), i.e. only when
# some mint loses its last holder. While the tracer stays active (the normal case: a KeyboardInterrupt/Timeout that
# landed in _open is caught by the harness, which carries on), the global callback stays on outside every section,
# I3 is false after a reconciliation, and H10 cell (a) (gated at 0 lost handlers outside sections) is no longer 0.
import sys, signal
sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/rev2')
import mech2 as mech
exec(open(__file__.rsplit('/', 2)[0] + '/rev2/p4_unwind_scope.py').read().split("def target()")[0].split("import mech2 as mech")[1])
M = sys.monitoring; E = M.events
def target(): return 1
class Injected(BaseException): pass
N = 300_000
v = sys.version.split()[0]
with mech.Tracer(target) as tr:
    a = run(N)
    orig = mech._unwind_on; calls = [0]
    def faulty():
        calls[0] += 1; orig()
        if calls[0] == 1: raise Injected          # lands after the first set, before the anchor commit
    mech._unwind_on = faulty
    try: tr.run('A', target)
    except Injected: pass
    mech._unwind_on = orig
    st = mech.state()
    b = run(N)
print(v, 'trace active, no section, fault-free        : lost %d (timeouts %d)' % a)
print(v, 'after a fault in _open before the commit    : anchors=%d global_events=%d' % (st['anchors'], st['global_events']))
print(v, 'trace active, no section, after that fault  : lost %d (timeouts %d)' % b)
