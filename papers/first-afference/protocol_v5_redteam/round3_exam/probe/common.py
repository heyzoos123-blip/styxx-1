import json, subprocess, tempfile, sys, os
from pathlib import Path
from styxx.protocol import Experiment, GateSpecError, coverage_trace
def exp_of(gates):
    d = Path(tempfile.mkdtemp())
    spec = {"gates": {n: {"metric": "m", "op": ">=", "value": 0.5, **g} for n, g in gates.items()},
            "outcomes": [{"when": {n: True for n in gates}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "SMOKE"}
    (d / "PREREG_x.md").write_text("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git","init","-q"],["git","add","-A"],["git","-c","user.email=a@b","-c","user.name=a","commit","-qm","x"]):
        subprocess.run(c, cwd=d, check=True)
    return Experiment(d / "PREREG_x.md")
