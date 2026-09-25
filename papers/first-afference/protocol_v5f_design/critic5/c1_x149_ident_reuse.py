# X149 as the spec text states it: "T2 closes section B ... Then T1 runs cov.run('A', catch_t)".
# If T1 is a NEW thread started after T2 ended, Linux often gives it T2's ident. _await_clearers skips
# announcements whose tid equals its own, so it never waits for, and never pops, T2's dead token:
# 'clearing == 0 after it' fails, and the no_liveness mutant is no longer killed.
import sys, threading, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
class Injected(BaseException): pass
def t(): raise KeyError
def catch_t():
    try: t()
    except KeyError: pass
def reset():
    mech._ANCHORS.clear(); mech._CLEARING.clear(); mech._HOOK[0] = None
    if mech.M.get_tool(4) is not None: mech.M.set_events(4, 0)
def outcome(fn):
    try: return fn()
    except mech.TraceInactive: return 'TRACE_INACTIVE'
    except mech.MachineryBusy: return 'MACHINERY_BUSY'
    except Injected: return 'Injected'

def x149(t1_kind):
    fired = [0]
    def hook(p):
        if threading.current_thread().name == 'T2' and p == 'off:announced' and not fired[0]: fired[0] = 1; raise Injected
    mech.BUSY[0] = 1.0
    with mech.Tracer(t) as tr:
        opened, close = threading.Event(), threading.Event()
        res = {}
        th2 = threading.Thread(target=lambda: res.setdefault('t2', (threading.get_ident(), outcome(lambda: tr.run('B', lambda: (opened.set(), close.wait(5)))))), name='T2')
        th2.start(); opened.wait(5); mech._HOOK[0] = hook; close.set(); th2.join(5); mech._HOOK[0] = None
        c1 = len(mech._CLEARING)
        out = {}
        def t1():
            out['tid'] = threading.get_ident()
            t0 = time.perf_counter(); out['r'] = outcome(lambda: tr.run('A', catch_t)); out['dt'] = round(time.perf_counter() - t0, 3)
        if t1_kind == 'main': t1()
        else:
            th1 = threading.Thread(target=t1, name='T1'); th1.start(); th1.join(10)
        c2 = len(mech._CLEARING)
    r = tr.result(); mech.BUSY[0] = 10.0
    return dict(same_ident=res['t2'][0] == out['tid'], closer=res['t2'][1], clearing_after_fault=c1, run_A=out['r'],
                calls=r['calls'].get('A'), clearing_after_A=c2)

v = sys.version.split()[0]
for kind in ('main', 'new-thread'):
    for mut in ((), ('no_liveness',)):
        agg = {}
        for i in range(20):
            mech.MUT.clear(); mech.MUT.update(mut); reset(); o = x149(kind); mech.MUT.clear(); reset()
            k = str(o); agg[k] = agg.get(k, 0) + 1
        print(v, 'T1=%-10s mutant=%-12s' % (kind, ','.join(mut) or 'spec'))
        for k, n in agg.items(): print('    %2d x %s' % (n, k))
