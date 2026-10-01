"""round1_module/t01_shared_code.py, rewritten against v5f's public API: factory-made functions sharing one code
object (declared check_high, only check_low called), and a decorator without functools.wraps (declared entry_b,
only entry_a called)."""
FX = '''
def _make(k):
    def check(x):
        return x > k
    return check
check_low = _make(0.1)
check_high = _make(0.9)
def plain(f):
    def inner(*a, **k):
        return f(*a, **k)
    return inner
@plain
def entry_a(): return "a"
@plain
def entry_b(): return "b"
'''


def main(api):
    fx = api.fixture("rp_fx_factory", FX)
    return {"factory_closure": api.trace(api.exp({"G": ["rp_fx_factory:check_high"]}), lambda c: c.run("G", fx.check_low, 0.5)),
            "no_wraps_decorator": api.trace(api.exp({"G": ["rp_fx_factory:entry_b"]}), lambda c: c.run("G", fx.entry_a))}
