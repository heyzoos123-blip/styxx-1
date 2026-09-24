import functools
@functools.lru_cache(maxsize=None)
def cached_bar(n):
    return n * 2
def real(): return 1
