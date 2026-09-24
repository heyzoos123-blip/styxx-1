import sys
sys.argv=['x']; sys.path.insert(0,'papers/first-afference'); sys.path.insert(0,'../fx')
import run_protocol_v5 as R, _fx2, tempfile
from pathlib import Path
from styxx.protocol import Experiment, coverage_trace, GateSpecError
def case(target, call):
    with tempfile.TemporaryDirectory() as td:
        exp = Experiment(R._commit_prereg(Path(td), R._spec(G={"exercises": [target]})))
        with coverage_trace(exp) as cov:
            with cov.section("G"): call()
        try: return exp.score({"m": 1.0, "coverage_trace": cov.record()}).verdict, cov.record()["sections"]
        except GateSpecError as e: return "REFUSED " + str(e)[:60]
print("non-wraps decorator, declared never called, sibling called:", case("_fx2:declared", _fx2.sibling))
print("closure factory, declared never called, sibling called:", case("_fx2:f_declared", _fx2.f_sibling))
