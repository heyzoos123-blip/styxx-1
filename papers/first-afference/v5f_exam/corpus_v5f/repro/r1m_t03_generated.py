"""round1_module/t03_generated.py, rewritten: a dataclass's generated __init__ (declared NullModel.__init__, only
AltModel constructed) and an inherited method (declared Sub.fit, only Other().fit() called)."""
FX = '''
from dataclasses import dataclass
@dataclass
class NullModel:
    n: int
    seed: int = 0
@dataclass
class AltModel:
    n: int
    seed: int = 0
class Base:
    def fit(self): return 1
class Sub(Base): pass
class Other(Base): pass
'''


def main(api):
    fx = api.fixture("rp_fx_dc", FX)
    return {"dataclass_init": api.trace(api.exp({"G": ["rp_fx_dc:NullModel.__init__"]}), lambda c: c.run("G", fx.AltModel, 3)),
            "inherited_method": api.trace(api.exp({"G": ["rp_fx_dc:Sub.fit"]}), lambda c: c.run("G", lambda: fx.Other().fit()))}
