from rtlib import *
import subprocess, types, sys
src = subprocess.run(["git","show","98a5c368:styxx/protocol.py"], cwd="/home/user/styxx-1", capture_output=True, check=True).stdout
v4 = types.ModuleType("v4p"); sys.modules["v4p"] = v4; exec(compile(src, "v4", "exec"), v4.__dict__)
e = exp(spec(G={}))
for label, E in (("v4", v4.Experiment), ("v5", Experiment)):
    x = E(e.prereg)
    try: print(label, "check_metrics(list):", x.check_metrics([1]))
    except Exception as ex: print(label, "check_metrics(list): ESCAPED", type(ex).__name__)
