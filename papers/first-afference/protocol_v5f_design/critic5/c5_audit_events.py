# Which C calls inside the revision-4 machinery raise audit events (so run arbitrary audit-hook code, and can raise)?
import sys, threading
seen = []
def hook(ev, args):
    if ev in ('sys._getframe', 'sys._current_frames', 'object.__setattr__', 'gc.get_referrers'): seen.append(ev)
sys.addaudithook(hook)
def txn(): return sys._getframe(1)
def unwind_off(): me = txn(); return me
unwind_off(); a = list(seen); seen.clear()
sys._current_frames(); b = list(seen); seen.clear()
import time; t0=time.perf_counter()
for i in range(10000): sys._current_frames()
cf = (time.perf_counter()-t0)/10000*1e6
ths=[threading.Thread(target=time.sleep, args=(1,)) for _ in range(50)]
[t.start() for t in ths]
t0=time.perf_counter()
for i in range(2000): sys._current_frames()
cf50 = (time.perf_counter()-t0)/2000*1e6
[t.join() for t in ths]
print(sys.version.split()[0], '_txn():', a, '| _alive():', b, '| _current_frames us: 1 thread %.2f, 51 threads %.2f' % (cf, cf50))
