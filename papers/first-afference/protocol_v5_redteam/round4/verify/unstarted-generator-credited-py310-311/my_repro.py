"""Independent repro: styxx v5e coverage_trace credits a declared generator/coroutine whose body
never executes, for five harness shapes; plus two controls (consumed -> PASS, never called -> refuse).
Run: PYTHONPATH=/home/user/styxx-1 <python> my_repro.py"""
import json, subprocess, sys, tempfile, textwrap, importlib
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="v_ugc_"))
MOD = "_v_ugc_mod"
(tmp / f"{MOD}.py").write_text(textwrap.dedent('''
    RAN = []
    def scan(rows):
        RAN.append("scan")
        for r in rows:
            yield r
    async def fetch(x):
        RAN.append("fetch")
        return x
'''))
sys.path.insert(0, str(tmp))
repo = tmp / "repo"; repo.mkdir()
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5,
                        "exercises": [f"{MOD}:scan", f"{MOD}:fetch"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "S"}
p = repo / "PREREG.md"
p.write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
for c in (["git", "init", "-q"], ["git", "add", "-A"],
          ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", "commit", "-qm", "c"]):
    subprocess.run(c, cwd=repo, check=True)

from styxx.protocol import Experiment, GateSpecError, coverage_trace
mod = importlib.import_module(MOD)
exp = Experiment(p)

def drop():                       # generator + coroutine created, never driven, dropped in section
    mod.scan([1]); c = mod.fetch(1); c.close()
def close_explicit():             # explicit close() of both, never started
    g = mod.scan([1]); g.close(); c = mod.fetch(1); c.close()
def throw_in():                   # throw into unstarted objects
    g = mod.scan([1])
    try: g.throw(ValueError)
    except ValueError: pass
    c = mod.fetch(1)
    try: c.throw(ValueError)
    except ValueError: pass
def consumed():                   # control: legitimately exercised
    list(mod.scan([1])); c = mod.fetch(1)
    try: c.send(None)
    except StopIteration: pass
def never():                      # control: never called
    pass

def one(label, fn):
    del mod.RAN[:]
    with coverage_trace(exp) as cov:
        cov.run("G", fn)
    rec = cov.record()
    try:
        v = exp.score({"m": 1.0, "coverage_trace": rec}); out = f"{v.verdict} {v.coverage['G']}"
    except GateSpecError as e:
        out = str(e)[:40]
    print(f"  {label:16s} body_ran={mod.RAN!s:22s} -> {out}")

print(sys.version.split()[0])
for lab, fn in [("drop", drop), ("close_explicit", close_explicit), ("throw_in", throw_in),
                ("CTRL consumed", consumed), ("CTRL never", never)]:
    one(lab, fn)
# close at a bare yield: created+primed outside the section, section only closes it
del mod.RAN[:]
with coverage_trace(exp) as cov:
    g = mod.scan([1, 2]); next(g); c = mod.fetch(1)
    n0 = len(mod.RAN)
    def close_bare():
        g.close()
        try: c.send(None)            # fetch legitimately driven so only scan is in question
        except StopIteration: pass
    cov.run("G", close_bare)
rec = cov.record()
try:
    v = exp.score({"m": 1.0, "coverage_trace": rec}); out = f"{v.verdict} {v.coverage['G']}"
except GateSpecError as e:
    out = str(e)[:40]
print(f"  {'close@bare-yield':16s} scan lines in section={[x for x in mod.RAN[n0:] if x=='scan']} -> {out}")
