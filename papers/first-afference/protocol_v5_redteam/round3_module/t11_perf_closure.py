import time, sys
from rtlib import *
import fx3_perf as m
def t(fn, n=200000):
    t0 = time.perf_counter()
    for i in range(n): fn(i)
    return time.perf_counter() - t0
base = {k: t(getattr(m, k)) for k in ("plain", "clos", "bigloc")}
e = exp(spec(G={"exercises": ["fx3_perf:plain", "fx3_perf:clos", "fx3_perf:bigloc"]}))
with coverage_trace(e) as cov:
    with cov.section("G"):
        tr = {k: t(getattr(m, k)) for k in ("plain", "clos", "bigloc")}
print(sys.version.split()[0], {k: f"{tr[k]/base[k]:.0f}x ({tr[k]*1e6/200000:.1f}us/call)" for k in tr})
