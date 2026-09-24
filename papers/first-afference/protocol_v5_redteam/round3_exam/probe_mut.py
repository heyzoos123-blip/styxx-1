import sys, os, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mutants_r3 import MUTANTS
B = os.path.dirname(os.path.abspath(__file__))
orig = open(f"{B}/repo2/styxx/protocol.py").read()
for name in sys.argv[1:]:
    d = f"{B}/pm/{name}"
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(f"{B}/repo2/styxx", f"{d}/styxx", ignore=shutil.ignore_patterns("__pycache__"))
    src = orig
    for o, n in MUTANTS[name]:
        assert src.count(o) == 1; src = src.replace(o, n)
    open(f"{d}/styxx/protocol.py", "w").write(src)
    p = subprocess.run([sys.executable, f"{B}/probe/probes.py"], env=dict(os.environ, PYTHONPATH=d),
                       capture_output=True, text=True, timeout=300)
    print(f"=== {name}")
    for l in (p.stdout + p.stderr[-600:]).splitlines():
        if "BROKEN" in l or "Error" in l: print("  ", l[:200])
    shutil.rmtree(d)
