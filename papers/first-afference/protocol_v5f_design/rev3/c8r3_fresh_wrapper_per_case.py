# MF4 harness rule, checked on the model: critic3/c8_cut_order_dependence.py, with every rebinding case using its
# own fresh top-level wrapper (a code never bound or scanned before in the process). After V61 has put its wrapper's
# code in the monotone cut, X35c and X141 keep their fresh-process outcomes.
import sys, types, asyncio, asyncio.events as ev
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech3 as mech
H = ev.Handle; ORIG = vars(H)['_run']
def W_v61(self): return ORIG(self)
def W_x35c(self): return ORIG(self)
def W_x141(self): return ORIG(self)
def f(): return 1
def v61(W):
    H._run = W
    try:
        with mech.Tracer(f) as tr: tr.run('A', f)
        return tr.result()['calls'], tr.result()['CUT_MOVED']
    finally: H._run = ORIG
def x35c(W):
    twin = types.FunctionType(W.__code__, globals(), 'twin'); H._run = W
    try:
        with mech.Tracer(f) as tr: tr.run('A', f)
        return 'accepted'
    except mech.CutUnavailable as e: return 'CUT_UNAVAILABLE'
    finally: H._run = ORIG; del twin
def x141(W):
    with mech.Tracer(f) as tr:
        H._run = W
        tr.run('G', f)
    H._run = ORIG
    return 'CUT_MOVED' if tr.result()['CUT_MOVED'] else 'no CUT_MOVED'
v = sys.version.split()[0]
mech._CUT.clear(); mech.cut_refresh()
print(v, 'shared W (critic c8):  V61', v61(W_v61), '-> X35c', x35c(W_v61), '| X141', x141(W_v61))
mech._CUT.clear(); mech.cut_refresh()
print(v, 'fresh W per case:      V61', v61(W_v61), '-> X35c', x35c(W_x35c), '| X141', x141(W_x141))
