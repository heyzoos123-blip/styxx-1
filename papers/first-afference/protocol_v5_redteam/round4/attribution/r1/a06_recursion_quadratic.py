"""NOTE (cost disclosure): the hook walks the WHOLE f_back chain (to the root or the cut) on every
hit, so a declared RECURSIVE target costs O(depth) per hit and O(depth^2) per top-level call. The
spec's cost table gives the walk only "per hit at depth 30: about 3-5 us". Doubling the recursion
depth roughly quadruples the traced time."""
import json, subprocess, sys, tempfile, time, threading
from pathlib import Path
sys.path.insert(0, "/home/user/styxx-1")
from styxx.protocol import Experiment, coverage_trace
FIX = Path(tempfile.mkdtemp(prefix="a06fx_"))
(FIX / "a06_fix.py").write_text("def depth(n):\n    return 0 if n == 0 else 1 + depth(n - 1)\n")
sys.path.insert(0, str(FIX)); import a06_fix
td = Path(tempfile.mkdtemp(prefix="a06_"))
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["a06_fix:depth"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "S"}
p = td / "PREREG_case.md"; p.write_text("# c\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for c in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=a@b", "-c",
          "user.name=a", "-c", "commit.gpgsign=false", "commit", "-qm", "c"]):
    subprocess.run(c, cwd=td, check=True)
exp = Experiment(p)
sys.setrecursionlimit(100000)
threading.stack_size(256 * 1024 * 1024)
res = {}
def main():
    for n in (2000, 4000, 8000):
        t0 = time.perf_counter(); a06_fix.depth(n); base = time.perf_counter() - t0
        with coverage_trace(exp) as cov:
            t0 = time.perf_counter(); cov.run("G", a06_fix.depth, n); tr = time.perf_counter() - t0
        res[n] = (base, tr)
        print(f"  depth {n}: untraced {base*1e3:.2f} ms, traced {tr*1e3:.0f} ms ({tr/base:.0f}x)")
t = threading.Thread(target=main); t.start(); t.join()
growth = res[8000][1] / res[2000][1]
print(f"  traced time x{growth:.1f} for x4 depth (linear would be x4, quadratic x16)")
if growth > 9:
    print(f"FINDING-REPRODUCED: per-hit f_back walk makes a declared recursive target quadratic in "
          f"depth ({res[8000][1]:.1f}s at depth 8000 vs {res[8000][0]*1e3:.1f} ms untraced)")
else:
    print("no finding: traced cost grows about linearly with recursion depth")
