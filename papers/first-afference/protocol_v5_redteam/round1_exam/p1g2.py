import sys, types
sys.argv=['x','--attempt-b']
sys.path.insert(0,'papers/first-afference')
import run_protocol_v5 as R
src = open(R.__file__).read().replace('if __name__ == "__main__"', 'if False')
def variant(name, *reps, extra=None):
    s = src
    for a, b in reps:
        assert a in s, a; s = s.replace(a, b)
    m = types.ModuleType(name); m.__file__ = R.__file__
    if extra: m.__dict__.update(extra)
    exec(compile(s, R.__file__, "exec"), m.__dict__)
    return m
def full(rng):
    import run_p1, numpy as np
    pw = sys.modules["styxx.power"]
    out = run_p1.degenerate(rng); g = rng.normal(0, 1, 500)
    pw.effective_n(g); pw.order_stat_bar(g, 5); pw.false_positive_rate(g, 0.5); pw.min_detectable_bar(g)
    return out
# (a) positive control
m = variant("pc", ('attempt("G4_refuses_degenerate", public, run_p1.degenerate)',
                   'attempt("G4_refuses_degenerate", public, lambda rng: (sys.modules.__setitem__("run_p1", run_p1), FULL(rng))[1])'),
            extra={"FULL": full})
r = m.p1_retro(); print("positive control G4 refused:", r["G4"]["refused"], "|", r["G4"]["detail"][:60], r["G4"]["calls"])
# (b) typo in one declared target
m = variant("typo", ('"reachable")]', '"reachabel")]'))
r = m.p1_retro(); print("typo G4 refused:", r["G4"]["refused"], "| detail:", r["G4"]["detail"][:120], "| calls:", r["G4"]["calls"])
