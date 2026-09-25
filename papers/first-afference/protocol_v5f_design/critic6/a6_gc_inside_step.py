# Does the cyclic gc (or a __del__ of cyclic garbage) ever run INSIDE a one-call step that allocates many
# GC-tracked objects (threshold 1)? Marker writes at the start and end of the consuming call.
import sys, gc, itertools, operator, collections
_CONSUME = collections.deque(maxlen=0).extend
_map, _chain, _repeat, _setitem = map, itertools.chain, itertools.repeat, operator.setitem
D = {}; inside = [0]; ran = [0]
def cb(phase, info):
    ran[0] += 1
    if 's' in D and 'e' not in D: inside[0] += 1
gc.callbacks.append(cb)
class Fin:
    def __del__(self):
        ran[0] += 1
        if 's' in D and 'e' not in D: inside[0] += 1
N = 2000
Z, O = (0,) * N, (1,) * N
gc.set_threshold(1, 1, 1)
for _ in range(300):
    a = Fin(); b = Fin(); a.o = b; b.o = a; del a, b
    D.clear()
    _CONSUME(_chain(_map(_setitem, (D,), ('s',), (1,)),
                    _chain.from_iterable(_map(_repeat, Z, O)),      # 2000 GC-tracked allocations inside the call
                    _map(_setitem, (D,), ('e',), (1,))))
gc.set_threshold(700, 10, 10)
print(sys.version.split()[0], 'gc callbacks/finalizers run:', ran[0], 'of them inside the one call:', inside[0])
