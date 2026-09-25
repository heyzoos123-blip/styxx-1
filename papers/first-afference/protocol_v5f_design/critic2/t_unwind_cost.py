# Cost of the process-wide PY_UNWIND callback on non-target code while a mint exists.
import sys, timeit
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech
def target(): return 1
def raiser(): raise KeyError('x')
def deep(n):
    if n == 0: raise KeyError('x')
    return deep(n - 1)
def one():
    try: raiser()
    except KeyError: pass
def five():
    try: deep(5)
    except KeyError: pass
def d_get():                       # the common "EAFP" idiom through one Python frame
    d = {}
    try: return d['k']
    except KeyError: return None
for name, fn in (('raise through 1 frame', one), ('raise through 6 frames', five), ('KeyError caught in-frame', d_get)):
    a = min(timeit.repeat(fn, number=200_000, repeat=5))
    with mech.Tracer(target):
        b = min(timeit.repeat(fn, number=200_000, repeat=5))
    print(f"{sys.version.split()[0]} {name}: x{b/a:.2f}")
