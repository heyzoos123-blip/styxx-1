"""round2_module/v1_b4_cprofile.py, rewritten: the same program as round 1's t06 (the trace run under the
harness's profiler). r1m_t06 covers the C profiler (cProfile; sys.monitoring tool 2 on 3.12+); this rewrite runs
the trace under the pure-Python profile.Profile, which installs itself with sys.setprofile."""
import sys


def main(api):
    import profile
    fx = api.fixture("rp_fx_simple", 'def f(): return 1\n')
    e = api.exp({"G": ["rp_fx_simple:f"]})
    pr = profile.Profile()
    res = {}

    def run():
        res["profiler_before_set"] = sys.getprofile() is not None
        res["trace"] = api.trace(e, lambda c: c.run("G", fx.f))
        res["profiler_after_set"] = sys.getprofile() is not None
    pr.runcall(run)
    res["profiler_after_runcall_none"] = sys.getprofile() is None
    return res
