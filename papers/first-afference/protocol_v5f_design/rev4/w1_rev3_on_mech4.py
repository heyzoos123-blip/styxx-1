# SM1 witnesses for revision 3's new rules, run on mech3.py under the spec and under each single-rule mutant
# (mech3.MUT). mech3's hooks stand in for the exam's fault tools: 'ours' is PY_START of _ours, 'on:enter' and
# 'on:return' are PY_START and PY_RETURN of _unwind_on (the id-3 tool), 'detach:popped' is the id-5 injector's first
# instruction in _detach after the pop, and 'off:cleared' is the C_RETURN of the clear's set_events. Every case runs
# with no other section open (the main thread before the self-trace).
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech; mech.REV4[0] = False
class Injected(BaseException): pass
def t(): raise KeyError
def f(): return 1
def g(): return 2
def catch_t():
    try: t()
    except KeyError: pass
def st(): return mech.state()

def x144():
    # the id-3 tool raises at the case thread's first return from _unwind_on in cov.run('A', f)
    n = [0]
    def hook(p):
        if p == 'on:return':
            n[0] += 1
            if n[0] == 1: raise Injected
    with mech.Tracer(f) as tr:
        mech._HOOK[0] = hook
        try: tr.run('A', f); out = 'no raise'
        except Injected: out = 'Injected'
        mech._HOOK[0] = None
        s = st()
    r = tr.result()
    return dict(raised=out, anchors=s['anchors'], global_events=s['global_events'], calls=r['calls'], MONITOR_LOST=r['MONITOR_LOST'])

def x143_setup(on_t1):
    # T2 opens B and waits; T1 opens A; the tool blocks T1 at its first return from _unwind_on; T2 closes B (the last
    # anchor); then T1 is released. on_t1(point, count) may raise on T1.
    at_first, resume = threading.Event(), threading.Event()
    cnt = {'on:return': 0, 'on:enter': 0}
    def hook(p):
        if threading.current_thread().name != 'T1' or p not in cnt: return
        cnt[p] += 1
        if p == 'on:return' and cnt[p] == 1: at_first.set(); resume.wait(5)
        on_t1(p, cnt[p])
    res = {}
    with mech.Tracer(t) as tr:
        t2_open, t2_close = threading.Event(), threading.Event()
        th2 = threading.Thread(target=lambda: tr.run('B', lambda: (t2_open.set(), t2_close.wait(5))), name='T2')
        th2.start(); t2_open.wait(5)
        mech._HOOK[0] = hook
        def T1():
            try: tr.run('A', catch_t); res['raised'] = 'no raise'
            except Injected: res['raised'] = 'Injected'
        th1 = threading.Thread(target=T1, name='T1'); th1.start()
        at_first.wait(5); t2_close.set(); th2.join(5); resume.set(); th1.join(5)
        mech._HOOK[0] = None
    r = tr.result(); s = st()
    return dict(raised=res.get('raised'), calls=r['calls'], MONITOR_LOST=r['MONITOR_LOST'], anchors=s['anchors'], global_events=s['global_events'])

def x143():  return x143_setup(lambda p, c: None)
def x143b():
    def on_t1(p, c):
        if p == 'on:enter' and c == 2: raise Injected      # T1's second _unwind_on, after its commit, before its set
    return x143_setup(on_t1)

def x143c():
    # the id-5 injector raises at _detach's first instruction after the pop, in cov.run('A', f); then a second tracer
    # declaring f (so its exit retires no mint) is entered and exited with no section; then the first tracer exits
    fired = [0]
    def hook(p):
        if p == 'detach:popped' and not fired[0]: fired[0] = 1; raise Injected
    tr = mech.Tracer(f); tr.__enter__()
    mech._HOOK[0] = hook
    try: tr.run('A', f); out = 'no raise'
    except Injected: out = 'Injected'
    mech._HOOK[0] = None
    s1 = st()
    with mech.Tracer(): pass                  # a transaction that retires no mint (in the spec: a second tracer
    s2 = st()                                 # declaring f, which joins the first tracer's mint; mech3 has no joining)
    tr.__exit__(None, None, None)
    r = tr.result()
    return dict(raised=out, events_after_fault=s1['global_events'], events_after_transaction=s2['global_events'],
                calls=r['calls'], MONITOR_LOST=r['MONITOR_LOST'])

def x145a():
    # closer: T2 closes B, the last anchor; the tool blocks T2 at its first _ours call after the pop until T1 has
    # committed section A and is in its body; if T2 then clears, it is blocked again after the clear until T1's body
    # has raised and caught t
    t1_in, t1_done, t2_first, t2_go = (threading.Event() for _ in range(4))
    state = {'n': 0, 'popped': False}
    def hook(p):
        if threading.current_thread().name != 'T2': return
        if p == 'detach:popped': state['popped'] = True
        if p == 'ours' and state['popped'] and state['n'] == 0:
            state['n'] = 1; t2_first.set(); t2_go.wait(5)
        if p == 'off:cleared' and state['popped']:
            t2_go.set(); t1_done.wait(5)
    with mech.Tracer(t) as tr:
        b_open, b_close = threading.Event(), threading.Event()
        th2 = threading.Thread(target=lambda: tr.run('B', lambda: (b_open.set(), b_close.wait(5))), name='T2')
        th2.start(); b_open.wait(5)
        mech._HOOK[0] = hook
        b_close.set(); t2_first.wait(5)
        def body():
            t1_in.set(); t2_go.set()
            th2.join(0.2)                      # T2 either finishes (spec) or blocks after its clear (mutant)
            catch_t(); t1_done.set()
        th1 = threading.Thread(target=lambda: tr.run('A', body), name='T1'); th1.start()
        th1.join(5); th2.join(5)
        mech._HOOK[0] = None
    r = tr.result()
    return dict(calls=r['calls'], MONITOR_LOST=r['MONITOR_LOST'])

def x145b():
    # retire: tracer Y (declares t) is active with no section open; thread X exits tracer Z (declares u), which retires
    # u's mint; the tool blocks X at its first _ours call after u's mint is gone, until section B (of Y) is open on TB
    def u(): return 0
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

v = sys.version.split()[0]
ROWS = (('X144', x144, 'commit_outside_try'), ('X143', x143, None), ('X143b', x143b, 'no_armed'),
        ('X143c', x143c, 'no_anchor_test'), ('X143c', x143c, 'no_reconcile_off'),
        ('X145a', x145a, 'off_rev2_order'), ('X145b', x145b, 'step6_rev2'))
for case, fn, mut in ROWS:
    mech.MUT.clear(); spec = fn()
    if mut is None:
        print(v, '%-6s spec: %s' % (case, spec)); continue
    mech.MUT.add(mut); mutant = fn(); mech.MUT.clear()
    print(v, '%-6s spec: %s' % (case, spec)); print(v, '%-6s %-18s: %s  -> %s' % ('', mut, mutant, 'differs' if mutant != spec else 'SAME'))
