# Revision 6 witnesses on rev6/mech6.py, each under the spec and under its single-rule mutant:
#   X154b  an audit-hook sweep of the exit's registration (k = 1..5): the hook's k-th call runs the interference on
#          another thread (free styxx's id; another tool takes it and registers callbacks for all five events) and
#          waits for it. Spec: exactly the k-th event's callback of the other tool is replaced; the trace notes
#          MONITOR_LOST; __exit__ returns. Mutant reg_rev5 (one gate before all five): 6-k callbacks replaced.
#   X154c  first acquisition, hook at k = 5 (the last exchange): spec moves on to id 3 and the trace counts;
#          mutant reg_no_owner (no owner read after the last exchange) keeps id 4, which the other tool holds.
#   X137g  another tool takes styxx's id while tracer P (declaring f) is live; tracer Q enters and rebinds to id 3;
#          P's section then calls f. Spec: P counts f (local events for P's mint were set on id 3) and notes
#          MONITOR_LOST; mutant rebind_no_local: f is not counted.
#   X157   an audit hook that raises at the exit's second register_callback: __exit__ propagates it (see
#          r6_b1_register.py's exit-raise row).
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech6 as mech
M = sys.monitoring; E = mech.E
OTHER = 'other-tool'
def other_cb(*a): pass
H = {'arm': False, 'k': 0, 'n': 0, 'fn': None}
def hook(ev, args):
    if ev == 'sys.monitoring.register_callback' and H['arm']:
        H['n'] += 1
        if H['n'] == H['k']:
            H['arm'] = False
            th = threading.Thread(target=H['fn']); th.start(); th.join()
sys.addaudithook(hook)

def take_by_other(t):
    M.free_tool_id(t); M.use_tool_id(t, OTHER)
    for e in mech._EVS5: M.register_callback(t, e, other_cb)

def cbs(t):
    out = []
    for e in mech._EVS5:
        c = M.register_callback(t, e, None); M.register_callback(t, e, c); out.append(c)
    return out

def free_all():
    for t in (3, 4):
        if M.get_tool(t) is not None:
            for e in mech._EVS5: M.register_callback(t, e, None)
            M.set_events(t, 0); M.free_tool_id(t)

def x154b(k, mut):
    free_all(); mech.reset()
    if mut: mech.MUT.add(mut)
    def f(): return 1
    tr = mech.Tracer(f); tr.__enter__(); tr.run('A', f)
    t = mech.TOOL[0]
    H.update(arm=True, k=k, n=0, fn=lambda: take_by_other(t))
    try: tr.__exit__(None, None, None); ex = 'returned'
    except Exception as e: ex = 'raised %r' % e
    H['arm'] = False
    after = cbs(t)
    replaced = [i + 1 for i, c in enumerate(after) if c is not other_cb]
    mech.MUT.clear()
    return dict(exit=ex, owner=M.get_tool(t), other_callbacks_replaced_at_events=replaced,
                monitor_lost=tr.result()['MONITOR_LOST'], calls=tr.result()['calls'])

def x154c(mut):
    free_all(); mech.MUT.clear(); mech._ANCHORS.clear(); mech.TOOL[0] = None; mech.bind()
    if mut: mech.MUT.add(mut)
    def f():
        try: raise KeyError
        except KeyError: pass
        return 1
    def body():
        return f()
    H.update(arm=True, k=5, n=0, fn=lambda: take_by_other(4))
    tr = mech.Tracer(f)
    try: tr.__enter__(); err = None
    except Exception as e: err = repr(e)
    H['arm'] = False
    tool = mech.TOOL[0]
    if err is None:
        tr.run('A', body); tr.__exit__(None, None, None)
    res = tr.result()
    mech.MUT.clear()
    return dict(enter_error=err, tool=tool, owner_of_4=M.get_tool(4), calls=res['calls'], monitor_lost=res['MONITOR_LOST'])

def x137g(mut):
    free_all(); mech.reset()
    if mut: mech.MUT.add(mut)
    def f(): return 1
    def g(): return 2
    P = mech.Tracer(f); P.__enter__()
    t0 = mech.TOOL[0]
    take_by_other(t0)                                # another tool takes styxx's id while P is live
    Q = mech.Tracer(g); Q.__enter__()                # Q's enter rebinds to the other id
    t1 = mech.TOOL[0]
    P.run('A', f)                                    # P's hit of f after the rebinding
    Q.run('B', g); Q.__exit__(None, None, None); P.__exit__(None, None, None)
    mech.MUT.clear()
    return dict(tool_before=t0, tool_after=t1, P_calls=P.result()['calls'], P_lost=P.result()['MONITOR_LOST'],
                Q_calls=Q.result()['calls'], Q_lost=Q.result()['MONITOR_LOST'])

def x137h(mut):
    """Another tool takes styxx's id (keeping the inherited global events) while P's section A is open; t raises
    inside A and is lost; A closes (the event is still set on the taken id: no flag); Q enters and rebinds; P exits."""
    free_all(); mech.reset()
    if mut: mech.MUT.add(mut)
    def t():
        raise KeyError
    def g(): return 2
    P = mech.Tracer(t); P.__enter__()
    t0 = mech.TOOL[0]
    def body():
        take_by_other(t0)
        try: t()
        except KeyError: pass
        return 1
    P.run('A', body)
    Q = mech.Tracer(g); Q.__enter__(); t1 = mech.TOOL[0]
    Q.run('B', g); Q.__exit__(None, None, None); P.__exit__(None, None, None)
    mech.MUT.clear()
    return dict(tool_after=t1, P_calls=P.result()['calls'], P_lost=P.result()['MONITOR_LOST'])

if __name__ == '__main__':
    for mut in (None, 'rebind_count_none'):
        print(sys.version.split()[0], 'X137h', mut or 'spec', x137h(mut), flush=True)
    v = sys.version.split()[0]
    for mut in (None, 'reg_rev5'):
        for k in (1, 2, 3, 4, 5):
            print(v, 'X154b', mut or 'spec', 'k=%d' % k, x154b(k, mut), flush=True)
    for mut in (None, 'reg_no_owner'):
        print(v, 'X154c', mut or 'spec', x154c(mut), flush=True)
    for mut in (None, 'rebind_no_local'):
        print(v, 'X137g', mut or 'spec', x137g(mut), flush=True)
