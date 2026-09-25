# The cut is process-wide and monotone, and the exam runs every rebinding case in one process (main thread, before
# the self-trace). If two cases use the same module-level wrapper, the earlier case's E2 leaves its code in the cut,
# and the later case's expected outcome flips: X35c (twin alive -> CUT_UNAVAILABLE) is accepted, and X141 (rebind
# during the trace -> CUT_MOVED) passes silently. The spec never requires a fresh wrapper code per case.
import sys, types, asyncio, asyncio.events as ev
sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/rev2')
import mech2 as mech
H = ev.Handle; ORIG = vars(H)['_run']
def W(self): return ORIG(self)          # a fixture's top-level wrapper (V61's shape)
def f(): return 1
def v61():
    H._run = W
    try:
        with mech.Tracer(f) as tr: tr.run('A', f)
        return tr.result()['calls'], tr.result()['CUT_MOVED']
    finally: H._run = ORIG
def x35c():
    twin = types.FunctionType(W.__code__, globals(), 'twin'); H._run = W
    try:
        with mech.Tracer(f) as tr: tr.run('A', f)
        return 'accepted', tr.result()['calls']
    except mech.CutUnavailable as e: return 'CUT_UNAVAILABLE', str(e)
    finally: H._run = ORIG; del twin
def x141():
    with mech.Tracer(f) as tr:
        H._run = W
        tr.run('G', f)
    H._run = ORIG
    return 'CUT_MOVED' if tr.result()['CUT_MOVED'] else 'no CUT_MOVED'
v = sys.version.split()[0]
mech._CUT.clear(); mech.cut_refresh()
print(v, 'fresh process: X35c ->', x35c()[0], '| X141 ->', x141())
mech._CUT.clear(); mech.cut_refresh()
print(v, 'after V61 ran with the same W', v61(), ': X35c ->', x35c()[0], '| X141 ->', x141())
