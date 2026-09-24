from rtlib import *
import subprocess, types, sys
src = subprocess.run(["git","show","98a5c368:styxx/protocol.py"], cwd="/home/user/styxx-1", capture_output=True, check=True).stdout
v4 = types.ModuleType("v4p"); sys.modules["v4p"] = v4; exec(compile(src, "v4", "exec"), v4.__dict__)
for extra in ({"section": "see prose section 3.2"}, {"exercises": "the reachable() path"},
              {"exercises": ["reachable() on the null"]}):
    p = commit(spec(G=extra))
    for label, E in (("v4", v4.Experiment), ("v5", Experiment)):
        try: out = E(p).score({"m": 1.0}).verdict
        except Exception as ex: out = f"RAISED {type(ex).__name__}: {str(ex)[:70]}"
        print(extra, label, "->", out)
