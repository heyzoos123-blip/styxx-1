# L-MONITOR / X137c: a party that clears styxx's global PY_UNWIND mid-section blinds the trace, and "exit detects it
# and adds the MONITOR_LOST note" via the close's UNWIND_LOST test. That test reads the event at close time. Any
# other section that opens (on any thread, any tracer) between the external clear and the close re-sets the event
# through its own _unwind_on(), so the close finds it set: the lost call is silent (NOT_EXERCISED, no note).
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
M = mech.M
def f(): return 1
def g(): raise KeyError
def h(): return 3
def reset():
    mech._ANCHORS.clear(); mech._CLEARING.clear(); mech._HOOK[0] = None
    if M.get_tool(4) is not None: M.set_events(4, 0)
def run(reopen):
    reset()
    with mech.Tracer(f, g) as tr, mech.Tracer(h) as other:
        def body():
            f(); M.set_events(4, 0)                 # the external party clears styxx's event
            try: g()                                 # g raises inside its body: its unwind is not seen
            except KeyError: pass
            if reopen:                               # an unrelated section opens and closes on another thread
                th = threading.Thread(target=lambda: other.run("B", h)); th.start(); th.join()
        tr.run('G', body)
    r = tr.result()
    return dict(other_section_in_between=reopen, calls_G=r['calls'].get('G'), MONITOR_LOST=r['MONITOR_LOST'])
v = sys.version.split()[0]
for reopen in (False, True): print(v, run(reopen))
