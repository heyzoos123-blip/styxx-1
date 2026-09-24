from rtlib import *
import fx_dc
e = exp(spec(G={"exercises": ["fx_dc:NullModel.__init__"]}))
with coverage_trace(e) as cov:
    with cov.section("G"):
        fx_dc.AltModel(3)          # NullModel is never constructed
print("dataclass __init__:", score(e, cov.record()))
e = exp(spec(G={"exercises": ["fx_dc:Sub.fit"]}))
with coverage_trace(e) as cov:
    with cov.section("G"):
        fx_dc.Other().fit()        # Sub never instantiated
print("inherited method:", score(e, cov.record()))
