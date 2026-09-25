# Revision 6, B1: _register under an audit hook on 'sys.monitoring.register_callback' that (1) yields to a thread that
# frees styxx's id and lets a foreign tool take it and register callbacks, at hook k = 1..5; (2) raises at hook k.
# Revision 6 (per-exchange gate + owner read after the last exchange) against revision 5's form (MUT 'reg_rev5').
# Reported per (form, k): which foreign callbacks styxx replaced, how many exchanges landed on the foreign id, what
# the registration reported (verdict, n, owner), and whether RECLAIMED (the _LOST counter) rose.
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech6 as mech
M = sys.monitoring; E = mech.E
def foreign_cb(*a): pass
FOREIGN = 'foreign-profiler'
state = {'arm': False, 'k': 0, 'hits': 0, 'mode': None}
go = threading.Event(); done = threading.Event()
def hook(ev, args):
    if ev != 'sys.monitoring.register_callback' or not state['arm']: return
    state['hits'] += 1
    if state['hits'] == state['k']:
        if state['mode'] == 'switch':
            state['arm'] = False; go.set(); done.wait(5)      # blocks: a real thread switch inside register_callback
        elif state['mode'] == 'raise':
            state['arm'] = False; raise RuntimeError('denied by sandbox')
sys.addaudithook(hook)

def foreign(t):
    go.wait(10)
    M.free_tool_id(t); M.use_tool_id(t, FOREIGN)
    for e in (E.PY_START, E.PY_RETURN, E.PY_UNWIND): M.register_callback(t, e, foreign_cb)
    done.set()

def read_cbs(t):
    out = {}
    for e in mech._EVS5:
        c = M.register_callback(t, e, None); M.register_callback(t, e, c); out[e] = c
    return out

def clean(t):
    for e in mech._EVS5: M.register_callback(t, e, None)
    if M.get_tool(t) is not None: M.free_tool_id(t)

NAMES = {E.PY_START: 'START', E.PY_RESUME: 'RESUME', E.PY_RETURN: 'RETURN', E.PY_YIELD: 'YIELD', E.PY_UNWIND: 'UNWIND'}
def switch_trial(form, k):
    mech.reset(); mech.MUT.clear()
    if form == 'rev5': mech.MUT.add('reg_rev5')
    t = mech.TOOL[0]
    go.clear(); done.clear(); state.update(arm=True, k=k, hits=0, mode='switch')
    th = threading.Thread(target=foreign, args=(t,)); th.start()
    lost0 = mech.RECLAIMED[0]
    r = mech._register_named(t)
    state['arm'] = False; go.set(); th.join()
    owner = M.get_tool(t)
    cbs = read_cbs(t)
    replaced = sorted(NAMES[e] for e in (E.PY_START, E.PY_RETURN, E.PY_UNWIND) if cbs[e] is not foreign_cb)
    added = sorted(NAMES[e] for e in (E.PY_RESUME, E.PY_YIELD) if cbs[e] is not None and owner == FOREIGN)
    v = mech.reg_verdict(r) if form == 'rev6' else ('(none)', len(r) - 1, None)
    out = dict(owner_after=owner, foreign_callbacks_replaced=replaced, styxx_leftovers_on_foreign_id_from_before_the_free=added,
               verdict=v[0], n=v[1], reported_owner=v[2])
    clean(t); mech.MUT.clear()
    return out

def raise_trial(form, k):
    mech.reset(); mech.MUT.clear()
    if form == 'rev5': mech.MUT.add('reg_rev5')
    t = mech.TOOL[0]
    for e in mech._EVS5: M.register_callback(t, e, None)
    state.update(arm=True, k=k, hits=0, mode='raise')
    try: mech._register_named(t); out = 'returned'
    except RuntimeError as e: out = 'raised'
    state['arm'] = False
    cbs = read_cbs(t)
    regd = [NAMES[e] for e, f in mech.CALLBACKS if cbs[e] is f]
    mech.MUT.clear()
    return dict(step=out, registered=regd)

def exit_raise_trial():
    """X5: an audit hook that raises at the exit's re-registration. __exit__ propagates it; X6-X8 do not run."""
    mech.reset(); mech.MUT.clear()
    def f(): return 1
    tr = mech.Tracer(f); tr.__enter__(); tr.run('A', f)
    state.update(arm=True, k=2, hits=0, mode='raise')
    try: tr.__exit__(None, None, None); out = 'returned'
    except RuntimeError: out = 'raised out of __exit__'
    state['arm'] = False
    res = dict(exit=out, exited_committed=tr.core.exited, anchors=len(mech._ANCHORS),
               mutex_owner_dead=(mech._GUARD['hint'] is None or not mech._tok_alive(mech._GUARD['hint'])))
    g = lambda: 2
    tr2 = mech.Tracer(g); tr2.__enter__(); tr2.run('B', g); tr2.__exit__(None, None, None)
    res['next_trace'] = tr2.result()['calls']; res['next_trace_lost'] = tr2.result()['MONITOR_LOST']
    return res

if __name__ == '__main__':
    v = sys.version.split()[0]
    for form in ('rev5', 'rev6'):
        for k in (1, 2, 3, 4, 5):
            print(v, 'switch', form, 'hook', k, switch_trial(form, k), flush=True)
    for form in ('rev5', 'rev6'):
        for k in (1, 3, 5):
            print(v, 'raise ', form, 'hook', k, raise_trial(form, k), flush=True)
    print(v, 'exit-raise', exit_raise_trial(), flush=True)
