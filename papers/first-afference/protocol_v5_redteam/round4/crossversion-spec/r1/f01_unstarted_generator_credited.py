"""F01: a declared generator (or coroutine) function whose body NEVER runs is credited on 3.10/3.11.

Harness shape (accidental, the P1 defect itself): the harness calls a generator function and forgets
to consume it (`mod.scan(rows)` instead of `list(mod.scan(rows))`), or builds a coroutine and closes
it to silence "never awaited". No line of the target's body executes. On CPython <= 3.11 the
generator's finaliser / close() throws GeneratorExit INTO the unstarted frame, which fires a profile
'call' event whose f_back is the harness frame, so the hook credits the section. On 3.12+ closing an
unstarted generator is a no-op (gh-100762 era change) and the same harness reads NOT_EXERCISED.
Run: PYTHONPATH=/home/user/styxx-1 python f01_unstarted_generator_credited.py
"""
import json, subprocess, sys, tempfile, textwrap, os
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="rt4xv_f01_"))
modname = "_rt4xv_f01_mod"
(tmp / f"{modname}.py").write_text(textwrap.dedent('''
    BODY_RAN = []
    def scan(rows):
        BODY_RAN.append("scan")          # proves whether the body executed
        for r in rows:
            yield r * 2
    async def fetch(x):
        BODY_RAN.append("fetch")
        return x
'''))
sys.path.insert(0, str(tmp))
repo = tmp / "repo"; repo.mkdir()
spec = {"gates": {
            "G_gen": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [f"{modname}:scan"]},
            "G_co":  {"metric": "m", "op": ">=", "value": 0.5, "exercises": [f"{modname}:fetch"]}},
        "outcomes": [{"when": {"G_gen": True, "G_co": True}, "verdict": "PASS"},
                     {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "S"}
p = repo / "PREREG_f01.md"
p.write_text("# f01\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", "commit", "-qm", "c"]):
    subprocess.run(cmd, cwd=repo, check=True)

from styxx.protocol import Experiment, GateSpecError, coverage_trace
import importlib
mod = importlib.import_module(modname)
exp = Experiment(p)

def gen_harness():
    mod.scan([1, 2, 3])          # BUG in harness: generator never consumed
    return 1.0

def co_harness():
    c = mod.fetch(1)             # build the coroutine, check its type, close it to silence the warning
    ok = type(c).__name__ == "coroutine"
    c.close()
    return 1.0 if ok else 0.0

with coverage_trace(exp) as cov:
    m1 = cov.run("G_gen", gen_harness)
    m2 = cov.run("G_co", co_harness)
rec = cov.record()
res = {"m": min(m1, m2), "coverage_trace": rec}
ver = sys.version.split()[0]
body_ran = list(mod.BODY_RAN)
calls = {s: [o["calls"] for o in ops] for s, ops in rec["sections"].items()}
try:
    v = exp.score(res)
    outcome = f"score -> {v.verdict} coverage={v.coverage}"
    passed = v.verdict == "PASS"
except GateSpecError as e:
    outcome = f"score refused: {str(e)[:90]}"
    passed = False
print(f"[{ver}] body executed: {body_ran}; recorded calls {calls}; {outcome}")
credited = any(o for ops in calls.values() for o in ops)
if credited and not body_ran:
    print(f"FINDING-REPRODUCED: on {ver} a declared generator/coroutine whose body never ran "
          f"(dropped / closed unstarted) is credited; {'score PASS' if passed else 'score did not pass'}")
else:
    print(f"no finding: on {ver} the unstarted generator/coroutine was not credited")
