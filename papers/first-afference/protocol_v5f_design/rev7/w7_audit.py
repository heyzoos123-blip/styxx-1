# Revision 7 self-audit witnesses on rev7/mech7.py (each trial in its own subprocess):
#   V67   no pending entry is stored while no anchor is registered (M6 "If no anchor is registered anywhere, store
#         nothing"): a declared function that raises out of its body is called 100 times outside every section while
#         the trace is active; pending entries of its mint afterwards: spec 0; mutant store_no_anchor 100.
#   X138c opens never take the robust mutex (M2): while another thread holds the mutex inside a transaction (blocked on
#         an Event for 3 s), an active tracer's run() on a third thread returns within 1 s. Mutant open_locks: the open
#         waits for the mutex and raises MACHINERY_BUSY after the (shortened, 2 s) bound.
#   R20   cut poisoning never over-credits (#21): a function built after E2 with a code that E2 put in the cut, run on
#         a section's stack between the anchor and f: f is dispatched, not credited.
#   R21   a hostile tool that frees styxx's id and re-takes it under styxx's own name object is taken for styxx: the
#         trace passes with no MONITOR_LOST (the disclosed residual).
#   R22   a code.replace() copy of M_T run with T's globals inside a section carries no monitoring events: never
#         observed (not credited, not in any bucket, no problem).
#   X156e a pass-through wrapper installed on sys.monitoring.set_events AFTER the first coverage_trace() is never
#         called by the machinery: a later trace passes and the wrapper's call counter stays 0.
import sys, os, json, subprocess, threading, time, types
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

def child(case, mut):
    import mech7 as mech
    M = sys.monitoring
    if case == 'X156e':
        mech.reset()
        n = {'calls': 0}
        real = M.set_events
        def set_events(t, ev): n['calls'] += 1; return real(t, ev)
        M.set_events = set_events
        def f(): return 1
        tr = mech.Tracer(f); tr.__enter__(); tr.run('A', f); tr.__exit__(None, None, None)
        M.set_events = real
        return dict(calls=tr.result()['calls'], lost=tr.result()['MONITOR_LOST'], wrapper_calls=n['calls'])
    mech.reset()
    if mut: mech.MUT.add(mut)
    if case == 'V67':
        def t(): raise KeyError
        tr = mech.Tracer(t); tr.__enter__()
        for _ in range(100):
            try: t()
            except KeyError: pass
        pend = sum(len(m.pend) for m in mech._MINTED.values())
        tr.__exit__(None, None, None)
        return dict(pending_while_active=pend)
    if case == 'X138c':
        mech.BUSY[0] = 2.0
        def f(): return 1
        tr = mech.Tracer(f); tr.__enter__()
        ev = threading.Event(); held = threading.Event()
        def owner():
            def block(): held.set(); ev.wait(3.0)
            mech._locked(block)
        th = threading.Thread(target=owner); th.start(); held.wait(2)
        res = {}
        def opener():
            t0 = time.monotonic()
            try: tr.run('A', f); res['out'] = 'returned'
            except Exception as e: res['out'] = repr(e)
            res['seconds'] = round(time.monotonic() - t0, 2)
        th2 = threading.Thread(target=opener); th2.start(); th2.join(5); ev.set(); th.join()
        tr.__exit__(None, None, None)
        return dict(open=res.get('out'), seconds=res.get('seconds'), calls=tr.result()['calls'])
    if case == 'R20':
        import asyncio.events as aev
        def f(): return 1
        def W(fn): return fn()                       # a module-level-like wrapper whose code E2 puts in the cut
        orig = aev.Handle._run
        aev.Handle._run = W
        mech.Tracer(lambda: 0).__enter__()           # an E2 while W is bound: W's code joins the cut
        aev.Handle._run = orig
        clone = types.FunctionType(W.__code__, globals())   # built after E2, sharing a cut code
        tr = mech.Tracer(f); tr.__enter__(); tr.run('A', clone, f); tr.__exit__(None, None, None)
        r = tr.result()
        return dict(calls=r['calls'], dispatched=r['dispatched'])
    if case == 'R22':                                # a code.replace() copy of M_T, run with T's globals in a section
        def f(): return 1
        tr = mech.Tracer(f); tr.__enter__()
        copy = types.FunctionType(f.__code__.replace(), f.__globals__)   # f.__code__ is M_T now
        tr.run('A', copy); tr.__exit__(None, None, None)
        r = tr.result()
        return dict(calls=r['calls'], dispatched=r['dispatched'], unattributed=r['unattributed'], problems=r['problems'])
    if case == 'R21':
        def f(): return 1
        tr = mech.Tracer(f); tr.__enter__(); tr.run('A', f)
        t = mech.TOOL[0]; n = M.get_tool(t)
        M.free_tool_id(t); M.use_tool_id(t, n)       # a hostile tool re-takes the id under styxx's own name object
        tr.run('A', f); tr.__exit__(None, None, None)
        return dict(calls=tr.result()['calls'], lost=tr.result()['MONITOR_LOST'])

def run(case, mut=''):
    p = subprocess.run([sys.executable, __file__, case, mut or '-'], capture_output=True, text=True, timeout=120)
    line = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ('ERROR ' + (p.stderr.strip().splitlines() or ['?'])[-1])
    print(sys.version.split()[0], '%-6s %-16s %s' % (case, mut or 'spec', line), flush=True)

if __name__ == '__main__':
    if len(sys.argv) == 3:
        print(json.dumps(child(sys.argv[1], None if sys.argv[2] == '-' else sys.argv[2]), default=repr)); sys.exit(0)
    for mut in (None, 'store_no_anchor'): run('V67', mut)
    for mut in (None, 'open_locks'): run('X138c', mut)
    run('R20'); run('R21'); run('R22'); run('X156e')
