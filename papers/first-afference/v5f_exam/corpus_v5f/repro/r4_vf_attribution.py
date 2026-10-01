"""round4/verify/ (the verifiers' repros of the attribution findings), rewritten:
call-tracing-credits-trace-callback-code/own_repro.py: a settrace callback that, at the section body's call event,
runs the declared target through sys.call_tracing (CT) or calls it directly (PLAIN), declared section 'S';
eager-task-child-section-nested-refusal/repro.py: c1 create_task of the child's own run_async B inside run_async
A, c2 the same in a TaskGroup, c3 a child that yields once before opening its section, c4 the V19 shape (a loop
inside cov.run A gathering two run_async B children), each with the default and the eager task factory (3.12+)."""
import asyncio, sys


def main(api):
    out = {}
    vt = api.fixture("rp_vf_ct", "def target(n):\n    return n * 2\n")
    e = api.exp({"G": ["rp_vf_ct:target"]}, sections={"G": "S"}, value=0)

    def section_body(k):
        total = 0
        for i in range(k):
            total += i
        return total
    for arm, use_ct in (("CT", True), ("PLAIN", False)):
        fired = []

        def tr(frame, event, arg):
            if event == "call" and frame.f_code is section_body.__code__ and not fired:
                fired.append(1)
                if use_ct:
                    sys.call_tracing(vt.target, (3,))
                else:
                    vt.target(3)
            return None

        def run(c):
            old = sys.gettrace()
            sys.settrace(tr)
            try:
                return c.run("S", section_body, 4)
            finally:
                sys.settrace(old)
        out[f"call_tracing_{arm}"] = api.trace(e, run)
        out[f"call_tracing_{arm}_fired"] = len(fired)
    vf = api.fixture("rp_vf_eager", "def f():\n    return 1\n\ndef g():\n    return 2\n")
    EXP = api.exp({"A": ["rp_vf_eager:f"], "B": ["rp_vf_eager:g"]})

    async def job():
        vf.g()

    def eager_on(eager):
        if eager:
            asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)

    def c1(eager):
        def drv(cov):
            async def a_body():
                vf.f()
                await asyncio.create_task(cov.run_async("B", job))

            async def amain():
                eager_on(eager)
                await cov.run_async("A", a_body)
            asyncio.run(amain())
        return drv

    def c2(eager):
        def drv(cov):
            async def a_body():
                vf.f()
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(cov.run_async("B", job))

            async def amain():
                eager_on(eager)
                await cov.run_async("A", a_body)
            asyncio.run(amain())
        return drv

    def c3(eager):
        def drv(cov):
            async def child():
                await asyncio.sleep(0)
                await cov.run_async("B", job)

            async def a_body():
                vf.f()
                await asyncio.create_task(child())

            async def amain():
                eager_on(eager)
                await cov.run_async("A", a_body)
            asyncio.run(amain())
        return drv

    def c4(eager):
        def drv(cov):
            def a():
                vf.f()

                async def amain():
                    eager_on(eager)
                    await asyncio.gather(cov.run_async("B", job), cov.run_async("B", job))
                asyncio.run(amain())
            cov.run("A", a)
        return drv
    for name, c in (("c1", c1), ("c2", c2), ("c3", c3), ("c4", c4)):
        for eager in (False, True):
            if eager and not hasattr(asyncio, "eager_task_factory"):
                out[f"eager_{name}_True"] = "absent"
                continue
            out[f"eager_{name}_{eager}"] = api.trace(EXP, c(eager))
    return out
