"""Run one witness under the original package and under the mutant, each in its own process."""
import json, os, subprocess, sys
B = "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify-exam"
key = sys.argv[1]
wit = sys.argv[2] if len(sys.argv) > 2 else f"{B}/{key}/witness.py"
roots = {"original": "/home/user/styxx-1", "mutant": f"{B}/{key}"}
out = {}
for label, root in roots.items():
    env = dict(os.environ, B6_ROOT=root, PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=B)                     # only for b6lib; styxx comes from B6_ROOT (first)
    p = subprocess.run([sys.executable, wit], env=env, cwd="/tmp", capture_output=True, text=True,
                       timeout=60)
    lines = [l for l in p.stdout.splitlines() if l.startswith("WITNESS ")]
    if not lines:
        out[label] = {"crash": (p.stdout + p.stderr)[-800:], "rc": p.returncode}
    else:
        out[label] = [json.loads(l[8:]) for l in lines]
        assert all(x["impl"].startswith(root) for x in out[label]), (label, root)
    print(f"--- {label} (rc={p.returncode})")
    for x in (out[label] if isinstance(out[label], list) else [out[label]]):
        x = dict(x); x.pop("impl", None)
        print(json.dumps(x, indent=1, sort_keys=True)[:3000])
strip = lambda L: [{k: v for k, v in x.items() if k != "impl"} for x in L] if isinstance(L, list) else L
print("SEPARATES:", strip(out["original"]) != strip(out["mutant"]))
