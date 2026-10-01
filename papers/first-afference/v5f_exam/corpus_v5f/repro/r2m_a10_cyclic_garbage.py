"""round2_module/a10_cyclic_garbage.py, rewritten: with the collector disabled, a module whose import built and
dropped a recursive closure sharing the declared closure's code (uncollected cyclic garbage); the declared closure
called in the section; then the same after gc.collect(). The collector is re-enabled at the end."""
import gc, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r2m_fx import CYC


def main(api):
    gc.disable()
    try:
        cyc = api.fixture("rp_fx2_cyc", CYC)
        out = {"uncollected": api.trace(api.exp({"G": ["rp_fx2_cyc:walk10"]}), lambda c: c.run("G", cyc.walk10, 0))}
        gc.collect()
        out["after_collect"] = api.trace(api.exp({"G": ["rp_fx2_cyc:walk10"]}), lambda c: c.run("G", cyc.walk10, 0))
    finally:
        gc.enable()
    return out
