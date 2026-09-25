# BF1 and M8: the callback-only functions (_on_entry, _on_exit, _on_unwind, _outcome, _publish) raise no events
# while they run as sys.monitoring callbacks, so no line-coverage tool and no INSTRUCTION injector sees them.
# The rev-2 driver calls them directly, outside any callback, as FunctionType(code, module globals) built from
# the code objects a _v5_faultpoints()-style map returns, inside a real trace and section.
# Measured: (1) lines of each function seen by a LINE tool (coverage.py sysmon's mechanism) and by settrace
# (ctrace's mechanism) during a real traced call, and during the driver; (2) whether an INSTRUCTION injector on
# tool 5 fires at the functions' back-edges (JUMP_BACKWARD) in each setting.
import sys, dis, types
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech2 as mech
M = sys.monitoring; E = M.events
CB = ('_on_entry', '_on_exit', '_on_unwind', '_outcome', '_publish')
faultpoints = {n: getattr(mech, n).__code__ for n in CB}   # stands for _v5_faultpoints()
codes = {c: n for n, c in faultpoints.items()}
lines_mon, lines_st, backedge_hits = {n: set() for n in CB}, {n: set() for n in CB}, {n: 0 for n in CB}
backedges = {n: {i.offset for i in dis.get_instructions(c) if i.opname.startswith('JUMP_BACKWARD')} for n, c in faultpoints.items()}
def line_cb(code, line):
    n = codes.get(code)
    if n: lines_mon[n].add(line)
def instr_cb(code, off):
    n = codes.get(code)
    if n and off in backedges[n]: backedge_hits[n] += 1
def st(frame, event, arg):
    n = codes.get(frame.f_code)
    if n and event == 'line': lines_st[n].add(frame.f_lineno)
    return st
M.use_tool_id(1, 'line-cover'); M.register_callback(1, E.LINE, line_cb)
M.use_tool_id(5, 'injector'); M.register_callback(5, E.INSTRUCTION, instr_cb)
for c in faultpoints.values():
    M.set_local_events(1, c, E.LINE); M.set_local_events(5, c, E.INSTRUCTION)

def f(): return 1
def g(): raise KeyError
def deep(n, fn):
    if n == 0: return fn()
    return deep(n - 1, fn)
def snapshot():
    return {n: len(lines_mon[n]) for n in CB}, {n: len(lines_st[n]) for n in CB}, dict(backedge_hits)
def reset():
    for n in CB: lines_mon[n].clear(); lines_st[n].clear(); backedge_hits[n] = 0

# settrace suppresses tool 5's INSTRUCTION events (dbg2.py), so the injector pass runs without it
# (1) real traced calls: two tracers share f's mint (two holders), a raising g, depth 5
sys.settrace(st)
with mech.Tracer(f, g) as t1:
    with mech.Tracer(f) as t2:
        def body():
            deep(5, f)
            try: deep(3, g)
            except KeyError: pass
        t1.run('A', lambda: t2.run('B', body))
sys.settrace(None)
real = snapshot(); real_rec = (t1.result()['calls'], t2.result()['calls'])
reset()

def driver_pass():
    # (2) the direct-call driver: the same code objects, called outside any callback
    global fn
    fn = {n: types.FunctionType(c, vars(mech)) for n, c in faultpoints.items()}
    with mech.Tracer(f) as t1:
        with mech.Tracer(f) as t2:
            m = mech._MINTED[id(f.__code__)]
            def fake_target_frame():                # a frame with f's globals, called under both anchors
                mcode = f.__code__
                fn['_on_entry'](mcode, 0)            # PY_START shape: stores a pending entry for this frame
                fn['_on_exit'](mcode, 10, None)       # PY_RETURN shape: pops and publishes
                fn['_on_entry'](mcode, 0)
                fn['_on_unwind'](mcode, 12, None)     # PY_UNWIND past the entry offset: publishes
                fn['_on_entry'](mcode, 0)
                fn['_on_unwind'](mcode, 0, None)      # PY_UNWIND at the entry offset: dropped
                fn['_on_entry'](g.__code__, 0)        # not minted: early return
                return 0
            t1.run('A', lambda: t2.run('B', lambda: deep(5, fake_target_frame)))
            def call_off_section(): fn['_on_entry'](f.__code__, 0); fn['_on_exit'](f.__code__, 10, None)
            call_off_section()                         # no anchor on the chain
    return t1, t2

sys.settrace(st); driver_pass(); sys.settrace(None)            # pass A: settrace (ctrace's mechanism)
st_lines = {n: len(lines_st[n]) for n in CB}
reset()
M.restart_events()                                              # settrace left tool 5's INSTRUCTION events off (p5b)
t1, t2 = driver_pass()                                          # pass B: LINE tool and INSTRUCTION injector, no settrace
drv = snapshot(); drv = (drv[0], st_lines, drv[2]); drv_rec = (t1.result()['calls'], t2.result()['calls'])
total = {n: len([l for l in set(i.positions.lineno for i in dis.get_instructions(c) if i.positions and i.positions.lineno)]) for n, c in faultpoints.items()}
ver = sys.version.split()[0]
print(ver, 'body lines per function              ', total)
print(ver, 'real callbacks: LINE-tool lines       ', real[0], '| settrace lines', real[1], '| back-edge injector hits', real[2], '| record', real_rec)
print(ver, 'direct-call driver: LINE-tool lines   ', drv[0], '| settrace lines', drv[1], '| back-edge injector hits', drv[2], '| record', drv_rec)
print(ver, 'back-edges per function (JUMP_BACKWARD*)', {n: sorted(v) for n, v in backedges.items()})
