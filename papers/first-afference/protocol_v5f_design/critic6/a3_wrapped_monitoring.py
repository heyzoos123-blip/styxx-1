import sys, threading, types
M = sys.monitoring; E = M.events
_real_set_events = M.set_events
W = {'armed': False, 'wait': None}
def set_events(tool, ev):                  # a pass-through wrapper that may block (log, lock, I/O)
    if W['armed'] and ev == 0:
        W['armed'] = False; W['wait']()
    return _real_set_events(tool, ev)
M.set_events = set_events
sys.path.insert(0, '/home/user/styxx-1/papers/first-afference/protocol_v5f_design/rev5')
import mech5 as mech
print(sys.version.split()[0], 'bound set_events is a C builtin?', type(mech._set_events) is types.BuiltinFunctionType)
def t(): raise KeyError
def catch_t():
    try: t()
    except KeyError: pass
mech.reset()
tr = mech.Tracer(t); tr.__enter__()
armedB = threading.Event(); cleared = threading.Event(); S_in_body = []
def bodyB():
    armedB.set(); cleared.wait(5)
    S_in_body.append(mech.events_set()); catch_t(); return 1
thB = threading.Thread(target=lambda: tr.run('B', bodyB))
def wait_in_wrapper():
    thB.start(); armedB.wait(5)            # B stores its anchor, finds S set, arms, enters its body
W['wait'] = wait_in_wrapper
W['armed'] = True
tr.run('A', lambda: 0)                     # A's close: the one call pops A, sees no anchor, calls the wrapper
cleared.set(); thB.join()
tr.__exit__(None, None, None)
r = tr.result()
print(' S seen inside armed body B:', S_in_body, '| B counted t:', r['calls'].get('B'), '| MONITOR_LOST:', r['MONITOR_LOST'])
