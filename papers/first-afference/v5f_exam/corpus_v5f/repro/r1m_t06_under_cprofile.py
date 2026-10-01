"""round1_module/t06_under_cprofile.py, rewritten: the whole trace runs under the harness's own profiler
(the repro ran it under `python -m cProfile`; here a cProfile.Profile is enabled around it, the same
sys.setprofile installation)."""
import sys


def main(api):
    import cProfile
    fx = api.fixture("rp_fx_simple", 'def f(): return 1\n')
    e = api.exp({"G": ["rp_fx_simple:f"]})
    pr = cProfile.Profile()
    pr.enable()
    before = {"getprofile_set": sys.getprofile() is not None,
              "monitoring_tool2": getattr(sys, "monitoring", None) and sys.monitoring.get_tool(2)}
    res = api.trace(e, lambda c: c.run("G", fx.f))
    after = {"getprofile_set": sys.getprofile() is not None,
             "monitoring_tool2": getattr(sys, "monitoring", None) and sys.monitoring.get_tool(2)}
    pr.disable()
    return {"profiler_before": before, "trace": res, "profiler_after_kept": after}
