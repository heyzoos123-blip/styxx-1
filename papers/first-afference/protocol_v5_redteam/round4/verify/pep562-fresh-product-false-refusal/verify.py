# Independent verifier repro for "pep562-fresh-product-false-refusal".
# Variants (each its own module, own prereg, own trace):
#   A  fresh product per access, defined in the declared module, called in the section  (the claim)
#   B  control: __getattr__ returns a stable module-level function (the V10 shape)
#   C  control: __getattr__ builds the product once and caches it in globals()
#   D  fresh product per access, but with functools.wraps(new_api) (the common helper shape)
#   E  remedy check: declare the callee new_api instead, same fresh-product shim
#   F  remedy check: declare the module's own __getattr__
#   G  A plus: is the minted product retained anywhere after exit? (leak check)
import gc, json, os, subprocess, sys, tempfile, textwrap
from pathlib import Path
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

TMP = Path(tempfile.mkdtemp(prefix="vpep562_"))
sys.path.insert(0, str(TMP))


def mod(name, src):
    (TMP / f"{name}.py").write_text(textwrap.dedent(src), encoding="utf-8")
    sys.modules.pop(name, None)


def exp_for(targets):
    d = Path(tempfile.mkdtemp(prefix="vpep562_repo_"))
    spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": targets}},
            "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "S"}
    p = d / "PREREG_v.md"
    p.write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=d, check=True)
    return Experiment(p)


def run(label, name, src, targets, call):
    mod(name, src)
    m = __import__(name)
    exp = exp_for(targets)
    with coverage_trace(exp) as cov:
        r = cov.run("G", call, m)
    rec = cov.record()
    try:
        v = exp.score({"m": 1.0, "coverage_trace": rec})
        out = f"PASS verdict={v.verdict}"
    except GateSpecError as e:
        out = "REFUSED " + str(e)[:150]
    print(f"{label}: result={r} calls={rec['sections']['G'][0]['calls']} "
          f"uncredited={rec['uncredited']} problems={rec['problems']}\n    -> {out}")
    left = (sys.getprofile(), len(P._MINTED), len(P._BY_FN), len(P._ANCHORS), len(P._THREADS), P._ACTIVE)
    assert left == (None, 0, 0, 0, 0, 0), left
    return out


FRESH = """
    def new_api(x):
        return x + 1
    def __getattr__(name):
        if name == "old_api":
            def old_api(x):
                return new_api(x)
            return old_api
        raise AttributeError(name)
"""
STABLE = """
    def new_api(x):
        return x + 1
    def _old_api(x):
        return new_api(x)
    def __getattr__(name):
        if name == "old_api":
            return _old_api
        raise AttributeError(name)
"""
CACHED = """
    def new_api(x):
        return x + 1
    def __getattr__(name):
        if name == "old_api":
            def old_api(x):
                return new_api(x)
            globals()[name] = old_api
            return old_api
        raise AttributeError(name)
"""
WRAPS = """
    import functools
    def new_api(x):
        return x + 1
    def __getattr__(name):
        if name == "old_api":
            @functools.wraps(new_api)
            def old_api(*a, **k):
                return new_api(*a, **k)
            return old_api
        raise AttributeError(name)
"""
print(sys.version.split()[0])
a = run("A fresh", "v_fresh", FRESH, ["v_fresh:old_api"], lambda m: m.old_api(1))
b = run("B stable", "v_stable", STABLE, ["v_stable:old_api"], lambda m: m.old_api(1))
c = run("C cached", "v_cached", CACHED, ["v_cached:old_api"], lambda m: m.old_api(1))
d = run("D wraps", "v_wraps", WRAPS, ["v_wraps:old_api"], lambda m: m.old_api(1))
e = run("E callee", "v_fresh2", FRESH, ["v_fresh2:new_api"], lambda m: m.old_api(1))
f = run("F getattr", "v_fresh3", FRESH, ["v_fresh3:__getattr__"], lambda m: m.old_api(1))
print("SUMMARY", {"A": a[:40], "B": b[:40], "C": c[:40], "D": d[:40], "E": e[:40], "F": f[:40]})
ok = (a.startswith("REFUSED [V5:NOT_EXERCISED]") and d.startswith("REFUSED [V5:NOT_EXERCISED]")
      and b.startswith("PASS") and c.startswith("PASS"))
print("CLAIM-REPRODUCED" if ok else "CLAIM-NOT-REPRODUCED")
