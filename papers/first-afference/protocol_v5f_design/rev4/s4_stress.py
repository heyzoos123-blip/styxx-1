# Randomized interleaving and fault stress on mech4.py: revision 3's s1 extended with (i) a hand-off between the
# _ANCHORS test and the clear ('off:tested'), which revision 3 can have only under an instrument that splits its
# one-line expression (REV 3s = revision 3 with SPLIT), and (ii) open-versus-own-exit races: in every round the main
# thread enters tracer Z, a racer thread opens Z's sections in a loop, and the main thread exits Z while it does.
# Usage: s4_stress.py REV(3|3s|4) MODE(clean|fault|fault-nodead) ROUNDS SEED
# Threads: W1..W3 loop Y.run('S', body) (body samples the event, calls t which raises inside, samples again);
#   R loops `with Tracer(u): pass` (retire step 6 and the reconciliation's _unwind_off); ZR races Z's exit.
# Every hook point yields the GIL with probability 0.3 at a 1 us switch interval. Fault modes raise Injected with
# probability 0.02 at hook points of W1..W3, R and ZR; fault-nodead skips the points inside _detach before its pop.
# Checks: U1 (in-body samples), C (Y counts every t call; no MONITOR_LOST on Y), Z: after each Z exit and ZR's join,
# no anchor of Z registered (B1) and no UNWIND_LOST on Z (f returns: every flag is false); quiescence as in s1.
import sys, threading, random, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
REVS, MODE, ROUNDS, SEED = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
Z = not (len(sys.argv) > 5 and sys.argv[5] == 'noz')   # noz: no Z races (so revision 3's B1 leak cannot mask U1)
mech.REV4[0] = REVS == '4'; mech.SPLIT[0] = REVS == '3s'
if REVS != '4':                                   # revision 3 as specified: step 8's re-check in _commit
    def commit_rev3_spec(o):
        mech._hk('commit:0'); mech._unwind_on(); mech._hk('commit:1')
        mech._ANCHORS[o.frame] = o
        mech._hk('commit:2'); mech._unwind_on(); mech._hk('commit:3')
        if o.core.exiting:
            mech._detach(o); raise mech.TraceInactive('[V5:TRACE_INACTIVE]')
        o.armed = True
    mech._commit = commit_rev3_spec
sys.setswitchinterval(1e-6)
class Injected(BaseException): pass
DEAD_POINTS = ('detach:claimed', 'detach:checked')
def t(): raise KeyError
def u(): return 0
def f(): return 1
tl = threading.local()
faults = {}
def hook(p):
    r = getattr(tl, 'rng', None)
    if r is None: return
    if p == 'detach:claimed': tl.predpop = True
    elif p == 'detach:popped': tl.predpop = False
    if r.random() < 0.3: time.sleep(0)
    if MODE != 'clean' and getattr(tl, 'faultable', False) and r.random() < 0.02:
        if MODE == 'fault-nodead' and (p in DEAD_POINTS or getattr(tl, 'predpop', False)): return
        if p == 'detach:claimed' or getattr(tl, 'predpop', False): tl.predpop = False
        faults[p] = faults.get(p, 0) + 1
        raise Injected
stats = dict(bodies=0, samples=0, unset=0, faults=0, retire=0, q=0, stale=0, stale_after=0, dead_rounds=0,
             anchor_no_event=0, z_races=0, z_leak=0, z_lost=0, z_inactive=0, z_ran=0, clearing_after=0)
PER = []
def body():
    c = tl.c; c['bodies'] += 1
    a = mech.events_set()
    try: t()
    except KeyError: pass
    b = mech.events_set()
    c['samples'] += 2; c['unset'] += (not a) + (not b)
def worker(Y, seed, go, park, stop):
    tl.rng = random.Random(seed); tl.c = dict(bodies=0, samples=0, unset=0, faults=0); PER.append(tl.c)
    while True:
        go.wait()
        if stop[0]: return
        n = 0
        while go.is_set() and n < 400:
            n += 1; tl.faultable = True
            try: Y.run('S', body)
            except Injected: tl.c['faults'] += 1
            tl.faultable = False
        park.wait()
def retirer(seed, go, park, stop):
    tl.rng = random.Random(seed)
    while True:
        go.wait()
        if stop[0]: return
        n = 0
        while go.is_set() and n < 200:
            n += 1; tl.faultable = False
            try:
                with mech.Tracer(u):
                    tl.faultable = True
                tl.faultable = False
            except Injected: stats['faults'] += 1
            tl.faultable = False; stats['retire'] += 1
        park.wait()
ZSEED = [SEED * 10 + 7]
def z_race(rng):
    z = mech.Tracer(f); z.__enter__()
    stopz = [False]; outc = {'ran': 0, 'inactive': 0}
    def racer():
        tl.rng = random.Random(ZSEED[0]); ZSEED[0] += 1
        while not stopz[0]:
            tl.faultable = True
            try: z.run('Z', f); outc['ran'] += 1
            except mech.TraceInactive: outc['inactive'] += 1; tl.faultable = False; return
            except Injected: stats['faults'] += 1
            tl.faultable = False
    th = threading.Thread(target=racer); th.start()
    time.sleep(rng.random() * 0.002)
    z.__exit__(None, None, None); stopz[0] = True; th.join()
    stats['z_races'] += 1; stats['z_ran'] += outc['ran']; stats['z_inactive'] += outc['inactive']
    if any(o.core is z.core for o in list(mech._ANCHORS.values())): stats['z_leak'] += 1
    if z.core.flags.get('UNWIND_LOST'): stats['z_lost'] += 1
mech._HOOK[0] = hook
v = sys.version.split()[0]; t0 = time.perf_counter()
mrng = random.Random(SEED * 1000)
with mech.Tracer(t) as Y:
    go = threading.Event(); stop = [False]; park = threading.Barrier(5)
    ths = [threading.Thread(target=worker, args=(Y, SEED * 10 + i, go, park, stop)) for i in range(3)]
    ths.append(threading.Thread(target=retirer, args=(SEED * 10 + 9, go, park, stop)))
    for th in ths: th.start()
    for rnd in range(ROUNDS):
        go.set()
        if Z:
            for _ in range(3): z_race(mrng)
        time.sleep(0.02 if Z else 0.05); go.clear()
        park.wait()
        stats['q'] += 1
        st = mech.state(); s = mech.events_set()
        if st['anchors'] and not s: stats['anchor_no_event'] += 1
        if MODE == 'clean':
            if st['anchors'] or s or st['clearing']: stats['stale'] += 1
        else:
            if not st['anchors'] and s: stats['stale'] += 1
            Y.run('S', lambda: None)                   # one fault-free open and close (main thread: no hook rng)
            st = mech.state(); s = mech.events_set()
            if st['anchors']: stats['dead_rounds'] += 1
            elif s: stats['stale_after'] += 1
            if st['clearing']: stats['clearing_after'] += 1
    stop[0] = True; go.set()
    for th in ths: th.join()
mech._HOOK[0] = None
for c in PER:
    stats['bodies'] += c['bodies']; stats['samples'] += c['samples']; stats['unset'] += c['unset']; stats['faults'] += c['faults']
r = Y.result(); end = mech.state()
counted = r['calls'].get('S', {}).get('t', 0)
print(v, 'rev %-2s %-12s %-3s seed %d: %d bodies, %d samples, %d unset in body (U1) | counted %d of %d, MONITOR_LOST %s | Z races %d: anchor left %d, false UNWIND_LOST %d, ran %d, TRACE_INACTIVE %d | quiescent %d: stale %d, anchor w/o event %d, stale after a close %d, dead-anchor rounds %d, clearing after a close %d | end anchors %d events %d clearing %d | faults %d, %.0f s' % (
    REVS, MODE, 'Z' if Z else 'noZ', SEED, stats['bodies'], stats['samples'], stats['unset'], counted, stats['bodies'], r['MONITOR_LOST'],
    stats['z_races'], stats['z_leak'], stats['z_lost'], stats['z_ran'], stats['z_inactive'],
    stats['q'], stats['stale'], stats['anchor_no_event'], stats['stale_after'], stats['dead_rounds'], stats['clearing_after'],
    end['anchors'], end['global_events'], end['clearing'], stats['faults'], time.perf_counter() - t0))
