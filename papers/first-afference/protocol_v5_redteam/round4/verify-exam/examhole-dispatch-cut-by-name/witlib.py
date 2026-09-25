"""Shared witness helpers. Usage inside a witness: `import witlib; P = witlib.load(sys.argv[1])`
puts the given import root FIRST on sys.path and imports styxx.protocol from it."""
import json, os, subprocess, sys, tempfile, textwrap, importlib
from pathlib import Path

sys.dont_write_bytecode = True


def load(import_root):
    sys.path.insert(0, str(Path(import_root).resolve()))
    import styxx.protocol as P
    assert Path(P.__file__).resolve().is_relative_to(Path(import_root).resolve()), P.__file__
    return P


_FIX = Path(tempfile.mkdtemp(prefix="witfx_"))
sys.path.insert(0, str(_FIX))


def fixture(name, src):
    (_FIX / f"{name}.py").write_text(textwrap.dedent(src))
    importlib.invalidate_caches()
    return importlib.import_module(name)


def exp(P, gates, outcomes=None):
    """A committed prereg in a fresh git repo; every gate reads metric m >= 0.5."""
    g = {n: dict({"metric": "m", "op": ">=", "value": 0.5}, **extra) for n, extra in gates.items()}
    if outcomes is None:
        outcomes = [{"when": {n: True for n in g}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}]
    spec = {"gates": g, "outcomes": outcomes, "smoke_verdict": "SMOKE"}
    td = Path(tempfile.mkdtemp(prefix="witexp_"))
    p = td / "PREREG_witness.md"
    p.write_text("# witness\n\n```gates\n" + json.dumps(spec, indent=1) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=w@w", "-c", "user.name=w", "-c", "commit.gpgsign=false",
               "commit", "-qm", "w"]):
        subprocess.run(c, cwd=td, check=True)
    return P.Experiment(p)


def outcome(P, e, harness):
    """Run harness(cov) inside a trace and score; return a short outcome string."""
    try:
        with P.coverage_trace(e) as cov:
            harness(cov)
    except P.GateSpecError as ex:
        return "REFUSED_AT_ENTRY " + str(ex)[:120]
    rec = cov.record()
    try:
        v = e.score({"m": 1.0, "coverage_trace": rec})
        return f"{v.verdict} {v.coverage}"
    except P.GateSpecError as ex:
        return "REFUSED " + str(ex)[:120]
