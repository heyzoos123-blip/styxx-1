# (a)1: `type(obj) in (staticmethod, classmethod)` runs a metaclass __eq__; `is` chains do not.
import sys, types
ran = []
class M(type):
    def __eq__(cls, other):
        ran.append('eq'); raise RuntimeError("user __eq__ ran")
    __hash__ = type.__hash__
    def __subclasscheck__(cls, sub): ran.append('subclasscheck'); return False
    def __instancecheck__(cls, inst): ran.append('instancecheck'); return False
class C(metaclass=M): pass
obj = C()
try:
    r = type(obj) in (staticmethod, classmethod); print("in: no raise", r, ran)
except RuntimeError as e:
    print("in-tuple test:", repr(e), ran)
ran.clear()
t = type(obj)
print("is-chain:", t is staticmethod or t is classmethod, ran)
ran.clear()
print("issubclass(type(obj), ModuleType):", issubclass(type(obj), types.ModuleType), ran)
print("issubclass(type(C), type):", issubclass(type(C), type), ran)
# the class itself as a path object
ran.clear()
LAZY = (types.GeneratorType, types.CoroutineType, types.AsyncGeneratorType)
try:
    print(type(obj) in LAZY)
except RuntimeError as e:
    print("_LAZY_TYPES in-test:", repr(e))
print(sys.version.split()[0])
