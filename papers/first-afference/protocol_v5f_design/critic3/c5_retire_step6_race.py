# M3 _retire step 6 ("if _ANCHORS is empty and the id carries _TOOL_NAME, set_events(tool, 0)") has no re-check,
# and openers never take the mutex. Interleaving: tracer X's exit tests _ANCHORS (empty) -> tracer Y, still active,
# opens section B on another thread (its _unwind_on sets PY_UNWIND, commits, re-checks: already set) -> X's step 6
# clears. B then runs with no PY_UNWIND for its whole life: a target that raises inside its body is never counted,
# and B's close sets UNWIND_LOST (MONITOR_LOST). The spec says "in every interleaving an open section ends with the
# event set" and I3 says the event is set while some anchor is registered.
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/rev2')
import mech2 as mech
M = sys.monitoring; E = M.events
def t(): raise KeyError
def other(): return 0
def body(ready, go):
    ready.set(); go.wait(5)          # B is open (anchor committed, both _unwind_on calls done) before t runs
    try: t()
    except KeyError: pass
def step6(tested, resume):           # spec M3 _retire step 6, with the pause the scheduler may insert
    if not mech._ANCHORS and mech._ours():
        tested.set(); resume.wait(5)
        M.set_events(mech.TOOL[0], 0)
def run(race):
    with mech.Tracer(t) as Y:                     # Y: active tracer that will open B
        tested, resume, ready, go = (threading.Event() for _ in range(4))
        ex = threading.Thread(target=step6, args=(tested, resume))
        if race: ex.start(); tested.wait(5)       # X's exit has seen _ANCHORS empty
        tb = threading.Thread(target=lambda: Y.run('B', body, ready, go)); tb.start(); ready.wait(5)
        if race: resume.set(); ex.join(5)         # X's step 6 clears after B committed
        ev_during = M.get_events(mech.TOOL[0])
        go.set(); tb.join(5)
    r = Y.result()
    return {'calls': r['calls'], 'MONITOR_LOST': r['MONITOR_LOST'], 'global_events_while_B_open': ev_during}
v = sys.version.split()[0]
print(v, 'no race              :', run(False))
print(v, 'retire step 6 races  :', run(True))
