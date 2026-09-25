"""Section B (coroutine) opens on worker thread W and suspends; it is resumed to completion on the
main thread INSIDE section A (a THREAD_HOP close), after which A calls its own target f."""
import sys, threading
import b6lib as W
mod = W.module("b6hop_fx", "def f():\n    return 1\ndef g():\n    return 2\n")
exp = W.experiment({"A": {"exercises": ["b6hop_fx:f"]}, "B": {"exercises": ["b6hop_fx:g"]}}, tag="hop")

class Once:
    def __await__(self):
        yield

async def bbody():
    mod.g()                                     # runs on W, credited to B
    await Once()                                # suspend; resumed later on main
    return "b-done"

probe = {}
with W.coverage_trace(exp) as cov:
    coro = cov.run_async("B", bbody)
    t = threading.Thread(target=lambda: coro.send(None))
    t.start(); t.join()
    def abody():
        probe["hook_before_resume"] = sys.getprofile() is W.P._hook
        try:
            coro.send(None)
        except StopIteration as e:
            probe["b_result"] = e.value
        probe["hook_after_hop_close"] = sys.getprofile() is W.P._hook
        return mod.f()
    cov.run("A", abody)
rec = cov.record()
notes = {s: [n[:20] for o in ops for n in o["notes"]] for s, ops in rec["sections"].items()}
calls = {s: [o["calls"] for o in ops] for s, ops in rec["sections"].items()}
W.emit({"probe": probe, "notes": notes, "calls": calls, "score": W.score(exp, rec),
        "state_at_end": W.globals_state()})
