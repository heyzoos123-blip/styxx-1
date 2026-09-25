# X34b's fixture is FunctionType(Handle._run.__code__, vars(fx)). E2 scans only codes *new to the cut*, and the
# stdlib codes are new at the process's first coverage_trace(). If the fixture clone exists then (fixture modules
# imported at exam start-up), the stdlib Handle._run code is "shareable": CUT_UNAVAILABLE, and it never enters the
# cut, so every later coverage_trace() in the process refuses too, while the clone lives. X34b's RESERVED_TARGET
# needs the clone to be created after the first coverage_trace(); the spec does not say so.
import sys, types, asyncio.events as ev
sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/rev2')
import mech2 as mech
v = sys.version.split()[0]
def f(): return 1
for when in ('clone made after the first coverage_trace()', 'clone made before it (fixture imported at start-up)'):
    mech._CUT.clear()
    if 'before' in when:
        clone = types.FunctionType(vars(ev.Handle)['_run'].__code__, {}, 'fx_clone')
        outs = []
        for i in range(3):
            try: mech.cut_refresh(); outs.append('ok')
            except mech.CutUnavailable as e: outs.append('CUT_UNAVAILABLE')
    else:
        mech.cut_refresh()
        clone = types.FunctionType(vars(ev.Handle)['_run'].__code__, {}, 'fx_clone')
        outs = []
        for i in range(3):
            try: mech.cut_refresh(); outs.append('ok')
            except mech.CutUnavailable as e: outs.append('CUT_UNAVAILABLE')
    print(v, '%-52s' % when, 'three coverage_trace() calls ->', outs)
    del clone
