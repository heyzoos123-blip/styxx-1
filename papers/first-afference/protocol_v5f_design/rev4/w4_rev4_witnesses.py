# SM1 witnesses for revision 4, run on mech4.py under the spec and under each single-rule mutant (mech4.MUT).
# mech4's hooks stand in for the exam's tools: 'commit:0' is PY_START of _commit (id-3 tool), 'open:checked' is the
# CALL of asyncio.events._get_running_loop in _open (id-3 tool with a local CALL event), 'wait:enter' is PY_START of
# _await_clearers, 'off:tested' is the CALL of the clear's set_events in _unwind_off (id-3 tool, local CALL event),
# 'off:withdrawn' is PY_RETURN of _unwind_off, 'commit:stored' / 'detach:claimed' / 'off:announced' are the id-5
# injector's landing rules (the first instruction after `anchors` rose / before the pop / after `clearing` rose).
# Every case runs with no other section open (the main thread before the self-trace).
import sys, threading, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
class Injected(BaseException): pass
def t(): raise KeyError
def f(): return 1
def g(): return 2
def catch_t():
    try: t()
    except KeyError: pass
def st(): return mech.state()
def reset():
    mech._ANCHORS.clear(); mech._CLEARING.clear(); mech._HOOK[0] = None
    if mech.M.get_tool(4) is not None: mech.M.set_events(4, 0)
def outcome(fn):
    try: return fn()
    except mech.TraceInactive: return 'TRACE_INACTIVE'
    except mech.MachineryBusy: return 'MACHINERY_BUSY'
    except Injected: return 'Injected'

def held_open(point, during, extra=None):
    """T1 runs tr.run('A', f); the hook holds T1 at `point` until during(tr) has returned on the main thread."""
    at, go = threading.Event(), threading.Event(); me = {}
    def hook(p):
        if threading.get_ident() != me.get('t1'): return
        if p == point and not at.is_set(): at.set(); go.wait(5)
        if extra: extra(p)
    tr = mech.Tracer(f); tr.__enter__()
    out = {}
    def t1():
        me['t1'] = threading.get_ident(); out['r'] = outcome(lambda: tr.run('A', f))
    mech._HOOK[0] = hook
    T1 = threading.Thread(target=t1); T1.start(); at.wait(5)
    during(tr)
    go.set(); T1.join(5); mech._HOOK[0] = None
    return tr, out.get('r')

def x146():            # B1: the id-3 tool holds T1 at PY_START of _commit until cov.__exit__() has returned
    tr, r = held_open('commit:0', lambda tr: tr.__exit__(None, None, None))
    s = st()
    return dict(run=r, anchors=s['anchors'], global_events=s['global_events'], problems=tr.core.problems)

def x146b():           # the late append: T1 held after step 2, before the append, until cov.__exit__() has returned
    tr, r = held_open('open:checked', lambda tr: tr.__exit__(None, None, None))
    s = st()
    return dict(run=r, anchors=s['anchors'], global_events=s['global_events'], problems=tr.core.problems)

def x146c():           # the prune: T1 held at PY_START of _commit while the facade dies and another trace reconciles
    def during(tr):
        tr.core.facade_dead = True
        with mech.Tracer(g): pass
    tr, r = held_open('commit:0', during)
    s = st()
    tr.__exit__(None, None, None)         # retire the pruned core's mint so that later cases start clean
    return dict(run=r, anchors=s['anchors'], global_events=s['global_events'])

def x146d():           # a double fault after the exit: a dead anchor of an exited core; the next reconciliation sweeps it
    n = {'k': 0}
    def extra(p):
        if p == 'commit:stored' and n['k'] == 0: n['k'] = 1; raise Injected
        if p == 'detach:claimed' and n['k'] == 1: n['k'] = 2; raise Injected
    tr, r = held_open('commit:0', lambda tr: tr.__exit__(None, None, None), extra)
    s1 = st()
    with mech.Tracer(g): pass
    s2 = st()
    return dict(run=r, anchors_after_faults=s1['anchors'], anchors_after_next_transaction=s2['anchors'],
                events_after_next_transaction=s2['global_events'])

def x145a():           # MF1: T2 closes B, the last anchor; the tool holds T2 between its test and its clear until T1
    # is in _await_clearers or in A's body; A's body calls t only after T2 has returned from _unwind_off
    ev = {k: threading.Event() for k in ('opened', 'close', 'at_clear', 'release', 'withdrawn')}
    def hook(p):
        name = threading.current_thread().name
        if name == 'T2':
            if p in ('off:tested', 'retire:tested') and not ev['at_clear'].is_set(): ev['at_clear'].set(); ev['release'].wait(5)
            if p in ('off:withdrawn', 'off:cleared') and ev['at_clear'].is_set(): ev['withdrawn'].set()
        if name == 'T1' and p == 'wait:enter': ev['release'].set()
    def body():
        ev['release'].set(); ev['withdrawn'].wait(5); catch_t()
    with mech.Tracer(t) as tr:
        th2 = threading.Thread(target=lambda: tr.run('B', lambda: (ev['opened'].set(), ev['close'].wait(5))), name='T2')
        th2.start(); ev['opened'].wait(5)
        mech._HOOK[0] = hook; ev['close'].set()
        ev['at_clear'].wait(5)
        th1 = threading.Thread(target=lambda: tr.run('A', body), name='T1'); th1.start()
        th1.join(5); th2.join(5); mech._HOOK[0] = None
    r = tr.result()
    return dict(calls=r['calls'].get('A'), MONITOR_LOST=r['MONITOR_LOST'])

def x145b():           # retire: Y active, no section; X exits Z (its mint retires); the tool holds X at its first
    def u(): return 0  # _ours call after u's mint is gone, until section B of Y is open; B's body then calls t
    x_blocked, x_go = threading.Event(), threading.Event()
    def hook(p):
        if threading.current_thread().name == 'X' and p == 'ours' and not x_blocked.is_set() \
                and not any(m.fn is u for m in list(mech._MINTED.values())):
            x_blocked.set(); x_go.wait(5)
    with mech.Tracer(t) as Y:
        z = mech.Tracer(u); z.__enter__()
        mech._HOOK[0] = hook
        x = threading.Thread(target=lambda: z.__exit__(None, None, None), name='X'); x.start()
        x_blocked.wait(5)
        ready, go = threading.Event(), threading.Event()
        def body(): ready.set(); go.wait(5); catch_t()
        tb = threading.Thread(target=lambda: Y.run('B', body), name='TB'); tb.start(); ready.wait(5)
        x_go.set(); x.join(5); mech._HOOK[0] = None
        go.set(); tb.join(5)
    r = Y.result()
    return dict(calls=r['calls'], MONITOR_LOST=r['MONITOR_LOST'])

def x143():            # the opener sets the event itself after its store: T1 held at PY_START of _commit while T2
    ev = {k: threading.Event() for k in ('opened', 'close', 'at', 'go')}   # closes B (the last anchor, clearing it)
    def hook(p):
        if threading.current_thread().name == 'T1' and p == 'commit:0' and not ev['at'].is_set(): ev['at'].set(); ev['go'].wait(5)
    with mech.Tracer(t) as tr:
        th2 = threading.Thread(target=lambda: tr.run('B', lambda: (ev['opened'].set(), ev['close'].wait(5))), name='T2')
        th2.start(); ev['opened'].wait(5)
        mech._HOOK[0] = hook
        th1 = threading.Thread(target=lambda: tr.run('A', catch_t), name='T1'); th1.start(); ev['at'].wait(5)
        ev['close'].set(); th2.join(5); ev['go'].set(); th1.join(5); mech._HOOK[0] = None
    r = tr.result(); s = st()
    return dict(calls=r['calls'].get('A'), MONITOR_LOST=r['MONITOR_LOST'], anchors=s['anchors'], global_events=s['global_events'])

def x143b():           # o.armed: after T2's close cleared the event, raise at PY_START of _commit's _unwind_on
    ev = {k: threading.Event() for k in ('opened', 'close', 'at', 'go')}
    def hook(p):
        if threading.current_thread().name != 'T1': return
        if p == 'commit:0' and not ev['at'].is_set(): ev['at'].set(); ev['go'].wait(5)
        if p == 'on:enter': raise Injected
    res = {}
    with mech.Tracer(t) as tr:
        th2 = threading.Thread(target=lambda: tr.run('B', lambda: (ev['opened'].set(), ev['close'].wait(5))), name='T2')
        th2.start(); ev['opened'].wait(5)
        mech._HOOK[0] = hook
        th1 = threading.Thread(target=lambda: res.setdefault('r', outcome(lambda: tr.run('A', catch_t))), name='T1'); th1.start()
        ev['at'].wait(5); ev['close'].set(); th2.join(5); ev['go'].set(); th1.join(5); mech._HOOK[0] = None
    r = tr.result(); s = st()
    return dict(run=res.get('r'), calls=r['calls'].get('A'), MONITOR_LOST=r['MONITOR_LOST'], anchors=s['anchors'], global_events=s['global_events'])

def x143c():           # injector at _detach's first instruction after the pop; a transaction; then the trace exits
    fired = [0]
    def hook(p):
        if p == 'detach:popped' and not fired[0]: fired[0] = 1; raise Injected
    tr = mech.Tracer(f); tr.__enter__()
    mech._HOOK[0] = hook
    out = outcome(lambda: tr.run('A', f))
    mech._HOOK[0] = None
    s1 = st()
    with mech.Tracer(): pass
    s2 = st()
    tr.__exit__(None, None, None)
    r = tr.result()
    return dict(run=out, events_after_fault=s1['global_events'], events_after_transaction=s2['global_events'],
                calls=r['calls'], MONITOR_LOST=r['MONITOR_LOST'])

def x144():            # raise at the case thread's first return from _unwind_on in cov.run('A', f)
    n = [0]
    def hook(p):
        if p == 'on:return':
            n[0] += 1
            if n[0] == 1: raise Injected
    with mech.Tracer(f) as tr:
        mech._HOOK[0] = hook
        out = outcome(lambda: tr.run('A', f))
        mech._HOOK[0] = None
        s = st()
    r = tr.result()
    return dict(run=out, anchors=s['anchors'], global_events=s['global_events'], calls=r['calls'], MONITOR_LOST=r['MONITOR_LOST'])

def x148():            # MF2: T1's close held at PY_START of _ours in its UNWIND_LOST test until the exit has returned
    at, go = threading.Event(), threading.Event(); st_ = {'claimed': False}; me = {}
    def hook(p):
        if threading.get_ident() != me.get('t1'): return
        if p == 'detach:claimed': st_['claimed'] = True
        elif p == 'ours' and st_['claimed'] and not at.is_set(): at.set(); go.wait(5)
    tr = mech.Tracer(f); tr.__enter__()
    def t1(): me['t1'] = threading.get_ident(); tr.run('A', f)
    mech._HOOK[0] = hook
    T1 = threading.Thread(target=t1); T1.start(); at.wait(5)
    tr.__exit__(None, None, None); go.set(); T1.join(5); mech._HOOK[0] = None
    r = tr.result()
    return dict(calls=r['calls'].get('A'), MONITOR_LOST=r['MONITOR_LOST'])

def x149():            # MF1: a clearer faulted inside its window leaves a dead announcement
    fired = [0]
    def hook(p):
        if threading.current_thread().name == 'T2' and p == 'off:announced' and not fired[0]: fired[0] = 1; raise Injected
    mech.BUSY[0] = 1.0                    # the model's busy bound, shortened from the spec's 10 s for the mutant row
    with mech.Tracer(t) as tr:
        opened, close = threading.Event(), threading.Event()
        res = {}
        th2 = threading.Thread(target=lambda: res.setdefault('t2', outcome(lambda: tr.run('B', lambda: (opened.set(), close.wait(5))))), name='T2')
        th2.start(); opened.wait(5); mech._HOOK[0] = hook; close.set(); th2.join(5); mech._HOOK[0] = None
        s1 = st()
        t0 = time.perf_counter(); r1 = outcome(lambda: tr.run('A', catch_t)); dt = time.perf_counter() - t0
        s2 = st()
    r = tr.result()
    mech.BUSY[0] = 10.0
    return dict(closer=res.get('t2'), clearing_after_fault=s1['clearing'], run_A=r1, A_open_under_1s=dt < 0.5,
                calls=r['calls'].get('A'), clearing_after_A=s2['clearing'])
def x149b():           # the reconciliation's sweep of dead announcements, with no open after the fault
    fired = [0]
    def hook(p):
        if threading.current_thread().name == 'T2' and p == 'off:announced' and not fired[0]: fired[0] = 1; raise Injected
    with mech.Tracer(t) as tr:
        opened, close = threading.Event(), threading.Event()
        th2 = threading.Thread(target=lambda: outcome(lambda: tr.run('B', lambda: (opened.set(), close.wait(5)))), name='T2')
        th2.start(); opened.wait(5); mech._HOOK[0] = hook; close.set(); th2.join(5); mech._HOOK[0] = None
        s1 = st()
        with mech.Tracer(g): pass
        s2 = st()
    return dict(clearing_after_fault=s1['clearing'], clearing_after_transaction=s2['clearing'])

v = sys.version.split()[0]
ROWS = (('X146', x146, ('detach_nulls', 'no_recheck')),
        ('X146b', x146b, ('no_exiting_test',)),
        ('X146c', x146c, ('no_fin_test',)),
        ('X146d', x146d, ('no_anchor_sweep',)),
        ('X145a', x145a, ('no_announce', 'withdraw_early', 'no_wait', 'on_before_wait')),
        ('X145b', x145b, ('step6_rev2',)),
        ('X143', x143, ('no_on',)),
        ('X143b', x143b, ('no_armed',)),
        ('X143c', x143c, ('no_anchor_test', 'no_reconcile_off')),
        ('X144', x144, ('commit_outside_try',)),
        ('X148', x148, ('anchor_first',)),
        ('X149', x149, ('no_liveness',)),
        ('X149b', x149b, ('no_token_sweep',)))
only = sys.argv[1:]
for case, fn, muts in ROWS:
    if only and case not in only: continue
    mech.MUT.clear(); reset(); spec = fn(); reset()
    print(v, '%-6s spec: %s' % (case, spec))
    for mu in muts:
        mech.MUT.clear(); mech.MUT.add(mu); reset(); mutant = fn(); mech.MUT.clear(); reset()
        print(v, '%-6s %-18s: %s  -> %s' % ('', mu, mutant, 'differs' if mutant != spec else 'SAME'))
    sys.stdout.flush()
