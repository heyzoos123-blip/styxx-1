# B1: an open racing its own tracer's exit. The critic's a3 (hooked) and a3b (natural) probes, re-run on mech4.py for
# revision 2 (REV3 False), revision 3 as specified (REV4 False, with step 8's 'exiting' re-check added to _commit, as
# the critic's commit_spec does), and revision 4 (REV4 True: owner-only release of o.frame, the re-check after the
# store, the anchor sweep).
# (1) Hooked: T1 runs tr.run('A', f); a hook blocks T1 at a point of its open path until the main thread's exit has
#     returned. Points: 'commit:0' (PY_START of _commit: the id-3 tool of case X146), the critic's 'commit:1' and
#     'on:read' (revision 3's points inside _commit), and revision 4's 'commit:stored' (after the store, before the
#     re-check) and 'on:read' (inside _unwind_on after the wait).
# (2) Natural: N enter/open/exit races at a 1 us switch interval, no hooks, per revision.
# Reported: run()'s outcome, registered anchors (and their key types), global events and clearing tokens after exit
# and after a later clean trace; for (2) the number of races that left an anchor, the outcomes, and false
# MONITOR_LOST (UNWIND_LOST set on a trace whose sections lost nothing: f returns, so nothing can be lost).
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
M = sys.monitoring
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
def f(): return 1
def commit_rev3_spec(o):                  # revision 3's _commit as specified: steps 7 and 8 (the critic's commit_spec)
    mech._hk('commit:0'); mech._unwind_on(); mech._hk('commit:1')
    mech._ANCHORS[o.frame] = o
    mech._unwind_on()
    if o.core.exiting:
        mech._detach(o); o.core.problems.append('[V5:TRACE_INACTIVE]'); raise mech.TraceInactive('[V5:TRACE_INACTIVE]')
    o.armed = True
ORIG_COMMIT = mech._commit
def setrev(rev):
    mech.REV3[0] = rev >= 3; mech.REV4[0] = rev >= 4
    mech._commit = commit_rev3_spec if rev == 3 else ORIG_COMMIT
def clean():
    mech._ANCHORS.clear(); mech._CLEARING.clear()
    if M.get_tool(4) is not None: M.set_events(4, 0)
def hooked(rev, point):
    setrev(rev); clean()
    at, go = threading.Event(), threading.Event(); me = {}
    def hook(p):
        if p == point and threading.get_ident() == me.get('t1') and not at.is_set():
            at.set(); go.wait(5)
    tr = mech.Tracer(f); tr.__enter__()
    mech._HOOK[0] = hook
    out = {}
    def t1():
        me['t1'] = threading.get_ident()
        try: out['r'] = tr.run('A', f)
        except Exception as e: out['r'] = type(e).__name__
    T1 = threading.Thread(target=t1); T1.start()
    if not at.wait(5): out['note'] = 'point not reached'
    tr.__exit__(None, None, None)         # the whole exit on the main thread while T1 is held
    go.set(); T1.join(); mech._HOOK[0] = None
    s1 = mech.state(); keys = sorted(type(k).__name__ for k in mech._ANCHORS)
    tr2 = mech.Tracer(f); tr2.__enter__(); tr2.run('C', f); tr2.__exit__(None, None, None)
    s2 = mech.state()
    r = tr.result()
    print(sys.version.split()[0], 'rev %d  %-13s run(): %-13s | after exit: anchors %d %s events %d clearing %d | after a later clean trace: anchors %d events %d | problems %s MONITOR_LOST %s%s'
          % (rev, point, out.get('r'), s1['anchors'], keys, s1['global_events'], s1['clearing'], s2['anchors'], s2['global_events'],
             tr.core.problems, r['MONITOR_LOST'], (' ' + out['note']) if 'note' in out else ''))
    clean()
for rev, pts in ((3, ('commit:0', 'commit:1', 'on:read')), (4, ('commit:0', 'commit:stored', 'on:read'))):
    for p in pts: hooked(rev, p)
def natural(rev, n):
    setrev(rev); clean()
    sys.setswitchinterval(1e-6)
    leaks = 0; kinds = set(); outcomes = {}; lost = 0; left_events = 0; left_clearing = 0
    for i in range(n):
        tr = mech.Tracer(f); tr.__enter__()
        box = {}
        def t1():
            try: tr.run('A', f); box['r'] = 'ran'
            except mech.TraceInactive: box['r'] = 'TRACE_INACTIVE'
        th = threading.Thread(target=t1); th.start()
        tr.__exit__(None, None, None); th.join()
        outcomes[box.get('r')] = outcomes.get(box.get('r'), 0) + 1
        if tr.core.flags.get('UNWIND_LOST'): lost += 1
        if mech._ANCHORS:
            leaks += 1; kinds.update(type(k).__name__ for k in mech._ANCHORS)
        if mech.events_set() and not mech._ANCHORS: left_events += 1
        if mech._CLEARING: left_clearing += 1
        clean()
    sys.setswitchinterval(0.005)
    print(sys.version.split()[0], 'rev %d natural, %d races: anchor left after exit and join in %d (key types %s); event set with no anchor %d; clearing left %d; outcomes %s; UNWIND_LOST (false: f returns) %d'
          % (rev, n, leaks, sorted(kinds), left_events, left_clearing, dict(sorted(outcomes.items())), lost))
for rev in (2, 3, 4):
    natural(rev, N)
