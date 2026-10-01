"""round4/attribution/r1/a03_fork_pool_nested.py, rewritten: a fork-context ProcessPoolExecutor created and first
used inside section A; each job opens its own section B (cov.run inside the submitted function); the jobs' results
in the parent (each child's outcome reduced to its refusal code), whether an idle worker has a profiler, and the
parent's trace. The jobs live in a fixture module so they pickle by reference; the tracer reaches the forked
workers as a module global set before the fork, as the repro's COV global did. POSIX only (fork)."""
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

JOBS = '''
import sys
import rp_a03_fix
COV = None
def job(i):
    try:
        COV.run("B", rp_a03_fix.g)
        r = "ok"
    except BaseException as ex:
        msg = str(ex)
        r = type(ex).__name__ + ":" + (msg[1:msg.index("]")] if msg.startswith("[V5:") else "")
    return r, sys.getprofile() is not None
def probe(i):
    return sys.getprofile() is not None
'''


def main(api):
    fx = api.fixture("rp_a03_fix", "def f(): return 1\ndef g(): return 2\n")
    jobs = api.fixture("rp_a03_jobs", JOBS)
    e = api.exp({"A": ["rp_a03_fix:f"], "B": ["rp_a03_fix:g"]}, sections={"A": "A", "B": "B"})
    out = {}

    def harness(c):
        jobs.COV = c
        with ProcessPoolExecutor(2, mp_context=mp.get_context("fork")) as ex:
            def gate_a():
                fx.f()
                res = []
                for fu in [ex.submit(jobs.job, i) for i in range(2)]:
                    try:
                        res.append(list(fu.result(timeout=30)))
                    except BaseException as er:        # noqa: BLE001
                        res.append(type(er).__name__)
                out["jobs"] = res
                out["idle_worker_profiler"] = ex.submit(jobs.probe, 0).result(timeout=30)
            c.run("A", gate_a)
    out["trace"] = api.trace(e, harness)
    return out
