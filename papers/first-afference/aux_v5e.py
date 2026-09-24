"""Auxiliary gates for protocol v5e: the oracle fuzzer, an independent second implementation, and
four Python versions. Frozen with PREREG_protocol_v5e_aux_2026_09_24.md, before v5e exists.

The main exam (run_protocol_v5e.py) checks one implementation against hand-written cases. This
checks three things it cannot:

1. THE RULE, NOT THE CASES. ``fuzz_v5e.py`` runs thousands of seeded random harness programs whose
   exact expected trace the generator computes itself. The primary implementation must match the
   oracle on every one, leave nothing behind, and -- as a positive control -- the fuzzer must SEE a
   missing dispatch cut when the implementation's ``_STOP`` is disabled.
2. TWO IMPLEMENTATIONS. A second implementation, written after the freeze by a separate agent from
   the frozen spec alone and without sight of the primary, lives at ``nversion_v5e/protocol_nv.py``
   (a complete replacement for ``styxx/protocol.py``). It must pass the frozen exam's cases, match
   the oracle, and produce normalized traces identical to the primary's on every fuzz program.
   Two independent implementations that disagree mean the spec is ambiguous or one is wrong; the
   exam passing both means it was not tuned to either.
3. FOUR PYTHONS. The frozen exam's case outcomes must be identical on 3.10, 3.11, 3.12 and 3.13
   (cases present on only some versions are version-keyed and skipped), and the fuzzer must find
   zero oracle disagreements on each.

Everything runs in subprocesses against private copies of the ``styxx`` package; the committed tree
is never modified. Writes ``protocol_v5e_aux_result.json`` and scores it against the aux prereg.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

PREREG = "PREREG_protocol_v5e_aux_2026_09_24.md"
RUNNER = HERE / "run_protocol_v5e.py"
FUZZER = HERE / "fuzz_v5e.py"
NV_IMPL = HERE / "nversion_v5e" / "protocol_nv.py"
N_FUZZ = 3000
N_FUZZ_CONTROL = 600
N_FUZZ_PER_VERSION = 1000
SMOKE = "--smoke" in sys.argv
DEFAULT_PYTHONS = [
    "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt3/venv3.10/bin/python",
    sys.executable,
    "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt3/venv3.12/bin/python",
    "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt3/venv3.13/bin/python",
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pkg_with(impl: Path | None, td: Path) -> str | None:
    """A private copy of the styxx package whose protocol.py is *impl* (None = the committed one)."""
    if impl is None:
        return None
    shutil.copytree(ROOT / "styxx", td / "styxx", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(impl, td / "styxx" / "protocol.py")
    return str(td)


def run(py: str, script: Path, args: list, import_root: str | None, out: Path,
        traces: Path | None = None, timeout: int = 3600) -> tuple[dict | None, str]:
    env = dict(os.environ, STYXX_V5_RESULT_OUT=str(out), PYTHONDONTWRITEBYTECODE="1")
    env.pop("STYXX_V5_IMPORT_ROOT", None)
    if import_root:
        env["STYXX_V5_IMPORT_ROOT"] = import_root
    if traces:
        env["STYXX_V5_FUZZ_TRACES"] = str(traces)
    try:
        p = subprocess.run([py, str(script), *args], cwd=ROOT, env=env, capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout}s"
    if not out.exists():
        return None, f"exit {p.returncode}, no result: {p.stderr.strip()[-400:]}"
    return json.loads(out.read_text(encoding="utf-8")), f"exit {p.returncode}"


def exam_clean(r: dict | None) -> tuple[bool, dict]:
    """The frozen exam's cases all hold (the verdict of a smoke run is INVALID by type)."""
    if not r:
        return False, {}
    oks = {}
    for fam in ("violation_cases", "valid_cases", "residual_cases"):
        for k, v in (r.get(fam) or {}).items():
            oks[f"{fam}:{k}"] = bool(v.get("ok"))
    clean = (bool(oks) and all(oks.values()) and r.get("p1_retro_exact") == 1.0
             and not r.get("n_crashes"))
    return clean, oks


def read_traces(p: Path) -> dict:
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            out[d.pop("seed")] = d
    return out


def main() -> int:
    n_fuzz = 200 if SMOKE else N_FUZZ
    work = Path(tempfile.mkdtemp(prefix="v5eaux_"))
    res: dict = {"prereg": PREREG, "smoke": SMOKE}
    shas = {"aux": sha(Path(__file__)), "runner": sha(RUNNER), "fuzzer": sha(FUZZER),
            "impl": sha(ROOT / "styxx" / "protocol.py"),
            "nversion_impl": sha(NV_IMPL) if NV_IMPL.exists() else None}
    res["shas"] = shas

    # 1. the primary implementation against the oracle, and the positive control
    f, how = run(sys.executable, FUZZER, ["--n", str(n_fuzz)], None, work / "f1.json",
                 work / "tr_primary.jsonl")
    res["fuzz_primary"] = {k: f[k] for k in ("fuzz_n_programs", "modes", "fuzz_oracle_disagreements",
                                             "fuzz_leftovers", "seconds", "disagreements")} if f else how
    res["fuzz_n_programs"] = f["fuzz_n_programs"] if f else 0
    res["fuzz_oracle_disagreements"] = f["fuzz_oracle_disagreements"] if f else 10 ** 6
    res["fuzz_leftovers"] = f["fuzz_leftovers"] if f else 10 ** 6
    c, how = run(sys.executable, FUZZER, ["--n", str(N_FUZZ_CONTROL), "--control-no-cut"], None,
                 work / "fc.json")
    res["fuzz_control_no_cut_disagreements"] = c["fuzz_oracle_disagreements"] if c else 0
    res["fuzz_control_detail"] = how

    # 2. the independent second implementation
    if NV_IMPL.exists():
        nvroot = pkg_with(NV_IMPL, work / "nv")
        e, how = run(sys.executable, RUNNER, ["--smoke", "--full-battery"], nvroot, work / "nv_exam.json")
        clean, oks = exam_clean(e)
        res["nversion_exam_clean"] = 1.0 if clean else 0.0
        res["nversion_exam_failures"] = sorted(k for k, v in oks.items() if not v)[:40] or how
        g, how = run(sys.executable, FUZZER, ["--n", str(n_fuzz)], nvroot, work / "f2.json",
                     work / "tr_nv.jsonl")
        res["nversion_fuzz_oracle_disagreements"] = g["fuzz_oracle_disagreements"] if g else 10 ** 6
        a, b = read_traces(work / "tr_primary.jsonl"), read_traces(work / "tr_nv.jsonl")
        diffs = [s for s in sorted(set(a) | set(b)) if a.get(s) != b.get(s)]
        res["nversion_trace_diffs"] = len(diffs) if a and b else 10 ** 6
        res["nversion_trace_diff_examples"] = [{"seed": s, "primary": a.get(s), "nversion": b.get(s)}
                                               for s in diffs[:10]]
    else:
        res["nversion_exam_clean"], res["nversion_fuzz_oracle_disagreements"] = 0.0, 10 ** 6
        res["nversion_trace_diffs"] = 10 ** 6
        res["nversion_exam_failures"] = f"{NV_IMPL} does not exist"

    # 3. four Pythons
    pythons = [p for p in (os.environ.get("STYXX_V5_PYTHONS", "").split(",") if
                           os.environ.get("STYXX_V5_PYTHONS") else DEFAULT_PYTHONS) if p]
    per = {}
    for py in pythons:
        v = subprocess.run([py, "-c", "import sys; print(sys.version.split()[0])"],
                           capture_output=True, text=True).stdout.strip() or "unavailable"
        e, how_e = run(py, RUNNER, ["--smoke", "--full-battery"], None, work / f"x_{v}.json")
        clean, oks = exam_clean(e)
        fz, how_f = run(py, FUZZER, ["--n", str(200 if SMOKE else N_FUZZ_PER_VERSION)], None,
                        work / f"xf_{v}.json")
        per[v] = {"exam_clean": clean, "oks": oks, "exam_run": how_e,
                  "fuzz_oracle_disagreements": fz["fuzz_oracle_disagreements"] if fz else 10 ** 6,
                  "fuzz_run": how_f}
    common = set.intersection(*(set(p["oks"]) for p in per.values())) if per else set()
    case_diffs = sorted(k for k in common if len({p["oks"][k] for p in per.values()}) > 1)
    res["crossversion_n_versions"] = len({v for v, p in per.items() if p["oks"]})
    res["crossversion_versions"] = sorted(per)
    res["crossversion_diffs"] = len(case_diffs) + sum(p["fuzz_oracle_disagreements"] for p in per.values())
    res["crossversion_detail"] = {"case_diffs": case_diffs[:40],
                                  "per_version": {v: {k: p[k] for k in ("exam_clean", "exam_run",
                                                                        "fuzz_oracle_disagreements",
                                                                        "fuzz_run")}
                                                  for v, p in per.items()},
                                  "version_keyed_skipped": sorted(set().union(*(set(p["oks"]) for p in per.values())) - common)
                                  if per else []}

    # frozen-ness of the aux's own inputs, read from the aux prereg
    import re
    text = (HERE / PREREG).read_text(encoding="utf-8") if (HERE / PREREG).exists() else ""
    frozen = dict(re.findall(r"FROZEN_([A-Z_]+)_SHA256: ([0-9a-f]{64})", text))
    res["aux_frozen"] = 1.0 if (frozen.get("AUX") == shas["aux"] and frozen.get("FUZZER") == shas["fuzzer"]
                                and frozen.get("RUNNER") == shas["runner"]) else 0.0

    try:
        from styxx.protocol import Experiment
        exp = Experiment(HERE / PREREG, require_power_basis=True, require_nonvacuous_gates=True)
        v = exp.score(res, smoke=SMOKE)
        res["verdict"], res["gates"], res["prereg_commit"] = v.verdict, v.gates, v.prereg_commit
        res["gates_sha256"] = v.gates_sha256
    except Exception as exc:                                     # noqa: BLE001
        res["verdict"] = f"UNSCORED__{type(exc).__name__}: {exc}"
    dest = Path(os.environ["STYXX_V5_RESULT_OUT"]) if os.environ.get("STYXX_V5_RESULT_OUT") \
        else HERE / f"protocol_v5e_aux_result{'_smoke' if SMOKE else ''}.json"
    dest.write_text(json.dumps(res, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: res[k] for k in res if k in (
        "fuzz_n_programs", "fuzz_oracle_disagreements", "fuzz_leftovers",
        "fuzz_control_no_cut_disagreements", "nversion_exam_clean", "nversion_fuzz_oracle_disagreements",
        "nversion_trace_diffs", "crossversion_n_versions", "crossversion_diffs", "aux_frozen", "verdict")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
