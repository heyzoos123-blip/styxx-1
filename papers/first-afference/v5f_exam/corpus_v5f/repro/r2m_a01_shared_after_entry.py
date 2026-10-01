"""round2_module/a1_shared_after_entry.py, rewritten: (a) a function sharing the declared wrapper's code made by a
runtime decoration inside the section (score_all never called); (b) a lazily imported plugin module applying the
same no-wraps decorator, imported inside the section; (c) a FunctionType clone of the declared code made after
the enter; (d) __code__ assignment of the declared code to a local function after the enter."""
import os, sys, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r2m_fx import CLONE, PLUGIN, TIMED


def main(api):
    m = api.fixture("rp_fx2_timed", TIMED)
    c = api.fixture("rp_fx2_clone", CLONE)
    out = {}
    e = api.exp({"G": ["rp_fx2_timed:score_all"]})
    out["a_runtime_decoration"] = api.trace(e, lambda cov: cov.run("G", lambda: m.get_cheap_handler()(1)))
    api.write("rp_fx2_plugin", PLUGIN)

    def plug():
        import rp_fx2_plugin
        return rp_fx2_plugin.plugin_entry(3)
    e = api.exp({"G": ["rp_fx2_timed:score_all"]})
    out["b_lazy_plugin"] = api.trace(e, lambda cov: cov.run("G", plug))
    e = api.exp({"G": ["rp_fx2_clone:target"]})
    out["c_functiontype_clone"] = api.trace(
        e, lambda cov: cov.run("G", lambda: types.FunctionType(c.target.__code__, {"__builtins__": __builtins__}, "clone")(2)))

    def reassign():
        def mock(x):
            return 0
        mock.__code__ = c.target.__code__
        return mock(1)
    e = api.exp({"G": ["rp_fx2_clone:target"]})
    out["d_code_assignment"] = api.trace(e, lambda cov: cov.run("G", reassign))
    return out
