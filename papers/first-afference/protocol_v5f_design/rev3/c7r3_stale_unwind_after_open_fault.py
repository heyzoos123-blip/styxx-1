# MF2 (critic3/c7_stale_unwind_after_open_fault.py, extended to every fault point of the open path). A trace is
# active and stays active. One fault is injected at one statement boundary of the open path (rev 2: _open after the
# append; rev 3: _commit, now the first statement of _run's try body, plus _unwind_on's point between its read and
# its set). The harness catches it and carries on with no section open. Then p4_unwind_scope's 20 us SIGALRM flood
# (the critic's method) counts `except ValueError` handlers lost in undeclared code. The critic's c7 point is
# "after the first _unwind_on() returned, before the commit": rev 2 open:on1, rev 3 commit:1.
import sys, signal, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech3 as mech
exec(open(__file__.rsplit('/', 1)[0] + '/p4_unwind_scope.py').read().split("def target()")[0].split("import mech2 as mech")[1])
def target(): return 1
class Injected(BaseException): pass
N = int(sys.argv[1]) if len(sys.argv) > 1 else 300_000
v = sys.version.split()[0]
POINTS = {False: ('open:appended', 'on:read', 'open:on1', 'open:committed', 'open:on2'),
          True: ('commit:0', 'on:read', 'commit:1', 'commit:2', 'commit:3')}
with mech.Tracer(target) as tr:
    base = run(N)
print(v, 'trace active, no section, fault-free: lost %d (timeouts %d)' % base)
for rev3 in (False, True):
    mech.REV3[0] = rev3
    for pt in POINTS[rev3]:
        fired = [0]
        def hook(p, pt=pt):
            if p == pt and not fired[0]: fired[0] = 1; raise Injected
        with mech.Tracer(target) as tr:
            mech._HOOK[0] = hook
            try: tr.run('A', target)
            except Injected: pass
            mech._HOOK[0] = None
            st = mech.state()
            lost = run(N)
        r = tr.result()
        print(v, 'rev %d fault at %-15s fired %d: anchors=%d global_events=%-4d | then no section: lost %6d (timeouts %d) | A calls %s MONITOR_LOST %s' % (
            3 if rev3 else 2, pt, fired[0], st['anchors'], st['global_events'], lost[0], lost[1], r['calls'], r['MONITOR_LOST']))
mech.REV3[0] = True
