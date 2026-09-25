# X135: tool id 3 calls PyThreadState_SetAsyncExc at the target's PY_START. Does the body run, and is the
# call confirmed under the v5f rule? Also the variant where the target's first statement is a call.
import sys, ctypes, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech
M = sys.monitoring; E = M.events
class Kill(Exception): pass
ran = []
def f1():
    ran.append(1)                 # body: a call first
    return 1
def f2():
    x = 1                         # body: no call, no back-edge before the return
    ran.append(x)
    return x
def arm(code):
    def cb(c, off):
        if c is code:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(threading.get_ident()), ctypes.py_object(Kill))
    M.use_tool_id(3, 'fault'); M.register_callback(3, E.PY_START, cb); M.set_local_events(3, code, E.PY_START)
def disarm(code):
    M.set_local_events(3, code, 0); M.free_tool_id(3)
for fn in (f1, f2):
    ran.clear()
    with mech.Tracer(fn) as tr:
        arm(fn.__code__)
        try: tr.run('A', fn)
        except Kill: pass
        disarm(fn.__code__)
    print(sys.version.split()[0], fn.__name__, 'body ran:', bool(ran), '| credited:', tr.result()['calls'])
