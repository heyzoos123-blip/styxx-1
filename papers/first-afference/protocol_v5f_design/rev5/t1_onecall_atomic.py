# Revision 5's premise, tested on CPython itself: a read-test-write on styxx's global event that is built as a lazy
# itertools/operator pipeline and consumed by ONE builtin call (a "one-call step") runs entirely in C. No Python code
# can run inside it: no instrument callback, trace/profile function, signal handler, finalizer or audit hook, and no
# other thread. So the `_ANCHORS` test and the clear cannot be separated by anything.
#
# Parts:
#   A  per-instruction sweep: at the k-th INSTRUCTION event (sys.monitoring, local) of the clearing function, the
#      callback registers an anchor; afterwards the event must not be clear while an anchor registered BEFORE the
#      clear exists. Same for opcode tracing (settrace + f_trace_opcodes), a CALL + C_RETURN tool, a BRANCH tool,
#      and a pure-Python sys.setprofile function (c_call). Run against the one-call step and against the two-statement
#      form (the control, which these instruments do split).
#   B  which callables the instruments see during one one-call step (only the outer consumer should appear).
#   C  audit events raised during a one-call step (expected none).
#   D  cyclic gc with threshold 1, finalizers that register an anchor; and a SIGALRM flood whose handler does the
#      same; count clears that landed after an anchor was registered (expected 0; the control is split by neither,
#      because both only run at eval-breaker checks, which the two-statement form also lacks between test and call).
#   E  threads: openers (store, one-call ON, then body samples of the event while registered) against closers
#      (one-call pop+OFF), with a pure-Python profiler on every thread whose c_call handler yields the GIL
#      (time.sleep(0)); count body samples with the event clear (U1). Control: the two-statement OFF.
#   F  get_tool returns the very object passed to use_tool_id (so `is` can test the name); set_events with an unchanged
#      value costs as much as get_events (no re-instrumentation).
import sys, threading, time, gc, signal, operator, itertools, collections
M = sys.monitoring; E = M.events
PYU = E.PY_UNWIND
T = 4
NAME = 'styxx.protocol/' + 'x' * 12
_map, _chain, _compress, _filter = map, itertools.chain, itertools.compress, filter
_is, _not, _and, _setitem = operator.is_, operator.not_, operator.and_, operator.setitem
_consume = collections.deque(maxlen=0).extend
_get_tool, _get_events, _set_events = M.get_tool, M.get_events, M.set_events
A = {}
NAME1, PYU1, ZERO1, NONE1 = (NAME,), (PYU,), (0,), (None,)

def off_onecall(key):
    # one call { A.pop(key, None); if get_tool(T) is NAME and not A and get_events(T) & PYU: set_events(T, 0) }
    _consume(_chain(_map(A.pop, (key,), NONE1),
                    _map(_set_events,
                         _compress(_compress(_compress((T,), _map(_is, _map(_get_tool, (T,)), NAME1)),
                                             _map(_not, (A,))),
                                   _map(_and, _map(_get_events, (T,)), PYU1)),
                         ZERO1)))

def off_split(key):                                  # the control: two statements (revision 3's shape, split open)
    A.pop(key, None)
    if not A:
        M.set_events(T, 0)

def on_onecall(key):
    # one call { if get_tool(T) is NAME and A.get(key) is not None and not (get_events(T) & PYU): set_events(T, PYU) }
    _consume(_map(_set_events,
                  _compress(_compress(_compress((T,), _map(_is, _map(_get_tool, (T,)), NAME1)),
                                      _map(_is, _map(A.get, (key,)), (True,))),
                            _map(_not, _map(_and, _map(_get_events, (T,)), PYU1))),
                  PYU1))

def S(): return bool(M.get_events(T) & PYU)

def setup():
    if M.get_tool(T) is None: M.use_tool_id(T, NAME)
    M.register_callback(T, E.PY_UNWIND, lambda *a: None)
    M.set_events(T, 0); A.clear()

# ---------------- A: per-instruction (per-event) sweep ----------------
def trial(off, k, instrument):
    """Register an anchor at the k-th event the instrument delivers inside off(); report a clear after it."""
    setup(); A['closer'] = True; M.set_events(T, PYU)
    st = {'n': 0, 'fired': False, 'S_at_insert': None}
    def act():
        st['n'] += 1
        if st['n'] == k and not st['fired']:
            st['fired'] = True; A['opener'] = True; st['S_at_insert'] = S()
    code = off.__code__
    if instrument == 'INSTRUCTION':
        M.use_tool_id(5, 'probe'); M.register_callback(5, E.INSTRUCTION, lambda c, o: act())
        M.set_local_events(5, code, E.INSTRUCTION)
    elif instrument == 'CALL+C_RETURN':
        M.use_tool_id(5, 'probe')
        M.register_callback(5, E.CALL, lambda c, o, f, a: act()); M.register_callback(5, E.C_RETURN, lambda c, o, f, a: act())
        M.register_callback(5, E.C_RAISE, lambda c, o, f, a: act())
        M.set_events(5, E.CALL | E.C_RETURN | E.C_RAISE)
    elif instrument == 'BRANCH':
        M.use_tool_id(5, 'probe'); M.register_callback(5, E.BRANCH, lambda c, o, d: act())
        M.set_local_events(5, code, E.BRANCH)
    elif instrument == 'setprofile':
        sys.setprofile(lambda f, ev, a: act() if ev in ('c_call', 'c_return') else None)
    elif instrument == 'opcode-trace':
        def tr(f, ev, a):
            if f.f_code is code:
                f.f_trace_opcodes = True
                if ev == 'opcode': act()
            return tr
        sys.settrace(tr)
    try:
        off('closer')
    finally:
        sys.setprofile(None); sys.settrace(None)
        if M.get_tool(5) is not None:
            M.set_events(5, 0)
            try: M.set_local_events(5, code, 0)
            except ValueError: pass
            for ev in (E.INSTRUCTION, E.CALL, E.C_RETURN, E.C_RAISE, E.BRANCH): M.register_callback(5, ev, None)
            M.free_tool_id(5)                        # free_tool_id alone leaves callbacks registered (rev1/p3)
    # violation: the opener's anchor was registered while the event was set, and the event is clear now with it registered
    return st['fired'], (st['fired'] and st['S_at_insert'] and not S() and 'opener' in A)

def part_a():
    out = {}
    for instrument in ('INSTRUCTION', 'CALL+C_RETURN', 'BRANCH', 'setprofile', 'opcode-trace'):
        for name, off in (('one-call', off_onecall), ('two-statement', off_split)):
            if instrument == 'opcode-trace': trial(off, 10 ** 6, instrument)   # prime (3.12 applies f_trace_opcodes from the next run)
            fired = viol = 0; k = 1
            while True:
                f, v = trial(off, k, instrument)
                if not f: break
                fired += 1; viol += bool(v); k += 1
                if k > 500: break
            setup(); A['closer'] = True; M.set_events(T, PYU); off('closer'); cleared_alone = not S()
            out[(instrument, name)] = (fired, viol, cleared_alone)
    return out

# ---------------- B: what the instruments see during one one-call step ----------------
def part_b():
    setup(); A['x'] = 1; M.set_events(T, PYU)
    seen_prof, seen_call = [], []
    sys.setprofile(lambda f, ev, a: seen_prof.append(getattr(a, '__qualname__', getattr(a, '__name__', repr(a)))) if ev == 'c_call' and ARMB[0] else None)
    M.use_tool_id(5, 'probe'); M.register_callback(5, E.CALL, lambda c, o, f, a: seen_call.append(getattr(f, '__qualname__', repr(f))) if ARMB[0] else None); M.set_events(5, E.CALL)
    ARMB[0] = True; off_onecall('x'); ARMB[0] = False
    M.set_events(5, 0); M.register_callback(5, E.CALL, None); M.free_tool_id(5); sys.setprofile(None)
    inner = {'pop', 'get_tool', 'get_events', 'set_events'}
    return dict(profile_c_calls=sorted(set(seen_prof)), monitoring_CALLs=sorted(set(seen_call)),
                inner_seen=sorted(inner & (set(seen_prof) | set(x.rsplit('.', 1)[-1] for x in seen_call))), cleared=not S())

ARMB = [False]
# ---------------- C: audit events ----------------
AUD = []
def part_c():
    setup(); A['x'] = 1; M.set_events(T, PYU)
    AUD.clear(); ARM[0] = True
    off_onecall('x'); on_onecall('nokey')
    ARM[0] = False
    return sorted(set(AUD))
ARM = [False]
sys.addaudithook(lambda ev, args: AUD.append(ev) if ARM[0] else None)

# ---------------- D: gc finalizers and a signal flood ----------------
def part_d(off, seconds=2.0):
    setup()
    st = {'late': 0, 'fired': 0}
    class Fin:
        def __del__(self):
            if 'closer' in A:                        # only while a close is in progress
                st['fired'] += 1; A['fin'] = True
                if S(): st['late'] += 0              # registered while S set: a later clear would be a violation
                FLAG[0] = S()
    FLAG = [None]
    def handler(sig, frm):
        if 'closer' in A:
            st['fired'] += 1; A['sig'] = True; FLAG[0] = S()
    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 0.00002, 0.00002)
    gc.set_threshold(1, 1, 1)
    viol = iters = 0; t0 = time.time()
    while time.time() - t0 < seconds:
        A.clear(); A['closer'] = True; M.set_events(T, PYU); FLAG[0] = None
        a = Fin(); b = Fin(); a.o = b; b.o = a; del a, b    # cyclic garbage: its finalizers run at the next gc
        off('closer')
        if FLAG[0] is True and not S() and ('fin' in A or 'sig' in A):
            viol += 1                                    # an anchor registered while S was set, then S cleared under it
        iters += 1
    signal.setitimer(signal.ITIMER_REAL, 0, 0); signal.signal(signal.SIGALRM, old); gc.set_threshold(700, 10, 10)
    A.clear()
    return dict(iters=iters, interrupts=st['fired'], violations=viol)

# ---------------- E: threads with a yielding pure-Python profiler ----------------
def part_e(off, seconds=3.0, nthreads=4):
    setup()
    stop = [False]; res = {'samples': 0, 'clear': 0, 'opens': 0}
    lock = threading.Lock()
    offc = (off_onecall.__code__, off_split.__code__)
    def prof(f, ev, a):                                # an instrument that runs Python code, and yields, at every C call
        if ev == 'c_call' and f.f_code in offc: time.sleep(0)   # made in the close path (the openers' ON is not yielded)
    def worker(i):
        sys.setprofile(prof)
        n = s = c = 0
        while not stop[0]:
            key = (i, n); n += 1
            A[key] = True                              # store
            on_onecall(key)                            # ON (one call)
            for _ in range(3):                         # the body: sample the event while registered, yielding between
                s += 1; c += not S(); time.sleep(0)
            off(key)                                   # close: pop + OFF
            time.sleep(0)                              # other work between sections
        sys.setprofile(None)
        with lock: res['samples'] += s; res['clear'] += c; res['opens'] += n
    ths = [threading.Thread(target=worker, args=(i,)) for i in range(nthreads)]
    old = sys.getswitchinterval(); sys.setswitchinterval(1e-6)
    [t.start() for t in ths]; time.sleep(seconds); stop[0] = True; [t.join() for t in ths]
    sys.setswitchinterval(old)
    return dict(res, S_left=S(), anchors_left=len(A))

# ---------------- F ----------------
def part_f():
    setup()
    same = M.get_tool(T) is NAME
    n = 200000
    t0 = time.perf_counter()
    for _ in range(n): M.get_events(T)
    ge = (time.perf_counter() - t0) / n * 1e6
    M.set_events(T, PYU)
    t0 = time.perf_counter()
    for _ in range(n): M.set_events(T, PYU)
    se_same = (time.perf_counter() - t0) / n * 1e6
    t0 = time.perf_counter()
    for _ in range(20000): M.set_events(T, 0); M.set_events(T, PYU)
    toggle = (time.perf_counter() - t0) / 40000 * 1e6
    A.clear(); A['k'] = 1
    t0 = time.perf_counter()
    for _ in range(n): on_onecall('k')
    on_c = (time.perf_counter() - t0) / n * 1e6
    t0 = time.perf_counter()
    for _ in range(n): A['k'] = 1; off_onecall('k'); M.set_events(T, PYU)
    off_c = (time.perf_counter() - t0) / n * 1e6
    return dict(get_tool_is_name=same, get_events_us=round(ge, 3), set_events_unchanged_us=round(se_same, 3),
                toggle_us=round(toggle, 3), on_onecall_S_set_us=round(on_c, 3), popoff_clear_plus_set_us=round(off_c, 3))

if __name__ == '__main__':
    v = sys.version.split()[0]
    print(v, 'A per-event sweep (events fired inside off(), violations):')
    for (ins, name), (f, vi, ca) in part_a().items(): print('   %-14s %-14s fired %3d  violations %d  (clears when undisturbed: %s)' % (ins, name, f, vi, ca))
    print(v, 'B', part_b())
    print(v, 'C audit events during one-call steps:', part_c())
    for name, off in (('one-call', off_onecall), ('two-statement', off_split)):
        print(v, 'D gc+SIGALRM', name, part_d(off))
    for name, off in (('one-call', off_onecall), ('two-statement', off_split)):
        print(v, 'E threads+yielding profiler', name, part_e(off))
    print(v, 'F', part_f())
