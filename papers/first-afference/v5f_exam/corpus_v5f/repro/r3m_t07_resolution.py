"""round3_module/t07_resolution_and_context.py, rewritten: a plain function declared through a SimpleNamespace,
a registry instance and a PEP 562 module __getattr__, the plain function called. (Part C1, a section context
manager entered in one context and exited in a copied one, is not applicable: v5f's sections are calls; see
NOT_APPLICABLE.json.)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r3m_fx import NS


def main(api):
    ns = api.fixture("rp_fx3_ns", NS)
    return {t: api.trace(api.exp({"G": [f"rp_fx3_ns:{t}"]}), lambda c: c.run("G", ns._a, 1)) for t in ("ops.a", "reg.a", "lazy_a")}
