"""An old trace re-scored against an edited prereg that ADDED a target: both STALE and TARGET_SET hold."""
import copy
import b6lib as W
mod = W.module("b6st_fx", "def f():\n    return 1\ndef g():\n    return 2\n")
old = W.experiment({"G": {"exercises": ["b6st_fx:f"]}}, tag="v1")
with W.coverage_trace(old) as cov:
    cov.run("G", mod.f)
rec = cov.record()
new = W.experiment({"G": {"exercises": ["b6st_fx:f", "b6st_fx:g"]}}, tag="v1")   # target added
only_stale = W.experiment({"G": {"exercises": ["b6st_fx:f"]}}, tag="v2")          # same targets, new block
forged = copy.deepcopy(rec); forged["targets"]["b6st_fx:g"] = "x:1"                # same block, extra target
out = {"old_trace_vs_old_prereg": W.score(old, rec),
       "BOTH_old_trace_vs_edited_prereg": W.score(new, rec),
       "control_only_stale": W.score(only_stale, rec),
       "control_only_target_set": W.score(old, forged)}
cm = new.check_metrics({"m": 1.0, "coverage_trace": rec})
out["check_metrics_on_edited"] = {k: (v.get("note") or "")[:40] for k, v in cm.items() if isinstance(v, dict) and not v.get("usable", True)}
W.emit(out)
