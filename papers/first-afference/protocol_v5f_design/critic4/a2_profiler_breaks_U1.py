# U1 ("an open section's body never runs with S clear ... on every interleaving") under a coexisting pure-Python
# setprofile function on the *closing* thread (the spec's V48 shape; line 822 says such tools coexist).
# (1) deterministic: the profiler's c_call event for set_events(tool, 0) inside _unwind_off runs after the
#     _ANCHORS test; there T1 commits A and enters its body; T2's clear then lands; at c_return T1's body raises t.
# (2) natural: no hooks, no forced hand-off; closers run under a trivial pure-Python profile function.
import sys, threading, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech3 as mech
M = sys.monitoring
def t(): raise KeyError
def catch_t():
    try: t()
    except KeyError: pass
def g(): return 1
OFFC = mech._unwind_off.__code__
def deterministic():
    in_body, go_t, t_done, at_call = (threading.Event() for _ in range(4))
    def body():
        in_body.set(); go_t.wait(5); catch_t(); t_done.set()
    def prof(frame, ev, arg):
        if frame.f_code is OFFC and arg is M.set_events:
            if ev == 'c_call' and not at_call.is_set():
                at_call.set(); in_body.wait(5)          # T1 opens A here, between the test and the clear
            elif ev == 'c_return' and at_call.is_set() and not go_t.is_set():
                go_t.set(); t_done.wait(5)              # A's body raises t with S clear
    with mech.Tracer(t, g) as tr:
        opened = threading.Event(); close = threading.Event()
        def t2():
            def b(): opened.set(); close.wait(5)
            sys.setprofile(prof)
            try: tr.run('B', b)
            finally: sys.setprofile(None)
        T2 = threading.Thread(target=t2); T2.start(); opened.wait(5)
        T1 = threading.Thread(target=lambda: at_call.wait(5) and tr.run('A', body))
        T1.start(); close.set(); T2.join(); T1.join()
    r = tr.result()
    print(sys.version.split()[0], 'deterministic: A', r['calls'].get('A'), 'MONITOR_LOST', r['MONITOR_LOST'],
          '(U1 claims A {t:1}, no MONITOR_LOST)')
def natural(seconds=4.0, prof_on=True):
    sys.setswitchinterval(1e-6)
    lost = [0]; calls = [0]; stop = [False]
    def p(frame, ev, arg): pass
    with mech.Tracer(t, g) as tr:
        def raiser():
            while not stop[0]:
                n0 = sum(o.calls.get('t', 0) for o in tr.core.openings)
                tr.run('A', catch_t); calls[0] += 1
        def closer():
            if prof_on: sys.setprofile(p)
            while not stop[0]: tr.run('B', g)
            sys.setprofile(None)
        ths = [threading.Thread(target=raiser)] + [threading.Thread(target=closer) for _ in range(2)]
        for th in ths: th.start()
        time.sleep(seconds); stop[0] = True
        for th in ths: th.join()
    r = tr.result()
    got = r['calls'].get('A', {}).get('t', 0)
    print(sys.version.split()[0], 'natural, closers under a pure-Python profiler=%s: A calls %d, t credited %d, lost %d, MONITOR_LOST %s'
          % (prof_on, calls[0], got, calls[0] - got, r['MONITOR_LOST']))
    sys.setswitchinterval(0.005)
deterministic()
for pon in (False, True):
    natural(prof_on=pon)
