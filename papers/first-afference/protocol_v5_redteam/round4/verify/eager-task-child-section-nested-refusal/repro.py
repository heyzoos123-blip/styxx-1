"""Independent repro: eager child task that opens its own run_async section from inside a run_async section."""
import asyncio, json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/home/user/styxx-1")
from styxx.protocol import Experiment, GateSpecError, coverage_trace

mod_dir = Path(tempfile.mkdtemp(prefix="vfx_"))
(mod_dir / "vfx_mod.py").write_text("def f():\n    return 1\n\ndef g():\n    return 2\n")
sys.path.insert(0, str(mod_dir))
import vfx_mod

def make_exp():
    d = Path(tempfile.mkdtemp(prefix="vexp_"))
    gates = {"A": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["vfx_mod:f"]},
             "B": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["vfx_mod:g"]}}
    spec = {"gates": gates, "outcomes": [{"when": {"A": True, "B": True}, "verdict": "PASS"},
                                         {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = d / "PREREG_v.md"
    p.write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    env = ["-c", "user.email=v@v", "-c", "user.name=v", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", *env, "commit", "-qm", "x"], cwd=d, check=True)
    return Experiment(p)

EXP = make_exp()

async def job():
    vfx_mod.g()

def eager_on():
    if hasattr(asyncio, "eager_task_factory"):
        asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
        return True
    return False

def outcome(driver):
    raised = None
    with coverage_trace(EXP) as cov:
        try:
            driver(cov)
        except Exception as e:  # noqa
            raised = f"{type(e).__name__}: {str(e)[:70]}"
    rec = cov.record()
    try:
        v = EXP.score({"m": 1.0, "coverage_trace": rec})
        s = f"{v.verdict} {v.coverage}"
    except GateSpecError as e:
        s = f"REFUSED {str(e)[:60]}"
    return s, raised, rec["problems"][:1]

# case 1: create_task inside run_async(A); child's coroutine IS cov.run_async("B", job)
def c1(eager):
    def drv(cov):
        async def a_body():
            vfx_mod.f()
            await asyncio.create_task(cov.run_async("B", job))
        async def main():
            if eager: eager_on()
            await cov.run_async("A", a_body)
        asyncio.run(main())
    return drv

# case 2: TaskGroup
def c2(eager):
    def drv(cov):
        async def a_body():
            vfx_mod.f()
            async with asyncio.TaskGroup() as tg:
                tg.create_task(cov.run_async("B", job))
        async def main():
            if eager: eager_on()
            await cov.run_async("A", a_body)
        asyncio.run(main())
    return drv

# case 3: eager, child yields once before opening its own section -> escapes creator's stack
def c3(eager):
    def drv(cov):
        async def child():
            await asyncio.sleep(0)
            await cov.run_async("B", job)
        async def a_body():
            vfx_mod.f()
            await asyncio.create_task(child())
        async def main():
            if eager: eager_on()
            await cov.run_async("A", a_body)
        asyncio.run(main())
    return drv

# case 4: V19 shape (loop inside cov.run(A)) with eager factory
def c4(eager):
    def drv(cov):
        def a():
            vfx_mod.f()
            async def main():
                if eager: eager_on()
                await asyncio.gather(cov.run_async("B", job), cov.run_async("B", job))
            asyncio.run(main())
        cov.run("A", a)
    return drv

print(sys.version.split()[0], "eager_task_factory available:", hasattr(asyncio, "eager_task_factory"))
for name, c in [("c1 create_task", c1), ("c2 TaskGroup", c2), ("c3 child yields first", c3), ("c4 V19-shape", c4)]:
    if name.startswith("c2") and not hasattr(asyncio, "TaskGroup"):
        continue
    for eager in (False, True):
        if eager and not hasattr(asyncio, "eager_task_factory"):
            continue
        s, r, p = outcome(c(eager))
        print(f"{name:24s} eager={eager!s:5s} -> {s} | raised={r} | problems={p and p[0][:40]}")
