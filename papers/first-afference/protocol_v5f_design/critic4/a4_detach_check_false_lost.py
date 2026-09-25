# _detach's UNWIND_LOST test (spec M7): `o.armed and _ANCHORS.get(fr) is o and _ours() and not (get_events & PY_UNWIND)`.
# The anchor test comes BEFORE two C calls, the reverse of the order revision 3 imposed on _unwind_off. A thread
# switch after the anchor test (at _ours's RESUME, or after get_tool returns) lets another thread's exit X3 pop this
# anchor and clear S, legitimately; the closer then reads S clear and flags UNWIND_LOST: a false MONITOR_LOST in a
# fault-free run, on a close racing its tracer's exit (the same disclosed race as a3).
# mech3's 'ours' hook is PY_START of _ours (the id-3 tool can do exactly this).
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech3 as mech
def f(): return 1
def run(order):
    at, go = threading.Event(), threading.Event(); st = {'claimed': False}
    me = {}
    def hook(p):
        if threading.get_ident() != me.get('t1'): return
        if p == 'detach:claimed': st['claimed'] = True
        elif p == 'ours' and st['claimed'] and not at.is_set():
            at.set(); go.wait(5)
    if order == 'events-first':          # the fix: read the event first, test the anchor last
        def _detach(o):
            o.fin.setdefault('fin', 1); mech._hk('detach:claimed'); fr = o.frame
            if fr is not None:
                if o.armed and mech._ours() and not (mech.M.get_events(mech.TOOL[0]) & mech.E.PY_UNWIND) and mech._ANCHORS.get(fr) is o:
                    mech.CORE_OF[id(o)].flags['UNWIND_LOST'] = True
                mech._ANCHORS.pop(fr, None)
            o.frame = None; mech._unwind_off()
        saved = mech._detach; mech._detach = _detach
    tr = mech.Tracer(f); tr.__enter__()
    def t1():
        me['t1'] = threading.get_ident(); tr.run('A', f)
    mech._HOOK[0] = hook
    T1 = threading.Thread(target=t1); T1.start(); at.wait(5)
    tr.__exit__(None, None, None)        # X3 re-detaches A: its anchor test passes, it pops, _unwind_off clears S
    go.set(); T1.join(); mech._HOOK[0] = None
    if order == 'events-first': mech._detach = saved
    r = tr.result()
    print(sys.version.split()[0], '%-12s' % order, 'A', r['calls'].get('A'), 'MONITOR_LOST', r['MONITOR_LOST'], '(fault-free; S was never cleared under a live section)')
run('spec'); run('events-first')
