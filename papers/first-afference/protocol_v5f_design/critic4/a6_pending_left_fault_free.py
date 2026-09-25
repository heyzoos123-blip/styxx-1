# Fault-free: a target frame entered while SOME anchor is registered anywhere (entry stored), that raises after the
# last anchor closed (S clear, no PY_UNWIND), leaves its pending entry until _retire. With the G_FI background
# tracer holding the shared mint for the whole sweep, `_v5_state()["mints"][..]["pending"]` then differs from S0,
# so C5 ("equals S0 except cut and tool") fails for a correct implementation unless the scenario avoids this shape.
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech3 as mech
closed = threading.Event()
def t():
    closed.wait(5); raise KeyError
def other(): return 0
with mech.Tracer(t, other) as bg:                     # the "background" tracer holding t's mint
    opened, go = threading.Event(), threading.Event()
    th = threading.Thread(target=lambda: bg.run('B', lambda: (opened.set(), go.wait(5)))); th.start(); opened.wait(5)
    def caller():
        try: t()                                      # outside any section: entry stored, since B's anchor exists
        except KeyError: pass
    c = threading.Thread(target=caller); c.start()
    import time; time.sleep(0.1); go.set(); th.join(); closed.set(); c.join()
    m = [m for m in mech._MINTED.values() if m.fn is t][0]
    print(sys.version.split()[0], 'fault-free: pending entries left on the held mint:', len(m.pend), '| anchors', len(mech._ANCHORS), 'events', mech.M.get_events(4))
