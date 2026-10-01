"""round4/crossversion-spec/r1/f05_profile_module_refuses_on_312.py, rewritten: the section run through
profile.Profile().runcall (a pure-Python sys.setprofile profiler) and through cProfile.Profile().runcall, each in
its own trace, scored."""
import sys


def main(api):
    import cProfile, profile
    mod = api.fixture("rp_xv_f05_mod", "def f(x=0):\n    return x\n")
    e = api.exp({"G": ["rp_xv_f05_mod:f"]})
    out = {}
    for label, cls in (("profile", profile.Profile), ("cProfile", cProfile.Profile)):
        def run(c):
            try:
                return cls().runcall(c.run, "G", mod.f, 1)
            finally:
                sys.setprofile(None)
        out[label] = api.trace(e, run)
    return out
