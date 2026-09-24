import sys; sys.path.insert(0, __file__.rsplit("/",1)[0])
from common import *
import pfx2
e = exp_of({"G": {"exercises": ["pfx2:bound_fit"]}})
try:
    with coverage_trace(e) as cov:
        with cov.section("G"):
            pfx2.Other().fit()
    r = {"m": 1.0, "coverage_trace": cov.record()}
    print("scored", e.score(r).verdict, r["coverage_trace"]["sections"])
except GateSpecError as ex:
    print("refused", str(ex)[:90])
