# Which instruments run Python code between `_ANCHORS` test and the following C call in the one-line
# `if D or set_events(...): return` shape (spec M7 _unwind_off)? The instrument's callback, when it runs in off()'s
# frame, makes D non-empty. r is an int only when D was empty at the test; r == 1 means D became non-empty between
# the test and the C call, i.e. the instrument ran Python code (with eval-breaker checks) inside the expression.
import sys, threading, cProfile, profile, time
M = sys.monitoring; E = M.events
D = {}
def off():
    return D or len(D)          # same shape as `if _ANCHORS or set_events(_TOOL[0], 0): return`
OFF = off.__code__
import dis
_TEST = [i.offset for i in dis.get_instructions(OFF) if 'JUMP_IF' in i.opname][0]
def poke(frame):
    # only a callback that runs after the emptiness test was executed (f_lasti past the conditional jump) pokes
    if frame is not None and frame.f_code is OFF and frame.f_lasti > _TEST: D['x'] = 1
def trial(name, arm, disarm, n=5):
    split = 0
    for _ in range(n):
        D.clear(); arm()
        try: r = off()
        finally: disarm()
        if type(r) is int and r == 1: split += 1
        D.clear()
    print('%-8s %-52s split %d/%d' % (sys.version.split()[0], name, split, n))
def prof(frame, event, arg): poke(frame)
def tr(frame, event, arg):
    if frame.f_code is OFF: poke(frame)
    return tr
def tr_ops(frame, event, arg):
    if frame.f_code is OFF: frame.f_trace_opcodes = True; poke(frame) if event == 'opcode' else None
    return tr_ops
def mon(ev, local=True):
    def cb(*a): poke(sys._getframe(1))
    def arm():
        M.use_tool_id(2, 'probe'); M.register_callback(2, ev, cb)
        if ev in (E.C_RETURN, E.C_RAISE): M.register_callback(2, E.CALL, None)
        if ev == E.C_RETURN: M.set_events(2, E.CALL | E.C_RETURN | E.C_RAISE); return   # C_RETURN needs CALL; global only
        M.set_local_events(2, OFF, ev) if local else M.set_events(2, ev)
    def disarm():
        M.set_local_events(2, OFF, 0); M.set_events(2, 0); M.register_callback(2, ev, None); M.free_tool_id(2)
    return arm, disarm
trial('none', lambda: None, lambda: None)
trial('sys.setprofile(pure Python fn)  [V48 shape]', lambda: sys.setprofile(prof), lambda: sys.setprofile(None))
trial('threading.setprofile_all_threads(pure Python fn)', lambda: threading.setprofile_all_threads(prof), lambda: threading.setprofile_all_threads(None))
_c = [None]
def carm():
    def timer(): poke(sys._getframe(1)); return time.perf_counter()
    _c[0] = cProfile.Profile(timer); _c[0].enable()
trial('cProfile.Profile(timer=<python fn>)', carm, lambda: _c[0].disable())
trial('sys.settrace, line events', lambda: sys.settrace(tr), lambda: sys.settrace(None))
trial('sys.settrace + f_trace_opcodes [spec: acknowledged]', lambda: sys.settrace(tr_ops), lambda: sys.settrace(None))
for nm, ev in (('LINE', E.LINE), ('CALL', E.CALL), ('C_RETURN (global, CALL enabled with no CALL callback)', E.C_RETURN), ('BRANCH', E.BRANCH), ('JUMP', E.JUMP), ('INSTRUCTION [spec: acknowledged]', E.INSTRUCTION)):
    a, d = mon(ev); trial('sys.monitoring tool 2, local ' + nm, a, d)
    if ev in (E.CALL, E.LINE):
        a, d = mon(ev, local=False); trial('sys.monitoring tool 2, global ' + nm, a, d)
