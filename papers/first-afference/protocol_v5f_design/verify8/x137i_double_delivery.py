# verify8 (wide self-audit, W1): a witness for "If both ids then deliver an event of one minted frame, the pending
# entry is keyed by the frame, so the second delivery finds no entry and publishes nothing: no double count" (M4 E4,
# "Rebinding (and re-taking) while traces are live"), which no case exercised: in X137g the other tool registers its
# own five callbacks on id 4, so only id 3 delivers.
# Shape (X137g with an owner that registers nothing): P declares f and is entered. Another tool frees styxx's id 4 and
# takes it with use_tool_id only (no callbacks, no events), so styxx's callbacks and f's mint's local events stay on
# id 4 (CPython keeps them across free_tool_id, p3). Q (f, g) is entered: it joins P's mint and rebinds to id 3,
# setting f's local events there too. P runs A: f once; Q runs B: f once and g once.
# Spec: P {f:1} with MONITOR_LOST; Q {f:1, g:1}; and f's PY_START is delivered to styxx on BOTH ids.
# Mutant 'pend_get' (a delivery that reads the pending entry without popping it): P {f:2}.
import sys, os, json, subprocess
R8 = '/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/rev8'
HERE = os.path.dirname(os.path.abspath(__file__))

def child(mut):
    if mut == 'pend_get':
        src = open(os.path.join(R8, 'mech8.py')).read()
        old = "    f = sys._getframe(1); p = m.pend.pop(id(f), None)\n    if p is not None and (p[0] is f or 'pend_bare_id' in MUT): _publish(code, p[2])"
        assert src.count(old) == 1
        src = src.replace(old, "    f = sys._getframe(1); p = m.pend.get(id(f), None)\n    if p is not None and (p[0] is f or 'pend_bare_id' in MUT): _publish(code, p[2])")
        path = os.path.join(HERE, '_mech8_pend_get.py'); open(path, 'w').write(src)
        sys.path.insert(0, HERE); import _mech8_pend_get as mech
    else:
        sys.path.insert(0, R8); import mech8 as mech
    M = sys.monitoring; E = mech.E
    def f(): return 1
    def g(): return 2
    P = mech.Tracer(f); P.__enter__()
    t0 = mech.TOOL[0]
    M.free_tool_id(t0); M.use_tool_id(t0, 'other-tool')          # takes the id, registers nothing
    Q = mech.Tracer(f, g); Q.__enter__()
    t1 = mech.TOOL[0]
    code = f.__code__
    starts = {}
    # count deliveries of f's PY_START to styxx's callback on each id (read-only: a wrapper would change identity,
    # so read the local events instead, which is what makes each id deliver)
    le = {t: M.get_local_events(t, code) for t in (t0, t1)}
    P.run('A', f); Q.run('B', f); Q.run('B', g)
    Q.__exit__(None, None, None); P.__exit__(None, None, None)
    return dict(mut=mut, tool_before=t0, tool_after=t1, local_events_on_each_id=le,
                P_calls=P.result()['calls'], P_lost=P.result()['MONITOR_LOST'],
                Q_calls=Q.result()['calls'], Q_lost=Q.result()['MONITOR_LOST'])

if __name__ == '__main__':
    if len(sys.argv) == 2:
        print(json.dumps(child(None if sys.argv[1] == '-' else sys.argv[1]), default=repr)); sys.exit(0)
    for mut in ('-', 'pend_get'):
        p = subprocess.run([sys.executable, __file__, mut], capture_output=True, text=True, timeout=120)
        out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else 'ERROR ' + p.stderr[-800:]
        print(sys.version.split()[0], 'X137i', 'spec' if mut == '-' else mut, out, flush=True)
