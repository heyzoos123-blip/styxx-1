"""round4/lifecycle/r1/f02_chaining_profiler_removed.py, rewritten: a user profiler started inside the section
that counts Python calls and (in the chaining variant) forwards to whatever profiler it found; after the section
closes, whether it is still installed and how many of 5 later calls it saw; the trace's verdict and notes."""
import sys


def main(api):
    mod = api.fixture("rp_lc_f02", "def work(x=0):\n    return x + 1\ndef later(x=0):\n    return x * 2\n")
    e = api.exp({"G": ["rp_lc_f02:work"]})

    class ChainingCounter:
        def __init__(self, chain):
            self.calls, self.prev, self.chain = 0, None, chain

        def __call__(self, frame, event, arg):
            if event == "call":
                self.calls += 1
            if self.chain and self.prev is not None:
                self.prev(frame, event, arg)

        def start(self):
            self.prev = sys.getprofile()
            sys.setprofile(self)
    out = {}
    for chain in (False, True):
        prof = ChainingCounter(chain)
        r = {}

        def body():
            prof.start()
            mod.work(1)

        def after(c):
            r["installed_after_close"] = sys.getprofile() is prof
            before = prof.calls
            for i in range(5):
                mod.later(i)
            r["later_calls_seen"] = prof.calls - before
            r["found_profiler"] = prof.prev is not None
        try:
            r["trace"] = api.trace(e, lambda c: c.run("G", body), after)
        finally:
            sys.setprofile(None)
        out["chaining" if chain else "control"] = r
    return out
