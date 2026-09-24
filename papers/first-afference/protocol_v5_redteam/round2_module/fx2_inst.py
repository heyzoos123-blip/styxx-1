class Base:
    def fit(self): return 1
class Sub(Base): pass
class Other(Base): pass
default_model = Sub()        # declared as "fx2_inst:default_model.fit"
