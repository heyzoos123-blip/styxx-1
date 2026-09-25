# Independent repro for "gc-freeze-hides-live-clone".
# Claim: CLONE_ALIVE uses gc.get_referrers(M_T), which does not scan the permanent generation.
# After gc.freeze(), a live same-globals clone of M_T (spec X57) or a live U with U.__code__ = M_T
# (spec X58) is not found, and the gate PASSES.
import gc, json, os, subprocess, sys, tempfile, textwrap, types
from pathlib import Path

sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

root = Path(tempfile.mkdtemp(prefix="vfy_frz_"))
(root / "vfy_mod.py").write_text(textwrap.dedent("""
    def f(x=0): return x + 1
    def u(x=0): return -1
"""))
sys.path.insert(0, str(root))
import vfy_mod as M

repo = root / "repo"; repo.mkdir()
gates = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["vfy_mod:f"]}},
         "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
         "smoke_verdict": "S"}
(repo / "PREREG_v.md").write_text("# v\n\n```gates\n" + json.dumps(gates) + "\n```\n")
for c in (["git", "init", "-q"], ["git", "add", "-A"],
          ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
           "commit", "-qm", "c"]):
    subprocess.run(c, cwd=repo, check=True)
exp = Experiment(repo / "PREREG_v.md")

orig_f, orig_u = M.f.__code__, M.u.__code__
calls = {"real_f": 0}


def score(rec):
    try:
        v = exp.score({"m": 1.0, "coverage_trace": rec})
        return f"PASS verdict={v.verdict} coverage={v.coverage} problems={rec['problems']}"
    except GateSpecError as e:
        return f"REFUSED {str(e)[:90]}"


def case(kind, freeze_where):
    keep = []

    def body():
        if kind == "clone":                         # X57 shape, but the real f is NOT called
            c = types.FunctionType(M.f.__code__, M.f.__globals__, "f_clone")
            keep.append(c)
            c(1)
        elif kind == "uswap":                       # X58 shape, real f NOT called
            M.u.__code__ = M.f.__code__
            M.u(1)
        if freeze_where == "in_section":
            gc.freeze()

    with coverage_trace(exp) as cov:
        cov.run("G", body)
        if freeze_where == "after_section":
            gc.freeze()                             # still inside the trace, before exit
    rec = cov.record()
    alive = bool(keep) if kind == "clone" else (M.u.__code__ is not orig_u)
    frozen = gc.get_freeze_count()
    out = score(rec)
    gc.unfreeze()
    M.u.__code__ = orig_u
    keep.clear()
    left = dict(minted=len(P._MINTED), by_fn=len(P._BY_FN), active=P._ACTIVE,
                f_restored=M.f.__code__ is orig_f)
    return out, alive, frozen, left


print(sys.version.split()[0])
for kind in ("clone", "uswap"):
    for fw in ("none", "in_section", "after_section"):
        out, alive, frozen, left = case(kind, fw)
        print(f"{kind:6s} freeze={fw:13s} alive_at_exit={alive} freeze_count>0={frozen > 0} -> {out}")
        print(f"        leftovers={left}")
