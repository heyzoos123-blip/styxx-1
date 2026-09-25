"""Independent repro: does a PEP 562 lazy re-export's FOREIGN_DEFINITION refusal say which module
to declare (closure table, row 'R3 nit: PEP 562')?"""
import json, os, subprocess, sys, tempfile, importlib
from pathlib import Path
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

HERE = Path(__file__).resolve().parent
work = Path(tempfile.mkdtemp(prefix="vpep562_", dir=HERE))
pkg = work / "vpkg"; pkg.mkdir()
(pkg / "__init__.py").write_text(
    "def __getattr__(name):\n"
    "    if name == 'solve':\n"
    "        from vpkg._impl import solve\n"
    "        return solve\n"
    "    if name == 'solve2':\n"
    "        from vpkg._gen import solve2\n"
    "        return solve2\n"
    "    raise AttributeError(name)\n")
(pkg / "_impl.py").write_text("def solve(x=0):\n    return x\n")
# a generated function: exec'd into _gen's own namespace (so declaring vpkg._gen:solve2 is valid)
(pkg / "_gen.py").write_text("exec(compile('def solve2(x=0):\\n    return x\\n', '<string>', 'exec'), globals())\n")
sys.path.insert(0, str(work))

def refuse(target):
    try:
        P._resolve_target(target)
        return None
    except GateSpecError as e:
        return str(e)

out = {"python": sys.version.split()[0]}
for tgt, defmod in (("vpkg:solve", "vpkg._impl"), ("vpkg:solve2", "vpkg._gen")):
    msg = refuse(tgt)
    fn = getattr(importlib.import_module("vpkg"), tgt.split(":")[1])
    out[tgt] = {
        "message": msg,
        "code": msg.split("]")[0] + "]" if msg else None,
        "names_defining_module": bool(msg) and (defmod in msg),
        "fn_globals___name__": fn.__globals__["__name__"],
        "co_filename": fn.__code__.co_filename,
        "correct_declaration_accepted": refuse(f"{defmod}:{tgt.split(':')[1]}") is None,
    }

# end-to-end through Experiment + coverage_trace for the plain lazy re-export
d = Path(tempfile.mkdtemp(prefix="vexp_", dir=HERE))
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["vpkg:solve"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "SMOKE"}
(d / "PREREG_v.md").write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
for c in (["git", "init", "-q"], ["git", "add", "-A"],
          ["git", "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "c"]):
    subprocess.run(c, cwd=d, check=True, capture_output=True)
e = Experiment(d / "PREREG_v.md")
try:
    with coverage_trace(e):
        pass
    out["end_to_end"] = "ENTERED (no refusal)"
except GateSpecError as ex:
    out["end_to_end"] = str(ex)
out["registries_clean"] = not (P._MINTED or P._BY_FN or P._ANCHORS or P._THREADS) and P._ACTIVE == 0
print(json.dumps(out, indent=1))
bad = [t for t in ("vpkg:solve", "vpkg:solve2")
       if out[t]["code"] == "[V5:FOREIGN_DEFINITION]" and not out[t]["names_defining_module"]
       and out[t]["correct_declaration_accepted"]]
print("REPRODUCED: refusal does not name the module to declare for", bad if bad else "none")
