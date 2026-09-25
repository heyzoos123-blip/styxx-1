# critic8/c1: revision 7 claims (M7 "The registration", line ~718) that "A fault, an audit hook, a thread switch or a
# greenlet switch can land between two exchanges, but never between an exchange and its count."
# But _register now DROPS each previous callback inside the consuming call (map_next decrefs its args right after
# _is_not returns and BEFORE filter/_LOST_APPEND run). If an outside party's replacement callback is only referenced by
# the monitoring slot, its deallocation (a __del__, a weakref.finalize, a closure's __del__) runs Python code there.
# (i)  observe: inside the finalizer, len(_REPL) is still the pre-count value (the repair has landed, the count not).
# (ii) exploit (X158's shape): the finalizer switches greenlets; the other greenlet runs Q's exit, which steals the
#      robust mutex (P's frames are off the chain), finds all five callbacks styxx's and _LOST unchanged: Q's lost
#      call is silent. Revision 6's in-X5 form is the same; revision 7's in-call count does not close it.
import sys, os, json, subprocess
REV7 = '/home/user/styxx-1/papers/first-afference/protocol_v5f_design/rev7'
REV6 = '/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/rev6'
sys.path.insert(0, REV7); sys.path.insert(0, os.path.join(REV6, 'site%d%d' % sys.version_info[:2]))

def child(mode, order):
    import mech7 as mech
    M = sys.monitoring; E = mech.E
    mech.reset()
    def f(): return 1
    P = mech.Tracer(f); P.__enter__()
    Q = mech.Tracer(f); Q.__enter__()
    P.run('A', f)
    t = mech.TOOL[0]
    seen = {}
    if mode == 'observe':
        class Repl:
            def __call__(self, *a): return None
            def __del__(self):
                seen['len_REPL_in_del'] = len(mech._REPL)
                seen['slot_is_styxx_in_del'] = None   # (reading the slot would itself raise an audit event; skip)
    else:
        import greenlet
        def q_exit():
            seen['q_exit_ran_inside_P_register'] = True
            Q.__exit__(None, None, None)
        class Repl:
            def __call__(self, *a): return None
            def __del__(self):
                seen['len_REPL_in_del'] = len(mech._REPL)
                g2 = greenlet.greenlet(q_exit); g2.switch()     # g2's parent is this greenlet; it returns here
    M.register_callback(t, E.PY_START, Repl())   # the slot holds the ONLY reference
    Q.run('B', f)                                 # lost: PY_START goes to Repl
    before = len(mech._REPL)
    if order == 'P-first':
        P.__exit__(None, None, None)
        if not Q.core.exited: Q.__exit__(None, None, None)
    else:
        Q.__exit__(None, None, None); P.__exit__(None, None, None)
    return dict(mode=mode, order=order, len_REPL_before_P_exit=before, **seen,
                len_REPL_after=len(mech._REPL),
                P_calls=P.result()['calls'], P_lost=P.result()['MONITOR_LOST'],
                Q_calls=Q.result()['calls'], Q_lost=Q.result()['MONITOR_LOST'])

if __name__ == '__main__':
    if len(sys.argv) == 3:
        print(json.dumps(child(sys.argv[1], sys.argv[2]), default=repr)); sys.exit(0)
    for mode in ('observe', 'greenlet'):
        for order in ('P-first',):
            p = subprocess.run([sys.executable, __file__, mode, order], capture_output=True, text=True, timeout=120)
            out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else 'ERROR ' + p.stderr[-800:]
            print(sys.version.split()[0], mode, order, out, flush=True)
