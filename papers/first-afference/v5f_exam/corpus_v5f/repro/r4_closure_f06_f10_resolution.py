"""round4/closure-audit/r1/f6_resolution_runs_user_getattribute.py and f10_pep562_message_names_no_module.py,
rewritten: f6, a target declared through a plain namespace instance and through a strict namespace whose
__getattribute__ raises KeyError for unknown attributes (the resolution's isinstance step reaches it), each
entered and run; f10, a package whose PEP 562 __getattr__ lazily re-exports solve from its _impl submodule, the
re-export declared (the refusal's code and the module:qualname it names)."""

F6 = '''
class StrictConfig:
    def __init__(self, **kw): object.__getattribute__(self, "__dict__").update(kw)
    def __getattribute__(self, name):
        d = object.__getattribute__(self, "__dict__")
        if name in d:
            return d[name]
        raise KeyError(f"unknown setting {name!r}")
class PlainNS:
    def __init__(self, **kw): self.__dict__.update(kw)
def handler(x=0): return x
hooks = StrictConfig(handler=handler)
plain = PlainNS(handler=handler)
'''


def main(api):
    fx = api.fixture("rp_ca_f6", F6)
    out = {p: api.trace(api.exp({"G": [f"rp_ca_f6:{p}"]}), lambda c: c.run("G", fx.handler, 1))
           for p in ("plain.handler", "hooks.handler")}
    api.write("rp_ca_pkg10.__init__", "def __getattr__(name):\n    if name == 'solve':\n"
              "        from rp_ca_pkg10._impl import solve\n        return solve\n    raise AttributeError(name)\n")
    api.write("rp_ca_pkg10._impl", "def solve(x=0): return x\n")
    out["f10_pep562_reexport"] = api.trace(api.exp({"G": ["rp_ca_pkg10:solve"]}))
    return out
