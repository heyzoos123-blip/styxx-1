"""Protocol v5 exam, per PREREG_protocol_v5_coverage_2026_09_24.md.

Violation mutants + valid cases + the P1 retro-case + whole-corpus byte-identity, and the exam
declares its own coverage: G0 and G1 name the v5 machinery in ``exercises``, and this runner
produces its result inside ``coverage_trace`` so the self-score refuses if the battery never
reached the code it grades. The retro-case READS the committed ``run_p1.py`` and
``p1_result.json`` and re-runs P1's own harness unmodified against the quarantined module.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from styxx.protocol import (Experiment, GateSpecError, _select_gates_block,  # noqa: E402
                            coverage_trace)

PREREG = "PREREG_protocol_v5_coverage_2026_09_24.md"
SMOKE = "--smoke" in sys.argv

FIXTURE = '''
import functools


def target():
    return 1


def other():
    return 2


def helper():
    return target()


def _deco(f):
    @functools.wraps(f)
    def w(*a, **k):
        return f(*a, **k)
    return w


@_deco
def wrapped():
    return 3


class K:
    def meth(self):
        return 4

    @staticmethod
    def stat():
        return 5
'''
FIX = "_v5_fixture"
T = f"{FIX}:target"
O = f"{FIX}:other"


def _commit_prereg(tmp: Path, spec) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / "PREREG_case.md"
    body = spec if isinstance(spec, str) else json.dumps(spec)
    p.write_text("# case\n\n```gates\n" + body + "\n```\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
    subprocess.run(["git", "-c", "user.email=exam@local", "-c", "user.name=exam",
                    "commit", "-qm", "case"], cwd=tmp, check=True)
    return p


def _spec(**gates):
    """gates: name -> extra keys. Every gate reads metric m >= 0.5."""
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, **extra} for n, extra in gates.items()}
    names = list(g)
    return {"gates": g,
            "outcomes": [{"when": {n: True for n in names}, "verdict": "PASS"},
                         {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "SMOKE"}


def _run(spec, harness, edit=None, trace=True) -> tuple[bool, str]:
    """Freeze spec, run harness(cov, fixture) under a trace, score. (refused, detail)."""
    fx = sys.modules[FIX]
    with tempfile.TemporaryDirectory() as td:
        try:
            exp = Experiment(_commit_prereg(Path(td), spec))
            res = {"m": 1.0}
            if trace:
                with coverage_trace(exp) as cov:
                    harness(cov, fx)
                res["coverage_trace"] = cov.record()
            else:
                harness(None, fx)
            if edit:
                edit(res)
            v = exp.score(res)
            return False, f"scored {v.verdict} coverage={v.coverage}"
        except GateSpecError as e:
            return True, f"refused: {str(e)[:150]}"


def _sec(name, *calls):
    def h(cov, fx):
        with cov.section(name):
            for c in calls:
                c(fx)
    return h


def violations() -> dict:
    V = {}
    V["never_called"] = _run(_spec(G={"exercises": [T]}), _sec("G", lambda f: f.other()))
    V["called_only_in_other_section"] = _run(
        _spec(G={"exercises": [T]}, H={"exercises": [O]}),
        lambda cov, f: (_sec("G")(cov, f), _sec("H", lambda f: f.target(), lambda f: f.other())(cov, f)))
    V["called_only_outside_sections"] = _run(
        _spec(G={"exercises": [T]}), lambda cov, f: (f.target(), _sec("G")(cov, f)))
    V["no_trace"] = _run(_spec(G={"exercises": [T]}), lambda cov, f: f.target(), trace=False)
    V["section_absent"] = _run(_spec(G={"exercises": [T]}), lambda cov, f: f.target())

    # stale: a genuine trace from prereg A scored against prereg B with the same targets
    def stale():
        with tempfile.TemporaryDirectory() as ta, tempfile.TemporaryDirectory() as tb:
            try:
                a = Experiment(_commit_prereg(Path(ta), _spec(G={"exercises": [T]})))
                bspec = _spec(G={"exercises": [T]})
                bspec["gates"]["G"]["value"] = 0.6
                b = Experiment(_commit_prereg(Path(tb), bspec))
                with coverage_trace(a) as cov:
                    with cov.section("G"):
                        sys.modules[FIX].target()
                v = b.score({"m": 1.0, "coverage_trace": cov.record()})
                return False, f"scored {v.verdict}"
            except GateSpecError as e:
                return True, f"refused: {str(e)[:150]}"
    V["stale_gates_sha"] = stale()

    def add_target(r):
        r["coverage_trace"]["targets"][O] = "0" * 64
    V["trace_target_set_differs"] = _run(_spec(G={"exercises": [T]}),
                                         _sec("G", lambda f: f.target()), edit=add_target)

    def wrong_tracer(r):
        r["coverage_trace"]["tracer"] = "handwritten/1"
    V["trace_wrong_tracer_id"] = _run(_spec(G={"exercises": [T]}),
                                      _sec("G", lambda f: f.target()), edit=wrong_tracer)
    V["target_unresolvable_attr"] = _run(_spec(G={"exercises": [f"{FIX}:nope"]}), _sec("G"))
    V["target_unresolvable_module"] = _run(_spec(G={"exercises": ["no_such_mod_v5:f"]}), _sec("G"))
    V["target_builtin"] = _run(_spec(G={"exercises": ["builtins:len"]}),
                               _sec("G", lambda f: len([])))
    V["exercises_empty"] = _run(_spec(G={"exercises": []}), _sec("G"))
    V["exercises_not_list"] = _run(_spec(G={"exercises": T}), _sec("G", lambda f: f.target()))
    V["exercises_non_string"] = _run(_spec(G={"exercises": [1]}), _sec("G"))
    V["exercises_no_colon"] = _run(_spec(G={"exercises": ["target"]}), _sec("G"))
    V["exercises_duplicate"] = _run(_spec(G={"exercises": [T, T]}), _sec("G", lambda f: f.target()))
    V["section_non_string"] = _run(_spec(G={"exercises": [T], "section": 5}),
                                   lambda cov, f: f.target())
    V["section_without_exercises"] = _run(_spec(G={"section": "S"}),
                                          lambda cov, f: None, trace=False)
    V["undeclared_section_opened"] = _run(_spec(G={"exercises": [T]}),
                                          _sec("NOT_A_GATE", lambda f: f.target()))
    for label, bad in (("bool", True), ("float", 1.0), ("negative", -1), ("zero", 0)):
        def edit(r, bad=bad):
            r["coverage_trace"]["sections"]["G"][T] = bad
        V[f"count_{label}"] = _run(_spec(G={"exercises": [T]}), _sec("G", lambda f: f.target()),
                                   edit=edit)

    def child_process(cov, f):
        with cov.section("G"):
            env = dict(os.environ, PYTHONPATH=os.pathsep.join(
                [str(Path(f.__file__).parent), os.environ.get("PYTHONPATH", "")]))
            subprocess.run([sys.executable, "-c", f"import {FIX}; {FIX}.target()"],
                           check=True, env=env)
    V["called_only_in_child_process"] = _run(_spec(G={"exercises": [T]}), child_process)
    return V


def valids() -> dict:
    V = {}
    V["direct_call"] = _run(_spec(G={"exercises": [T]}), _sec("G", lambda f: f.target()))
    V["transitive_call"] = _run(_spec(G={"exercises": [T]}), _sec("G", lambda f: f.helper()))
    V["wraps_decorated"] = _run(_spec(G={"exercises": [f"{FIX}:wrapped"]}),
                                _sec("G", lambda f: f.wrapped()))
    V["method"] = _run(_spec(G={"exercises": [f"{FIX}:K.meth"]}),
                       _sec("G", lambda f: f.K().meth()))
    V["staticmethod"] = _run(_spec(G={"exercises": [f"{FIX}:K.stat"]}),
                             _sec("G", lambda f: f.K.stat()))

    def in_thread(f):
        th = threading.Thread(target=f.target)
        th.start()
        th.join()
    V["thread_started_in_section"] = _run(_spec(G={"exercises": [T]}), _sec("G", in_thread))
    V["two_gates_share_section"] = _run(
        _spec(G={"exercises": [T], "section": "S"}, H={"exercises": [O], "section": "S"}),
        _sec("S", lambda f: f.target(), lambda f: f.other()))
    V["declaring_beside_undeclaring"] = _run(_spec(G={"exercises": [T]}, H={}),
                                             _sec("G", lambda f: f.target()))

    def nested():
        with tempfile.TemporaryDirectory() as ta, tempfile.TemporaryDirectory() as tb:
            try:
                a = Experiment(_commit_prereg(Path(ta), _spec(G={"exercises": [T]})))
                b = Experiment(_commit_prereg(Path(tb), _spec(H={"exercises": [O]})))
                fx = sys.modules[FIX]
                with coverage_trace(a) as ca:
                    with ca.section("G"):
                        fx.target()
                        with coverage_trace(b) as cb:
                            with cb.section("H"):
                                fx.other()
                                fx.target()
                va = a.score({"m": 1.0, "coverage_trace": ca.record()})
                vb = b.score({"m": 1.0, "coverage_trace": cb.record()})
                return False, f"scored {va.verdict}/{vb.verdict} outer={va.coverage} inner={vb.coverage}"
            except GateSpecError as e:
                return True, f"refused: {str(e)[:150]}"
    V["nested_tracers"] = nested()
    return V


def _load_quarantined_power():
    path = ROOT / "styxx" / "power_QUARANTINED.py.txt"
    loader = importlib.machinery.SourceFileLoader("styxx.power", str(path))
    spec = importlib.util.spec_from_loader("styxx.power", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["styxx.power"] = mod
    loader.exec_module(mod)
    return mod


def p1_retro() -> dict:
    """P1's own G4 (and, ungated, G1) with a v5 declaration, against P1's own harness."""
    import numpy as np
    _load_quarantined_power()
    spec = importlib.util.spec_from_file_location("run_p1", HERE / "run_p1.py")
    run_p1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_p1)
    committed = json.loads((HERE / "p1_result.json").read_text(encoding="utf-8"))
    p1_gates = json.loads(_select_gates_block(
        (HERE / "PREREG_p1_power_refusal_2026_08_08.md").read_text(encoding="utf-8")))
    public = [f"styxx.power:{n}" for n in
              ("effective_n", "order_stat_bar", "false_positive_rate", "min_detectable_bar",
               "reachable")]

    def attempt(gate, targets, battery):
        g = json.loads(json.dumps(p1_gates))
        g["gates"][gate]["exercises"] = targets
        with tempfile.TemporaryDirectory() as td:
            try:
                exp = Experiment(_commit_prereg(Path(td), json.dumps(g)))
                res = dict(committed)
                with coverage_trace(exp) as cov:
                    with cov.section(gate):
                        out = battery(np.random.default_rng(run_p1.SEED))
                res["coverage_trace"] = cov.record()
                if gate == "G4_refuses_degenerate":
                    res["degenerate_refusal_rate"] = round(
                        float(np.mean([c["refused"] for c in out])), 4)
                v = exp.score(res)
                return {"refused": False, "detail": f"scored {v.verdict}",
                        "calls": res["coverage_trace"]["sections"].get(gate)}
            except GateSpecError as e:
                return {"refused": True, "detail": str(e)[:400],
                        "calls": res.get("coverage_trace", {}).get("sections", {}).get(gate)
                        if isinstance(res, dict) else None}

    return {"G4": attempt("G4_refuses_degenerate", public, run_p1.degenerate),
            "G1_ungated": attempt("G1_historical_in_sample", ["styxx.power:order_stat_bar"],
                                  run_p1.historical),
            "declared_public_functions": public}


def corpus() -> tuple[int, list]:
    diffs, pairs = [], []
    for res_file in sorted(ROOT.glob("papers/*/*_result.json")):
        try:
            d = json.loads(res_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(d, dict):
            continue
        pr, old = d.get("prereg"), d.get("verdict")
        if not isinstance(pr, str) or not isinstance(old, str) or old.startswith("UNSCORED"):
            continue
        # Same scope rule as v4: only verdicts styxx.protocol itself produced.
        if "prereg_commit" not in d or "gates" not in d:
            continue
        prereg_path = res_file.parent / pr
        if not prereg_path.exists() or prereg_path.name == PREREG:
            continue
        pairs.append((prereg_path, res_file, d, old))
    if SMOKE:
        pairs = pairs[:5]
    for prereg_path, res_file, d, old in pairs:
        try:
            new = Experiment(prereg_path).score(d, smoke=bool(d.get("smoke"))).verdict
        except Exception as e:
            new = f"RAISED:{type(e).__name__}"
        if new != old:
            diffs.append({"result": f"{res_file.parent.name}/{res_file.name}",
                          "was": old, "now": new})
    return len(pairs), diffs


def main() -> int:
    fixdir = Path(tempfile.mkdtemp(prefix="v5fix_"))
    (fixdir / f"{FIX}.py").write_text(FIXTURE, encoding="utf-8")
    sys.path.insert(0, str(fixdir))
    __import__(FIX)

    self_exp = Experiment(HERE / PREREG, require_power_basis=True, require_nonvacuous_gates=True)
    with coverage_trace(self_exp) as cov:
        with cov.section("G0_mutants_refused"):
            viol = violations()
        with cov.section("G1_valid_still_scores"):
            vals = valids()
    retro = p1_retro()
    checked, diffs = corpus()

    res = {"prereg": PREREG, "smoke": SMOKE,
           "violation_cases": {k: {"refused": r, "detail": s} for k, (r, s) in viol.items()},
           "valid_cases": {k: {"scored": not r, "detail": s} for k, (r, s) in vals.items()},
           "p1_retro": retro,
           "n_violation_mutants": len(viol),
           "frac_violation_mutants_refused": round(
               sum(r for r, _ in viol.values()) / len(viol), 4),
           "n_valid_cases": len(vals),
           "frac_valid_cases_scored": round(sum(not r for r, _ in vals.values()) / len(vals), 4),
           "p1_retro_case_refused": 1.0 if retro["G4"]["refused"] else 0.0,
           "p1_g1_retro_refused_ungated": retro["G1_ungated"]["refused"],
           "n_corpus_results_rescored": checked,
           "n_corpus_verdict_diffs": len(diffs), "corpus_diffs": diffs,
           "coverage_trace": cov.record()}

    try:
        res["metric_check"] = self_exp.check_metrics(res)
        bad = sorted(n for n, dd in res["metric_check"].items() if not dd["usable"])
        if bad and not SMOKE:
            raise SystemExit(f"unresolvable gate metrics or coverage: {bad}")
        v = self_exp.score(res, smoke=SMOKE)
        res["verdict"], res["gates"] = v.verdict, v.gates
        res["coverage"] = v.coverage
        res["prereg_commit"] = v.prereg_commit
        res["gates_sha256"] = v.gates_sha256
    except BaseException as exc:
        res["verdict"] = f"UNSCORED__{type(exc).__name__}: {exc}"

    (HERE / f"protocol_v5_result{'_smoke' if SMOKE else ''}.json").write_text(
        json.dumps(res, indent=2) + "\n", encoding="utf-8")
    print(f"violations refused {res['frac_violation_mutants_refused']} of {len(viol)} | "
          f"valid scored {res['frac_valid_cases_scored']} of {len(vals)}")
    for k, (r, s) in viol.items():
        if not r:
            print(f"  MUTANT SURVIVED {k}: {s}")
    for k, (r, s) in vals.items():
        if r:
            print(f"  VALID REFUSED {k}: {s}")
    print(f"P1 retro G4: refused={retro['G4']['refused']} calls={retro['G4']['calls']}")
    print(f"P1 retro G1 (ungated): refused={retro['G1_ungated']['refused']} "
          f"calls={retro['G1_ungated']['calls']}")
    print(f"corpus: {checked} rescored, {len(diffs)} diffs")
    for d in diffs[:5]:
        print("  DIFF:", d)
    print(f"VERDICT: {res['verdict']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
