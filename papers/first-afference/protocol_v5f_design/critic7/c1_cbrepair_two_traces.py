# critic7 c1: X5's registration REPAIRS a replaced callback for every later trace, but only the exiting trace notes it.
# Shape: tracers P and Q both declare t (t raises out of its body, so it needs PY_START + PY_UNWIND to count; a plain
# returning f is used too). An outside party (not a tool owner) replaces styxx's PY_START callback on styxx's id with its
# own (register_callback needs no ownership). Q's section B calls f: lost (PY_START went to the foreign callback).
# P exits first: its X5 registration gets the foreign callback back as "previous" -> P notes MONITOR_LOST, and the
# registration repairs the slot. Q exits: its X5 registration finds all five previous callbacks styxx's, _LOST unchanged,
# local events intact, no UNWIND_LOST flag -> Q has NO MONITOR_LOST although its call was lost through the outside party.
# L-MONITOR says a callback replacement is silent only if the PARTY restores it before exit; here the machinery does.
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run'))
import mech6 as mech
M = sys.monitoring; E = mech.E

def foreign_cb(*a): return None

def trial(order):
    mech.reset()
    def f(): return 1
    P = mech.Tracer(f); P.__enter__()
    Q = mech.Tracer(f); Q.__enter__()              # joins P's mint of f
    t = mech.TOOL[0]
    M.register_callback(t, E.PY_START, foreign_cb) # outside party replaces styxx's entry callback (no free, no take)
    Q.run('B', f)                                  # f's PY_START goes to foreign_cb: lost
    first, second = (P, Q) if order == 'P-first' else (Q, P)
    first.__exit__(None, None, None); second.__exit__(None, None, None)
    return dict(P_calls=P.result()['calls'], P_lost=P.result()['MONITOR_LOST'],
                Q_calls=Q.result()['calls'], Q_lost=Q.result()['MONITOR_LOST'])

if __name__ == '__main__':
    v = sys.version.split()[0]
    for order in ('P-first', 'Q-first'):
        print(v, order, trial(order), flush=True)
