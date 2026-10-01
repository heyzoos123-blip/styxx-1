"""Revision 13 follow-ups: the witness shapes the exam author proposes for rows SM1 finds UNWITNESSED, each run on
unpatched ref_v5f.py and on the row's patch (the patch text as the SM1 catalog row carries it), one fresh process
per (script, mode, interpreter). The scripts import ref (or its patched copy) as styxx.protocol from a temp dir.
Usage: python run_all.py OUT.json"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = [("h15_run_async_declared.py", ["ref", "h15"], []),
        ("h18_equal_globals_clone.py", ["ref", "h18"], ["h18"]),
        ("census_p04_s04_s05_s08.py", ["ref", "p04", "s04", "s05", "s08"], []),
        ("census_e03_e06_ks_lost.py", ["ref", "e03", "e06", "pl"], []),
        ("r62_v5_state_and_fork.py", ["ref", "R62_conditions_M10", "R62_scope_M10", "R62_scope_M9", "R62_deletion_M9"], [])]
out = {}
for py in ("/usr/bin/python3.12", "/usr/bin/python3.13"):
    for script, modes, extra in RUNS:
        for m in modes:
            r = subprocess.run([py, "-W", "ignore", os.path.join(HERE, script), m, *extra], capture_output=True, text=True,
                               timeout=300, cwd=HERE)
            out.setdefault(py.rsplit("/", 1)[1], {}).setdefault(script, {})[m] = (r.stdout.strip() or r.stderr.strip()[-400:])
json.dump(out, open(sys.argv[1], "w"), indent=1)
print("written", sys.argv[1])
