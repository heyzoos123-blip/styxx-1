# Revision 8 (the eighth critic's N2): a deterministic witness for A13 ("while an entry is pending, its frame id
# cannot be reused"), on rev8/mech8.py. Mutant pend_bare_id: the pending entry is keyed by id(frame) and does not hold
# the frame, and a pop publishes on a matching id.
# Shape (case V70): tracer P declares f. Main opens section A; A's body releases worker thread T2 and waits until f
# has entered on T2 (so f's entry is stored as pending, outcome 'u': f is under no anchor of P on T2), then returns:
# A closes, the last anchor, and PY_UNWIND is cleared. Main then lets f raise on T2: its unwind is not delivered, so
# the entry is stranded. T2 drops the exception and at once calls f again, which returns; no anchor is registered at
# its entry. P exits. Spec: the stranded entry holds f's first frame, so the second frame has another id and nothing
# is published: P NOT_EXERCISED for f, unattributed {} and dispatched {}. Mutant: the first frame dies, the second
# reuses its id, and its PY_RETURN publishes the stale entry: unattributed {f: 1}.
import sys, os, json, subprocess, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def trial(mech, mut):
    mech.reset()
    if mut: mech.MUT.add(mut)
    entered, go, ids = threading.Event(), threading.Event(), []
    def f(box):
        ids.append(id(sys._getframe(0)))
        if box is not None:
            entered.set(); go.wait(); raise KeyError
        return 1
    P = mech.Tracer(f); P.__enter__()
    start = threading.Event()
    def worker():
        start.wait()
        try: f(True)
        except KeyError: pass
        f(None)
    th = threading.Thread(target=worker); th.start()
    def body():
        start.set(); entered.wait(); return 0
    P.run('A', body)
    anchors_after_A = len(mech._ANCHORS); ev_after_A = mech.events_set()
    go.set(); th.join()
    P.__exit__(None, None, None)
    r = P.result()
    return dict(calls=r['calls'], unattributed=r['unattributed'], dispatched=r['dispatched'], lost=r['MONITOR_LOST'],
                same_id=ids[0] == ids[1], anchors_after_A=anchors_after_A, event_after_A=ev_after_A)

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'child':
        import mech8 as mech
        mut = None if sys.argv[2] == '-' else sys.argv[2]
        print(json.dumps([trial(mech, mut) for _ in range(int(os.environ.get('A13_N', '1')))])); sys.exit(0)
    v = sys.version.split()[0]
    for mut in (None, 'pend_bare_id'):
        summary = {}
        for rep in range(20):                            # 20 fresh processes x 50 in-process trials = 1000 per row
            p = subprocess.run([sys.executable, __file__, 'child', mut or '-'], capture_output=True, text=True,
                               timeout=300, env=dict(os.environ, A13_N='50'))
            if not p.stdout.strip(): print(v, 'ERROR', p.stderr[-600:]); break
            for t in json.loads(p.stdout.strip().splitlines()[-1]):
                k = json.dumps({x: t[x] for x in ('calls', 'unattributed', 'dispatched', 'lost', 'same_id', 'anchors_after_A', 'event_after_A')}, sort_keys=True)
                summary[k] = summary.get(k, 0) + 1
        for k, n in summary.items(): print(v, '%-12s %4d x %s' % (mut or 'spec', n, k), flush=True)
