"""round4/attribution/r1/a06_recursion_quadratic.py, rewritten: a declared recursive target run at depths 2000,
4000 and 8000 in a section, in a thread with a 256 MB stack and a raised recursion limit. The repro measured the
traced time's growth (a cost, not a spec-fixed observable); the rewrite records each trace's outcome."""
import sys, threading


def main(api):
    fx = api.fixture("rp_a06_fix", "def depth(n):\n    return 0 if n == 0 else 1 + depth(n - 1)\n")
    e = api.exp({"G": ["rp_a06_fix:depth"]})
    out = {}
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(100000)
    old_stack = threading.stack_size(256 * 1024 * 1024)
    try:
        def run():
            for n in (2000, 4000, 8000):
                out[f"depth_{n}"] = api.trace(e, lambda c: c.run("G", fx.depth, n))
        t = threading.Thread(target=run)
        t.start()
        t.join()
    finally:
        threading.stack_size(old_stack)
        sys.setrecursionlimit(old_limit)
    return out
