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
