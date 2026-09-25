"""F3: a result that IS a dict (collections.OrderedDict / defaultdict, or a dict loaded with
json.load(object_pairs_hook=OrderedDict)) and that carries the tracer's own exact-dict record()
under "coverage_trace" is refused [V5:NO_TRACE] with the message "the result carries no
'coverage_trace' dict" -- which is false. _check_coverage tests `type(result) is dict` while the
spec's step 1 says only "the result is not a dict" (the EXACT test is stated for the trace only),
and every v3/v4 path of score() (_resolve: isinstance(obj, dict)) accepts the same result.
check_metrics contradicts itself on it: present=True, usable=False, note "... carries no ... dict".

Run: PYTHONPATH=/home/user/styxx-1 python f3_dict_subclass_result.py
"""
import collections
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from styxx.protocol import Experiment, GateSpecError, coverage_trace

tmp = Path(tempfile.mkdtemp(prefix="rt4sc_f3_"))
modname = "rt4sc_fx_" + uuid.uuid4().hex[:8]
(tmp / f"{modname}.py").write_text("def f():\n    return 1\n")
sys.path.insert(0, str(tmp))
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5,
                        "exercises": [f"{modname}:f"]},
                  "H": {"metric": "m", "op": ">=", "value": 0.5}},     # an undeclaring v3 gate
        "outcomes": [{"when": {"G": True, "H": True}, "verdict": "PASS"},
                     {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "SMOKE"}
repo = tmp / "repo"
repo.mkdir()
(repo / "PREREG_x.md").write_text("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
            ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
             "commit", "-qm", "x"]):
    subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
exp = Experiment(repo / "PREREG_x.md")
mod = __import__(modname)

with coverage_trace(exp) as cov:
    m = cov.run("G", mod.f)
rec = cov.record()
print(f"python {sys.version.split()[0]}")


def score(res, label):
    try:
        v = exp.score(res)
        out = f"PASS ({v.verdict})"
    except GateSpecError as e:
        out = f"REFUSED {str(e)[:120]}"
    print(f"  {label:44s} -> {out}")
    return out


plain = score({"m": 1.0, "coverage_trace": rec}, "plain dict result")
res_dd = collections.defaultdict(dict)          # a common way to accumulate nested results
res_dd["m"] = 1.0
res_dd["coverage_trace"] = rec                  # the tracer's own exact dict
dd = score(res_dd, "defaultdict result, exact-dict trace")
od = score(collections.OrderedDict(m=1.0, coverage_trace=rec), "OrderedDict result, exact-dict trace")
cm = exp.check_metrics(res_dd)["G:exercises"]
print(f"  check_metrics(defaultdict)['G:exercises'] -> present={cm['present']} usable={cm['usable']} "
      f"note={cm['note'][:70]!r}")
false_msg = "carries no 'coverage_trace' dict"
if plain.startswith("PASS") and dd.startswith("REFUSED [V5:NO_TRACE]") and false_msg in dd:
    print("FINDING-REPRODUCED: a dict-subclass result (defaultdict/OrderedDict) carrying the exact-dict "
          "record() is refused [V5:NO_TRACE] 'the result carries no coverage_trace dict' (false); "
          "check_metrics says present=True and gives the same false note")
else:
    print("no finding: dict-subclass results are scored like dicts")
