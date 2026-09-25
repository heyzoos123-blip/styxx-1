# Revision 6 (M3): an isolating witness for F14's rule (the close's event read has no name gate), on a REAL greenlet
# library (greenlet 3.5.6, unpacked into rev6/site312 and rev6/site313; the rt3 venvs are not modified).
# The model check found it (m6_modelcheck.py mutants, blind_read_gated: 'ext+greenlet: [exit(X), rec] || open(X)',
# LOSTNOTE): a greenlet switch inside a reconciliation's reclaim, after the re-take and before its count in _LOST,
# lets another greenlet's exit steal the mutex (the owner's frames are off the thread's chain) and run its whole
# MONITOR_LOST test before the count lands.
# Shape: styxx's id is freed; tracer X's section A opens (its _unwind_on is gated off: the id is not named), calls t,
# which raises out of its body (lost: no PY_UNWIND), and closes. Greenlet g2 runs a transaction whose reclaim takes
# the id back; an audit hook at its registration's 5th register_callback switches to greenlet g1, which runs X's
# __exit__ to completion; then g2 finishes and counts.
# Spec: X notes MONITOR_LOST (the close's ungated read found the event clear under A's armed anchor).
# Mutant blind_read_gated (revision 4's gated read): X has no MONITOR_LOST although t's call was lost.
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'site%d%d' % sys.version_info[:2]))
import greenlet
import mech6 as mech
M = sys.monitoring
H = {'arm': False, 'n': 0, 'to': None}
def hook(ev, args):
    if ev == 'sys.monitoring.register_callback' and H['arm']:
        H['n'] += 1
        if H['n'] == 5:
            H['arm'] = False
            H['to'].switch()                       # a greenlet switch inside register_callback's audit hook
sys.addaudithook(hook)

def trial(mut):
    mech.reset()
    if mut: mech.MUT.add(mut)
    def t(): raise KeyError
    X = mech.Tracer(t); X.__enter__()
    tid = mech.TOOL[0]
    M.free_tool_id(tid)                            # an outside party frees styxx's id (nobody takes it)
    def body():
        try: t()
        except KeyError: pass
        return 1
    X.run('A', body)                               # _unwind_on gated off; t's call is lost; A closes
    order = []
    def exit_X():
        order.append('X exit start'); X.__exit__(None, None, None); order.append('X exit done')
    def rec():
        order.append('rec start'); mech._locked(mech.reconcile); order.append('rec done (counted)')
    g1 = greenlet.greenlet(exit_X)
    g2 = greenlet.greenlet(rec)
    g1.parent = g2                                 # when X's exit finishes, control returns to g2
    H.update(arm=True, n=0, to=g1)
    g2.switch()
    r = X.result()
    mech.MUT.clear()
    return dict(order=order, X_calls=r['calls'], X_MONITOR_LOST=r['MONITOR_LOST'], flag=bool(X.core.flags.get('UNWIND_LOST')),
                reclaimed=mech.RECLAIMED[0], tool_ours=M.get_tool(tid) is mech.NAME)

if __name__ == '__main__':
    v = sys.version.split()[0]
    for mut in (None, 'blind_read_gated'):
        print(v, 'greenlet', greenlet.__version__, mut or 'spec', trial(mut), flush=True)
