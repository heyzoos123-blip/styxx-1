# An open racing the tracer's exit (a supported, disclosed race: spec lines 145, 304, 1070). Revision 3 moved the
# anchor commit into _commit(o), which stores `_ANCHORS[o.frame] = o` (spec M7). If exit's X3 detaches the appended
# opening first, _detach has already set o.frame = None, so _commit stores _ANCHORS[None] = o. Every later
# _detach of o (the race re-check of step 8, the finally, a prune) reads fr = o.frame = None and skips the pop.
# Result: a registered anchor forever, so PY_UNWIND stays set for the rest of the process and no _unwind_off clears it.
# (1) deterministic, with mech3's hooks standing in for the id-3 tool at PY_START/PY_RETURN of _unwind_on;
# (2) the same with the spec's step-8 race re-check added to _commit;
# (3) natural: no hooks, 1 us switch interval, enter / thread opens / main exits.
import sys, threading, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech3 as mech
M = sys.monitoring
def f(): return 1
EXITING = [False]
def commit_spec(o):                      # spec M7 _commit, with step 8's race re-check
    mech._hk('commit:0'); mech._unwind_on(); mech._hk('commit:1')
    mech._ANCHORS[o.frame] = o
    mech._unwind_on()
    if EXITING[0]:
        mech._detach(o); raise RuntimeError('[V5:TRACE_INACTIVE]')
    o.armed = True
_orig_exit = mech.Tracer.__exit__
def exit_spec(self, *a):
    EXITING[0] = True                    # X1: the 'exiting' claim precedes X3
    return _orig_exit(self, *a)
def run(point, spec):
    mech._ANCHORS.clear(); EXITING[0] = False
    if spec: mech._commit = commit_spec; mech.Tracer.__exit__ = exit_spec
    at, go = threading.Event(), threading.Event()
    me = {}
    def hook(p):
        if p == point and threading.get_ident() == me.get('t1') and not at.is_set():
            at.set(); go.wait(5)
    tr = mech.Tracer(f); tr.__enter__()
    mech._HOOK[0] = hook
    out = {}
    def t1():
        me['t1'] = threading.get_ident()
        try: out['r'] = tr.run('A', f)
        except Exception as e: out['r'] = repr(e)
    T1 = threading.Thread(target=t1); T1.start(); at.wait(5)
    tr.__exit__(None, None, None)        # exit on the main thread while T1 is inside _commit, before its store
    go.set(); T1.join(); mech._HOOK[0] = None
    s1 = mech.state(); keys = [type(k).__name__ for k in mech._ANCHORS]
    EXITING[0] = False
    tr2 = mech.Tracer(f); tr2.__enter__(); tr2.run('C', f); tr2.__exit__(None, None, None)   # a later, clean trace
    s2 = mech.state()
    print(sys.version.split()[0], '%-9s %-8s' % (point, 'step8' if spec else 'mech3'), 'run():', out.get('r'),
          '| after exit: anchors', s1['anchors'], 'key types', keys, 'events', s1['global_events'],
          '| after a later clean trace: anchors', s2['anchors'], 'events', s2['global_events'])
    mech._commit = run.orig_commit; mech.Tracer.__exit__ = _orig_exit; mech._ANCHORS.clear(); M.set_events(4, 0)
run.orig_commit = mech._commit
for spec in (False, True):
    for point in ('commit:0', 'commit:1', 'on:read'):
        run(point, spec)
def natural(n=20000):
    sys.setswitchinterval(1e-6); leaks = 0
    for i in range(n):
        tr = mech.Tracer(f); tr.__enter__()
        th = threading.Thread(target=lambda: tr.run('A', f)); th.start()
        tr.__exit__(None, None, None); th.join()
        if None in mech._ANCHORS: leaks += 1; mech._ANCHORS.pop(None)
    sys.setswitchinterval(0.005); M.set_events(4, 0)
    print(sys.version.split()[0], 'natural (no hooks): _ANCHORS[None] leaked in %d of %d enter/open/exit races' % (leaks, n))
natural()
