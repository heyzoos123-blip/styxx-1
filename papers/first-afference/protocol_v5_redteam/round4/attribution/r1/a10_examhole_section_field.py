"""EXAM_HOLE (the declared `section` field is never exercised at score time). Mutant of
Experiment._check_coverage: `openings = tr["sections"].get(c["section"])` becomes
`tr["sections"].get(name)` -- the gate's NAME instead of its declared section. The frozen exam
(--smoke --full-battery --mutation-mode) passes it: no exam case, and no gate of the v5e prereg
itself, declares a `section` that differs from the gate name (only X06/X07 use the key, as parse
violations). Two harnesses separate them:
  (1) two gates sharing one declared section (the feature the key exists for): original PASS,
      mutant SECTION_ABSENT (false refusal);
  (2) gates X (exercises f, section "Y") and Y (exercises g, section "X"), harness opens each
      gate's work under the gate's NAME: original NOT_EXERCISED, mutant PASS (false PASS)."""
import json, os, shutil, subprocess, sys, tempfile, textwrap
from pathlib import Path
ROOT = Path("/home/user/styxx-1")
HERE = Path(__file__).resolve().parent
OLD = '        openings = tr["sections"].get(c["section"])'
NEW = '        openings = tr["sections"].get(name)'
src = (ROOT / "styxx" / "protocol.py").read_text()
assert src.count(OLD) == 1
mdir = Path(tempfile.mkdtemp(prefix="a10mut_", dir=str(HERE)))
shutil.copytree(ROOT / "styxx", mdir / "styxx", ignore=shutil.ignore_patterns("__pycache__"))
(mdir / "styxx" / "protocol.py").write_text(src.replace(OLD, NEW))

HARNESS = textwrap.dedent(r'''
    import json, subprocess, sys, tempfile
    from pathlib import Path
    sys.path.insert(0, sys.argv[1])
    from styxx.protocol import Experiment, GateSpecError, coverage_trace
    fix = Path(tempfile.mkdtemp())
    (fix / "a10_fix.py").write_text("def f(): return 1\ndef g(): return 2\n")
    sys.path.insert(0, str(fix))
    import a10_fix
    def mk(gates):
        td = Path(tempfile.mkdtemp())
        g = {n: {"metric": "m", "op": ">=", "value": 0.5, **x} for n, x in gates.items()}
        spec = {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"},
                                         {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
        p = td / "PREREG_case.md"
        p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n")
        for c in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=a@b",
                  "-c", "user.name=a", "-c", "commit.gpgsign=false", "commit", "-qm", "c"]):
            subprocess.run(c, cwd=td, check=True)
        return Experiment(p)
    def score(exp, rec):
        try:
            v = exp.score({"m": 1.0, "coverage_trace": rec})
            return f"{v.verdict}"
        except GateSpecError as e:
            return "REFUSED " + str(e)[:24]
    e1 = mk({"G_fast": {"exercises": ["a10_fix:f"], "section": "run"},
             "G_slow": {"exercises": ["a10_fix:g"], "section": "run"}})
    with coverage_trace(e1) as cov:
        cov.run("run", lambda: (a10_fix.f(), a10_fix.g()))
    r1 = score(e1, cov.record())
    e2 = mk({"X": {"exercises": ["a10_fix:f"], "section": "Y"},
             "Y": {"exercises": ["a10_fix:g"], "section": "X"}})
    with coverage_trace(e2) as cov:
        cov.run("X", a10_fix.f)      # X's work opened under the gate NAME, not its section "Y"
        cov.run("Y", a10_fix.g)
    r2 = score(e2, cov.record())
    print(json.dumps([r1, r2]))
''')
hf = mdir / "harness.py"
hf.write_text(HARNESS)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
o = json.loads(subprocess.run([sys.executable, str(hf), str(ROOT)], capture_output=True, text=True, env=env).stdout)
m = json.loads(subprocess.run([sys.executable, str(hf), str(mdir)], capture_output=True, text=True, env=env).stdout)
print(f"  (1) shared section: original {o[0]!r}, mutant {m[0]!r}")
print(f"  (2) swapped sections: original {o[1]!r}, mutant {m[1]!r}")
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
if survived and o[0] == "PASS" and m[0].startswith("REFUSED [V5:SECTION_ABSENT]") \
        and o[1].startswith("REFUSED [V5:NOT_EXERCISED]") and m[1] == "PASS":
    print("FINDING-REPRODUCED: a mutant that ignores the declared `section` passes the frozen exam; "
          "it falsely refuses a shared-section harness and falsely PASSes a swapped-section one")
else:
    print("no finding: the exam detects the mutant, or the harnesses do not separate it")
