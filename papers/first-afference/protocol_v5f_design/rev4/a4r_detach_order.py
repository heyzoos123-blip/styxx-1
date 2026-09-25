# MF2 on mech4.py: the critic's a4 interleaving. T1 closes A; a hook blocks T1 at PY_START of _ours inside its close's
# UNWIND_LOST test (after its claim) until the main thread's exit has returned (X3 re-detached A, popped it and
# cleared the event, legitimately). Revision 3's order (anchor test first) then reads the event clear and flags
# UNWIND_LOST; revision 4's order (event first, anchor last) finds the anchor gone. Mutant: anchor_first.
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
def f(): return 1
def run(label, rev4, mut=()):
    mech.REV4[0] = rev4; mech.MUT.clear(); mech.MUT.update(mut)
    at, go = threading.Event(), threading.Event(); st = {'claimed': False}; me = {}
    def hook(p):
        if threading.get_ident() != me.get('t1'): return
        if p == 'detach:claimed': st['claimed'] = True
        elif p == 'ours' and st['claimed'] and not at.is_set():
            at.set(); go.wait(5)
    tr = mech.Tracer(f); tr.__enter__()
    def t1():
        me['t1'] = threading.get_ident(); tr.run('A', f)
    mech._HOOK[0] = hook
    T1 = threading.Thread(target=t1); T1.start(); at.wait(5)
    tr.__exit__(None, None, None)
    go.set(); T1.join(); mech._HOOK[0] = None; mech.MUT.clear()
    r = tr.result(); s = mech.state()
    print(sys.version.split()[0], '%-24s A %s MONITOR_LOST %s | anchors %d events %d' % (label, r['calls'].get('A'), r['MONITOR_LOST'], s['anchors'], s['global_events']))
run('rev 3 (anchor first)', False)
run('rev 4 (event first)', True)
run('rev 4 mutant anchor_first', True, ('anchor_first',))
