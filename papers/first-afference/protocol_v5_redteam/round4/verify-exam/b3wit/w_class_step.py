"""Witness: examhole-class-step-exact-type. Methods of classes whose metaclass is not `type`."""
import os
from b3lib import write_module, trace_and_score, leftovers, emit
import importlib

M = "b3cls"   # fixed name: each run is its own process with its own temp dir
write_module(M, '''
import abc, enum, typing

class Model(abc.ABC):                       # metaclass ABCMeta
    def fit(self): return 1

class Color(enum.Enum):                     # metaclass EnumType / EnumMeta
    RED = 1
    def describe(self): return self.name

class Meta(type): pass

class Custom(metaclass=Meta):               # user metaclass
    def go(self): return 3

class Proto(typing.Protocol):               # _ProtocolMeta
    def need(self) -> int: ...

class Impl:
    def need(self) -> int: return 4

class Plain:                                # control: metaclass is exactly type
    def run(self): return 5

class ABase(abc.ABC):
    def inh(self): return 6

class ASub(ABase): pass                     # inherited through an ABC
''')
mod = importlib.import_module(M)
out = {}
out["abc_method"] = trace_and_score({"G": [f"{M}:Model.fit"]},
                                    {"G": lambda: type("Lin", (mod.Model,), {})().fit()})
out["enum_method"] = trace_and_score({"G": [f"{M}:Color.describe"]}, {"G": lambda: mod.Color.RED.describe()})
out["custom_metaclass_method"] = trace_and_score({"G": [f"{M}:Custom.go"]}, {"G": lambda: mod.Custom().go()})
out["plain_class_control"] = trace_and_score({"G": [f"{M}:Plain.run"]}, {"G": lambda: mod.Plain().run()})
out["abc_inherited_code"] = trace_and_score({"G": [f"{M}:ASub.inh"]}, {"G": lambda: mod.ASub().inh()})
out["abc_missing_code"] = trace_and_score({"G": [f"{M}:Model.nope"]}, {"G": lambda: None})
out["leftovers"] = leftovers()
emit(out)
