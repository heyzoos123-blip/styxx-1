# Does E2's gc-referrer clause see a live twin that gc.freeze() moved to the permanent generation?
# And does it see a dead-but-uncollected twin (false refusal depending on gc timing)?
import sys, gc, types
sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/rev2')
import mech2 as mech, asyncio.events as ev
H = ev.Handle; ORIG = vars(H)['_run']
def W1(self): return ORIG(self)
def W2(self): return ORIG(self)
def W3(self): return ORIG(self)
def tryit(W):
    mech._CUT.clear(); mech.cut_refresh()
    H._run = W
    try: mech.cut_refresh(); r = 'accepted (code enters the cut)'
    except mech.CutUnavailable as e: r = 'CUT_UNAVAILABLE ' + str(e)
    H._run = ORIG; return r
v = sys.version.split()[0]
twin = types.FunctionType(W1.__code__, {'ORIG': ORIG}, 'twin')
print(v, 'live twin, not frozen      :', tryit(W1))
twin2 = types.FunctionType(W2.__code__, {'ORIG': ORIG}, 'twin2')
gc.freeze()
print(v, 'live twin, frozen          :', tryit(W2), '| twin alive:', twin2 is not None)
gc.unfreeze()
# dead twin in a reference cycle, not yet collected
gc.disable()
t3 = types.FunctionType(W3.__code__, {'ORIG': ORIG}, 'twin3'); t3.self = t3; del t3
print(v, 'dead twin in a cycle       :', tryit(W3))
gc.collect(); gc.enable()
print(v, 'same after gc.collect()    :', tryit(W3))
