# X143 as placed by the spec (not in the main-thread-before-self-trace list) runs inside the self-trace, where the
# case's own cov.run(<gate section>, case) anchor is registered for the whole case. _ANCHORS is process-global, so
# B is never "the last registered anchor", _unwind_off returns early, the event is never cleared, and the mutant
# (no re-check after the commit) scores the same as the spec: X143 cannot witness its SM1 row there.
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/rev2')
import mech2 as mech
def t(): raise KeyError
def body():
    try: t()
    except KeyError: pass
def sentinel(): return 0
def x143(recheck):
    orig_on = mech._unwind_on
    n1 = [0]; at_first = threading.Event(); resume = threading.Event()
    def on():
        if threading.current_thread().name != 'T1': return orig_on()
        n1[0] += 1
        if n1[0] == 1: orig_on(); at_first.set(); resume.wait(5)
        elif n1[0] == 2 and recheck: orig_on()
    mech._unwind_on = on
    with mech.Tracer(t) as tr:
        t2_open = threading.Event(); t2_close = threading.Event()
        def T2():
            def sec(): t2_open.set(); t2_close.wait(5)
            tr.run('B', sec)
        th2 = threading.Thread(target=T2, name='T2'); th2.start(); t2_open.wait(5)
        th1 = threading.Thread(target=lambda: tr.run('A', body), name='T1'); th1.start()
        at_first.wait(5); t2_close.set(); th2.join(5); resume.set(); th1.join(5)
    mech._unwind_on = orig_on
    return tr.result()['calls']
def placed(inside_selftrace):
    out = {}
    for rc in (True, False):
        if inside_selftrace:
            with mech.Tracer(sentinel) as selftrace:          # the exam's self-trace, gate section open around the case
                res = []
                selftrace.run('SELF', lambda: res.append(x143(rc)))
            out['spec' if rc else 'mutant'] = res[0]
        else:
            out['spec' if rc else 'mutant'] = x143(rc)
    return out
v = sys.version.split()[0]
print(v, 'main thread, before the self-trace:', placed(False))
print(v, 'inside the self-trace (default)   :', placed(True))
