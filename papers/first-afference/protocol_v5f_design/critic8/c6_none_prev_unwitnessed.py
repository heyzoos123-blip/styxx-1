# critic8/c6: revision 7 keeps None previous callbacks in the in-call count on purpose ("A party that registers None
# over styxx's callback removes it, which is a loss, and must count"; Revision 7, "Considered and rejected"). Which
# exam case witnesses that rule? X158 replaces the callback with a callable; G_ATOM's matrix has no None-previous case.
# Here: X158's shape with the outside party registering None over styxx's PY_START callback, under the spec and under
# a mutant that does not count None previous callbacks (a Python-level stand-in for the mutated pipeline).
import sys, os, json, subprocess
sys.path.insert(0, '/home/user/styxx-1/papers/first-afference/protocol_v5f_design/rev7')
def child(mut, order):
    import mech7 as mech
    M = sys.monitoring; E = mech.E
    mech.reset()
    if mut == 'exclude_none':
        def reg(t):
            out = []
            for e, f in zip(mech._EVS5, mech._FNS5):
                if M.get_tool(t) is not mech.NAME: break
                p = M.register_callback(t, e, f)
                if p is not f and p is not None: mech._REPL_APPEND(True); out.append(None)
            return out + [M.get_tool(t)]
        mech._register_named = reg
    def f(): return 1
    P = mech.Tracer(f); P.__enter__(); Q = mech.Tracer(f); Q.__enter__()
    P.run('A', f)
    t = mech.TOOL[0]
    M.register_callback(t, E.PY_START, None)      # the outside party removes styxx's entry callback
    Q.run('B', f)                                 # lost
    a, b = (P, Q) if order == 'P-first' else (Q, P)
    a.__exit__(None, None, None); b.__exit__(None, None, None)
    return dict(P=P.result()['calls'], P_lost=P.result()['MONITOR_LOST'], Q=Q.result()['calls'], Q_lost=Q.result()['MONITOR_LOST'])
if __name__ == '__main__':
    if len(sys.argv) == 3: print(json.dumps(child(sys.argv[1], sys.argv[2]))); sys.exit(0)
    for mut in ('spec', 'exclude_none'):
        for order in ('P-first', 'Q-first'):
            p = subprocess.run([sys.executable, __file__, mut, order], capture_output=True, text=True)
            print(sys.version.split()[0], mut, order, (p.stdout.strip() or p.stderr[-400:]), flush=True)
