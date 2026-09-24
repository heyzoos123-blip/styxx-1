from rtlib import *
import time, pathlib, sys
src = "\n".join(f"def t{i}(): return {i}" for i in range(40))
pathlib.Path("fx2_many.py").write_text(src)
import fx2_many
e = exp(spec(G={"exercises": [f"fx2_many:t{i}" for i in range(40)]}))
for heap in (0, 3_000_000):
    junk = [[i] for i in range(heap)]       # gc-tracked objects, like a loaded ML stack
    t0 = time.perf_counter(); coverage_trace(e); dt = time.perf_counter() - t0
    print(f"heap +{heap:>9} tracked objects: coverage_trace() construction {dt:.2f}s for 40 targets")
    del junk
