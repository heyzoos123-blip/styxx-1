import threading
from common import *
e = exp_of({"G": {"exercises": ["threading:Thread.start"]}})
with coverage_trace(e) as cov:
    with cov.section("G"):
        t = threading.Thread(target=lambda: None); t.start(); t.join()
r = {"m": 1.0, "coverage_trace": cov.record()}
print(r["coverage_trace"]["sections"]); print(e.score(r).verdict)
