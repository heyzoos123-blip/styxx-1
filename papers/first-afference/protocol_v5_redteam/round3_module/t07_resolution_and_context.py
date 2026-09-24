from rtlib import *
import contextvars, fx3_ns, fx_simple
for t in ["fx3_ns:ops.a", "fx3_ns:reg.a", "fx3_ns:lazy_a"]:
    def go(t=t):
        e = exp(spec(G={"exercises": [t]}))
        with coverage_trace(e) as cov:
            with cov.section("G"): fx3_ns._a(1)
        return score(e, cov.record())
    attempt(f"R {t} (plain function reached through a namespace / lazy attr)", go)
# SECTION_CONTEXT leaves the opening context's section variable set forever
def sc():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}, H={"exercises": ["fx_simple:g"]}))
    with coverage_trace(e) as cov:
        cm = cov.section("G")
        cm.__enter__()                     # opened here
        try:
            contextvars.copy_context().run(cm.__exit__, None, None, None)   # closed elsewhere
        except GateSpecError as ex:
            print("   close:", str(ex)[:40])
        try:
            with cov.section("H"): fx_simple.g()
        except GateSpecError as ex:
            print("   opening H afterwards in the original context:", str(ex)[:90])
    return cov.record()["sections"]
attempt("C1 after SECTION_CONTEXT", sc)
