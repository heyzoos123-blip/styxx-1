"""(a) explicit __exit__ on success plus the same __exit__ again in a finally."""
import b6lib as W
mod = W.module("b6de_fx", "def f():\n    return 1\n")
exp = W.experiment({"G": {"exercises": ["b6de_fx:f"]}}, tag="a1")
cov = W.coverage_trace(exp)
cov.__enter__()
try:
    cov.run("G", mod.f)
    cov.__exit__(None, None, None)
finally:
    r2 = cov.__exit__(None, None, None)
first = W.score(exp, cov.record())
after_first = W.globals_state()
exp2 = W.experiment({"H": {"exercises": ["b6de_fx:f"]}}, tag="a2")
with W.coverage_trace(exp2) as cov2:            # later, independent trace, same process
    cov2.run("H", mod.f)
second = W.score(exp2, cov2.record())
W.emit({"second_exit_returned": r2, "first_trace": first, "state_after_double_exit": after_first,
        "later_independent_trace": second, "state_at_end": W.globals_state()})
