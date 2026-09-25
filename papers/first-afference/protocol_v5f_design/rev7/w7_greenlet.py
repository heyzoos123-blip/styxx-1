# Revision 7 (N5): X137f exactly as the case text states it, on greenlet 3.5.6 (rev6/site312, rev6/site313):
# g2's transaction is the ENTER of a tracer Y declaring g (rev6/w6_greenlet.py used a bare reconciliation), and the
# audit hook switches at the 5th sys.monitoring.register_callback event of g2's reclaim. Spec: X notes MONITOR_LOST
# through the close's ungated event read; mutant blind_read_gated (revision 4's form): no note, t's call lost.
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'rev6', 'site%d%d' % sys.version_info[:2]))
import greenlet
import mech7 as mech
M = sys.monitoring
H = {'arm': False, 'n': 0, 'to': None}
def hook(ev, args):
    if ev == 'sys.monitoring.register_callback' and H['arm']:
        H['n'] += 1
        if H['n'] == 5:
            H['arm'] = False
            H['to'].switch()
sys.addaudithook(hook)

def trial(mut):
    mech.reset(); mech.RECLAIMED[0] = 0
    if mut: mech.MUT.add(mut)
    def t(): raise KeyError
    def g(): return 2
    X = mech.Tracer(t); X.__enter__()
    tid = mech.TOOL[0]
    M.free_tool_id(tid)
    def body():
        try: t()
        except KeyError: pass
        return 1
    X.run('A', body)
    order = []
    Y = mech.Tracer(g)
    def exit_X():
        order.append('X exit start'); X.__exit__(None, None, None); order.append('X exit done')
    def enter_Y():
        order.append('Y enter start'); Y.__enter__(); order.append('Y enter done (reclaim counted)')
    g1 = greenlet.greenlet(exit_X); g2 = greenlet.greenlet(enter_Y); g1.parent = g2
    H.update(arm=True, n=0, to=g1)
    g2.switch()
    Y.run('B', g); Y.__exit__(None, None, None)
    r = X.result()
    mech.MUT.clear()
    return dict(order=order, X_calls=r['calls'], X_MONITOR_LOST=r['MONITOR_LOST'], flag=bool(X.core.flags.get('UNWIND_LOST')),
                reclaimed=mech.RECLAIMED[0], Y_calls=Y.result()['calls'], Y_lost=Y.result()['MONITOR_LOST'])

if __name__ == '__main__':
    v = sys.version.split()[0]
    for mut in (None, 'blind_read_gated'):
        print(v, 'X137f greenlet', greenlet.__version__, mut or 'spec', trial(mut), flush=True)
