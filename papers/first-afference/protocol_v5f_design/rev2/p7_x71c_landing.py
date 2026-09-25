# M7: X71c's port needs a SIGALRM handler to call f inside exit's X3 (after the credit stop X2, while G's on-stack
# opening is still registered). How often does a trial land, by the number of suspended openings K, and does a
# landed trial separate the spec (credit stop, then detach) from the M10 mutant (detach, then credit stop)?
# A trial "lands" iff the handler called f in the window; that is observable (the rev-2 port uses the witness
# tracer's union for it). Rev 2 repeats void trials up to a frozen bound.
import sys, signal, types
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech2 as mech
def f(): return 1

class Mutant(mech.Tracer):                          # M10: credit stop after detach
    def __exit__(self, *a):
        for o in list(self.core.openings): mech._detach(o)
        self.core.by_code = {}
        return super().__exit__(*a)

def trial(K, cls):
    tr = cls(f).__enter__()
    @types.coroutine
    def suspend(): yield
    async def afn(): await suspend()
    coros = []
    for _ in range(K):
        c = tr.run_async('G', afn); c.send(None); coros.append(c)
    landed = []
    def body():
        start = len(mech._ANCHORS)
        def handler(*a):
            n = len(mech._ANCHORS)
            if not landed and 1 <= n < start: landed.append(n); f()
        signal.signal(signal.SIGALRM, handler)
        signal.setitimer(signal.ITIMER_REAL, 0.0002, 0.0002)
        tr.__exit__(None, None, None)
        signal.setitimer(signal.ITIMER_REAL, 0, 0)
    tr.run('G', body)                               # G's on-stack opening, appended last, detached last
    for c in coros: c.close()
    return bool(landed), tr.result()['calls']

ver = sys.version.split()[0]
for K in (1_000, 10_000, 100_000):
    for cls, label in ((mech.Tracer, 'spec  '), (Mutant, 'mutant')):
        res = [trial(K, cls) for _ in range(10)]
        landed = sum(1 for l, _ in res if l)
        credited = sum(1 for l, c in res if l and c.get('G', {}).get('f'))
        print(ver, 'K=%-7d %s: landed %2d/10; of landed trials, G credited f in %d' % (K, label, landed, credited))
