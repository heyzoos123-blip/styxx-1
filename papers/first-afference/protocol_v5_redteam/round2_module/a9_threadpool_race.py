from rtlib import *
import fx_simple as fs
from multiprocessing.pool import ThreadPool
from concurrent.futures import ThreadPoolExecutor
def mp_threadpool():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            with ThreadPool(4) as p:          # documented usage; __exit__ calls terminate()
                p.map(lambda _: fs.f(), range(8))
    return score(e, cov.record())
def cf_pool():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            with ThreadPoolExecutor(4) as p: list(p.map(lambda _: fs.f(), range(8)))
    return score(e, cov.record())
for i in range(3): attempt(f"A9a multiprocessing.pool.ThreadPool as ctx manager (run {i})", mp_threadpool)
attempt("A9b concurrent.futures ThreadPoolExecutor ctx manager (control)", cf_pool)
