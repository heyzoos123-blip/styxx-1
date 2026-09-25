# critic8/c3: A13 needs a witness in which a dead frame's id is reused by a new frame of the same code. Is that reuse
# deterministic on the verified builds (single thread, no allocation between)? 1000 trials of: a frame object is
# materialised (sys._getframe) inside g, g raises and the exception (with its traceback) is dropped, so the frame dies;
# then g runs again and its frame's id is compared.
import sys, gc
def g(box):
    box.append(id(sys._getframe(0)))
    raise KeyError
def trial():
    b = []
    try: g(b)
    except KeyError: pass
    try: g(b)
    except KeyError: pass
    return b[0] == b[1]
gc.disable()
same = sum(trial() for _ in range(1000))
gc.enable()
same_gc = sum(trial() for _ in range(1000))
print(sys.version.split()[0], 'frame id reused: %d/1000 (gc disabled), %d/1000 (gc enabled)' % (same, same_gc))
