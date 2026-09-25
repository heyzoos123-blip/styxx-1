"""Batch-3 witness helpers (independent of the reporter's scripts).

argv[1] = an import root that holds styxx/. Fixture modules are written to a fresh temp dir with
per-process unique names, so the original and the mutant each import them cleanly.
"""
import json, os, subprocess, sys, tempfile, importlib
from pathlib import Path

ROOT = sys.argv[1]
sys.dont_write_bytecode = True
sys.path.insert(0, ROOT)
import styxx.protocol as P                                               # noqa: E402
from styxx.protocol import Experiment, GateSpecError, coverage_trace     # noqa: E402
assert Path(P.__file__).resolve().is_relative_to(Path(ROOT).resolve()), P.__file__

TMP = Path(tempfile.mkdtemp(prefix="b3w_"))
sys.path.insert(0, str(TMP))
_N = [0]


def write_module(relname: str, src: str):
    """relname like 'pkg/__init__' or 'mod'; returns nothing, file is importable afterwards."""
    p = TMP / (relname + ".py")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(src, encoding="utf-8")
    importlib.invalidate_caches()


def experiment(gates: dict) -> Experiment:
    """gates: {gate_name: [targets]} -> Experiment on a committed prereg (metric m >= 0.5)."""
    _N[0] += 1
    d = TMP / f"prereg{_N[0]}"
    d.mkdir()
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, "exercises": list(t)} for n, t in gates.items()}
    spec = {"gates": g,
            "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "SMOKE"}
    (d / "PREREG_w.md").write_text("# w\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=w@local", "-c", "user.name=w", "-c", "commit.gpgsign=false",
                 "commit", "-qm", "w"]):
        subprocess.run(cmd, cwd=d, check=True, capture_output=True)
    return Experiment(d / "PREREG_w.md")


def _fmt_refusal(e):
    s = str(e)
    i = s.find("]")
    return s[:i + 1], s[i + 1:].strip()[:160]


def trace_and_score(gates: dict, section_calls: dict):
    """Run a coverage trace; for each section call its callable; score. Returns an outcome dict."""
    e = experiment(gates)
    try:
        with coverage_trace(e) as cov:
            for sec, fn in section_calls.items():
                cov.run(sec, fn)
        rec = cov.record()
    except GateSpecError as ex:
        code, msg = _fmt_refusal(ex)
        return {"stage": "entry", "outcome": "REFUSED", "code": code, "msg": msg}
    try:
        v = e.score({"m": 1.0, "coverage_trace": rec})
        return {"stage": "score", "outcome": v.verdict, "coverage": v.coverage}
    except GateSpecError as ex:
        code, msg = _fmt_refusal(ex)
        return {"stage": "score", "outcome": "REFUSED", "code": code, "msg": msg}


def leftovers():
    return {k: (len(getattr(P, k)) if hasattr(getattr(P, k, None), "__len__") else repr(getattr(P, k, None)))
            for k in ("_MINTED", "_BY_FN", "_ANCHORS", "_THREADS") if hasattr(P, k)} | {
        "profile": repr(sys.getprofile())}


def emit(d):
    print(json.dumps(d, indent=1, default=str, sort_keys=True))
