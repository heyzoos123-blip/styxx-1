# verify8 (wide self-audit, W2): `_run` (and `_run_async`) read their own frame with `sys._getframe()` as the argument
# of `_open` (M7 code, line 628), and `sys._getframe` raises the audit event `sys._getframe`. The Exception-safety
# "Sources" list omits this site, and says "the open and close paths still raise no audit event". The corrected claim:
# the open path raises exactly this one audit event, before `_open`, so a hook that raises on it propagates out of
# run() before any machinery state is touched: fn does not run, no opening is appended, no anchor is stored.
# Probe on rev8/mech8.py: a hook raising RuntimeError('hook') on the first 'sys._getframe' event on the case thread
# while armed, armed only around cov.run('A', f). Mutant 'frame_after_append': `_open` reads the frame (an audited
# call) after appending the opening.
import sys, os, json, subprocess, threading
R8 = '/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/rev8'
HERE = os.path.dirname(os.path.abspath(__file__))

def child(mut, event='sys._getframe'):
    if mut == 'frame_after_append':
        src = open(os.path.join(R8, 'mech8.py')).read()
        old = "        self.core.openings.append(o)\n        return o"
        assert src.count(old) == 1
        src = src.replace(old, "        self.core.openings.append(o)\n        sys._getframe()\n        return o")
        path = os.path.join(HERE, '_mech8_frame_after_append.py'); open(path, 'w').write(src)
        sys.path.insert(0, HERE); import _mech8_frame_after_append as mech
    else:
        sys.path.insert(0, R8); import mech8 as mech
    ran = []
    def f(): ran.append(1); return 1
    P = mech.Tracer(f); P.__enter__()
    tid = threading.get_ident(); H = {'arm': False, 'seen': 0}
    def hook(ev, args):
        if ev == event and H['arm'] and threading.get_ident() == tid:
            H['seen'] += 1
            if mut == 'frame_after_append' and H['seen'] == 1: return   # let _run's own read pass; raise at the later one
            H['arm'] = False; raise RuntimeError('hook')
    sys.addaudithook(hook)
    H['arm'] = True
    try: P.run('A', f); out = 'returned'
    except RuntimeError as e: out = 'raised ' + str(e)
    H['arm'] = False
    st = dict(anchors=len(mech._ANCHORS), openings=len(P.core.openings), f_ran=len(ran))
    P.run('A', f)
    P.__exit__(None, None, None)
    r = P.result()
    return dict(mut=mut, event=event, first_run=out, after_refused_open=st, calls=r['calls'], lost=r['MONITOR_LOST'],
                problems=r['problems'], openings_total=len(P.core.openings))

if __name__ == '__main__':
    if len(sys.argv) == 3:
        print(json.dumps(child(None if sys.argv[1] == '-' else sys.argv[1], sys.argv[2]), default=repr)); sys.exit(0)
    # the open path's other audit events (the walk's f_code reads and cut lookups) are raised on too, spec only
    for mut, event in (('-', 'sys._getframe'), ('frame_after_append', 'sys._getframe'),
                       ('-', 'object.__getattr__'), ('-', 'builtins.id')):
        p = subprocess.run([sys.executable, __file__, mut, event], capture_output=True, text=True, timeout=120)
        out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else 'ERROR ' + p.stderr[-800:]
        print(sys.version.split()[0], 'V71', 'spec' if mut == '-' else mut, out, flush=True)
