"""Verifier's own repro for dict-subclass-result-no-trace.

Claim: _check_coverage tests `type(result) is dict`, so a result that IS a dict (a dict subclass)
carrying the tracer's own exact-dict record() under "coverage_trace" is refused NO_TRACE with a
message saying the result carries no trace dict. Spec step 1: "NO_TRACE: the result is not a dict,
or `dict.get(result, "coverage_trace")` is not an exact dict."

Run: PYTHONPATH=/home/user/styxx-1 python own_repro.py
"""
import collections
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from styxx.protocol import Experiment, GateSpecError, coverage_trace

base = Path(__file__).resolve().parent / "work"
base.mkdir(exist_ok=True)
tmp = Path(tempfile.mkdtemp(prefix="own_", dir=base))
mod = "vfy_" + uuid.uuid4().hex[:8]
(tmp / f"{mod}.py").write_text("def g(x):\n    return x + 1\n")
sys.path.insert(0, str(tmp))

spec = {"gates": {"A": {"metric": "score", "op": ">=", "value": 0.5,
                        "exercises": [f"{mod}:g"]}},
        "outcomes": [{"when": {"A": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "SMOKE"}
repo = tmp / "r"
repo.mkdir()
(repo / "PREREG_v.md").write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
            ["git", "-c", "user.email=v@v", "-c", "user.name=v", "-c", "commit.gpgsign=false",
             "commit", "-qm", "v"]):
    subprocess.run(cmd, cwd=repo, check=True, capture_output=True)

exp = Experiment(repo / "PREREG_v.md")
m = __import__(mod)
with coverage_trace(exp) as cov:
    cov.run("A", m.g, 1)
rec = cov.record()
assert type(rec) is dict


class Result(dict):
    """A plain dict subclass with NO overrides at all."""


def attempt(label, res):
    tr = dict.get(res, "coverage_trace")
    spec_says_no_trace = (not isinstance(res, dict)) or (type(tr) is not dict)
    try:
        v = exp.score(res)
        got = f"PASS verdict={v.verdict} coverage={v.coverage}"
    except GateSpecError as e:
        got = f"REFUSED {str(e)[:95]}"
    print(f"{label:32s} isinstance(dict)={isinstance(res, dict)!s:5s} "
          f"type(dict.get(res,'coverage_trace')) is dict={type(tr) is dict!s:5s} "
          f"spec step1 fires={spec_says_no_trace!s:5s}\n    -> {got}")
    return got


print(sys.version.split()[0])
out = {}
out["plain"] = attempt("plain dict", {"score": 1.0, "coverage_trace": rec})
out["subclass"] = attempt("bare dict subclass", Result(score=1.0, coverage_trace=rec))
dd = collections.defaultdict(float)
dd["score"] = 1.0
dd["coverage_trace"] = rec
out["defaultdict"] = attempt("defaultdict", dd)
out["ordered"] = attempt("OrderedDict", collections.OrderedDict(score=1.0, coverage_trace=rec))
cm = exp.check_metrics(Result(score=1.0, coverage_trace=rec))
print("check_metrics(subclass):", {k: (v["present"], v["usable"], (v["note"] or "")[:60])
                                   for k, v in cm.items()})

# v3 path of score() accepts dict-subclass results: an undeclaring gate on the same result.
spec3 = {"gates": {"B": {"metric": "score", "op": ">=", "value": 0.5}},
         "outcomes": [{"when": {"B": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
         "smoke_verdict": "SMOKE"}
(repo / "PREREG_w.md").write_text("# w\n\n```gates\n" + json.dumps(spec3) + "\n```\n")
for cmd in (["git", "add", "-A"],
            ["git", "-c", "user.email=v@v", "-c", "user.name=v", "-c", "commit.gpgsign=false",
             "commit", "-qm", "w"]):
    subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
exp3 = Experiment(repo / "PREREG_w.md")
print("v3 gate on bare dict subclass ->", exp3.score(Result(score=1.0)).verdict)

falsemsg = "carries no 'coverage_trace' dict"
if out["plain"].startswith("PASS") and all(
        out[k].startswith("REFUSED [V5:NO_TRACE]") and falsemsg in out[k]
        for k in ("subclass", "defaultdict", "ordered")):
    print("REPRODUCED: dict-subclass results with an exact-dict trace refuse NO_TRACE "
          "although spec step 1 does not fire")
else:
    print("NOT REPRODUCED")
