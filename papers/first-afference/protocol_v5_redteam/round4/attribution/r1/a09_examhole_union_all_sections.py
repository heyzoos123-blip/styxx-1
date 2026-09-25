"""EXAM_HOLE (credit to the wrong section is never tested). Mutant of Experiment._check_coverage:
the union of `calls` is taken over the openings of EVERY section of the trace instead of the
gate's own section (SECTION_ABSENT still checks the gate's section). The frozen exam
(--smoke --full-battery --mutation-mode) passes it: every exam case that has two sections
declares DISJOINT targets for them, or leaves the target uncredited everywhere, so a call
credited to section B never has the chance to satisfy gate A. On a two-gate harness where
section A runs only g and section B runs only f (A declares f, B declares g), the original
refuses both gates NOT_EXERCISED and the mutant scores PASS -- a false PASS."""
import json, os, shutil, subprocess, sys, tempfile, textwrap
from pathlib import Path
ROOT = Path("/home/user/styxx-1")
HERE = Path(__file__).resolve().parent
OLD = ('        for o in openings:\n            for t, n in o["calls"].items():\n'
       '                union[t] = union.get(t, 0) + n')
NEW = ('        for o in [o for ops in tr["sections"].values() for o in ops]:\n'
       '            for t, n in o["calls"].items():\n'
       '                union[t] = union.get(t, 0) + n')
src = (ROOT / "styxx" / "protocol.py").read_text()
assert src.count(OLD) == 1
mdir = Path(tempfile.mkdtemp(prefix="a09mut_", dir=str(HERE)))
shutil.copytree(ROOT / "styxx", mdir / "styxx", ignore=shutil.ignore_patterns("__pycache__"))
(mdir / "styxx" / "protocol.py").write_text(src.replace(OLD, NEW))

HARNESS = textwrap.dedent(r'''
    import json, subprocess, sys, tempfile
    from pathlib import Path
    sys.path.insert(0, sys.argv[1])
    from styxx.protocol import Experiment, GateSpecError, coverage_trace
    fix = Path(tempfile.mkdtemp())
    (fix / "a09_fix.py").write_text("def f(): return 1\ndef g(): return 2\n")
    sys.path.insert(0, str(fix))
    import a09_fix
    td = Path(tempfile.mkdtemp())
    gates = {"A": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["a09_fix:f"]},
             "B": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["a09_fix:g"]}}
    spec = {"gates": gates, "outcomes": [{"when": {"A": True, "B": True}, "verdict": "PASS"},
                                         {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=a@b", "-c",
              "user.name=a", "-c", "commit.gpgsign=false", "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True)
    exp = Experiment(p)
    with coverage_trace(exp) as cov:
        cov.run("A", a09_fix.g)      # gate A's section never runs f
        cov.run("B", a09_fix.f)      # gate B's section never runs g
    try:
        v = exp.score({"m": 1.0, "coverage_trace": cov.record()})
        print(f"{v.verdict} {v.coverage}")
    except GateSpecError as e:
        print("REFUSED " + str(e)[:110])
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
if survived and orig.startswith("REFUSED [V5:NOT_EXERCISED]") and mut.startswith("PASS"):
    print("FINDING-REPRODUCED: scoring each gate on the union over ALL sections passes the frozen "
          "exam and gives a false PASS when the target ran only in another gate's section")
else:
    print("no finding: the exam detects the all-sections union, or the harness does not separate them")
