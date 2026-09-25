"""Witness: examhole-inherited-direct-base-only. Names inherited from beyond the first MRO base."""
import importlib
from b3lib import write_module, trace_and_score, leftovers, emit

write_module("b3inh", '''
class Base:
    def fit(self): return 1

class Mid(Base): pass

class Leaf(Mid): pass                      # fit comes from the GRANDPARENT

class LoggingMixin:
    def log(self): return 0

class Model(LoggingMixin, Base): pass      # fit comes from the SECOND direct base (a mixin first)

class Direct(Base): pass                   # control: fit comes from the direct base (X14's shape)
''')
m = importlib.import_module("b3inh")
out = {}
out["grandparent_method"] = trace_and_score({"G": ["b3inh:Leaf.fit"]}, {"G": lambda: m.Leaf().fit()})
out["mixin_second_base_method"] = trace_and_score({"G": ["b3inh:Model.fit"]}, {"G": lambda: m.Model().fit()})
out["object_dunder_via_parent"] = trace_and_score({"G": ["b3inh:Leaf.__init__"]}, {"G": lambda: m.Leaf()})
out["direct_base_control"] = trace_and_score({"G": ["b3inh:Direct.fit"]}, {"G": lambda: m.Direct().fit()})
out["truly_missing_control"] = trace_and_score({"G": ["b3inh:Leaf.nope"]}, {"G": lambda: None})
out["leftovers"] = leftovers()
emit(out)
