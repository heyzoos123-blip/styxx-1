"""round3_module/t01_wraps_family.py, rewritten: a a declared functools.wraps wrapper, only a plain sibling
calling the same inner function called; b class-based update_wrapper siblings (declared fast, safe called);
c a temporary wraps sibling made per call (declared public, other_entry called); d an undecorated declared target
with two wraps aliases, called directly."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r3m_fx import WRAPS


def main(api):
    m = api.fixture("rp_fx3_wraps", WRAPS)
    T = lambda t, fn, *a: api.trace(api.exp({"G": [f"rp_fx3_wraps:{t}"]}), lambda c: c.run("G", fn, *a))
    return {"a_plain_sibling": T("run_fast", m.run_safe, 1), "b_class_siblings": T("fast", m.safe, 1),
            "c_temporary_sibling": T("public", m.other_entry, 1), "d_undecorated_with_aliases": T("score", m.score, 1)}
