# V36b as worded: the worker "started before the trace, is inside f" while the tracer exits.
# CLONE_ALIVE's gate needs excess = getrefcount(M_T) - 2 - (F_T.__code__ is M_T) > 0. If the worker entered
# f before the mint it runs the ORIGINAL code: excess is 0 and neither weakened freeze rule ("> 0",
# "!= baseline") can fire, so V36b does not witness them. Only a worker entering f after __enter__ does.
import sys, gc, threading
def f(ev=None):
    if ev is not None: ev.wait(10)
    return 1
class Mint: pass
def excess_of(m, fn):
    return sys.getrefcount(m.code) - 2 - (fn.__code__ is m.code)
def trial(during):
    junk = [object() for _ in range(1000)]; gc.freeze()
    ev = threading.Event(); started = threading.Event()
    def work(): started.set(); f(ev)
    if not during:
        t = threading.Thread(target=work); t.start(); started.wait()
    m = Mint(); m.original = f.__code__; m.code = f.__code__.replace(); m.freeze0 = gc.get_freeze_count()
    f.__code__ = m.code
    if during:
        t = threading.Thread(target=work); t.start(); started.wait()
    f(); del junk
    f.__code__ = m.original
    ex = excess_of(m, f); cnt = gc.get_freeze_count()
    fires = {'rise(spec)': ex > 0 and cnt > m.freeze0, 'gt0(mutant)': ex > 0 and cnt > 0, 'ne(mutant)': ex > 0 and cnt != m.freeze0}
    ev.set(); t.join(); gc.unfreeze()
    return ex, fires
for during in (False, True):
    ex, fires = trial(during)
    print(sys.version.split()[0], 'worker enters f', 'after __enter__ ' if during else 'before the trace', 'excess', ex, fires)
