# CPython #130279 check. For every instruction offset of a function, one trial: an INSTRUCTION
# callback at that offset calls signal.raise_signal; the handler raises Boom at the next eval-breaker
# check. A trial is a SKIP if Boom's traceback passes through the function's frame but its finally
# (or with-exit) did not run.
import dis, signal, sys, types
M = sys.monitoring; E = M.events; TOOL = 5
class Boom(Exception): pass
def handler(s, f): raise Boom
signal.signal(signal.SIGUSR1, handler)
FIN = []
class CM:
    def __enter__(self): return self
    def __exit__(self, *a): FIN.append('exit'); return False

def while_in_try(n):
    try:
        i = 0
        while i < n:
            i += 1
    finally:
        FIN.append('fin')
def for_if_in_try(xs):
    try:
        for x in xs:
            if x:
                pass
    finally:
        FIN.append('fin')
def while_in_with(n):
    with CM():
        i = 0
        while i < n:
            i += 1
def callee_loop():
    i = 0
    while i < 3:
        i += 1
    return i
def _run(fn):                          # the design's shape: no loop in the try body
    end = "raised"
    try:
        result = fn(); end = "returned"
    finally:
        FIN.append(end)
    return result
class Yield3:
    def __await__(self):
        for _ in range(3):
            yield None
        return 7
async def afn():
    return await Yield3()
async def _run_async(afn):             # the design's async shape: one await in the try body
    end = "raised"
    try:
        result = await afn(); end = "returned"
    finally:
        FIN.append(end)
    return result

def drive(coro):
    try:
        while True: coro.send(None)
    except StopIteration as e:
        return e.value

def trial(code, call, off):
    state = {'armed': True}
    def cb(c, o):
        if state['armed'] and c is code and o == off:
            state['armed'] = False; signal.raise_signal(signal.SIGUSR1)
    M.register_callback(TOOL, E.INSTRUCTION, cb)
    M.set_local_events(TOOL, code, E.INSTRUCTION)
    FIN.clear(); through = False; line = None
    try:
        call()
    except Boom as e:
        tb = e.__traceback__
        while tb is not None:
            if tb.tb_frame.f_code is code: through = True; line = tb.tb_lineno
            tb = tb.tb_next
    finally:
        M.set_local_events(TOOL, code, 0)
    fired = not state['armed']
    return fired, through and line in BODY[code], bool(FIN)

import inspect
BODY = {}
def body_lines(fn):
    src, start = inspect.getsourcelines(fn)
    lines = [l.strip() for l in src]
    opener = next(i for i, l in enumerate(lines) if l.startswith(('try:', 'with ')))
    closer = next((i for i, l in enumerate(lines) if l.startswith('finally:')), len(lines))
    return {start + i for i in range(opener + 1, closer)}
def sweep(name, code, call):
    offs = sorted({i.offset for i in dis.get_instructions(code)})
    skips, fired_n, through_n = [], 0, 0
    for off in offs:
        fired, through, fin = trial(code, call, off)
        fired_n += fired; through_n += through
        if through and not fin:
            op = next(i.opname for i in dis.get_instructions(code) if i.offset == off)
            skips.append((off, op))
    print(f"{sys.version.split()[0]} {name:15s} offsets={len(offs):3d} fired={fired_n:3d} "
          f"raised-in-body={through_n:3d} finally/with-exit SKIPPED={skips}")

M.use_tool_id(TOOL, 'probe')
for fn in (while_in_try, for_if_in_try, while_in_with, _run, _run_async): BODY[fn.__code__] = body_lines(fn)
sweep('while_in_try', while_in_try.__code__, lambda: while_in_try(3))
sweep('for_if_in_try', for_if_in_try.__code__, lambda: for_if_in_try([1, 0, 1]))
sweep('while_in_with', while_in_with.__code__, lambda: while_in_with(3))
sweep('_run', _run.__code__, lambda: _run(callee_loop))
sweep('_run_async', _run_async.__code__, lambda: drive(_run_async(afn)))
