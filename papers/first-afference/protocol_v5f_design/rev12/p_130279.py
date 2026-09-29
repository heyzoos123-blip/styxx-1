# rev12 (GAP-49): which shapes CPython #130279 affects, on 3.12.3 and 3.13.12, and by which delivery.
# For each shape and each instruction offset of it, one trial per delivery:
#   direct  an INSTRUCTION callback at that offset raises Boom itself (the exception is raised AT the offset)
#   signal  an INSTRUCTION callback at that offset calls signal.raise_signal; the handler raises Boom at the next
#           eval-breaker check (the #130279 delivery: an asynchronous exception at a back-edge's check)
# A trial is a SKIP if Boom passed through the shape's frame and its finally / with-exit did not run.
# Also: a SIGALRM timer into the uninstrumented shape (no sys.monitoring at all), 200 trials each.
import dis, signal, sys, random
M = sys.monitoring; E = M.events; TOOL = 5
class Boom(Exception): pass
def handler(s, f): raise Boom
signal.signal(signal.SIGUSR1, handler); signal.signal(signal.SIGALRM, handler)
FIN = []
class CM:
    def __enter__(self): return self
    def __exit__(self, *a): FIN.append(1); return False
def while_try(n):
    try:
        i = 0
        while i < n: i += 1
    finally: FIN.append(1)
def for_try(xs):
    try:
        for x in xs: pass
    finally: FIN.append(1)
def for_if_tail_try(xs):
    try:
        for x in xs:
            if x: pass
    finally: FIN.append(1)
def for_call_tail_try(xs):
    try:
        for x in xs: FIN.append
    finally: FIN.append(1)
def while_continue_try(n):
    try:
        i = 0
        while i < n:
            i += 1
            if i & 1: continue
    finally: FIN.append(1)
def while_with(n):
    with CM():
        i = 0
        while i < n: i += 1
def for_with(xs):
    with CM():
        for x in xs: pass
def for_call_tail_with(xs):          # the H9 mutant's shape: `with _M: for o in list(...): _detach(o, ...)`
    with CM():
        for x in xs: len(FIN)
def with_in_try_loop(xs):            # nesting depth 2: the loop inside a with inside a try/finally
    try:
        with CM():
            for x in xs: pass
    finally: FIN.append(1)
def with_inside_loop(xs):            # the with inside the loop body: the back-edge is after the with-exit
    for x in xs:
        with CM(): pass
def loop_before_try(xs):             # the design's shape: no loop in the try body
    for x in xs: pass
    try: pass
    finally: FIN.append(1)
SHAPES = [(while_try, lambda f: f(3)), (for_try, lambda f: f([1, 2, 3])), (for_if_tail_try, lambda f: f([1, 0, 1])),
          (for_call_tail_try, lambda f: f([1, 2, 3])), (while_continue_try, lambda f: f(4)), (while_with, lambda f: f(3)),
          (for_with, lambda f: f([1, 2, 3])), (for_call_tail_with, lambda f: f([1, 2, 3])),
          (with_in_try_loop, lambda f: f([1, 2, 3]))]
# with_inside_loop and loop_before_try (a back-edge outside every protected range) are controls by construction:
# nothing is owed at their back-edges, so they are not swept.
EXPECT = {'while_try': 1, 'for_try': 1, 'for_if_tail_try': 1, 'for_call_tail_try': 1, 'while_continue_try': 1,
          'while_with': 1, 'for_with': 1, 'for_call_tail_with': 1, 'with_in_try_loop': 2, 'with_inside_loop': 3,
          'loop_before_try': 1}

import inspect
def body_lines(fn):
    src, start = inspect.getsourcelines(fn)
    L = [l.strip() for l in src]
    op = next(i for i, l in enumerate(L) if l.startswith(('try:', 'with ')))
    if L[op].startswith('try:') and L[op + 1].startswith('with '): op += 1   # innermost block: the with
    cl = next((i for i, l in enumerate(L) if l.startswith('finally:')), len(L))
    if fn.__name__ == 'with_inside_loop': return {start + i for i in range(len(L)) if L[i].startswith('with ')}
    if fn.__name__ == 'loop_before_try': return {start + i for i in range(len(L)) if L[i].startswith('try:')}
    return {start + i for i in range(op + 1, cl)}
def trial(fn, call, off, how):
    code = fn.__code__; st = {'armed': True}
    def cb(c, o):
        if st['armed'] and c is code and o == off:
            st['armed'] = False
            if how == 'direct': raise Boom
            signal.raise_signal(signal.SIGUSR1)
    M.register_callback(TOOL, E.INSTRUCTION, cb); M.set_local_events(TOOL, code, E.INSTRUCTION)
    FIN.clear(); through = False
    try: call(fn)
    except Boom as e:
        tb = e.__traceback__
        while tb is not None:
            if tb.tb_frame.f_code is code and tb.tb_lineno in BODY[fn.__name__]: through = True
            tb = tb.tb_next
    finally: M.set_local_events(TOOL, code, 0)
    return through, len(FIN)

BODY = {fn.__name__: body_lines(fn) for fn, _ in SHAPES}
if len(sys.argv) > 1 and sys.argv[1] == 'alarm':
    ALARM_ONLY = True
else:
    ALARM_ONLY = False
if not ALARM_ONLY: M.use_tool_id(TOOL, 'probe130279')
ver = sys.version.split()[0]
for fn, call in ([] if ALARM_ONLY else SHAPES):
    ins = list(dis.get_instructions(fn.__code__))
    for how in ('direct', 'signal'):
        skips = []
        for i in ins:
            through, n = trial(fn, call, i.offset, how)
            if through and n < EXPECT[fn.__name__]:
                skips.append('%d:%s' % (i.offset, i.opname))
        print('%s %-20s %-6s skipped at %s' % (ver, fn.__name__, how, skips or 'none'))
if not ALARM_ONLY:
    M.free_tool_id(TOOL); sys.exit()
# uninstrumented (run as `p_130279.py alarm`, a fresh process: no code object here was ever instrumented): SIGALRM into a long loop of each shape (the with-in-loop shape counts only exits owed)
for fn, big in ((while_try, lambda f: f(10**9)), (for_try, lambda f: f(range(10**9))), (while_with, lambda f: f(10**9)),
                (for_with, lambda f: f(range(10**9))), (for_call_tail_with, lambda f: f(range(10**9))),
                (with_in_try_loop, lambda f: f(range(10**9)))):
    sk = 0; N = 200; landed = 0
    for _ in range(N):
        FIN.clear(); through = False; signal.setitimer(signal.ITIMER_REAL, random.uniform(0.0005, 0.003))
        try: big(fn)
        except Boom as e:
            tb = e.__traceback__
            while tb is not None:
                if tb.tb_frame.f_code is fn.__code__ and tb.tb_lineno in BODY[fn.__name__]: through = True
                tb = tb.tb_next
        signal.setitimer(signal.ITIMER_REAL, 0)
        landed += through
        if through and len(FIN) < EXPECT[fn.__name__]: sk += 1
    print('%s %-20s SIGALRM uninstrumented: exit/finally skipped in %d of %d landed in the body (%d trials)' % (ver, fn.__name__, sk, landed, N))
