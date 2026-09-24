import sys; sys.path.insert(0, __file__.rsplit("/",1)[0])
from common import *
import pfx3
e = exp_of({"G": {"exercises": ["pfx3:run_fast"]}})
ran = []
try:
    with coverage_trace(e) as cov:
        with cov.section("G"):
            ran.append("harness ran"); pfx3.run_safe()
    print("scored")
except GateSpecError as ex:
    print(ran, "refused", str(ex)[:40], "...", str(ex)[-60:])
