# Randomized interleaving and fault stress of the section-scoped PY_UNWIND protocol (MF1, MF2), on mech3.py.
# Usage: s1_unwind_stress.py REV(2|3) MODE(clean|fault|fault-nodead) ROUNDS SEED
#
# Threads, all sharing one active tracer Y that declares t (t raises inside its body):
#   W1..W3  loop Y.run('S', body). body samples the event on its own thread, calls t, samples again.
#   R       loops `with Tracer(u): pass`: every exit runs _retire step 6 and ends its reconciliation (rev 3).
# Every hook point of the protocol (mech3._HOOK: each statement boundary of _commit/_open, _unwind_on, _unwind_off,
# _detach, retire step 6) yields the GIL with probability 0.3, so the scheduler visits the interleavings between
# them, at a 1 us switch interval. In fault mode, a hook on W1..W3 (anywhere) or on R during its exit raises
# Injected with probability 0.02, which is caught around Y.run / the with statement. fault-nodead is the same except
# at every point inside _detach before its pop (including the _ours() its UNWIND_LOST check calls), where a fault
# leaves a dead anchor (which keeps the event set, by design, until its trace exits) and would mask the stale-set
# check.
# Checks:
#   U1  every event sample taken inside a body is "set" (an open section always has the event set);
#   C   Y's count of t equals the number of bodies that ran t (every raising call confirmed; none added), and no
#       MONITOR_LOST;
#   U2  at each quiescent point (all threads parked outside sections): clean mode: no anchor and no event set;
#       fault mode: after one fault-free close by the main thread, no event set unless a dead anchor remains
#       (a fault in _detach before its pop), and at Y's exit no anchor and no event set.
import sys, threading, random, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech3 as mech
REV, MODE, ROUNDS, SEED = int(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
mech.REV3[0] = REV == 3
sys.setswitchinterval(1e-6)
class Injected(BaseException): pass
DEAD_POINTS = ('detach:claimed', 'detach:checked')      # a fault here leaves a dead anchor (the finally is cut short)
def t(): raise KeyError
def u(): return 0
tl = threading.local()
rng_lock = threading.Lock()
faults = {}
def hook(p):
    r = getattr(tl, 'rng', None)
    if r is None: return
    if p == 'detach:claimed': tl.predpop = True          # inside _detach, before its pop (_ours() runs here too)
    elif p == 'detach:popped': tl.predpop = False
    if r.random() < 0.3: time.sleep(0)
    if MODE != 'clean' and getattr(tl, 'faultable', False) and r.random() < 0.02:
        if MODE == 'fault-nodead' and (p in DEAD_POINTS or getattr(tl, 'predpop', False)): return
        if p == 'detach:claimed' or getattr(tl, 'predpop', False): tl.predpop = False
        faults[p] = faults.get(p, 0) + 1
        raise Injected
stats = {'bodies': 0, 'samples': 0, 'unset_in_body': 0, 'faults_caught': 0, 'retire_cycles': 0,
         'quiescent_checks': 0, 'stale_set_at_quiescence': 0, 'stale_after_repair': 0, 'dead_anchor_rounds': 0,
         'anchor_without_event_at_quiescence': 0}
PER = []                                                 # per-thread counters, summed at the end
def body():
    c = tl.c
    c['bodies'] += 1
    a = mech.events_set()
    try: t()
    except KeyError: pass
    b = mech.events_set()
    c['samples'] += 2
    c['unset_in_body'] += (not a) + (not b)
def worker(Y, seed, go, park, stop):
    tl.rng = random.Random(seed); tl.c = {'bodies': 0, 'samples': 0, 'unset_in_body': 0, 'faults': 0}; PER.append(tl.c)
    while True:
        go.wait()
        if stop[0]: return
        n = 0
        while go.is_set() and n < 400:
            n += 1
            tl.faultable = True
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
            n += 1
            tl.faultable = False
            try:
                with mech.Tracer(u):
                    tl.faultable = True
                tl.faultable = False
            except Injected: stats['faults_caught'] += 1
            tl.faultable = False
            stats['retire_cycles'] += 1
        park.wait()
mech._HOOK[0] = hook
v = sys.version.split()[0]
t0 = time.perf_counter()
with mech.Tracer(t) as Y:
    go = threading.Event(); stop = [False]
    park = threading.Barrier(5)
    ths = [threading.Thread(target=worker, args=(Y, SEED * 10 + i, go, park, stop), name='W%d' % i) for i in range(3)]
    ths.append(threading.Thread(target=retirer, args=(SEED * 10 + 9, go, park, stop), name='R'))
    for th in ths: th.start()
    for rnd in range(ROUNDS):
        go.set(); time.sleep(0.05); go.clear()
        park.wait()                                      # every thread parked outside any section
        stats['quiescent_checks'] += 1
        st = mech.state(); s = mech.events_set()
        if st['anchors'] and not s: stats['anchor_without_event_at_quiescence'] += 1
        if MODE == 'clean':
            if st['anchors'] or s: stats['stale_set_at_quiescence'] += 1
        else:
            if not st['anchors'] and s: stats['stale_set_at_quiescence'] += 1
            Y.run('S', lambda: None)                     # one fault-free close (main thread has no hook rng)
            st = mech.state(); s = mech.events_set()
            if st['anchors']: stats['dead_anchor_rounds'] += 1
            elif s: stats['stale_after_repair'] += 1
    stop[0] = True; go.set()
    for th in ths: th.join()
mech._HOOK[0] = None
for c in PER:
    for k in ('bodies', 'samples', 'unset_in_body'): stats[k] += c[k]
    stats['faults_caught'] += c['faults']
r = Y.result()
end = mech.state()
counted = r['calls'].get('S', {}).get('t', 0)
print(v, 'rev %d %-5s seed %d: %d bodies, %d in-body samples, %d unset in body (U1) | counted %d of %d t calls, MONITOR_LOST %s (C) | '
      'quiescent %d: stale set %d, anchor without event %d, stale after one close %d, dead-anchor rounds %d | after exit anchors %d events %d (U2) | faults %d, retire cycles %d, %.0f s' % (
      REV, MODE, SEED, stats['bodies'], stats['samples'], stats['unset_in_body'], counted, stats['bodies'], r['MONITOR_LOST'],
      stats['quiescent_checks'], stats['stale_set_at_quiescence'], stats['anchor_without_event_at_quiescence'],
      stats['stale_after_repair'], stats['dead_anchor_rounds'], end['anchors'], end['global_events'],
      stats['faults_caught'], stats['retire_cycles'], time.perf_counter() - t0))
if MODE != 'clean': print(v, '   faults by point:', dict(sorted(faults.items())))
