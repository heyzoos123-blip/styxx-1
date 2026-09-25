# SM1 witnesses for revision 5, run on mech5.py under the spec and under each single-rule mutant (mech5.MUT).
#
# Two kinds of witness:
#  * INSTRUCTION SWEEPS (the exam's new witness family, "IS"): a sys.monitoring INSTRUCTION tool (id 5, local events on
#    one machinery code object, filtered to one thread's live ident) runs an interfering action to completion at the
#    k-th instruction that thread executes there, one trial per k, until a trial's k-th instruction never executes.
#    The action runs on another thread while the swept thread waits inside the callback, so the sweep places the
#    action between every two consecutive instructions of the function. A rule that says "these reads and writes are
#    one C call" is witnessed by an IS: the spec passes every trial; a mutant that splits the call fails the trial
#    that lands in the split. No timeout decides any outcome.
#  * HOLDS: mech5's _HOOK stands in for the exam's id-3 tool (PY_START / PY_RETURN / CALL events) or the id-5 injector,
#    exactly as in rev4/w4_rev4_witnesses.py.
# Every case runs with no other section open (the main thread before the self-trace), each trial on fresh tracers.
import sys, threading, time, types
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech5 as mech
M = mech.M; E = M.events; PYU = E.PY_UNWIND
class Injected(BaseException): pass
def t(): raise KeyError
def f(): return 1
def g(): return 2
def catch_t():
    try: t()
    except KeyError: pass
def st(): return mech.state()
def outcome(fn):
    try: return fn()
    except mech.TraceInactive: return 'TRACE_INACTIVE'
    except mech.MachineryBusy as e: return str(e)
    except Injected: return 'Injected'
    except ValueError as e: return 'ValueError: ' + str(e)

# ------------------------------------------------------------------------------------------------ instruction sweep
class Sweep:
    def __init__(self, code, k, action):
        self.code, self.k, self.action = code, k, action
        self.tid = None; self.n = 0; self.fired = False
    def cb(self, code, off):
        if threading.get_ident() != self.tid or self.fired: return
        self.n += 1
        if self.n == self.k: self.fired = True; self.action()
    def __enter__(self):
        M.use_tool_id(5, 'sweep'); M.register_callback(5, E.INSTRUCTION, self.cb); M.set_local_events(5, self.code, E.INSTRUCTION)
        return self
    def __exit__(self, *a):
        M.set_local_events(5, self.code, 0); M.register_callback(5, E.INSTRUCTION, None); M.free_tool_id(5)

def on_thread(fn, name):
    th = threading.Thread(target=fn, name=name); th.start(); return th

def sweep(trial, limit=400):
    """Run trial(k) for k = 1, 2, ... until the k-th instruction is not reached; return (trials, failing trial outputs)."""
    bad = []; k = 1
    while k <= limit:
        mech.reset_keep_mut()
        fired, ok, out = trial(k)
        if not fired: break
        if not ok: bad.append((k, out))
        k += 1
    return k - 1, bad

def summarize(res):
    n, bad = res
    return 'trials %d, failing %d%s' % (n, len(bad), ('  first: k=%d %s' % bad[0]) if bad else '')

# IS-OFF (X145 (a), rewritten): T2 closes B, the last anchor. At each instruction of T2's _unwind_off, T1 runs
# cov.run('A', body) up to the start of A's body. body waits until T2's run() has returned, then calls t, which raises
# inside its body and is caught. Spec, every trial: A {t:1}, no MONITOR_LOST.
def is_off():
    def trial(k):
        ev = {x: threading.Event() for x in ('b_open', 'b_close', 'a_started', 't2_done')}
        tr = mech.Tracer(t); tr.__enter__()
        def body():
            ev['a_started'].set(); ev['t2_done'].wait(5); catch_t()
        box = {}
        def action():
            box['t1'] = on_thread(lambda: tr.run('A', body), 'T1'); ev['a_started'].wait(5)
        sw = Sweep(mech._unwind_off.__code__, k, action)
        def t2():
            sw.tid = threading.get_ident(); tr.run('B', lambda: (ev['b_open'].set(), ev['b_close'].wait(5)))
        with sw:
            th2 = on_thread(t2, 'T2'); ev['b_open'].wait(5); ev['b_close'].set(); th2.join(5)
        ev['t2_done'].set()
        if 't1' in box: box['t1'].join(5)
        tr.__exit__(None, None, None); r = tr.result()
        ok = (not sw.fired) or (r['calls'].get('A') == {'t': 1} and not r['MONITOR_LOST'])
        return sw.fired, ok, dict(A=r['calls'].get('A'), ML=r['MONITOR_LOST'])
    return sweep(trial)

# IS-POPOFF (X152): T1 runs cov.run('A', f), the only section. At each instruction of T1's _detach and of its
# _unwind_off, the action reads _v5_state(). Spec: no trial reads anchors == 0 with global_events != 0.
def is_popoff(code_of):
    def trial(k):
        tr = mech.Tracer(f); tr.__enter__(); seen = []
        sw = Sweep(code_of(), k, lambda: seen.append(st()))
        def t1(): sw.tid = threading.get_ident(); tr.run('A', f)
        with sw:
            on_thread(t1, 'T1').join(5)
        tr.__exit__(None, None, None)
        bad = [s for s in seen if s['anchors'] == 0 and s['global_events']]
        return sw.fired, not bad, dict(seen=seen)
    return sweep(trial)

# IS-ON (X153): two tracers, no section open. T1 runs covA.run('A', bodyA). At each instruction of T1's _unwind_on, T2
# runs covB.run('B', bodyB) up to the start of B's body. Both bodies wait for `release`. Spec: no MONITOR_LOST on
# either trace in any trial (the event was never cleared under anything).
def is_on():
    def trial(k):
        ev = {x: threading.Event() for x in ('a_started', 'b_started', 'release')}
        ta = mech.Tracer(f); ta.__enter__(); tb = mech.Tracer(g); tb.__enter__()
        box = {}
        def action():
            box['t2'] = on_thread(lambda: tb.run('B', lambda: (g(), ev['b_started'].set(), ev['release'].wait(5))), 'T2')
            ev['b_started'].wait(5)
        sw = Sweep(mech._unwind_on.__code__, k, action)
        def t1():
            sw.tid = threading.get_ident(); ta.run('A', lambda: (f(), ev['a_started'].set(), ev['release'].wait(5)))
        with sw:
            th1 = on_thread(t1, 'T1'); ev['a_started'].wait(5)
        ev['release'].set(); th1.join(5)
        if 't2' in box: box['t2'].join(5)
        ta.__exit__(None, None, None); tb.__exit__(None, None, None)
        ra, rb = ta.result(), tb.result()
        ok = not ra['MONITOR_LOST'] and not rb['MONITOR_LOST']
        return sw.fired, ok, dict(A_ML=ra['MONITOR_LOST'], B_ML=rb['MONITOR_LOST'], A=ra['calls'], B=rb['calls'])
    return sweep(trial)

# IS-BLIND (X148, rewritten): T1 runs cov.run('A', body); body waits for `go`. At each instruction of T1's close
# (_detach), the action runs cov.__exit__() to completion on another thread (X3 pops A and clears the event). f
# returns, so any MONITOR_LOST is false. Spec: no MONITOR_LOST in any trial.
def is_blind():
    def trial(k):
        tr = mech.Tracer(f); tr.__enter__()
        def action(): on_thread(lambda: tr.__exit__(None, None, None), 'X').join(5)
        sw = Sweep(mech._detach.__code__, k, action)
        def t1(): sw.tid = threading.get_ident(); tr.run('A', f)
        with sw:
            on_thread(t1, 'T1').join(5)
        tr.__exit__(None, None, None); r = tr.result()
        return sw.fired, not r['MONITOR_LOST'], dict(ML=r['MONITOR_LOST'], A=r['calls'].get('A'))
    return sweep(trial)

# IS-COMMIT (X143, as a sweep): T2 holds section B open; T1 runs cov.run('A', catch_t). At each instruction of T1's
# _commit, the action lets T2 close B (the last other anchor) to completion. Spec: A {t:1}, no MONITOR_LOST.
def is_commit():
    def trial(k):
        ev = {x: threading.Event() for x in ('b_open', 'b_close')}
        tr = mech.Tracer(t); tr.__enter__()
        th2 = on_thread(lambda: tr.run('B', lambda: (ev['b_open'].set(), ev['b_close'].wait(5))), 'T2'); ev['b_open'].wait(5)
        def action(): ev['b_close'].set(); th2.join(5)
        sw = Sweep(mech._commit.__code__, k, action)
        def t1(): sw.tid = threading.get_ident(); tr.run('A', catch_t)
        with sw:
            on_thread(t1, 'T1').join(5)
        ev['b_close'].set(); th2.join(5)
        tr.__exit__(None, None, None); r = tr.result()
        return sw.fired, r['calls'].get('A') == {'t': 1} and not r['MONITOR_LOST'], dict(A=r['calls'].get('A'), ML=r['MONITOR_LOST'])
    return sweep(trial)

# IS-GATE (X154): every name-gated write. T1 runs the transition; at each instruction of the named function on T1, the
# action frees styxx's id and another tool takes it with its own events (RAISE) and a RAISE callback. Spec: in every
# trial that tool's events are still exactly RAISE afterwards (styxx wrote nothing on an id it does not hold).
def is_gate(which):
    def other_cb(*a): return None
    def trial(k):
        tr = mech.Tracer(f); tr.__enter__()
        if which == 'on': code, run = mech._unwind_on.__code__, (lambda: tr.run('A', f))
        elif which == 'off': code, run = mech._unwind_off.__code__, (lambda: tr.run('A', f))
        elif which == 'register': code, run = mech._register_named.__code__, (lambda: tr.__exit__(None, None, None))
        else: code, run = mech._set_local_named.__code__, (lambda: tr.__exit__(None, None, None))
        took = {}
        mcode = [m.code for m in mech._MINTED.values() if m.fn is f][0]
        def action():
            for e in mech._EVS5: M.register_callback(4, e, None)
            M.free_tool_id(4); M.use_tool_id(4, 'other-tool'); M.register_callback(4, E.RAISE, other_cb)
            M.set_events(4, E.RAISE); M.set_local_events(4, mcode, E.LINE); took['yes'] = True
        sw = Sweep(code, k, action)
        def t1(): sw.tid = threading.get_ident(); outcome(run)
        with sw:
            on_thread(t1, 'T1').join(5)
        ok = True; out = {}
        if took:
            out = dict(events=M.get_events(4), local=M.get_local_events(4, mcode), name=M.get_tool(4))
            cbs = [M.register_callback(4, e, None) for e in mech._EVS5]      # read (and clear) what is registered now
            out['styxx_callbacks'] = sum(cb is not None for cb in cbs)
            ok = out['events'] == E.RAISE and out['local'] == E.LINE and out['name'] == 'other-tool' and out['styxx_callbacks'] == 0
            M.set_events(4, 0); M.set_local_events(4, mcode, 0); M.register_callback(4, E.RAISE, None); M.free_tool_id(4)
        outcome(lambda: tr.__exit__(None, None, None))
        return sw.fired, ok, out
    return sweep(trial)

# IS-TAKE (X155): X137's free variant; at each instruction of the exit transaction's _take (the reclaim), another tool
# takes the freed id. Spec, every trial: __exit__ raises nothing, MONITOR_LOST is noted, the other tool keeps the id.
def is_take():
    def gr(): raise KeyError
    def trial(k):
        tr = mech.Tracer(f, gr); tr.__enter__()
        def body():
            f(); M.free_tool_id(4)
            try: gr()
            except KeyError: pass
        tr.run('G', body)
        took = {}
        def action():                                # the other tool's own call; if styxx won, *it* gets ValueError
            try: M.use_tool_id(4, 'other-tool'); took['yes'] = True
            except ValueError: took['lost_race'] = True
        sw = Sweep(mech._take.__code__, k, action)
        box = {}
        def x(): sw.tid = threading.get_ident(); box['exit'] = outcome(lambda: tr.__exit__(None, None, None))
        with sw:
            on_thread(x, 'X').join(5)
        r = tr.result(); name = M.get_tool(4)
        ok = box.get('exit') is False and r['MONITOR_LOST'] and (name == 'other-tool' if took.get('yes') else True)
        if name == 'other-tool':
            for e in mech._EVS5: M.register_callback(4, e, None)
            M.free_tool_id(4)
        return sw.fired, ok, dict(exit=box.get('exit'), ML=r['MONITOR_LOST'], id4=name)
    return sweep(trial)

# ------------------------------------------------------------------------------------------------ holds
def held_open(point, during, extra=None, fn=f, tracer_fns=(f,)):
    at, go = threading.Event(), threading.Event(); me = {}
    def hook(p):
        if threading.get_ident() != me.get('t1'): return
        if p == point and not at.is_set(): at.set(); go.wait(5)
        if extra: extra(p)
    tr = mech.Tracer(*tracer_fns); tr.__enter__()
    out = {}
    def t1():
        me['t1'] = threading.get_ident(); out['r'] = outcome(lambda: tr.run('A', fn))
    mech._HOOK[0] = hook
    T1 = threading.Thread(target=t1); T1.start(); at.wait(5)
    during(tr)
    go.set(); T1.join(5); mech._HOOK[0] = None
    return tr, out.get('r')

def x146():
    tr, r = held_open('commit:0', lambda tr: tr.__exit__(None, None, None))
    s = st(); return dict(run=r, anchors=s['anchors'], global_events=s['global_events'], problems=tr.core.problems)

def x146b():
    tr, r = held_open('open:checked', lambda tr: tr.__exit__(None, None, None))
    s = st(); return dict(run=r, anchors=s['anchors'], global_events=s['global_events'], problems=tr.core.problems)

def x146c():
    def during(tr):
        tr.core.facade_dead = True
        with mech.Tracer(g): pass
    tr, r = held_open('commit:0', during)
    s = st(); tr.__exit__(None, None, None)
    return dict(run=r, anchors=s['anchors'], global_events=s['global_events'])

def x146d():
    n = {'k': 0}
    def extra(p):
        if p == 'commit:stored' and n['k'] == 0: n['k'] = 1; raise Injected
        if p == 'detach:claimed' and n['k'] == 1: n['k'] = 2; raise Injected
    tr, r = held_open('commit:0', lambda tr: tr.__exit__(None, None, None), extra)
    s1 = st()
    with mech.Tracer(g): pass
    s2 = st()
    return dict(run=r, anchors_after_faults=s1['anchors'], anchors_after_next_transaction=s2['anchors'],
                events_after_next_transaction=s2['global_events'])

def x146e():           # ON's own-anchor gate: T1 held after step 8, before ON, until cov.__exit__() has returned
    seen = {}
    def body(): seen['S'] = mech.events_set(); seen['anchors'] = len(mech._ANCHORS); return 1
    tr, r = held_open('commit:checked', lambda tr: tr.__exit__(None, None, None), fn=body)
    return dict(run=r, S_in_body=seen.get('S'), anchors_in_body=seen.get('anchors'), after=st()['global_events'])

def x143b():           # o.armed: T1 held before its store until T2's close cleared the event; then a fault after step 8
    ev = {k: threading.Event() for k in ('opened', 'close', 'at', 'go')}
    def hook(p):
        if threading.current_thread().name != 'T1': return
        if p == 'commit:0' and not ev['at'].is_set(): ev['at'].set(); ev['go'].wait(5)
        if p == 'commit:checked': raise Injected
    res = {}
    with mech.Tracer(t) as tr:
        th2 = threading.Thread(target=lambda: tr.run('B', lambda: (ev['opened'].set(), ev['close'].wait(5))), name='T2')
        th2.start(); ev['opened'].wait(5)
        mech._HOOK[0] = hook
        th1 = threading.Thread(target=lambda: res.setdefault('r', outcome(lambda: tr.run('A', f))), name='T1')
        th1.start(); ev['at'].wait(5)
        ev['close'].set(); th2.join(5); ev['go'].set(); th1.join(5); mech._HOOK[0] = None
    r = tr.result(); s = st()
    return dict(run=res.get('r'), MONITOR_LOST=r['MONITOR_LOST'], anchors=s['anchors'], global_events=s['global_events'])

def x143c():           # the anchor test: T1's finally faulted after _detach's pop-and-clear, before o.frame = None
    fired = [0]
    def hook(p):
        if p == 'detach:done' and not fired[0] and threading.current_thread().name == 'T1': fired[0] = 1; raise Injected
    res = {}
    tr = mech.Tracer(f); tr.__enter__()
    mech._HOOK[0] = hook
    th = threading.Thread(target=lambda: res.setdefault('r', outcome(lambda: tr.run('A', f))), name='T1'); th.start(); th.join(5)
    mech._HOOK[0] = None
    s1 = st(); tr.__exit__(None, None, None); r = tr.result()
    return dict(run=res.get('r'), events_right_after=s1['global_events'], calls=r['calls'].get('A'), MONITOR_LOST=r['MONITOR_LOST'])

def x137d():           # MF2: an outside party clears the event inside G, g's raise is lost, and another tracer's
    def gr(): raise KeyError         # section opens and closes on another thread before G closes
    def h(): return 3
    with mech.Tracer(f, gr) as tr, mech.Tracer(h) as other:
        def body():
            f(); M.set_events(4, 0)
            try: gr()
            except KeyError: pass
            th = threading.Thread(target=lambda: other.run('B', h)); th.start(); th.join()
        tr.run('G', body)
    r = tr.result()
    return dict(calls=r['calls'].get('G'), MONITOR_LOST=r['MONITOR_LOST'], other_ML=other.result()['MONITOR_LOST'])

def x137c():           # the plain X137c: an outside clear inside G, g raises, nothing reopens
    def gr(): raise KeyError
    with mech.Tracer(f, gr) as tr:
        def body():
            f(); M.set_events(4, 0)
            try: gr()
            except KeyError: pass
        tr.run('G', body)
    r = tr.result()
    return dict(calls=r['calls'].get('G'), MONITOR_LOST=r['MONITOR_LOST'])

def x137_free():       # X137's free variant: f, free_tool_id, g (raises and is caught), close; then exit
    def gr(): raise KeyError
    res = {}
    with mech.Tracer(f, gr) as tr:
        def body():
            f(); M.free_tool_id(4)
            try: gr()
            except KeyError: pass
        res['run'] = outcome(lambda: tr.run('G', body))
    r = tr.result(); s = st()
    return dict(run=res['run'], calls=r['calls'].get('G'), MONITOR_LOST=r['MONITOR_LOST'], tool_ours=M.get_tool(4) is mech.NAME,
                global_events=s['global_events'])

def x137e():           # a free between another enter's reconciliation and its _ensure_tool: the first trace still notes it
    first = mech.Tracer(f); first.__enter__(); first.run('A', f)
    at = threading.Event(); done = [0]
    def hook(p):
        if p == 'enter:reconciled' and not done[0]: done[0] = 1; M.free_tool_id(4)
    mech._HOOK[0] = hook
    second = mech.Tracer(g); second.__enter__(); mech._HOOK[0] = None
    second.__exit__(None, None, None); first.__exit__(None, None, None)
    return dict(first=first.result()['calls'], first_ML=first.result()['MONITOR_LOST'], tool_ours=M.get_tool(4) is mech.NAME)

def x137b():           # the taken variant, extended: after another tool takes the id, section H opens and closes, then exit
    def other_cb(*a): return None
    with mech.Tracer(f) as tr:
        def body():
            f()
            for e in mech._EVS5: pass            # styxx's callbacks stay registered after a free (rev1/p3)
            M.free_tool_id(4); M.use_tool_id(4, 'other-tool'); M.register_callback(4, E.RAISE, other_cb); M.set_events(4, E.RAISE)
        tr.run('G', body)
        tr.run('H', f)
    out = dict(name=M.get_tool(4), events=M.get_events(4), raise_cb_is_other=M.register_callback(4, E.RAISE, other_cb) is other_cb,
               MONITOR_LOST=tr.result()['MONITOR_LOST'])
    M.set_events(4, 0); M.register_callback(4, E.RAISE, None); M.free_tool_id(4)
    return out

def x138b():           # N3: the mutex's bound with time.monotonic frozen and time.sleep replaced (freezegun, gevent)
    hold, go = threading.Event(), threading.Event()
    mech.BUSY[0] = 1.0
    th = threading.Thread(target=lambda: mech._locked(lambda: (hold.set(), go.wait(3.0))), name='holder'); th.start(); hold.wait(5)
    real_mono, real_sleep = time.monotonic, time.sleep
    calls = [0]
    time.monotonic = lambda: 1000.0
    def fake_sleep(s): calls[0] += 1; real_sleep(s)
    time.sleep = fake_sleep
    t0 = time.perf_counter()
    try: r = outcome(lambda: mech._locked(lambda: 'got it'))
    finally: time.monotonic, time.sleep = real_mono, real_sleep
    dt = time.perf_counter() - t0
    go.set(); th.join(5); mech.BUSY[0] = 10.0
    return dict(result=r, waited_s=round(dt, 1), patched_sleep_calls=calls[0])

# ------------------------------------------------------------------------------------------------ the critic's shapes
def c2_r19_sweep():    # R19's shape at every hook point of a close: open run_async('A') there, leave it suspended,
    import types as _t                                   # resume it after the close; its body calls t (raises)
    @_t.coroutine
    def suspend(): yield
    async def af():
        await suspend(); catch_t(); return 'done'
    points = ['detach:claimed', 'detach:event-read', 'detach:checked', 'off:enter', 'off:tested', 'off:return', 'detach:done']
    out = {}
    for point in points:
        mech.reset_keep_mut(); box = {}
        with mech.Tracer(f) as tr, mech.Tracer(t) as tr2:
            def hook(p):
                if p == point and 'co' not in box:
                    co = tr2.run_async('A', af); box['co'] = co; co.send(None)
            mech._HOOK[0] = hook
            tr.run('B', lambda: None); mech._HOOK[0] = None
            if 'co' in box:
                try: box['co'].send(None)
                except StopIteration: pass
        r = tr2.result()
        if 'co' in box: out[point] = (r['calls'].get('A'), r['MONITOR_LOST'])
    return out

def c3_user_lock():    # T1 holds a user lock around cov.run('A', f); T2's close runs user code needing that lock
    L = threading.Lock(); out = {}
    points = ['detach:claimed', 'detach:checked', 'off:enter', 'off:return', 'detach:done']
    for point in points:
        mech.reset_keep_mut(); inwin = threading.Event(); fired = [0]
        with mech.Tracer(f) as tr:
            opened, close = threading.Event(), threading.Event()
            def hook(p):
                if threading.current_thread().name == 'T2' and p == point and not fired[0]:
                    fired[0] = 1; inwin.set()
                    if L.acquire(timeout=30): L.release()
            def t1():
                with L:
                    close.set(); inwin.wait(5)
                    t0 = time.perf_counter(); out[point] = (outcome(lambda: tr.run('A', f)), round(time.perf_counter() - t0, 3))
            th2 = threading.Thread(target=lambda: tr.run('B', lambda: (opened.set(), close.wait(5))), name='T2'); th2.start(); opened.wait(5)
            mech._HOOK[0] = hook
            th1 = threading.Thread(target=t1, name='T1'); th1.start(); th1.join(40); th2.join(40); mech._HOOK[0] = None
    return out

def c8_nested():       # both closers interrupted inside their close by code that runs a section
    out = {}; fired = set(); popped = threading.Barrier(2); inw = threading.Barrier(2); opened = threading.Barrier(2)
    mech.reset_keep_mut()
    with mech.Tracer(f) as tr, mech.Tracer(g) as inner:
        def hook(p):
            n = threading.current_thread().name
            if n not in ('T1', 'T2') or n in fired: return
            if p == 'detach:checked': popped.wait(5)
            if p == 'off:enter':
                fired.add(n); inw.wait(5); t0 = time.perf_counter()
                out[n] = (outcome(lambda: inner.run('I' + n, g)), round(time.perf_counter() - t0, 3))
        def worker(): tr.run('S' + threading.current_thread().name, lambda: opened.wait(5))
        mech._HOOK[0] = hook
        ths = [threading.Thread(target=worker, name=n) for n in ('T1', 'T2')]
        [x.start() for x in ths]; [x.join(20) for x in ths]; mech._HOOK[0] = None
    return out

# ------------------------------------------------------------------------------------------------ table
def reset_keep_mut():
    keep = set(mech.MUT); mech.reset(); mech.MUT.update(keep)
mech.reset_keep_mut = reset_keep_mut

CASES = [
    # (case, spec-outcome predicate description, mutants the case must kill)
    ('IS-OFF (X145a)', lambda: summarize(is_off()), ['off_split']),
    ('IS-POPOFF _unwind_off (X152)', lambda: summarize(is_popoff(lambda: mech._unwind_off.__code__)), ['popoff_split']),
    ('IS-POPOFF _detach (X152)', lambda: summarize(is_popoff(lambda: mech._detach.__code__)), []),
    ('IS-ON (X153)', lambda: summarize(is_on()), ['on_capture_split', 'on_capture_nogate']),
    ('IS-BLIND (X148)', lambda: summarize(is_blind()), ['blind_anchor_first']),
    ('IS-COMMIT (X143)', lambda: summarize(is_commit()), ['no_on', 'on_before_store']),
    ('IS-GATE on (X154)', lambda: summarize(is_gate('on')), ['gate_split']),
    ('IS-GATE off (X154)', lambda: summarize(is_gate('off')), ['gate_split']),
    ('IS-GATE retire (X154)', lambda: summarize(is_gate('retire')), ['gate_split']),
    ('IS-GATE register (X154)', lambda: summarize(is_gate('register')), ['gate_split']),
    ('X146', x146, ['detach_nulls', 'no_recheck']),
    ('X146b', x146b, ['no_exiting_test']),
    ('X146c', x146c, ['no_fin_test']),
    ('X146d', x146d, ['no_anchor_prune']),
    ('X146e', x146e, ['on_ungated_own']),
    ('X143b', x143b, ['blind_no_armed']),
    ('X143c', x143c, ['blind_no_anchor']),
    ('X137c', x137c, []),
    ('X137d', x137d, ['on_no_capture']),
    ('X137 free', x137_free, ['no_rec_off']),
    ('IS-TAKE (X155)', lambda: summarize(is_take()), ['take_split']),
    ('X137e', x137e, ['ensure_nocount']),
    ('X137b ext', x137b, ['no_gate']),
    ('X138b', x138b, ['time_at_call']),
]

if __name__ == '__main__':
    v = sys.version.split()[0]
    only = sys.argv[1:]
    for name, fn, muts in CASES:
        if only and not any(o in name for o in only): continue
        mech.reset()
        print(v, '%-30s spec: %s' % (name, fn()), flush=True)
        for mu in muts:
            mech.reset(); mech.MUT.add(mu)
            r = fn()
            mech.reset()
            print(v, '%-30s   %-18s %s' % ('', mu, r), flush=True)
    if not only or 'critic' in only:
        mech.reset(); print(v, 'c2 (R19 shape at every close point): spec', c2_r19_sweep())
        mech.reset(); mech.MUT.add('off_split'); print(v, 'c2 (R19 shape at every close point): off_split', c2_r19_sweep()); mech.reset()
        mech.reset(); print(v, 'c3 (user lock around the open; the close needs it): spec', c3_user_lock())
        mech.reset(); print(v, 'c8 (sections opened inside both closers): spec', c8_nested())
