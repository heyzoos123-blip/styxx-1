import json, subprocess, sys, tempfile, os
from pathlib import Path
sys.path.insert(0, "/home/user/styxx-1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from styxx.protocol import Experiment, GateSpecError, coverage_trace

def spec(**gates):
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, **extra} for n, extra in gates.items()}
    return {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"},
                                      {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "SMOKE"}

def exp(s):
    td = Path(tempfile.mkdtemp(prefix="rt1_"))
    p = td / "PREREG_case.md"
    body = s if isinstance(s, str) else json.dumps(s)
    p.write_text("# case\n\n```gates\n" + body + "\n```\n", encoding="utf-8")
    for c in (["git","init","-q"],["git","add","-A"],["git","-c","user.email=a@b","-c","user.name=a","commit","-qm","c"]):
        subprocess.run(c, cwd=td, check=True)
    return Experiment(p)

def commit(s):
    import types
    td = Path(tempfile.mkdtemp(prefix='rt1_')); p = td / 'PREREG_case.md'
    p.write_text('# case\n\n```gates\n' + json.dumps(s) + '\n```\n', encoding='utf-8')
    for c in (['git','init','-q'],['git','add','-A'],['git','-c','user.email=a@b','-c','user.name=a','commit','-qm','c']):
        subprocess.run(c, cwd=td, check=True)
    return p

def score(e, rec, m=1.0):
    try:
        v = e.score({"m": m, "coverage_trace": rec})
        return f"VERDICT {v.verdict} coverage={v.coverage}"
    except GateSpecError as ex:
        return f"REFUSED {str(ex)[:200]}"

def attempt(label, fn):
    try:
        out = fn()
        print(label, "->", out)
    except GateSpecError as ex:
        print(label, "-> GateSpecError", str(ex)[:170])
    except BaseException as ex:
        print(label, "-> ESCAPED", type(ex).__name__, str(ex)[:170])
    finally:
        import sys, threading
        if sys.getprofile() is not None or threading.getprofile() is not None:
            print("   [leak] sys.getprofile=", sys.getprofile(), " threading.getprofile=", threading.getprofile())
            sys.setprofile(None); threading.setprofile(None)
