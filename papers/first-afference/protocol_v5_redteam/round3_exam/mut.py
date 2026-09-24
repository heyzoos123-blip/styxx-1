import subprocess, sys, json, os, re
R = "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt6/repo"
P = f"{R}/styxx/protocol.py"
OUT = "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt6/out"
from mutants_r3 import MUTANTS
orig = open(P).read()
only = sys.argv[1:]
for name, reps in MUTANTS.items():
    if only and name not in only: continue
    src = orig
    for old, new in reps:
        n = src.count(old)
        assert n == 1, (name, old, n)
        src = src.replace(old, new)
    open(P, "w").write(src)
    try:
        try:
            p = subprocess.run([sys.executable, "papers/first-afference/run_protocol_v5d.py", "--smoke", "--full-battery"],
                               cwd=R, env=dict(os.environ, PYTHONPATH=R), capture_output=True, text=True, timeout=180)
            out = p.stdout + p.stderr; rc = p.returncode
        except subprocess.TimeoutExpired as e:
            out = "TIMEOUT"; rc = "timeout"
    finally:
        open(P, "w").write(orig)
    open(f"{OUT}/{name}.txt", "w").write(out)
    fails = [l.strip()[:170] for l in out.splitlines() if "FAILED" in l]
    retro = [l for l in out.splitlines() if l.startswith("P1 retro")]
    retro_exact = bool(retro) and "exact=True" in retro[0]
    head = [l for l in out.splitlines() if l.startswith(("violations", "valid scored"))]
    detected = rc != 0 or bool(fails) or not retro_exact or "VERDICT" not in out
    print(f"### {name}: {'DETECTED' if detected else 'SURVIVES'} rc={rc} retro_exact={retro_exact} {head}")
    for f in fails: print("    ", f)
    if rc != 0 or "VERDICT" not in out: print("    TAIL:", out[-400:].replace("\n", " | "))
    sys.stdout.flush()
