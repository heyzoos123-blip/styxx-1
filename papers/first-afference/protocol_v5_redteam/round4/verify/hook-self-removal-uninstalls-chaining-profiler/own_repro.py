"""Independent repro: styxx's _hook self-removal (sys.setprofile(None)) removes a user profiler
that chains to the profiler it found (styxx's hook) when started inside a section.

Variants:
  plain      : user profiler does not forward (control) -> expected survives
  chain_all  : forwards every event to prev
  chain_py   : forwards only Python 'call'/'return' events (no c_call), to show it is not only the
               sys.getprofile() c_call inside _close that triggers the removal
Also records WHERE the removal happens (frame name of the event that the hook self-removed on) and
whether the calls made after the user's profiler replaced the hook were counted anyway (the
PROFILER_LOST note says they were not observed).
"""
import importlib, json, subprocess, sys, tempfile, textwrap
from pathlib import Path
from styxx.protocol import Experiment, coverage_trace
import styxx.protocol as P

tmp = Path(tempfile.mkdtemp(prefix="vf_chain_"))
(tmp / "vf_chain_mod.py").write_text(textwrap.dedent("""
    def target():
        return 1
    def after():
        return 2
"""))
sys.path.insert(0, str(tmp))
mod = importlib.import_module("vf_chain_mod")
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5,
                        "exercises": ["vf_chain_mod:target"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "S"}
pr = tmp / "PREREG_vf.md"
pr.write_text("# vf\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for c in (["git", "init", "-q"], ["git", "add", "-A"],
          ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
           "commit", "-qm", "c"]):
    subprocess.run(c, cwd=tmp, check=True)
exp = Experiment(pr)

removed_at = []
_real_setprofile = sys.setprofile


def make_prof(mode):
    state = {"seen_after": 0, "prev": None}

    def prof(frame, event, arg):
        if event == "call" and frame.f_code.co_name == "after":
            state["seen_after"] += 1
        prev = state["prev"]
        if prev is None or mode == "plain":
            return
        if mode == "chain_py" and event not in ("call", "return"):
            return
        before = sys.getprofile  # noqa -- keep it simple; we read the effect after
        prev(frame, event, arg)
        # detect the moment the forwarded call removed *us*
        if not removed_at and event is not None:
            pass
    state["fn"] = prof
    return state


def run(mode):
    st = make_prof(mode)

    def body():
        st["prev"] = sys.getprofile()      # finds styxx's _hook (the section installed it)
        assert st["prev"] is P._hook
        _real_setprofile(st["fn"])         # user's profiler replaces it, and chains to it
        mod.target()                       # called only AFTER the replacement

    with coverage_trace(exp) as cov:
        cov.run("G", body)
        installed_after_close = sys.getprofile() is st["fn"]
        for _ in range(5):
            mod.after()
    still_installed_after_exit = sys.getprofile() is st["fn"]
    _real_setprofile(None)
    rec = cov.record()
    sec = rec["sections"]["G"][0]
    try:
        verdict = exp.score({"m": 1.0, "coverage_trace": rec}).verdict
    except P.GateSpecError as e:
        verdict = str(e)[:40]
    return {"mode": mode, "installed_after_close": installed_after_close,
            "installed_after_exit": still_installed_after_exit,
            "after_calls_seen_by_user_profiler": st["seen_after"],
            "calls": sec["calls"], "notes": [n[:60] for n in sec["notes"]],
            "problems": rec["problems"], "verdict": verdict}


# locate the event on which the hook removes the user's profiler (chain_all)
def where():
    hits = []
    orig_hook = P._hook

    def spy(frame, event, arg):
        was = sys.getprofile()
        orig_hook(frame, event, arg)
        if was is not None and sys.getprofile() is None and not hits:
            hits.append((event, frame.f_code.co_name, getattr(arg, "__name__", None)))
    st = {"prev": None}

    def prof(frame, event, arg):
        if st["prev"] is not None:
            st["prev"](frame, event, arg)

    def body():
        st["prev"] = spy                   # stand-in for the found hook, same behaviour
        _real_setprofile(prof)
        mod.target()
    with coverage_trace(exp) as cov:
        cov.run("G", body)
    _real_setprofile(None)
    return hits


print(sys.version.split()[0])
for m in ("plain", "chain_all", "chain_py"):
    print(json.dumps(run(m)))
print("removal happened on event:", where())
