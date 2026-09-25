"""Independent repro: C lru_cache wrapper whose __wrapped__ was re-stamped by functools.wraps.
The resolver takes F_T = wrapper.__dict__['__wrapped__'] (spec step 4 literally), not the function
the C wrapper actually calls. Counters inside each function show what really ran."""
import gc, json, os, subprocess, sys, tempfile, textwrap, types, functools
from pathlib import Path
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

HERE = Path(__file__).resolve().parent
WORK = Path(tempfile.mkdtemp(prefix="vrf_", dir=HERE / "tmp"))
sys.path.insert(0, str(WORK))

def write_mod(name, src):
    (WORK / f"{name}.py").write_text(textwrap.dedent(src), encoding="utf-8")
    sys.modules.pop(name, None)

def make_exp(targets):
    d = Path(tempfile.mkdtemp(prefix="repo_", dir=WORK))
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

def score(exp, rec):
    try:
        v = exp.score({"m": 1.0, "coverage_trace": rec})
        return f"PASS verdict={v.verdict} coverage={v.coverage}"
    except GateSpecError as e:
        return f"REFUSED {str(e)[:150]}"

def real_callee(w):
    return [r for r in gc.get_referents(w) if type(r) is types.FunctionType]

def clean():
    return (sys.getprofile() is None and not P._MINTED and not P._BY_FN and not P._ANCHORS
            and not P._THREADS and P._ACTIVE == 0)

print(sys.version.split()[0])
# ---- restamped: the reference lives in a module-level dict (not a name, not a class) ----
write_mod("vrf_restamp", """
    import functools
    CALLS = {"ref": 0, "fast": 0}
    REG = {}
    def _build():
        def power_ref(n):
            CALLS["ref"] += 1
            return sum(range(n))
        @functools.wraps(power_ref)
        @functools.lru_cache(maxsize=None)
        def power(n):
            CALLS["fast"] += 1
            return n * (n - 1) // 2
        return power, power_ref
    power, REG["ref"] = _build()
""")
import vrf_restamp as m
rc = real_callee(m.power)
print("real callee is __wrapped__?", rc and rc[0] is m.power.__wrapped__,
      "| real callee name/line:", [(f.__qualname__, f.__code__.co_firstlineno) for f in rc],
      "| __wrapped__:", m.power.__wrapped__.__qualname__, m.power.__wrapped__.__code__.co_firstlineno)

exp = make_exp(["vrf_restamp:power"])
# (a) the section calls ONLY the reference; the declared wrapper and its cached function never run
m.CALLS.update(ref=0, fast=0)
with coverage_trace(exp) as cov:
    cov.run("G", m.REG["ref"], 10)
rec = cov.record()
print("(a) CALLS:", m.CALLS, "| targets prov:", rec["targets"], "|", score(exp, rec), "| clean:", clean())
# (b) the section calls ONLY the declared wrapper, a cache miss: its cached function runs
m.power.cache_clear(); m.CALLS.update(ref=0, fast=0)
with coverage_trace(exp) as cov:
    r = cov.run("G", m.power, 10)
print("(b) CALLS:", m.CALLS, "result", r, "|", score(exp, cov.record()), "| clean:", clean())

# ---- control: an unstamped lru_cache (the spec's assumption holds) ----
write_mod("vrf_plain", """
    import functools
    CALLS = {"fast": 0}
    @functools.lru_cache(maxsize=None)
    def power(n):
        CALLS["fast"] += 1
        return n * (n - 1) // 2
""")
import vrf_plain as pm
print("control: real callee is __wrapped__?", real_callee(pm.power)[0] is pm.power.__wrapped__)
expc = make_exp(["vrf_plain:power"])
with coverage_trace(expc) as cov:
    cov.run("G", pm.power, 10)
print("control miss:", pm.CALLS, score(expc, cov.record()))
with coverage_trace(expc) as cov:
    cov.run("G", lambda: None)
print("control nothing:", score(expc, cov.record()))

# ---- (c) reference bound at module level: refusal + remedy; then follow the remedy ----
write_mod("vrf_named", """
    import functools
    CALLS = {"ref": 0, "fast": 0}
    def reference(n):
        CALLS["ref"] += 1
        return sum(range(n))
    @functools.wraps(reference)
    @functools.lru_cache(maxsize=None)
    def fast(n):
        CALLS["fast"] += 1
        return n * (n - 1) // 2
""")
import vrf_named as nm
try:
    with coverage_trace(make_exp(["vrf_named:fast"])):
        pass
    print("(c) entered (no refusal)")
except GateSpecError as e:
    print("(c) refusal:", str(e))
exp_r = make_exp(["vrf_named:reference"])        # the remedy: "declare that name instead"
with coverage_trace(exp_r) as cov:
    cov.run("G", nm.fast, 10)                    # call the declared-by-remedy's wrapper... no: call fast
print("(c') remedy followed, section calls fast (miss):", nm.CALLS, "|", score(exp_r, cov.record()))
