# Revision 6, M1: a pass-through Python wrapper on sys.monitoring.set_events installed BEFORE the first
# coverage_trace() (critic6/a3's shape), and a Python subclass bound as itertools.chain before import.
# Revision 6 refuses UNSUPPORTED_VERSION at binding; with the check removed (MUT 'no_builtin_check') the wrapper is
# captured and U1 fails as in critic6/a3. Each variant runs in a fresh subprocess (binding happens once per process).
import sys, subprocess, os
HERE = os.path.dirname(os.path.abspath(__file__))
CHILD = r'''
import sys, threading, itertools
sys.path.insert(0, HERE)
M = sys.monitoring; E = M.events
VARIANT, MUTANT = sys.argv[1], sys.argv[2] == '1'
if VARIANT == 'wrap_set_events':
    _real = M.set_events
    W = {'armed': False, 'wait': None}
    def set_events(tool, ev):
        if W['armed'] and ev == 0:
            W['armed'] = False; W['wait']()
        return _real(tool, ev)
    M.set_events = set_events
elif VARIANT == 'patched_chain':
    class chain(itertools.chain): pass
    itertools.chain = chain
import mech6 as mech
if MUTANT: mech.MUT.add('no_builtin_check'); mech.bind(); mech.MUT.clear()   # bind with the check removed
try:
    mech.reset()
except mech.Unsupported as e:
    print('refused at the first binding:', e); sys.exit(0)
mut = set(mech.MUT)
if VARIANT != 'wrap_set_events':
    print('bound; chain is', mech._chain); sys.exit(0)
def t(): raise KeyError
def catch_t():
    try: t()
    except KeyError: pass
tr = mech.Tracer(t); tr.__enter__()
armedB = threading.Event(); cleared = threading.Event(); S_in_body = []
def bodyB():
    armedB.set(); cleared.wait(5)
    S_in_body.append(mech.events_set()); catch_t(); return 1
thB = threading.Thread(target=lambda: tr.run('B', bodyB))
def wait_in_wrapper():
    thB.start(); armedB.wait(5)
W['wait'] = wait_in_wrapper; W['armed'] = True
tr.run('A', lambda: 0)
cleared.set(); thB.join()
tr.__exit__(None, None, None)
r = tr.result()
print('bound the wrapper; S inside armed body B:', S_in_body, '| B counted t:', r['calls'].get('B'), '| MONITOR_LOST:', r['MONITOR_LOST'])
'''.replace('HERE', repr(HERE))
for variant in ('wrap_set_events', 'patched_chain'):
    for mutant in ('0', '1'):
        out = subprocess.run([sys.executable, '-c', CHILD, variant, mutant], capture_output=True, text=True, timeout=60)
        print(sys.version.split()[0], variant, 'rev6' if mutant == '0' else 'no_builtin_check', '->',
              (out.stdout.strip() or out.stderr.strip().splitlines()[-1]), flush=True)
