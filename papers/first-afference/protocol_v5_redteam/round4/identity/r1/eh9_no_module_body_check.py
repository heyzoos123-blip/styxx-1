"""EXAM_HOLE: X25/X25b pin the cache-body rule only where the wrapper's holder is also the body's
namespace. A mutant that drops the vars(mod) clause (keeping the holder clause) passes the frozen
exam. Paired harness: a class-held cache wrapper whose body is bound at module level; the section
calls only the body. Original: NOT_A_FUNCTION at entry (spec step 4). Mutant: PASS although the
declared wrapper was never called."""
MUT_NAME = 'cache-body check against vars(mod) dropped (holder check kept)'
SUBS = [('        if any(v is body for v in vars(mod).values()) or (\n                holder is not None and any(v is body for v in holder.values())):', '        if (\n                holder is not None and any(v is body for v in holder.values())):')]
EXPECT_ORIG = 'REFUSED_AT_ENTRY [V5:NOT_A_FUNCTION]'
HARNESS = 'import json, os, subprocess, sys, tempfile, textwrap, types\nfrom pathlib import Path\nsys.path.insert(0, os.environ["RT4_STYXX_ROOT"])\nimport styxx.protocol as P\nfrom styxx.protocol import Experiment, GateSpecError, coverage_trace\nassert Path(P.__file__).resolve().is_relative_to(Path(os.environ["RT4_STYXX_ROOT"]).resolve())\n_TMP = Path(tempfile.mkdtemp(prefix="rt4id_h_"))\nsys.path.insert(0, str(_TMP))\ndef write_mod(name, src):\n    (_TMP / f"{name}.py").write_text(textwrap.dedent(src), encoding="utf-8")\n    sys.modules.pop(name, None)\ndef make_exp(**gates):\n    d = Path(tempfile.mkdtemp(prefix="rt4id_repo_"))\n    g = {k: {"metric": "m", "op": ">=", "value": 0.5, **v} for k, v in gates.items()}\n    spec = {"gates": g, "outcomes": [{"when": {k: True for k in g}, "verdict": "PASS"},\n                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}\n    p = d / "PREREG_case.md"\n    p.write_text("# case\\n\\n```gates\\n" + json.dumps(spec) + "\\n```\\n", encoding="utf-8")\n    for c in (["git", "init", "-q"], ["git", "add", "-A"],\n              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",\n               "commit", "-qm", "c"]):\n        subprocess.run(c, cwd=d, check=True)\n    return Experiment(p)\ndef score(exp, rec, m=1.0):\n    try:\n        v = exp.score({"m": m, "coverage_trace": rec})\n        return f"PASS {v.coverage}"\n    except GateSpecError as e:\n        return f"REFUSED {str(e)[:120]}"\nwrite_mod("rt4_cls_cache", """\n    import functools\n    def _impl(x):                            # the body, bound at module level\n        return x * 3\n    class Scorer:\n        fast = staticmethod(functools.lru_cache(maxsize=None)(_impl))\n""")\nimport rt4_cls_cache as cc\nexp = make_exp(G={"exercises": ["rt4_cls_cache:Scorer.fast"]})\ntry:\n    with coverage_trace(exp) as cov:\n        cov.run("G", cc._impl, 1)            # the cache wrapper is never called\n    print(score(exp, cov.record()))\nexcept GateSpecError as e:\n    print("REFUSED_AT_ENTRY", str(e)[:130])\n'
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
