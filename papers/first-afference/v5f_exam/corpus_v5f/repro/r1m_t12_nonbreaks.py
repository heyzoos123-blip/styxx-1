"""round1_module/t12_nonbreaks.py, rewritten: a classmethod, __call__, a raising function, recursion and getattr
access, all declared and called in the section; then the fixture module reloaded after the enter and its new
function called."""
import importlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r1m_fx import CM


def main(api):
    fx = api.fixture("rp_fx_cm", CM)
    out = {}
    e = api.exp({"G": ["rp_fx_cm:K.make", "rp_fx_cm:K.__call__", "rp_fx_cm:boom", "rp_fx_cm:rec"]})

    def body():
        fx.K.make()()
        getattr(fx, "rec")(3)
        try:
            fx.boom()
        except ValueError:
            pass
    out["kinds"] = api.trace(e, lambda c: c.run("G", body))
    e = api.exp({"G": ["rp_fx_cm:rec"]})
    mod = {}

    def rel(c):
        mod["m"] = importlib.reload(fx)
    out["reload_after_enter"] = api.trace(e, rel, lambda c: c.run("G", lambda: mod["m"].rec(0)))
    return out
