"""EXAM_HOLE: no exam case declares a target in a module whose type is a ModuleType subclass (a
module that set __class__ for module-level properties; on 3.10 also the LazyLoader recipe). A
mutant that takes the module step only when type(obj) is types.ModuleType passes the frozen exam.
Paired harness: a ModuleType-subclass module whose target is reached through its PEP 562
__getattr__. Original: PASS (V10's rule). Mutant: INSTANCE_PATH at entry."""
MUT_NAME = 'module step taken only for type(obj) is types.ModuleType'
SUBS = [('        if isinstance(obj, types.ModuleType):\n            if i > 0:', '        if type(obj) is types.ModuleType:\n            if i > 0:')]
EXPECT_ORIG = 'PASS'
HARNESS = 'import json, os, subprocess, sys, tempfile, textwrap, types\nfrom pathlib import Path\nsys.path.insert(0, os.environ["RT4_STYXX_ROOT"])\nimport styxx.protocol as P\nfrom styxx.protocol import Experiment, GateSpecError, coverage_trace\nassert Path(P.__file__).resolve().is_relative_to(Path(os.environ["RT4_STYXX_ROOT"]).resolve())\n_TMP = Path(tempfile.mkdtemp(prefix="rt4id_h_"))\nsys.path.insert(0, str(_TMP))\ndef write_mod(name, src):\n    (_TMP / f"{name}.py").write_text(textwrap.dedent(src), encoding="utf-8")\n    sys.modules.pop(name, None)\ndef make_exp(**gates):\n    d = Path(tempfile.mkdtemp(prefix="rt4id_repo_"))\n    g = {k: {"metric": "m", "op": ">=", "value": 0.5, **v} for k, v in gates.items()}\n    spec = {"gates": g, "outcomes": [{"when": {k: True for k in g}, "verdict": "PASS"},\n                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}\n    p = d / "PREREG_case.md"\n    p.write_text("# case\\n\\n```gates\\n" + json.dumps(spec) + "\\n```\\n", encoding="utf-8")\n    for c in (["git", "init", "-q"], ["git", "add", "-A"],\n              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",\n               "commit", "-qm", "c"]):\n        subprocess.run(c, cwd=d, check=True)\n    return Experiment(p)\ndef score(exp, rec, m=1.0):\n    try:\n        v = exp.score({"m": m, "coverage_trace": rec})\n        return f"PASS {v.coverage}"\n    except GateSpecError as e:\n        return f"REFUSED {str(e)[:120]}"\nimport importlib.util\n# a module that installs a ModuleType subclass (for a module-level property) and also has a\n# PEP 562 __getattr__ for a lazily created helper defined in the module\nwrite_mod("rt4_modsub", """\n    import sys, types\n    def _make_helper():\n        def helper(x=0):\n            return x + 1\n        return helper\n    def __getattr__(name):\n        if name == "helper":\n            fn = _make_helper()\n            globals()["helper"] = fn         # cached after the first access\n            return fn\n        raise AttributeError(name)\n    class _Mod(types.ModuleType):\n        @property\n        def version(self):\n            return "1.0"\n    sys.modules[__name__].__class__ = _Mod\n""")\nimport rt4_modsub\nexp = make_exp(G={"exercises": ["rt4_modsub:helper"]})\ntry:\n    with coverage_trace(exp) as cov:\n        cov.run("G", lambda: rt4_modsub.helper(1))\n    print(score(exp, cov.record()))\nexcept GateSpecError as e:\n    print("REFUSED_AT_ENTRY", str(e)[:120])\n'
# ---- EXAM_HOLE driver (self-contained) ----
# 1. builds the mutant (one exact text substitution in a COPY of styxx/, under a temp dir);
# 2. runs the frozen exam against it exactly as mutation_gate.run_exam does;
# 3. runs the paired harness (HARNESS below) against the original and against the mutant.
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
REPO = Path("/home/user/styxx-1")

def build_mutant():
    src = (REPO / "styxx" / "protocol.py").read_text(encoding="utf-8")
    for old, new in SUBS:
        assert src.count(old) == 1, "mutation anchor not unique"
        src = src.replace(old, new)
    root = Path(tempfile.mkdtemp(prefix="rt4id_mut_"))
    shutil.copytree(REPO / "styxx", root / "styxx", ignore=shutil.ignore_patterns("__pycache__"))
    (root / "styxx" / "protocol.py").write_text(src, encoding="utf-8")
    return root

def run_exam(root):
    out = root / "result.json"
    env = dict(os.environ, STYXX_V5_IMPORT_ROOT=str(root), STYXX_V5_RESULT_OUT=str(out),
               PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, str(REPO / "papers/first-afference/run_protocol_v5e.py"),
                        "--smoke", "--full-battery", "--mutation-mode"], cwd=REPO, env=env,
                       capture_output=True, text=True, timeout=300)
    if p.returncode != 0 or not out.exists():
        return False, f"exam exit {p.returncode}"
    r = json.loads(out.read_text())
    bad = {k: sorted(n for n, v in r.get(k, {}).items() if not v.get("ok"))
           for k in ("violation_cases", "valid_cases", "residual_cases")}
    det = any(bad.values()) or r.get("p1_retro_exact") != 1.0 or r.get("n_crashes")
    return (not det), f"failed={bad} retro={r.get('p1_retro_exact')} crashes={r.get('n_crashes')}"

def run_harness(root):
    env = dict(os.environ, RT4_STYXX_ROOT=str(root), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-c", HARNESS], env=env, capture_output=True, text=True,
                       timeout=60)
    return (p.stdout.strip().splitlines() or ["<no output> " + p.stderr[-300:]])[-1]

if __name__ == "__main__":
    mroot = build_mutant()
    survived, how = (True, "skipped") if "--no-exam" in sys.argv else run_exam(mroot)
    print("frozen exam vs mutant:", "PASSES (mutant survives)" if survived else "fails", how)
    orig = run_harness(REPO)
    mut = run_harness(mroot)
    print("paired harness, original:", orig)
    print("paired harness, mutant  :", mut)
    if survived and orig.startswith(EXPECT_ORIG) and not mut.startswith(EXPECT_ORIG):
        print(f"FINDING-REPRODUCED: EXAM_HOLE {MUT_NAME}: the frozen exam passes the mutant; on the "
              f"paired harness the original gives {orig[:60]!r}, the mutant {mut[:60]!r}")
    else:
        print("no finding: mutant detected or harness outcomes agree")
