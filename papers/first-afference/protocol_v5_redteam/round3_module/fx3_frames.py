import asyncio
class Base:
    def fit(self, x): return x
class Model(Base):
    def fit(self, x):                   # __class__ cell (super())
        return super().fit(x) + 1
def _mk_gen(k):
    def gen(n):                         # generator with a free variable: 'call' on every resume
        for i in range(n):
            yield i + k
    return gen
gen = _mk_gen(10)
def _mk_coro(k):
    async def coro(n):
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return n + k
    return coro
coro = _mk_coro(5)
def _mk_cellarg(k):
    def cellarg(x):                     # free var k AND an argument captured by an inner lambda
        return list(map(lambda y: x + y + k, [1, 2]))
    return cellarg
cellarg = _mk_cellarg(100)
def _mk_lazy():
    cache = None
    def get():                          # lazy-init idiom: rebinds its own free variable
        nonlocal cache
        if cache is None:
            cache = [1, 2, 3]
        return cache
    return get
get = _mk_lazy()
def _mk_rec():
    def walk(n):                        # recursive closure: free var is itself
        return 0 if n == 0 else 1 + walk(n - 1)
    return walk
walk = _mk_rec()
