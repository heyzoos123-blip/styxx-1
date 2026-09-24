import sys, tempfile
sys.argv=['x']; sys.path.insert(0,'papers/first-afference'); sys.path.insert(0,'../fx')
import run_protocol_v5 as R, _fx3
from pathlib import Path
from styxx.protocol import Experiment, coverage_trace, GateSpecError
with tempfile.TemporaryDirectory() as td:
    exp = Experiment(R._commit_prereg(Path(td), R._spec(G={"exercises": ["_fx3:declared"]})))
    with coverage_trace(exp) as cov:
        with cov.section("G"): _fx3.sibling()
    try: print("wraps sibling:", exp.score({"m": 1.0, "coverage_trace": cov.record()}).verdict)
    except GateSpecError as e: print("wraps sibling: REFUSED", str(e)[:50])
