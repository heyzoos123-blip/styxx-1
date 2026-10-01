"""round2_module/a2_resolution.py, rewritten: (a) a method declared through a module-level instance
(default_model.fit), only another subclass's instance used; (b) two functools.wraps variants of one function,
the other variant called; (c) a singledispatch public entry really called."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r2m_fx import INST, SD, WRAPS


def main(api):
    inst, wr, sd = api.fixture("rp_fx2_inst", INST), api.fixture("rp_fx2_wraps", WRAPS), api.fixture("rp_fx2_sd", SD)
    return {"a_instance_path": api.trace(api.exp({"G": ["rp_fx2_inst:default_model.fit"]}), lambda c: c.run("G", lambda: inst.Other().fit())),
            "b_wraps_variant": api.trace(api.exp({"G": ["rp_fx2_wraps:run_fast"]}), lambda c: c.run("G", wr.run_safe, 1)),
            "c_singledispatch": api.trace(api.exp({"G": ["rp_fx2_sd:process"]}), lambda c: c.run("G", sd.process, 5))}
