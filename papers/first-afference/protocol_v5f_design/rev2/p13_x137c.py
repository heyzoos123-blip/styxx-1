# X137c (M4): inside G, f is called, then a party clears styxx's global events, then g raises inside its body and is
# caught inside G. g's unwind is not seen (not counted); G's close finds PY_UNWIND cleared -> MONITOR_LOST.
import sys
sys.path.insert(0, '.')
import mech2 as mech
M = sys.monitoring
def f(): return 1
def g(): raise KeyError
with mech.Tracer(f, g) as tr:
    def body():
        f(); M.set_events(4, 0)
        try: g()
        except KeyError: pass
    tr.run('G', body)
r = tr.result()
print(sys.version.split()[0], 'X137c record', r['calls'], 'MONITOR_LOST', r['MONITOR_LOST'])
with mech.Tracer(f, g) as tr:                           # control: no clearing
    def body2():
        f()
        try: g()
        except KeyError: pass
    tr.run('G', body2)
r = tr.result()
print(sys.version.split()[0], 'control record', r['calls'], 'MONITOR_LOST', r['MONITOR_LOST'])
