class Base:
    def fit(self): return 8
class Sub(Base): pass
class Other(Base): pass
bound_fit = Sub().fit
