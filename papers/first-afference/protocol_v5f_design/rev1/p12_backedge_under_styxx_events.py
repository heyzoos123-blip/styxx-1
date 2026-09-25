# Does v5f's own instrumentation (local PY_START|PY_RESUME|PY_RETURN|PY_YIELD on the minted target
# code, global PY_UNWIND) create or widen the #130279 skip in a TARGET's own try/finally or with?
# Also: the exam injector's INSTRUCTION events (tool 5) on 3.12.
import signal, sys, random
M = sys.monitoring; E = M.events
class Boom(Exception): pass
def h(s, f): raise Boom
signal.signal(signal.SIGALRM, h)
FIN = []
class CM:
    def __enter__(self): return self
    def __exit__(self, *a): FIN.append(1); return False
def while_try():
    try:
        i = 0
        while i < 10**9:
            i += 1
    finally:
        FIN.append(1)
def while_with():
    with CM():
        i = 0
        while i < 10**9:
            i += 1
def run(fn, N=300):
    skipped = 0
    for _ in range(N):
        FIN.clear()
        signal.setitimer(signal.ITIMER_REAL, random.uniform(0.0005, 0.003))
        try: fn()
        except Boom: pass
        if not FIN: skipped += 1
    return f"{skipped}/{N}"
v = sys.version.split()[0]
M.use_tool_id(4, 'styxx-like')
for ev in ('PY_START', 'PY_RESUME', 'PY_RETURN', 'PY_YIELD', 'PY_UNWIND'):
    M.register_callback(4, getattr(E, ev), (lambda *a: None))
for fn in (while_try, while_with):
    fn.__code__ = fn.__code__.replace()          # mint
    M.set_local_events(4, fn.__code__, E.PY_START | E.PY_RESUME | E.PY_RETURN | E.PY_YIELD)
M.set_events(4, E.PY_UNWIND)
print(v, "v5f event set on the target:", "while_try skipped", run(while_try), "| while_with skipped", run(while_with))
M.set_events(4, 0)
for fn in (while_try, while_with): M.set_local_events(4, fn.__code__, 0)
M.use_tool_id(5, 'injector'); M.register_callback(5, E.INSTRUCTION, lambda c, o: None)
for fn in (while_try, while_with): M.set_local_events(5, fn.__code__, E.INSTRUCTION)
print(v, "INSTRUCTION events (injector):", "while_try skipped", run(while_try, 100), "| while_with skipped", run(while_with, 100))
for fn in (while_try, while_with): M.set_local_events(5, fn.__code__, 0)
M.register_callback(5, E.JUMP, lambda *a: None)
for fn in (while_try, while_with): M.set_local_events(5, fn.__code__, E.JUMP)
print(v, "JUMP events:", "while_try skipped", run(while_try, 100), "| while_with skipped", run(while_with, 100))
