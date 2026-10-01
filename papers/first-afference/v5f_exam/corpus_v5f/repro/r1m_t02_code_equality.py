"""round1_module/t02_code_equality.py, rewritten: a vendored copy whose code equals the declared function's
(declared score_null of the new module, only the vendored copy runs); and a pinned copy of a module exec'd under
another name (the repro exec'd git's copy of styxx.protocol; here a copy of a fixture module, since the probe
never reads the implementation's history)."""
NEW = '''
def score_null(xs):
    return sum(xs) / len(xs)
'''


def main(api):
    import sys, types
    new = api.fixture("rp_impl_new", NEW)
    old = api.fixture("rp_legacy.rp_impl_old", NEW)
    out = {"same_object": new.score_null is old.score_null, "code_equal": new.score_null.__code__ == old.score_null.__code__}
    out["vendored_copy"] = api.trace(api.exp({"G": ["rp_impl_new:score_null"]}), lambda c: c.run("G", old.score_null, [1, 2, 3]))
    pinned = types.ModuleType("rp_pinned")
    pinned.__file__ = "git:HEAD:rp_impl_new.py"
    sys.modules["rp_pinned"] = pinned
    exec(compile(NEW, pinned.__file__, "exec"), pinned.__dict__)
    out["pinned_copy"] = api.trace(api.exp({"G": ["rp_impl_new:score_null"]}), lambda c: c.run("G", pinned.score_null, [1, 2]))
    sys.modules.pop("rp_pinned", None)
    return out
