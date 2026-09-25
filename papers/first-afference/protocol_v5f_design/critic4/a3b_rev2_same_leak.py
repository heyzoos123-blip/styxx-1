# Is a3's leak new in revision 3? Revision 2 (mech3.REV3 = False) commits in _open with the frame argument.
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech3 as mech
mech.REV3[0] = False
def f(): return 1
sys.setswitchinterval(1e-6); leaks = 0; kinds = set(); n = 20000
for i in range(n):
    tr = mech.Tracer(f); tr.__enter__()
    th = threading.Thread(target=lambda: tr.run('A', f)); th.start()
    tr.__exit__(None, None, None); th.join()
    if mech._ANCHORS:
        leaks += 1; kinds.update(type(k).__name__ for k in mech._ANCHORS); mech._ANCHORS.clear()
print(sys.version.split()[0], 'revision 2 natural: anchor leaked after exit in %d of %d races, key types %s' % (leaks, n, sorted(kinds)))
