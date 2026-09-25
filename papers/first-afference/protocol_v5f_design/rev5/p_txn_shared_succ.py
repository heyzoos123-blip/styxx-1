# N6: `_Txn(tid, fid, code, succ={})` read as a mutable default: one succ dict shared by every token. The robust
# mutex's walk (M2) then cycles at the second acquisition. A fresh dict per token (the spec) works.
import sys
SHARED = {}
class Txn:
    def __init__(self, shared):
        self.succ = SHARED if shared else {}
def run(shared, n=3, limit=1000):
    guard = {'hint': Txn(shared)}
    out = []
    for i in range(n):
        me = Txn(shared); r = guard['hint']; steps = 0
        while 'next' in r.succ:                     # walk to the last token (every earlier one is released/dead)
            r = r.succ['next']; steps += 1
            if steps > limit: out.append('transaction %d: walk did not end (cycle)' % (i + 1)); return out
        if r.succ.setdefault('next', me) is me: guard['hint'] = me
        me.succ.setdefault('next', Txn(shared))      # _release
        out.append('transaction %d: acquired after %d steps' % (i + 1, steps))
    return out
print(sys.version.split()[0], 'fresh dict per token:', run(False))
SHARED.clear()
print(sys.version.split()[0], 'one shared dict     :', run(True))
