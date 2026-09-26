# verify8: every audit event raised on the case thread during one cov.run('A', f) on rev8/mech8.py (f raises none).
import sys, os, threading
sys.path.insert(0, '/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/rev8')
import mech8 as mech
def f(): return 1
P = mech.Tracer(f); P.__enter__(); P.run('A', f)
tid = threading.get_ident(); ev = []; arm = [False]
sys.addaudithook(lambda e, a: ev.append(e) if arm[0] and threading.get_ident() == tid else None)
def outer(): return P.run('A', f)
arm[0] = True; outer(); arm[0] = False
P.__exit__(None, None, None)
print(sys.version.split()[0], 'audit events during one run():', ev)
