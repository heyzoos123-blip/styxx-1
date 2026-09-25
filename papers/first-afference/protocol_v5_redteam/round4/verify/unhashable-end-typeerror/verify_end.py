"""Independent verifier repro: an opening whose `end` is not a hashable value.

Spec (score step 3): BAD_TRACE ... "each opening is a dict with exactly the four keys, `end` is in
the enum" -> refuse. check_metrics "reports usable: False with the refusal text and never raises".
Controls: hashable-but-wrong ends (1, None, b'returned', 'finished') must refuse BAD_TRACE; an
untouched trace must PASS.
"""
import copy, json, os, subprocess, sys, tempfile, traceback
from pathlib import Path
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
from styxx.protocol import Experiment, GateSpecError, coverage_trace

work = Path(tempfile.mkdtemp(prefix="vend_"))
(work / "vend_tgt.py").write_text("def g(x):\n    return x + 1\n")
sys.path.insert(0, str(work))
import vend_tgt

spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["vend_tgt:g"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "SMOKE"}
pre = work / "PREREG_v.md"
pre.write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n")
env = dict(os.environ, GIT_AUTHOR_NAME="v", GIT_AUTHOR_EMAIL="v@v", GIT_COMMITTER_NAME="v",
           GIT_COMMITTER_EMAIL="v@v")
for c in (["git", "init", "-q"], ["git", "add", "PREREG_v.md"],
          ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "p"]):
    subprocess.run(c, cwd=work, check=True, env=env)

exp = Experiment(pre)
with coverage_trace(exp) as cov:
    cov.run("G", vend_tgt.g, 1)
base = cov.record()
# the realistic path: a result persisted as JSON, then edited/merged by a script and reloaded
base = json.loads(json.dumps(base))

def attempt(label, end):
    rec = copy.deepcopy(base)
    if end is not ...:
        rec["sections"]["G"][0]["end"] = end
    res = {"m": 1.0, "coverage_trace": rec}
    row = []
    for fn in ("score", "check_metrics"):
        try:
            r = getattr(exp, fn)(res)
            if fn == "score":
                row.append(f"score -> verdict {r.verdict}")
            else:
                e = r["G:exercises"]
                row.append(f"check_metrics -> usable={e['usable']} note={str(e['note'])[:40]!r}")
        except GateSpecError as e:
            row.append(f"{fn} -> refused {str(e)[:32]!r}")
        except Exception as e:
            tb = traceback.extract_tb(e.__traceback__)[-1]
            row.append(f"{fn} -> RAISED {type(e).__name__}: {e} (at {Path(tb.filename).name}:{tb.lineno} `{tb.line}`)")
    print(f"[{label}]")
    for x in row:
        print("   ", x)

print(sys.version.split()[0])
attempt("control: untouched", ...)
attempt("control: 'finished'", "finished")
attempt("control: 1", 1)
attempt("control: None", None)
attempt("control: b'returned'", b"returned")
attempt("list ['returned'] (JSON-loadable)", ["returned"])
attempt("dict {} (JSON-loadable)", {})
attempt("set {'returned'}", {"returned"})
