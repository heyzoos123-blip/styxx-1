# rev9 probe (GAP-15, GAP-05, GAP-19): renders the spec-fixed texts through ref_v5f.py and checks the
# "has not started" test of LAZY_RESULT on both verified interpreters. usage: python p_texts.py <module file>
import sys, os, json, types, collections, importlib.util, subprocess, tempfile
modfile = sys.argv[1]
sp = importlib.util.spec_from_file_location("styxx_protocol_t", modfile)
P = importlib.util.module_from_spec(sp); sys.modules["styxx_protocol_t"] = P; sp.loader.exec_module(P)
print(sys.version.split()[0])
# GAP-05: _v5_state() before the first coverage_trace()
print("state before any tracer:", P._v5_state())
# LAZY_RESULT: the not-started test, for each lazy type, created / suspended / finished
def g():
    yield 1
async def c():
    return 1
async def ag():
    yield 1
for mk in (g, c, ag):
    o = mk()
    print(type(o).__qualname__, "created:", P._lazy_text(o)[-27:])
    if mk is g:
        next(o); print("  suspended:", P._lazy_text(o)[-27:]); o.close(); print("  closed:", P._lazy_text(o)[-27:])
    elif mk is c:
        o.close(); print("  closed:", P._lazy_text(o)[-27:])
    else:
        o.aclose().close(); print("  aclose():", P._lazy_text(o)[-27:])
# NO_TRACE, three wordings, through check_metrics (the entry point for a non-dict result)
W = tempfile.mkdtemp(prefix="rev9t_")
spec = {"gates": {"A": {"metric": "m", "op": ">=", "value": 0.0, "exercises": ["fxt:f", "fxt:g"]}},
        "outcomes": [{"when": {"A": True}, "verdict": "PASS"}, {"when": {"A": False}, "verdict": "FAIL"}],
        "smoke_verdict": "INVALID__smoke"}
open(os.path.join(W, "PREREG_T.md"), "w").write("# t\n\n```gates\n" + json.dumps(spec) + "\n```\n")
gi = ["git", "-c", "user.name=t", "-c", "user.email=t@invalid", "-c", "commit.gpgsign=false"]
subprocess.run(["git", "init", "-q"], cwd=W, check=True)
subprocess.run(gi + ["add", "."], cwd=W, check=True); subprocess.run(gi + ["commit", "-q", "-m", "t"], cwd=W, check=True)
E = P.Experiment(os.path.join(W, "PREREG_T.md"))
for label, res in (("list result", [1]), ("no key", {"m": 1.0}),
                   ("OrderedDict trace", {"m": 1.0, "coverage_trace": collections.OrderedDict(tracer=1)})):
    print("NO_TRACE", label, "->", E.check_metrics(res)["A:exercises"]["note"])
