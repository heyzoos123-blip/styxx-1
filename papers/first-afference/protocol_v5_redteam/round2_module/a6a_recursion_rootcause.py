from rtlib import *
import fx2_rec, sys, threading
e = exp(spec(G={"exercises": ["fx2_rec:parse"]}))
cov = coverage_trace(e); cov.__enter__()
print("before:", type(sys.getprofile()).__name__)
try: fx2_rec.parse("x" * 100000)
except RecursionError as ex:
    import traceback; tb = traceback.extract_tb(ex.__traceback__)
    print("RecursionError raised in:", {f.name for f in tb[-3:]})
print("after caught RecursionError, sys.getprofile():", sys.getprofile())
# without tracer: same depth -> RecursionError anyway (the harness's expected refusal)
