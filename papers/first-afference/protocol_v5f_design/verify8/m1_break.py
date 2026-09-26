# verify8: one attempt to break revision 8's M1 fix (tee registration) on rev8/mech8.py.
# Shapes (all X158-like, greenlet-switching finalizer runs Q's exit):
#   wrf     : the finalizer is a weakref.finalize on the replacement (not __del__)
#   closure : the finalizer is __del__ of an object held only by the replacement's closure
#   two     : PY_START and PY_RETURN both replaced; each finalizer records len(_REPL); the first switches
#   raise   : an audit hook raises at P's X5 exchange 3 after exchange 1 repaired the replacement;
#             the finalizer runs when the exception (and the traceback holding _register's frame) is dropped
# Expect under spec: every finalizer sees the post-count len, and Q is noted (Q_lost True). Under reg_rev7: some silent.
import sys, os, json, subprocess, gc, weakref
R8 = '/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/rev8'
R6 = '/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/rev6'
sys.path.insert(0, R8); sys.path.insert(0, os.path.join(R6, 'site%d%d' % sys.version_info[:2]))

def child(shape, form):
    import mech8 as mech, greenlet
    M = sys.monitoring; E = mech.E
    mech.reset()
    if form == 'rev7': mech.MUT.add('reg_rev7')
    def f(): return 1
    P = mech.Tracer(f); P.__enter__()
    Q = mech.Tracer(f); Q.__enter__()
    P.run('A', f)
    t = mech.TOOL[0]
    seen = {'fin_len': []}
    def q_exit():
        if not Q.core.exited: Q.__exit__(None, None, None)
    def fin():
        seen['fin_len'].append(len(mech._REPL))
        if len(seen['fin_len']) == 1:
            greenlet.greenlet(q_exit).switch()
    class Plain:
        def __call__(self, *a): return None
    class Del(Plain):
        def __del__(self): fin()
    if shape == 'wrf':
        r = Plain(); weakref.finalize(r, fin); M.register_callback(t, E.PY_START, r); del r
    elif shape == 'closure':
        class Held:
            def __del__(self): fin()
        def mk():
            h = Held()
            def repl(*a):
                h; return None
            return repl
        M.register_callback(t, E.PY_START, mk())
    elif shape == 'two':
        M.register_callback(t, E.PY_START, Del()); M.register_callback(t, E.PY_RETURN, Del())
    elif shape == 'raise':
        M.register_callback(t, E.PY_START, Del())
    Q.run('B', f)
    before = len(mech._REPL)
    if shape == 'raise':
        cnt = [0]; armed = [True]
        def hook(ev, args):
            if armed[0] and ev == 'sys.monitoring.register_callback':
                cnt[0] += 1
                if cnt[0] == 3: armed[0] = False; raise RuntimeError('hook3')
        sys.addaudithook(hook)
        try:
            P.__exit__(None, None, None)
        except RuntimeError as e:
            seen['P_exit'] = 'raised ' + str(e)
        seen['len_after_except'] = len(mech._REPL)
        gc.collect()
    else:
        P.__exit__(None, None, None)
    if not Q.core.exited: Q.__exit__(None, None, None)
    return dict(shape=shape, form=form, before=before, **seen, len_after=len(mech._REPL),
                Q_calls=Q.result()['calls'], Q_lost=Q.result()['MONITOR_LOST'],
                P_lost=P.result()['MONITOR_LOST'] if P.core.exited else 'P not exited')

if __name__ == '__main__':
    if len(sys.argv) == 3:
        print(json.dumps(child(sys.argv[1], sys.argv[2]), default=repr)); sys.exit(0)
    for form in ('spec', 'rev7'):
        for shape in ('wrf', 'closure', 'two', 'raise'):
            p = subprocess.run([sys.executable, __file__, shape, form], capture_output=True, text=True, timeout=120)
            out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else 'ERROR ' + p.stderr[-600:]
            print(sys.version.split()[0], form, shape, out, flush=True)
