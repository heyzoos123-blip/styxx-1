"""Independent repro for 'recursion-walk-quadratic' (NOTE, cost disclosure).

Separates three things the claim bundles together:
  A. per-hit walk cost as a function of stack depth above the cut, for a NON-recursive declared
     target called at a fixed depth (padding frames come from an UNDECLARED helper). The spec's
     cost row is "f_back walk, per hit at depth 30: about 3-5 us".
  B. a RECURSIVE declared target, traced vs. a control that runs the identical recursion through an
     undeclared twin inside the same open section (hook installed, same events, no walk).
  C. correctness: the recursive target is scored PASS with calls == n+1 (no false verdict).
"""
import json, subprocess, sys, tempfile, threading, time
from pathlib import Path

sys.path.insert(0, "/home/user/styxx-1")
from styxx.protocol import Experiment, coverage_trace

FIX = Path(tempfile.mkdtemp(prefix="vrq_fx_"))
(FIX / "vrq_fix.py").write_text(
    "def rec(n):\n    return 0 if n == 0 else 1 + rec(n - 1)\n"          # declared, recursive
    "def twin(n):\n    return 0 if n == 0 else 1 + twin(n - 1)\n"        # undeclared control
    "def leaf():\n    return 1\n"                                        # declared, non-recursive
    "def leaf2():\n    return 1\n"                                       # undeclared twin of leaf
    "def pad(d, k):\n"                                                   # undeclared padding
    "    if d == 0:\n"
    "        s = 0\n"
    "        for _ in range(k):\n"
    "            s += leaf()\n"
    "        return s\n"
    "    return pad(d - 1, k)\n"
    "def pad_twin(d, k):\n"                                              # undeclared, no hits
    "    if d == 0:\n"
    "        s = 0\n"
    "        for _ in range(k):\n"
    "            s += leaf2()\n"
    "        return s\n"
    "    return pad_twin(d - 1, k)\n")
sys.path.insert(0, str(FIX))
import vrq_fix

td = Path(tempfile.mkdtemp(prefix="vrq_"))
spec = {"gates": {
            "G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["vrq_fix:rec"]},
            "H": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["vrq_fix:leaf"]}},
        "outcomes": [{"when": {"G": True, "H": True}, "verdict": "PASS"},
                     {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "S"}
p = td / "PREREG_case.md"
p.write_text("# c\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for c in (["git", "init", "-q"], ["git", "add", "-A"],
          ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
           "commit", "-qm", "c"]):
    subprocess.run(c, cwd=td, check=True)
exp = Experiment(p)
sys.setrecursionlimit(100000)
threading.stack_size(256 * 1024 * 1024)
out = {"py": sys.version.split()[0]}


def main():
    K = 20000
    # ---- A: per-hit cost vs. depth (non-recursive target, K hits at depth d) ----
    per_hit = {}
    for d in (30, 300, 3000):
        with coverage_trace(exp) as cov:
            t0 = time.perf_counter(); cov.run("H", vrq_fix.pad, d, K); t_hit = time.perf_counter() - t0
            t0 = time.perf_counter(); cov.run("H", vrq_fix.pad_twin, d, K); t_ctl = time.perf_counter() - t0
        per_hit[d] = (t_hit - t_ctl) / K * 1e6
        print(f"  A depth~{d:5d}: walk cost per hit {per_hit[d]:7.2f} us  "
              f"(hits {t_hit*1e3:.0f} ms, no-hit control {t_ctl*1e3:.0f} ms)")
    out["per_hit_us"] = per_hit
    # ---- B/C: recursive declared target vs. undeclared twin, same open section ----
    rec = {}
    for n in (1000, 2000, 4000, 8000):
        t0 = time.perf_counter(); vrq_fix.rec(n); base = time.perf_counter() - t0
        with coverage_trace(exp) as cov:
            t0 = time.perf_counter(); cov.run("G", vrq_fix.twin, n); ctl = time.perf_counter() - t0
            t0 = time.perf_counter(); r = cov.run("G", vrq_fix.rec, n); tr = time.perf_counter() - t0
            cov.run("H", vrq_fix.leaf)
        trace = cov.record()
        calls = sum(o["calls"].get("vrq_fix:rec", 0) for o in trace["sections"]["G"])
        v = exp.score({"m": 1.0, "coverage_trace": trace}).verdict
        rec[n] = (base, ctl, tr, calls, v)
        print(f"  B n={n:5d}: untraced {base*1e3:6.2f} ms | hook-only twin {ctl*1e3:7.2f} ms | "
              f"declared rec {tr*1e3:7.0f} ms | calls={calls} (expect {n+1}) verdict={v} r={r}")
    out["rec"] = {str(k): v for k, v in rec.items()}


t = threading.Thread(target=main); t.start(); t.join()
ph = out["per_hit_us"]
lin = ph[3000] / ph[30]
g2 = out["rec"]["8000"][2] / out["rec"]["4000"][2]
g4 = out["rec"]["8000"][2] / out["rec"]["2000"][2]
hook_only_g4 = out["rec"]["8000"][1] / out["rec"]["2000"][1]
print(f"  per-hit walk cost ratio depth 3000/30 = x{lin:.0f} (depth ratio x100)")
print(f"  declared recursion: x{g2:.1f} for x2 depth, x{g4:.1f} for x4 depth; "
      f"hook-only twin x{hook_only_g4:.1f} for x4 depth")
ok = all(v[3] == int(k) + 1 and v[4] == "PASS" for k, v in out["rec"].items())
print(f"  correctness (calls == n+1 and PASS at every n): {ok}")
print("QUADRATIC" if g4 > 9 else "NOT-QUADRATIC")
Path(__file__).with_name(f"own_{out['py']}.json").write_text(json.dumps(out, indent=1))
