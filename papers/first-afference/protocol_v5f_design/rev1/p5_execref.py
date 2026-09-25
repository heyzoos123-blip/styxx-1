# (a)5: a frame of T executing on another thread holds a reference to M_T that gc cannot see;
# a suspended generator's frame reference is visible (through the generator object)
import gc, sys, threading, time
def f(ev, go):
    ev.set(); go.wait(); return 1
M_T = f.__code__.replace(); f.__code__ = M_T
ev, go = threading.Event(), threading.Event()
t = threading.Thread(target=f, args=(ev, go)); t.start(); ev.wait()
def census(code):
    rc = sys.getrefcount(code) - 1          # minus getrefcount's argument
    refs = gc.get_referrers(code)
    return rc, sorted(type(r).__name__ for r in refs)
print(sys.version.split()[0], 'executing on another thread: refcount, gc referrers =', census(M_T))
go.set(); t.join()
print('after it returned:', census(M_T))
def gen():
    yield 1
M_G = gen.__code__.replace(); gen.__code__ = M_G
it = gen(); next(it)
print('suspended generator:', census(M_G))
