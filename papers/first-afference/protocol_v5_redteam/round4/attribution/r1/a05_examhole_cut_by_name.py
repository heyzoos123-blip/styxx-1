"""EXAM_HOLE: the dispatch cut's IDENTITY is not pinned. Mutant: the hook's cut test
`f.f_code is stop` (identity with asyncio.events.Handle._run.__code__) becomes a NAME test,
`f.f_code.co_name == "_run"`. The frozen exam (--smoke --full-battery --mutation-mode) passes the
mutant: no case puts a non-asyncio frame named `_run` between an anchor and a target. On a
harness whose own helper is called `_run` (the exam's own fixture module defines one), the
mutant refuses NOT_EXERCISED (counted as 'dispatched') while the original PASSes."""
import json, os, shutil, subprocess, sys, tempfile, textwrap
from pathlib import Path
ROOT = Path("/home/user/styxx-1")
HERE = Path(__file__).resolve().parent
OLD = "        if f.f_code is stop:\n            cut = True"
NEW = '        if f.f_code.co_name == "_run":\n            cut = True'

src = (ROOT / "styxx" / "protocol.py").read_text()
assert src.count(OLD) == 1
mdir = Path(tempfile.mkdtemp(prefix="a05mut_", dir=str(HERE)))
shutil.copytree(ROOT / "styxx", mdir / "styxx", ignore=shutil.ignore_patterns("__pycache__"))
(mdir / "styxx" / "protocol.py").write_text(src.replace(OLD, NEW))

HARNESS = textwrap.dedent(r'''
    import json, subprocess, sys, tempfile
    from pathlib import Path
    sys.path.insert(0, sys.argv[1])
    import styxx.protocol as P
    from styxx.protocol import Experiment, GateSpecError, coverage_trace
    fix = Path(tempfile.mkdtemp())
    (fix / "a05_fix.py").write_text("def f(): return 1\n")
    sys.path.insert(0, str(fix))
    import a05_fix
    td = Path(tempfile.mkdtemp())
    spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["a05_fix:f"]}},
            "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "S"}
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=a@b", "-c",
              "user.name=a", "-c", "commit.gpgsign=false", "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True)
    exp = Experiment(p)

    def _run(cfg):                 # an ordinary harness helper that happens to be named _run
        return a05_fix.f() + cfg

    with coverage_trace(exp) as cov:
        cov.run("G", _run, 1)
    try:
        v = exp.score({"m": 1.0, "coverage_trace": cov.record()})
        print(f"{v.verdict} {v.coverage}")
    except GateSpecError as e:
        print("REFUSED " + str(e)[:150])
''')
hf = mdir / "harness.py"
hf.write_text(HARNESS)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
orig = subprocess.run([sys.executable, str(hf), str(ROOT)], capture_output=True, text=True, env=env).stdout.strip()
mut = subprocess.run([sys.executable, str(hf), str(mdir)], capture_output=True, text=True, env=env).stdout.strip()
print("  original:", orig)
print("  mutant:  ", mut)

out = mdir / "result.json"
env2 = dict(env, STYXX_V5_IMPORT_ROOT=str(mdir), STYXX_V5_RESULT_OUT=str(out))
p = subprocess.run([sys.executable, str(ROOT / "papers/first-afference/run_protocol_v5e.py"),
                    "--smoke", "--full-battery", "--mutation-mode"], cwd=ROOT, env=env2,
                   capture_output=True, text=True, timeout=50)
survived = False
if p.returncode == 0 and out.exists():
    r = json.loads(out.read_text())
    fv = [k for k, v in r.get("violation_cases", {}).items() if not v.get("ok")]
    fg = [k for k, v in r.get("valid_cases", {}).items() if not v.get("ok")]
    survived = not fv and not fg and r.get("p1_retro_exact") == 1.0 and not r.get("n_crashes")
    print(f"  exam vs mutant: exit 0, failed violations {fv}, failed valids {fg}, "
          f"retro {r.get('p1_retro_exact')}, crashes {r.get('n_crashes')}")
else:
    print(f"  exam vs mutant: exit {p.returncode} {p.stderr[-200:]}")
shutil.rmtree(mdir, ignore_errors=True)
if survived and orig.startswith("PASS") and mut.startswith("REFUSED [V5:NOT_EXERCISED]"):
    print("FINDING-REPRODUCED: name-based dispatch cut mutant passes the frozen exam and falsely "
          "refuses a harness whose helper is named _run (original PASS)")
else:
    print("no finding: the exam detects the name-based cut, or the harness does not separate them")
