# Can RecursionError (a declared fault source) land INSIDE a one-call step, after its first write?
# Pipeline shape of _register: gate, then repeat(t, 5) created inside the consuming call, then writes.
# Here: write 1 (setitem into D), then an itertools.repeat construction, then write 2.
import sys, itertools, operator, collections
_CONSUME = collections.deque(maxlen=0).extend
_map, _chain, _repeat, _setitem = map, itertools.chain, itertools.repeat, operator.setitem
D = {}
def step():
    D.clear()
    _CONSUME(_chain(_map(_setitem, (D,), ('w1',), (1,)),
                    _chain.from_iterable(_map(_repeat, (0,), (1,))),
                    _map(_setitem, (D,), ('w2',), (1,))))
res = {'inside_partial': 0, 'clean_raise': 0, 'ok': 0}
def r(n):
    if n: return list(map(r, (n - 1,)))
    try: step(); res['ok'] += 1
    except RecursionError:
        if 'w1' in D and 'w2' not in D: res['inside_partial'] += 1
        else: res['clean_raise'] += 1
    return 0
sys.setrecursionlimit(100000)
for d in range(0, 12000, 1):
    try: r(d)
    except RecursionError: pass
print(sys.version.split()[0], res)
