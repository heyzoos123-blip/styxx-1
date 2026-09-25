"""EXPLORATORY (not preregistered): the N-version implementation on all four Pythons."""
import json, subprocess, sys, tempfile, hashlib
from pathlib import Path
ROOT = Path("/home/user/styxx-1"); HERE = ROOT / "papers/first-afference"
sys.path.insert(0, str(HERE))
import aux_v5e as A
SP = "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt3"
pys = [sys.executable, f"{SP}/venv3.10/bin/python", f"{SP}/venv3.12/bin/python", f"{SP}/venv3.13/bin/python"]
work = Path(tempfile.mkdtemp(prefix="nvx_")); root = A.pkg_with(A.NV_IMPL, work / "pkg")
per = {}
for py in pys:
    v = subprocess.run([py, "-c", "import sys;print(sys.version.split()[0])"], capture_output=True, text=True).stdout.strip()
    e, how = A.run(py, A.RUNNER, ["--smoke", "--full-battery"], root, work / f"x_{v}.json")
    clean, oks = A.exam_clean(e)
    fz, howf = A.run(py, A.FUZZER, ["--n", "1000"], root, work / f"f_{v}.json", traces=work / f"t_{v}.jsonl")
    per[v] = {"exam_clean": clean, "n_cases": len(oks), "failing": sorted(k for k, ok in oks.items() if not ok),
              "fuzz_n": fz and fz["fuzz_n_programs"], "fuzz_oracle_disagreements": fz and fz["fuzz_oracle_disagreements"],
              "fuzz_leftovers": fz and fz["fuzz_leftovers"], "runs": [how, howf], "_oks": oks}
common = set.intersection(*(set(p["_oks"]) for p in per.values()))
diffs = sorted(k for k in common if len({p["_oks"][k] for p in per.values()}) > 1)
for p in per.values(): p.pop("_oks")
out = {"generator": "papers/first-afference/nversion_crossversion_exploratory.py",
       "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       "what": "EXPLORATORY, not preregistered and not a gate: the N-version implementation "
               "(nversion_v5e/protocol_nv.py) run through the frozen exam (--smoke --full-battery) and the frozen fuzzer "
               "(--n 1000) on each of four CPython versions. The aux prereg gates the PRIMARY on four versions and the "
               "N-version on the scoring interpreter only; this fills the other three cells.",
       "nversion_sha256": hashlib.sha256(A.NV_IMPL.read_bytes()).hexdigest(),
       "runner_sha256": A.sha(A.RUNNER), "fuzzer_sha256": A.sha(A.FUZZER),
       "per_version": per, "n_versions": len(per), "case_outcome_diffs_across_versions": diffs,
       "n_versions_clean": sum(1 for p in per.values() if p["exam_clean"] and p["fuzz_oracle_disagreements"] == 0 and p["fuzz_leftovers"] == 0)}
(HERE / "protocol_v5e_nversion_crossversion_exploratory.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps({v: {k: p[k] for k in ("exam_clean", "n_cases", "fuzz_oracle_disagreements", "fuzz_leftovers")} for v, p in per.items()}), "diffs", len(diffs))
