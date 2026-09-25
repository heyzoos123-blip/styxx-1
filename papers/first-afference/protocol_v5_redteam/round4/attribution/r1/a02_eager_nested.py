"""Spec, "Sections are calls": "A task inside any loop, including a loop that runs inside another
section, may open its own `run_async` section." With asyncio.eager_task_factory (3.12+), a task
created from inside a run_async section starts its first step synchronously ON THE CREATOR'S
STACK, so the child's own run_async(B) _open walks into A's anchor with no Handle._run between:
NESTED_SECTION is raised (and recorded, refusing every gate). Same harness with the default
factory: PASS. The documented remedy for gather children ("run_async inside the task") is what
fails."""
import asyncio, json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/home/user/styxx-1")
from styxx.protocol import Experiment, GateSpecError, coverage_trace

FIX = Path(tempfile.mkdtemp(prefix="a02fx_"))
(FIX / "a02_fix.py").write_text("def f(): return 1\ndef g(): return 2\n")
sys.path.insert(0, str(FIX))
import a02_fix

def mkexp(gates):
    td = Path(tempfile.mkdtemp(prefix="a02_"))
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, **x} for n, x in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True)
    return Experiment(p)

if not hasattr(asyncio, "eager_task_factory"):
    print(f"no finding: asyncio.eager_task_factory does not exist on {sys.version.split()[0]} (3.12+ only)")
    sys.exit(0)

exp = mkexp({"A": {"exercises": ["a02_fix:f"]}, "B": {"exercises": ["a02_fix:g"]}})

def harness(eager):
    async def job():
        a02_fix.g()
        await asyncio.sleep(0)

    async def gate_a():
        a02_fix.f()
        # A's own work fans out; each child opens its OWN section, as the spec's remedy says
        await asyncio.gather(*(cov.run_async("B", job) for _ in range(3)))

    async def main():
        if eager:
            asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
        await cov.run_async("A", gate_a)

    raised = None
    with coverage_trace(exp) as cov:
        try:
            asyncio.run(main())
        except GateSpecError as e:
            raised = str(e)[:120]
    rec = cov.record()
    try:
        v = exp.score({"m": 1.0, "coverage_trace": rec})
        out = f"{v.verdict} {v.coverage}"
    except GateSpecError as e:
        out = f"REFUSED {str(e)[:130]}"
    return out, raised

default, r1 = harness(False)
eager, r2 = harness(True)
print(f"  default task factory: {default} (raised in harness: {r1})")
print(f"  eager_task_factory:   {eager} (raised in harness: {r2})")
if default.startswith("PASS") and "NESTED_SECTION" in eager:
    print("FINDING-REPRODUCED: with eager_task_factory a child task's own run_async section, created "
          "inside another section, refuses NESTED_SECTION (whole trace); default factory PASSes")
else:
    print("no finding: eager children open their own sections without refusal")
