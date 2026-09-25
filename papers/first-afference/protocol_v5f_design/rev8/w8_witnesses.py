# Revision 8: rev7/w7_witnesses.py run on rev8/mech8.py (the tee registration); unchanged otherwise. Revision 7 witnesses on rev7/mech7.py. EVERY trial runs in its own fresh subprocess of the same interpreter
# (python w7_witnesses.py CASE MUT [ARG]), which prints one JSON line; the parent prints one row per trial.
#   X158   (B1)   tracers P and Q both declare f; an outside party replaces styxx's PY_START callback on styxx's id;
#                 Q's section B calls f (lost); P exits first, then Q (and the Q-first order). Spec: both note
#                 MONITOR_LOST. Mutant cbrep_nocount (revision 6): Q, which lost the call, has no note.
#   X154b  (M4)   revision 6's audit-hook sweep of the exit's registration, one fresh subprocess per trial k = 1..5;
#                 the other tool's callbacks are read after the exit by exchange-and-restore, hook disarmed.
#   X154d  (N4, M5.2)  a yielding audit hook inside the RECLAIM's registration. (a) the hook frees styxx's id (nobody
#                 takes it) at the first register_callback event of each of the enter's two reclaims: both split with
#                 owner None and are not counted; the fall-through re-takes the SAME id. Spec (revision 7): the
#                 re-take is counted, P notes MONITOR_LOST. Mutant retake_nocount (revision 6's prototype rule): no
#                 note. (b) the hook's thread frees the id and another tool takes it: Q rebinds to id 3 (counted).
#   X157b  (N4)   a RAISING audit hook inside the reclaim's registration (Q's enter, after an outside free): Q's
#                 __enter__ propagates it; the id is left named (the take succeeded) and uncounted; P exits.
#   X157c  (F14, found in revision 7's model)  X157b's shape with a LOST call: P's section A opens after the free and
#                 loses t's raising call; the raising hook keeps the reclaim from counting; only the close's ungated
#                 event read notes it. Mutant blind_read_gated: P has no MONITOR_LOST, t's call lost (a silent loss).
#   X158b  (B1)   X158 (a) with a fault injected right after P's exit registration returns (the test hook
#                 'exit:registered'). Spec: the count was made inside the registration's call, so Q is noted. Mutant
#                 count_after_register (the critic's proposed form): the fault skips the count and Q's loss is silent.
#   X137h7 (rev. 7 form of X137h)  the rebinding count as the only detector: a rebinding to an id that still carries
#                 styxx's own callbacks, so the registration's in-call count finds nothing to count.
#   X137g  (N5)   revision 6's X137g with Q declaring f AND g, as the case text says.
#   X156c  (M3)   first coverage_trace() binds; then itertools.chain is replaced by a Python subclass and the module
#                 is reloaded (re-binding the vocabulary); the next coverage_trace() must refuse. Mutant check_once.
#   X156d  (N1)   collections.deque replaced (before import) by a Python subclass named 'deque' that drops maxlen.
#                 Spec refuses; mutant deque_by_name (revision 6's name test) binds it.
#   X37b   (N6)   sys.version_info replaced by a tuple subclass with micro 99 AFTER import, before coverage_trace().
#   RELOAD (B1, M1's reload paragraph)  P and Q live across importlib.reload; P exits first, then Q. Spec: both
#                 note MONITOR_LOST (the first exit's registration finds the pre-reload callbacks and counts it).
import sys, os, json, subprocess, threading, importlib, itertools, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

def child(case, mut, arg):
    if case == 'X156d':
        class deque(collections.deque):
            def __init__(self, iterable=(), maxlen=None): super().__init__(iterable)   # drops maxlen
        collections.deque = deque
    import mech8 as mech
    M = sys.monitoring; E = mech.E
    OTHER = 'other-tool'
    def other_cb(*a): return None
    def take_by_other(t):
        M.free_tool_id(t); M.use_tool_id(t, OTHER)
        for e in mech._EVS5: M.register_callback(t, e, other_cb)
    def cbs(t):                                     # the callback-read method: exchange, then restore
        out = []
        for e in mech._EVS5:
            c = M.register_callback(t, e, None); M.register_callback(t, e, c); out.append(c)
        return out
    H = {'arm': False, 'n': 0, 'act': None, 'tid': None}
    def hook(ev, args):
        if ev == 'sys.monitoring.register_callback' and H['arm'] and threading.get_ident() == H['tid']:
            H['n'] += 1
            H['act'](H['n'])
    if case in ('X154b', 'X154d', 'X157b', 'X157c'): sys.addaudithook(hook)
    if case == 'X156c':
        if mut: mech.MUT.update(mut.split('+'))
        mech.Tracer(lambda: 0)                     # the first coverage_trace(): binds
        class chain(itertools.chain): pass
        itertools.chain = chain
        importlib.reload(mech)                      # re-binds the one-call vocabulary (MUT and _MON are kept)
        try: mech.Tracer(lambda: 0); return dict(refused=None, chain_bound=mech._chain.__module__ + '.' + mech._chain.__qualname__)
        except mech.Unsupported as e: return dict(refused=str(e))
    if case == 'X156d':
        if mut: mech.MUT.update(mut.split('+'))
        try: mech.Tracer(lambda: 0); return dict(refused=None, maxlen=mech._CONSUME.__self__.maxlen)
        except mech.Unsupported as e: return dict(refused=str(e))
    if case == 'X37b':
        class V(tuple): pass
        real = sys.version_info
        sys.version_info = V((real[0], real[1], 99, 'final', 0))
        try: mech.Tracer(lambda: 0); return dict(refused=None)
        except mech.Unsupported as e: return dict(refused=str(e))
        finally: sys.version_info = real
    mech.reset()
    if mut: mech.MUT.update(mut.split('+'))
    if case in ('X158', 'X158c'):                  # revision 8 (N4): X158c registers None over the entry callback
        def f(): return 1
        P = mech.Tracer(f); P.__enter__()
        Q = mech.Tracer(f); Q.__enter__()          # joins P's mint of f
        P.run('A', f)                               # counted: before the replacement
        t = mech.TOOL[0]
        M.register_callback(t, E.PY_START, None if case == 'X158c' else other_cb)   # outside party replaces (X158c: removes) styxx's entry callback
        Q.run('B', f)                               # lost
        first, second = (P, Q) if arg == 'P-first' else (Q, P)
        first.__exit__(None, None, None); second.__exit__(None, None, None)
        return dict(order=arg, P_calls=P.result()['calls'], P_lost=P.result()['MONITOR_LOST'],
                    Q_calls=Q.result()['calls'], Q_lost=Q.result()['MONITOR_LOST'],
                    entry_cb_restored=cbs(t)[0] is mech._on_entry)
    if case == 'X154b':
        k = int(arg)
        def f(): return 1
        tr = mech.Tracer(f); tr.__enter__(); tr.run('A', f)
        t = mech.TOOL[0]
        def act(n):
            if n == k:
                H['arm'] = False
                th = threading.Thread(target=take_by_other, args=(t,)); th.start(); th.join()
        H.update(arm=True, n=0, act=act, tid=threading.get_ident())
        try: tr.__exit__(None, None, None); ex = 'returned'
        except Exception as e: ex = 'raised %r' % e
        H['arm'] = False
        after = cbs(t)
        return dict(k=k, exit=ex, owner=M.get_tool(t), other_replaced_at=[i + 1 for i, c in enumerate(after) if c is not other_cb],
                    calls=tr.result()['calls'], monitor_lost=tr.result()['MONITOR_LOST'])
    if case == 'X154d':
        def f(): return 1
        def g(): return 2
        P = mech.Tracer(f); P.__enter__(); P.run('A', f)
        t = mech.TOOL[0]
        M.free_tool_id(t)                           # outside party frees styxx's id (nobody takes it)
        def act(n):
            if arg == 'free' and n in (1, 2):       # first event of each reclaim's registration: free the id again
                th = threading.Thread(target=M.free_tool_id, args=(t,)); th.start(); th.join()
            if arg == 'take' and n == 1:
                H['arm'] = False
                th = threading.Thread(target=take_by_other, args=(t,)); th.start(); th.join()
        H.update(arm=True, n=0, act=act, tid=threading.get_ident())
        Q = mech.Tracer(g); Q.__enter__()
        H['arm'] = False
        log = [x[:3] for x in mech.REG_LOG]
        tool_after = mech.TOOL[0]
        Q.run('B', g); Q.__exit__(None, None, None); P.__exit__(None, None, None)
        return dict(variant=arg, registrations=log, tool_after_enter=tool_after, reclaimed=mech.RECLAIMED[0],
                    P_calls=P.result()['calls'], P_lost=P.result()['MONITOR_LOST'],
                    Q_calls=Q.result()['calls'], Q_lost=Q.result()['MONITOR_LOST'])
    if case == 'X157b':
        class Denied(Exception): pass
        def f(): return 1
        def g(): return 2
        P = mech.Tracer(f); P.__enter__(); P.run('A', f)
        t = mech.TOOL[0]
        M.free_tool_id(t)
        def act(n):
            if n == 2:
                H['arm'] = False; raise Denied('audit hook refuses')
        H.update(arm=True, n=0, act=act, tid=threading.get_ident())
        Q = mech.Tracer(g)
        try: Q.__enter__(); qe = 'entered'
        except Denied as e: qe = 'Denied propagated'
        H['arm'] = False
        mid = dict(tool_ours=M.get_tool(t) is mech.NAME, reclaimed=mech.RECLAIMED[0], guard_dead=mech._GUARD['hint'] is not None)
        P.__exit__(None, None, None)
        R = mech.Tracer(g); R.__enter__(); R.run('C', g); R.__exit__(None, None, None)
        return dict(Q_enter=qe, after_Q=mid, P_calls=P.result()['calls'], P_lost=P.result()['MONITOR_LOST'],
                    R_calls=R.result()['calls'], R_lost=R.result()['MONITOR_LOST'], state=mech.state())
    if case == 'X157c':                             # X157b with a lost call: F14's rule without greenlets
        class Denied(Exception): pass
        def t(): raise KeyError
        def g(): return 2
        P = mech.Tracer(t); P.__enter__()
        tid = mech.TOOL[0]
        M.free_tool_id(tid)                         # outside party frees styxx's id (nobody takes it)
        def body():
            try: t()
            except KeyError: pass
            return 1
        P.run('A', body)                            # _unwind_on gated off (not named): t's unwind is not seen
        def act(n):
            if n == 2:
                H['arm'] = False; raise Denied('audit hook refuses')
        H.update(arm=True, n=0, act=act, tid=threading.get_ident())
        Q = mech.Tracer(g)
        try: Q.__enter__(); qe = 'entered'
        except Denied: qe = 'Denied propagated'
        H['arm'] = False
        P.__exit__(None, None, None)
        return dict(Q_enter=qe, reclaimed=mech.RECLAIMED[0], P_calls=P.result()['calls'], P_lost=P.result()['MONITOR_LOST'],
                    P_flag=bool(P.core.flags.get('UNWIND_LOST')))
    if case == 'X137h7':                            # revision 7 form of X137h: the rebinding count is the only detector
        def t(): raise KeyError
        def g(): return 2
        def h(): return 3
        def raise_cb(*a): return None
        P = mech.Tracer(g); P.__enter__()            # takes id 4
        assert mech.TOOL[0] == 4
        M.set_events(4, 0); M.free_tool_id(4); M.use_tool_id(4, 'tool-A')    # A takes id 4, leaving styxx's callbacks
        M.register_callback(4, E.RAISE, raise_cb)
        Q = mech.Tracer(h); Q.__enter__()            # rebinds to id 3 (fresh: counted)
        R = mech.Tracer(t); R.__enter__()            # entered after that rebinding
        def body():
            M.free_tool_id(3); M.use_tool_id(3, 'tool-B')                    # B takes id 3, keeping PY_UNWIND set
            for e in mech._EVS5: M.register_callback(3, e, other_cb)         # and replaces styxx's callbacks there
            try: t()                                                          # entry delivered to B: lost
            except KeyError: pass
            return 1
        R.run('A', body)                             # A's close: the event is still set on id 3: no flag
        M.register_callback(4, E.RAISE, None); M.free_tool_id(4)             # A frees id 4 (styxx's callbacks still there)
        S = mech.Tracer(g); S.__enter__()            # 3 is B's: rebinds to id 4, whose previous callbacks are styxx's
        tool_after = mech.TOOL[0]
        S.__exit__(None, None, None); Q.__exit__(None, None, None); R.__exit__(None, None, None); P.__exit__(None, None, None)
        return dict(tool_after=tool_after, R_calls=R.result()['calls'], R_lost=R.result()['MONITOR_LOST'],
                    registrations=[x[:3] for x in mech.REG_LOG[-3:]],
                    **({} if arg != 'all' else dict(P_calls=P.result()['calls'], P_lost=P.result()['MONITOR_LOST'],   # revision 8 (N7)
                        Q_calls=Q.result()['calls'], Q_lost=Q.result()['MONITOR_LOST'],
                        S_calls=S.result()['calls'], S_lost=S.result()['MONITOR_LOST'])))
    if case == 'X158b':                             # B1's count must be inside the registration's call
        class Injected(Exception): pass
        def f(): return 1
        P = mech.Tracer(f); P.__enter__()
        Q = mech.Tracer(f); Q.__enter__()
        P.run('A', f)
        t = mech.TOOL[0]
        M.register_callback(t, E.PY_START, other_cb)
        Q.run('B', f)                               # lost
        def hk(point):
            if point == 'exit:registered': mech._HOOK[0] = None; raise Injected('fault after the registration')
        mech._HOOK[0] = hk
        try: P.__exit__(None, None, None); pe = 'returned'
        except Injected: pe = 'Injected propagated'
        mech._HOOK[0] = None
        Q.__exit__(None, None, None)
        return dict(P_exit=pe, Q_calls=Q.result()['calls'], Q_lost=Q.result()['MONITOR_LOST'],
                    entry_cb_restored=cbs(t)[0] is mech._on_entry)
    if case == 'X137g':
        def f(): return 1
        def g(): return 2
        P = mech.Tracer(f); P.__enter__()
        t0 = mech.TOOL[0]
        take_by_other(t0)
        Q = mech.Tracer(f, g); Q.__enter__()        # joins P's mint of f, mints g, rebinds to id 3
        t1 = mech.TOOL[0]
        P.run('A', f); Q.run('B', f); Q.run('B', g)
        Q.__exit__(None, None, None); P.__exit__(None, None, None)
        return dict(tool_before=t0, tool_after=t1, P_calls=P.result()['calls'], P_lost=P.result()['MONITOR_LOST'],
                    Q_calls=Q.result()['calls'], Q_lost=Q.result()['MONITOR_LOST'])
    if case == 'RELOAD':
        def f(): return 1
        P = mech.Tracer(f); P.__enter__(); P.run('A', f)
        Q = mech.Tracer(f); Q.__enter__(); Q.run('B', f)
        importlib.reload(mech)                      # kept: registries, id, name, RECLAIMED; re-bound: the callbacks
        if mut: mech.MUT.update(mut.split('+'))
        P.__exit__(None, None, None); Q.__exit__(None, None, None)
        return dict(P_calls=P.result()['calls'], P_lost=P.result()['MONITOR_LOST'],
                    Q_calls=Q.result()['calls'], Q_lost=Q.result()['MONITOR_LOST'], tool=mech.TOOL[0])
    raise SystemExit('unknown case')

def run(case, mut='', arg=''):
    p = subprocess.run([sys.executable, __file__, case, mut or '-', arg or '-'], capture_output=True, text=True, timeout=120)
    line = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ('ERROR ' + (p.stderr.strip().splitlines() or ['?'])[-1])
    print(sys.version.split()[0], '%-7s %-15s %-8s %s' % (case, mut or 'spec', arg, line), flush=True)

if __name__ == '__main__':
    if len(sys.argv) == 4:
        case, mut, arg = sys.argv[1], sys.argv[2], sys.argv[3]
        out = child(case, None if mut == '-' else mut, None if arg == '-' else arg)
        print(json.dumps(out, default=repr)); sys.exit(0)
    for mut in (None, 'cbrep_nocount', 'count_after_register'):
        for order in ('P-first', 'Q-first'): run('X158', mut, order)
    for mut in (None, 'count_after_register', 'cbrep_nocount'): run('X158b', mut)
    for mut in (None, 'cbrep_nocount'): run('RELOAD', mut)
    for mut in (None, 'rebind_count_none'): run('X137h7', mut)
    for mut in (None, 'reg_rev5'):
        for k in '12345': run('X154b', mut, k)
    for mut in (None, 'retake_nocount'): run('X154d', mut, 'free')
    for mut in (None, 'rebind_count_none'): run('X154d', mut, 'take')
    run('X157b')
    for mut in (None, 'blind_read_gated'): run('X157c', mut)
    for mut in (None, 'rebind_no_local'): run('X137g', mut)
    for mut in (None, 'check_once'): run('X156c', mut)
    for mut in (None, 'deque_by_name'): run('X156d', mut)
    run('X37b')
