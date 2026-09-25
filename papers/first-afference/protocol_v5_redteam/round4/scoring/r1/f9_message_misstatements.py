"""F9 (message texts): two emitted texts state something false about what happened.

 (a) NESTED_SECTION: "section 'G' opened on the stack of an open opening of section 'G' of the same
     trace -- one call would count for two gates". When the section re-enters ITSELF (a recursive
     battery helper that wraps each case in cov.run of the same section), there is one section and
     (here) one gate; nothing could count for two gates. The refusal is disclosed (over-blocking 4);
     its stated reason is not true for this shape.
 (b) LAZY_RESULT: run() appends "fn returned a generator; its body runs after the section closed, so
     none of it counts" whenever fn RETURNS a generator object -- even when fn did all of its work
     (and all of its target calls, which ARE credited) inside the section and merely returns a lazy
     view of its results. The note then appears in the NOT_EXERCISED message of that gate as the
     apparent explanation, while the credited count shows the claim "none of it counts" is false.

Run: PYTHONPATH=/home/user/styxx-1 python f9_message_misstatements.py
"""
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from styxx.protocol import Experiment, GateSpecError, coverage_trace

tmp = Path(tempfile.mkdtemp(prefix="rt4sc_f9_"))
modname = "rt4sc_fx_" + uuid.uuid4().hex[:8]
(tmp / f"{modname}.py").write_text("def f():\n    return 1\n\ndef g():\n    return 2\n")
sys.path.insert(0, str(tmp))
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5,
                        "exercises": [f"{modname}:f", f"{modname}:g"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
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
print(f"python {sys.version.split()[0]}")

# (a) the section re-enters itself
with coverage_trace(exp) as cov:
    def battery():
        mod.f()
        try:
            cov.run("G", mod.g)
        except GateSpecError as e:
            return str(e)
    msg_a = cov.run("G", battery)
print(f"  (a) {msg_a[:160]}")

# (b) fn does its work in the section and returns a lazy view of the results
with coverage_trace(exp) as cov:
    def battery_b():
        results = [mod.f() for _ in range(3)]             # all the work happens here
        return (r * 2 for r in results)                   # a generator expression over results
    list(cov.run("G", battery_b))
rec = cov.record()
op = rec["sections"]["G"][0]
try:
    exp.score({"m": 1.0, "coverage_trace": rec})
    msg_b = "PASS"
except GateSpecError as e:
    msg_b = str(e)
print(f"  (b) opening: calls={op['calls']} notes={op['notes']}")
a_false = "one call would count for two gates" in msg_a and msg_a.count("section 'G'") == 2
b_false = "none of it counts" in op["notes"][0] and op["calls"] == {f"{modname}:f": 3} \
    and "LAZY_RESULT" in msg_b
if a_false or b_false:
    print(f"FINDING-REPRODUCED: refusal/note text misstates what happened: (a) NESTED_SECTION of a "
          f"section inside itself says 'one call would count for two gates' [{a_false}]; (b) "
          f"LAZY_RESULT says 'none of it counts' next to calls={op['calls']} credited from the same "
          f"opening, and is quoted in the NOT_EXERCISED message [{b_false}]")
else:
    print("no finding: the texts are accurate")
