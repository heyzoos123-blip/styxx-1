"""Protocol v5 (declared harness coverage) regression tests.

Each refusal is matched on the reason it is supposed to fire for, not merely on GateSpecError:
a mutant that refuses for an incidental earlier reason never reaches the property it names,
which is the P1 defect (cycle 158) in test form. The P1 retro-case runs the committed harness.
"""
import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from styxx.protocol import (Experiment, GateSpecError, _select_gates_block,  # noqa: E402
                            coverage_trace)

FIX = "_v5_testfix"
T, O = f"{FIX}:target", f"{FIX}:other"
FIXTURE = '''
import functools
def target(): return 1
def other(): return 2
def helper(): return target()
def _deco(f):
    @functools.wraps(f)
    def w(*a, **k): return f(*a, **k)
    return w
@_deco
def wrapped(): return 3
class K:
    def meth(self): return 4
'''


@pytest.fixture()
def fx(tmp_path, monkeypatch):
    d = tmp_path / "fixmod"
    d.mkdir()
    (d / f"{FIX}.py").write_text(FIXTURE, encoding="utf-8")
    monkeypatch.syspath_prepend(str(d))
    sys.modules.pop(FIX, None)
    mod = __import__(FIX)
    yield mod
    sys.modules.pop(FIX, None)


@pytest.fixture()
def mk(tmp_path):
    n = [0]

    def _mk(**gates):
        n[0] += 1
        repo = tmp_path / f"repo{n[0]}"
        repo.mkdir()
        g = {k: {"metric": "m", "op": ">=", "value": 0.5, **v} for k, v in gates.items()}
        spec = {"gates": g, "outcomes": [{"when": {k: True for k in g}, "verdict": "PASS"},
                                         {"when": {}, "verdict": "FAIL"}],
                "smoke_verdict": "SMOKE"}
        p = repo / "PREREG_case.md"
        p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "case"], cwd=repo, check=True)
        return Experiment(p)
    return _mk


def _traced(exp, section, *calls):
    with coverage_trace(exp) as cov:
        with cov.section(section):
            for c in calls:
                c()
    return {"m": 1.0, "coverage_trace": cov.record()}


# -- refusals, each on its own reason ---------------------------------------------------------

def test_never_called_is_a_coverage_violation(mk, fx):
    exp = mk(G={"exercises": [T]})
    with pytest.raises(GateSpecError, match=r"COVERAGE VIOLATION .*_v5_testfix:target"):
        exp.score(_traced(exp, "G", fx.other))


def test_call_in_another_section_does_not_count(mk, fx):
    exp = mk(G={"exercises": [T]}, H={"exercises": [O]})
    with coverage_trace(exp) as cov:
        with cov.section("G"):
            pass
        with cov.section("H"):
            fx.target()
            fx.other()
    with pytest.raises(GateSpecError, match=r"gate 'G': COVERAGE VIOLATION"):
        exp.score({"m": 1.0, "coverage_trace": cov.record()})


def test_call_outside_sections_does_not_count(mk, fx):
    exp = mk(G={"exercises": [T]})
    with coverage_trace(exp) as cov:
        fx.target()
        with cov.section("G"):
            pass
    rec = cov.record()
    assert rec["unsectioned"] == {T: 1}
    with pytest.raises(GateSpecError, match="COVERAGE VIOLATION"):
        exp.score({"m": 1.0, "coverage_trace": rec})


def test_no_trace_refuses(mk, fx):
    with pytest.raises(GateSpecError, match="carries no 'coverage_trace'"):
        mk(G={"exercises": [T]}).score({"m": 1.0})


def test_unopened_section_refuses(mk, fx):
    exp = mk(G={"exercises": [T]})
    with coverage_trace(exp) as cov:
        fx.target()
    with pytest.raises(GateSpecError, match="section 'G' is absent"):
        exp.score({"m": 1.0, "coverage_trace": cov.record()})


def test_stale_trace_from_another_gates_block_refuses(mk, fx):
    a = mk(G={"exercises": [T]})
    b = mk(G={"exercises": [T], "metric_means": "different block"})
    with pytest.raises(GateSpecError, match="taken against gates block"):
        b.score(_traced(a, "G", fx.target))


@pytest.mark.parametrize("bad", [True, 1.0, -1, 0, "1"])
def test_hand_edited_count_refuses(mk, fx, bad):
    exp = mk(G={"exercises": [T]})
    res = _traced(exp, "G", fx.target)
    res["coverage_trace"]["sections"]["G"][T] = bad
    with pytest.raises(GateSpecError, match="positive integer call counts"):
        exp.score(res)


def test_trace_target_set_must_match_declaration(mk, fx):
    exp = mk(G={"exercises": [T]})
    res = _traced(exp, "G", fx.target)
    res["coverage_trace"]["targets"][O] = "0" * 64
    with pytest.raises(GateSpecError, match="target set"):
        exp.score(res)


@pytest.mark.parametrize("exercises, reason", [
    ([], "non-empty list"), ("x:y", "non-empty list"), ([1], "ASCII"),
    (["target"], "ASCII"), ([T, T], "twice"), (["mаd:f"], "ASCII")])
def test_malformed_declarations_refuse_at_construction(mk, exercises, reason):
    with pytest.raises(GateSpecError, match=reason):
        mk(G={"exercises": exercises})


def test_section_without_exercises_refuses(mk):
    with pytest.raises(GateSpecError, match="'section' without 'exercises'"):
        mk(G={"section": "S"})


@pytest.mark.parametrize("target, reason", [
    (f"{FIX}:nope", "does not resolve"), ("no_such_mod_v5t:f", "does not resolve"),
    ("builtins:len", "no Python code object")])
def test_unobservable_targets_refuse_before_work_runs(mk, fx, target, reason):
    exp = mk(G={"exercises": [target]})
    with pytest.raises(GateSpecError, match=reason):
        coverage_trace(exp)


def test_undeclared_section_refuses_at_open(mk, fx):
    exp = mk(G={"exercises": [T]})
    with coverage_trace(exp) as cov:
        with pytest.raises(GateSpecError, match="not declared by any gate"):
            with cov.section("G4"):
                fx.target()


def test_tracer_needs_a_declaration(mk):
    with pytest.raises(GateSpecError, match="no gate in this prereg declares"):
        coverage_trace(mk(G={}))


# -- valid declarations score -----------------------------------------------------------------

@pytest.mark.parametrize("target, call", [
    (T, lambda f: f.target()), (T, lambda f: f.helper()),
    (f"{FIX}:wrapped", lambda f: f.wrapped()), (f"{FIX}:K.meth", lambda f: f.K().meth())])
def test_valid_declarations_score(mk, fx, target, call):
    exp = mk(G={"exercises": [target]})
    v = exp.score(_traced(exp, "G", lambda: call(fx)))
    assert v.verdict == "PASS" and v.coverage == {"G": {target: 1}}


def test_thread_started_in_section_counts(mk, fx):
    exp = mk(G={"exercises": [T]})

    def run():
        th = threading.Thread(target=fx.target)
        th.start()
        th.join()
    assert exp.score(_traced(exp, "G", run)).verdict == "PASS"


def test_shared_section_and_undeclaring_gate(mk, fx):
    exp = mk(G={"exercises": [T], "section": "S"}, H={"exercises": [O], "section": "S"}, J={})
    v = exp.score(_traced(exp, "S", fx.target, fx.other))
    assert v.verdict == "PASS" and set(v.coverage) == {"G", "H"}


def test_nested_tracers_both_see_their_calls_and_restore_the_profiler(mk, fx):
    before = sys.getprofile()
    a, b = mk(G={"exercises": [T]}), mk(H={"exercises": [O]})
    with coverage_trace(a) as ca:
        with ca.section("G"):
            with coverage_trace(b) as cb:
                with cb.section("H"):
                    fx.other()
                    fx.target()
    assert a.score({"m": 1.0, "coverage_trace": ca.record()}).verdict == "PASS"
    assert b.score({"m": 1.0, "coverage_trace": cb.record()}).verdict == "PASS"
    assert sys.getprofile() is before


def test_tracer_stops_counting_after_exit(mk, fx):
    exp = mk(G={"exercises": [T]})
    with coverage_trace(exp) as cov:
        with cov.section("G"):
            fx.target()
    fx.target()
    assert cov.record()["sections"]["G"] == {T: 1}


def test_undeclared_prereg_is_untouched(mk):
    v = mk(G={}).score({"m": 1.0})
    assert v.verdict == "PASS" and v.coverage == {}


# -- the P1 retro-case, against the committed harness -----------------------------------------

def test_p1_g4_refuses_against_its_own_harness(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    fa = ROOT / "papers" / "first-afference"
    loader = importlib.machinery.SourceFileLoader(
        "styxx.power", str(ROOT / "styxx" / "power_QUARANTINED.py.txt"))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("styxx.power", loader))
    monkeypatch.setitem(sys.modules, "styxx.power", mod)
    loader.exec_module(mod)
    spec = importlib.util.spec_from_file_location("run_p1_v5test", fa / "run_p1.py")
    run_p1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_p1)

    gates = json.loads(_select_gates_block(
        (fa / "PREREG_p1_power_refusal_2026_08_08.md").read_text(encoding="utf-8")))
    public = [f"styxx.power:{n}" for n in ("effective_n", "order_stat_bar",
                                          "false_positive_rate", "min_detectable_bar",
                                          "reachable")]
    gates["gates"]["G4_refuses_degenerate"]["exercises"] = public
    p = tmp_path / "PREREG_p1_retro.md"
    p.write_text("# retro\n\n```gates\n" + json.dumps(gates) + "\n```\n", encoding="utf-8")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "r"]):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    exp = Experiment(p)
    res = json.loads((fa / "p1_result.json").read_text(encoding="utf-8"))
    with coverage_trace(exp) as cov:
        with cov.section("G4_refuses_degenerate"):
            run_p1.degenerate(np.random.default_rng(run_p1.SEED))
    res["coverage_trace"] = cov.record()
    assert res["coverage_trace"]["sections"]["G4_refuses_degenerate"] == \
        {"styxx.power:reachable": 12}
    with pytest.raises(GateSpecError, match=r"COVERAGE VIOLATION .*order_stat_bar"):
        exp.score(res)
