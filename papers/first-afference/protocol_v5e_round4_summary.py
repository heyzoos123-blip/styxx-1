"""The protocol v5 arc through red-team round 4, measured from the committed receipts.

This script derives every number the v5e round-4 finding states from the receipts that hold it, so
the finding can be certified against numeric leaves instead of numbers copied into prose. It adds
one measurement of its own: it re-runs the round-4 closure-audit battery
(``protocol_v5_redteam/round4/closure-audit/r1/held_battery.py``) on each available interpreter and
records how many of the rebuilt round-1..3 attacks held.

Inputs, all committed: the v5 family's result receipts, ``protocol_v5_redteam_audit.json`` (rounds
1-4), the frozen mutation gate's receipt, its positive control on v5d, the blind-spot probe, the
fuzzer controls, the aux result, the exploratory N-version cross-version receipt, and the round-4
semantic-mutation census. Writes ``protocol_v5e_round4_summary.json``.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE / "protocol_v5e_round4_summary.json"
BATTERY = HERE / "protocol_v5_redteam" / "round4" / "closure-audit" / "r1" / "held_battery.py"
PYTHONS = [sys.executable] + [
    f"/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt3/venv3.{v}/bin/python"
    for v in (10, 12, 13)]


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def battery() -> dict:
    per = {}
    for py in PYTHONS:
        if not Path(py).exists() and py != sys.executable:
            continue
        v = subprocess.run([py, "-c", "import sys;print(sys.version.split()[0])"],
                           capture_output=True, text=True).stdout.strip()
        p = subprocess.run([py, str(BATTERY)], capture_output=True, text=True, timeout=600,
                           env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"}, cwd=BATTERY.parent)
        m = re.search(r"^(\d+)/(\d+) held$", p.stdout, re.M)
        per[v] = {"held": int(m.group(1)) if m else 0, "cases": int(m.group(2)) if m else 0,
                  "exit": p.returncode}
    return per


def main() -> int:
    audit = load("protocol_v5_redteam_audit.json")
    r4 = audit["round_4"]
    e = load("protocol_v5e_result.json")
    aux = load("protocol_v5e_aux_result.json")
    mg = load("run_protocol_v5e_mutation_gate.json")
    ctl = load("mutation_gate_control_v5d.json")
    blind = load("mutation_gate_blindspots.json")
    fz = load("protocol_v5e_fuzz_controls.json")
    nvx = load("protocol_v5e_nversion_crossversion_exploratory.json")
    census = json.loads((HERE / "protocol_v5_redteam" / "round4_exam_mutation" /
                         "semantic_mutation_census.json").read_text(encoding="utf-8"))
    arc = {
        "v5_attempt_a": load("protocol_v5_result_run1.json")["verdict"],
        "v5b": load("protocol_v5b_result.json")["verdict"],
        "v5c": load("protocol_v5c_result.json")["verdict"],
        "v5d": load("protocol_v5d_result.json")["verdict"],
        "v5e": e["verdict"],
        "v5e_aux": aux["verdict"],
    }
    rounds = {r: {"n_blockers": len(audit[r]["module_red_team"]["blockers"]),
                  "n_defects": len(audit[r]["module_red_team"]["defects"])}
              for r in ("round_1", "round_2", "round_3")}
    rounds["round_1"]["n_exam_defects"] = len(audit["round_1"]["exam_audit"]["defects"])
    for r in ("round_2", "round_3"):
        ex = audit[r]["exam_mutation_audit"]
        rounds[r]["n_exam_survivors_blocker_class"] = len(ex["survivors_blocker_class"])
        rounds[r]["n_exam_defects"] = len(ex["defects"])
    names = re.findall(r'@case\("([^"]+)"', BATTERY.read_text(encoding="utf-8"))
    blocker_rows = [n for n in names if re.match(r"R[123]-B\d", n)]
    battery_composition = {
        "n_cases": len(names), "n_blocker_cases": len(blocker_rows),
        "n_other_cases": len(names) - len(blocker_rows),
        "n_blocker_classes_covered": len({n.split()[0] for n in blocker_rows}),
        "blockers_with_variants": sorted({n.split()[0] for n in blocker_rows if n.split()[1] == "v:"}),
    }
    battery_composition["n_blockers_with_variants"] = len(battery_composition["blockers_with_variants"])
    fi = load("fault_injection_v5_result.json")
    cr = json.loads((HERE / "protocol_v5_redteam" / "round4" / "capture_recapture.json").read_text(encoding="utf-8"))
    bn = json.loads((HERE / "protocol_v5_redteam" / "round4" / "blockers_against_nversion.json").read_text(encoding="utf-8"))
    bat = battery()
    held_everywhere = all(b["held"] == b["cases"] and b["cases"] > 0 for b in bat.values())
    res = {
        "what": "numbers for FINDING_protocol_v5e_round4, derived from the committed receipts; the closure "
                "battery is re-run here on every available interpreter",
        "generator": "papers/first-afference/protocol_v5e_round4_summary.py",
        "generator_sha256": sha(Path(__file__)),
        "arc_verdicts": arc,
        "prior_rounds": rounds,
        "prior_rounds_total_blockers": sum(r["n_blockers"] for r in rounds.values()),
        "v5e_exam": {
            "n_gates": len(e["gates"]), "n_gates_passed": sum(bool(v) for v in e["gates"].values()),
            "n_violation_cases": e["n_violation_cases"], "n_valid_cases": e["n_valid_cases"],
            "n_residual_cases": e["n_residual_cases"],
            "frac_violation_cases_refused_with_expected_code": e["frac_violation_cases_refused_with_expected_code"],
            "frac_valid_cases_exact": e["frac_valid_cases_exact"],
            "frac_residuals_as_documented": e["frac_residuals_as_documented"],
            "h2_propagated": e["h2_propagated"], "h2_n_cases": e["hazards"]["H2"]["n"],
            "h3_keyboard_interrupt_ok": e["h3_ok"], "h3_keyboard_interrupt_n_cases": e["hazards"]["H3"]["n"],
            "h1_hangs": e["h1_hangs"],
            "n_pairable_results": e["n_pairable_results"],
            "n_v4_v5_outcome_disagreements": e["n_v4_v5_outcome_disagreements"],
            "n_results_v5_scored": e["n_results_v5_scored"],
        },
        "aux": {"n_gates": len(aux["gates"]), "n_gates_passed": sum(bool(v) for v in aux["gates"].values()),
                "fuzz_n_programs": aux["fuzz_n_programs"],
                "fuzz_oracle_disagreements": aux["fuzz_oracle_disagreements"],
                "fuzz_control_no_cut_disagreements": aux["fuzz_control_no_cut_disagreements"],
                "nversion_trace_diffs": aux["nversion_trace_diffs"],
                "crossversion_n_versions": aux["crossversion_n_versions"],
                "crossversion_diffs": aux["crossversion_diffs"],
                "crossversion_n_version_keyed_cases_skipped": len(aux["crossversion_detail"]["version_keyed_skipped"])},
        "all_frozen_gates": {"n": len(e["gates"]) + len(aux["gates"]),
                             "passed": sum(bool(v) for v in e["gates"].values()) +
                                       sum(bool(v) for v in aux["gates"].values())},
        "nversion_exploratory": {"n_versions": nvx["n_versions"], "n_versions_clean": nvx["n_versions_clean"],
                                 "n_cells_clean_both_impls": nvx["n_versions_clean"] + aux["crossversion_n_versions"]},
        "fuzzer_controls": {
            "v1_no_cut_programs": fz["first_version"]["C1_no_cut"]["fuzz_n_programs"],
            "v1_no_cut_disagreements": fz["first_version"]["C1_no_cut"]["fuzz_oracle_disagreements"],
            "final_programs": fz["final_version"]["C1_no_cut"]["fuzz_n_programs"],
            "final_no_cut": fz["final_version"]["C1_no_cut"]["fuzz_oracle_disagreements"],
            "final_credit_any_open": fz["final_version"]["C2_credit_any_open"]["fuzz_oracle_disagreements"],
            "final_no_mint": fz["final_version"]["C3_no_mint"]["fuzz_oracle_disagreements"]},
        "mutation_gate": {"n_sites": mg["n_refusal_sites"], "n_detected": mg["n_mutants_detected"],
                          "n_hygiene_violations": mg["n_hygiene_violations"],
                          "v5d_control_sites": ctl["n_refusal_sites"], "v5d_control_detected": ctl["n_mutants_detected"],
                          "v5d_control_hygiene_violations": ctl["n_hygiene_violations"],
                          "blind_shapes": blind["n_blind_shapes"], "shapes_probed": len(blind["shapes"]) - 3,
                          "coded_literals_in_impl": blind["census"]["coded_literals"],
                          "coded_literals_outside_sites": blind["n_coded_literals_outside_every_site"]},
        "semantic_census": {"n_mutants": census["n_applied"], "n_detected": census["n_detected"],
                            "n_survived": census["n_survived"], "baseline_clean": census["baseline_clean"]},
        "round_4": {"n_lenses": len(r4["method"]["lenses"]), "n_candidates": r4["method"]["n_candidates"],
                    "n_after_dedup": r4["method"]["n_after_dedup"], "n_confirmed": r4["n_confirmed"],
                    "n_not_confirmed": r4["n_not_confirmed"], **{f"n_{k.lower()}": v for k, v in r4["counts_confirmed"].items()},
                    "dry": r4["dry"]},
        "closure_battery_composition": battery_composition,
        "fault_injection": {"n_fault_points": fi["n_fault_points"], "n_not_clean": fi["n_not_clean"],
                            "n_scenarios": len(fi["scenarios"]), **{f"n_{k.lower()}": v for k, v in fi["totals"].items()},
                            "python": fi["python"]},
        "capture_recapture": {k: {"s_obs": cr[k]["s_obs"], "chao2": cr[k]["chao2"],
                                  "estimated_unfound": cr[k]["estimated_unfound"],
                                  "ci95_low": cr[k]["ci95"][0], "ci95_high": cr[k]["ci95"][1],
                                  "share_found": cr[k]["share_found"]}
                              for k in ("all_clusters", "confirmed_only", "confirmed_module_findings", "confirmed_exam_holes")},
        "blockers_vs_nversion": {"n_blockers": bn["n_blockers"],
                                 "n_reproduced_on_primary": bn["n_blockers_reproduced_on_primary"],
                                 "n_reproduced_on_nversion": bn["n_blockers_reproduced_on_nversion"],
                                 "same_versions_every_blocker": all(v["primary"] == v["nversion"] for v in bn["reproduced_on"].values())},
        "round_4_surfaced_unverified": r4.get("n_surfaced_unverified", 0),
        "closure_battery": bat,
        "closure_battery_n_versions": len(bat),
        "closure_battery_cases": max((b["cases"] for b in bat.values()), default=0),
        "closure_battery_held_on_every_version": held_everywhere,
    }
    OUT.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("all_frozen_gates", "round_4", "closure_battery", "semantic_census")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
