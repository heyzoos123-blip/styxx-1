from rtlib import *
import subprocess, types, sys
import impl_new
from legacy import impl_old
print("same object?", impl_new.score_null is impl_old.score_null,
      "| code equal?", impl_new.score_null.__code__ == impl_old.score_null.__code__)
# declared: the NEW implementation. harness honestly runs only the vendored OLD copy.
e = exp(spec(G={"exercises": ["impl_new:score_null"]}))
with coverage_trace(e) as cov:
    with cov.section("G"):
        impl_old.score_null([1, 2, 3])
print("vendored copy:", score(e, cov.record()))

# The repo's own pattern (run_protocol_v5.py::_pinned_v4): a pinned copy exec'd from git.
src = subprocess.run(["git", "show", "HEAD:styxx/protocol.py"], cwd="/home/user/styxx-1",
                     capture_output=True, check=True).stdout
pinned = types.ModuleType("protocol_pinned"); pinned.__file__ = "git:HEAD:styxx/protocol.py"
sys.modules["protocol_pinned"] = pinned
exec(compile(src, pinned.__file__, "exec"), pinned.__dict__)
e = exp(spec(G={"exercises": ["styxx.protocol:Experiment._check_coverage",
                              "styxx.protocol:_resolve_target"]}))
with coverage_trace(e) as cov:
    with cov.section("G"):
        # only the PINNED copy runs; the live styxx.protocol functions are never called here
        pe = pinned.Experiment(e.prereg)
        try: pe._check_coverage("G", {"coverage_trace": {}})
        except Exception: pass
        pinned._resolve_target("impl_new:score_null")
print("pinned copy of styxx.protocol:", score(e, cov.record()))
