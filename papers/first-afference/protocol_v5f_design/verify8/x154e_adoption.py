# verify8 (wide self-audit, W7): "A tool left named ours with missing callbacks (a fault, including a raising audit
# hook, inside `_register`) is adopted and re-registered at the next enter when `_TOOL[0]` is None" (Exception-safety,
# Per-transition prefixes; also "If `_TOOL[0]` was None, the next enter adopts the id and registers again"). No exam
# case reached the adoption path (the Revision 8 section says so for N1).
# Shape: fresh process. An audit hook raises at the 3rd `sys.monitoring.register_callback` event of the first enter
# (E4's first acquisition of id 4, after its take), then disarms. The enter raises; id 4 is left named styxx's with
# only its PY_START and PY_RESUME callbacks; `_TOOL[0]` is None. A second tracer on f is entered and runs A: f.
# Spec: the second enter adopts id 4 and registers all five callbacks: tool 4, PASS {f:1}, no MONITOR_LOST.
# Mutant 'adopt_no_register' (an adopted id is not registered again): f's return is never delivered: {} (NOT_EXERCISED).
import sys, os, json, subprocess, threading
R8 = '/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/rev8'
HERE = os.path.dirname(os.path.abspath(__file__))

def child(mut):
    if mut == 'adopt_no_register':
        src = open(os.path.join(R8, 'mech8.py')).read()
        old = ("        if not _named(i):\n            _take(i)\n            if not _named(i): continue\n"
               "        ok, _r = _register_checked(i, 'ensure')\n")
        assert src.count(old) == 1
        src = src.replace(old, "        adopted = _named(i)\n        if not adopted:\n            _take(i)\n"
                               "            if not _named(i): continue\n"
                               "        ok, _r = (True, False) if adopted else _register_checked(i, 'ensure')\n")
        path = os.path.join(HERE, '_mech8_adopt_no_register.py'); open(path, 'w').write(src)
        sys.path.insert(0, HERE); import _mech8_adopt_no_register as mech
    else:
        sys.path.insert(0, R8); import mech8 as mech
    def f(): return 1
    tid = threading.get_ident(); H = {'arm': True, 'n': 0}
    def hook(ev, args):
        if ev == 'sys.monitoring.register_callback' and H['arm'] and threading.get_ident() == tid:
            H['n'] += 1
            if H['n'] == 3: H['arm'] = False; raise RuntimeError('hook3')
    sys.addaudithook(hook)
    P = mech.Tracer(f)
    try: P.__enter__(); first = 'entered'
    except RuntimeError as e: first = 'raised ' + str(e)
    after_first = dict(tool=mech.TOOL[0], id4_name_is_ours=sys.monitoring.get_tool(4) == mech.NAME)
    Q = mech.Tracer(f); Q.__enter__(); Q.run('A', f); Q.__exit__(None, None, None)
    return dict(mut=mut, first_enter=first, after_first=after_first, tool=mech.TOOL[0],
                Q_calls=Q.result()['calls'], Q_lost=Q.result()['MONITOR_LOST'])

if __name__ == '__main__':
    if len(sys.argv) == 2:
        print(json.dumps(child(None if sys.argv[1] == '-' else sys.argv[1]), default=repr)); sys.exit(0)
    for mut in ('-', 'adopt_no_register'):
        p = subprocess.run([sys.executable, __file__, mut], capture_output=True, text=True, timeout=120)
        out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else 'ERROR ' + p.stderr[-800:]
        print(sys.version.split()[0], 'X154e', 'spec' if mut == '-' else mut, out, flush=True)
