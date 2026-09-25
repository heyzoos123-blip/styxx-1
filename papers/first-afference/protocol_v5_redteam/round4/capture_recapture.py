"""EXPLORATORY, not preregistered: how many distinct findings did round 4 leave unfound?

Round 4 ran seven lenses against the same fixed implementation (v5e at 8b805e26). Each lens is a
sampling occasion and each distinct finding (a dedup cluster) is a "species". A finding reported by
several lenses was "recaptured". Ecology's incidence-based richness estimators apply to this setup
unchanged. Chao2 estimates the total number of distinct findings reachable by occasions like these from
Q1 (found by exactly one lens) and Q2 (found by exactly two):

    S_chao2 = S_obs + ((m-1)/m) * Q1*(Q1-1) / (2*(Q2+1))      (bias-corrected, m occasions)

The 95% interval uses Chao's (1987) log-normal construction around the undiscovered part f0.

Assumptions, and why the direction of the error is UNKNOWN (a first version of this script called the
estimate a lower bound; a verified attack on the round-4 finding showed that is not supported):
  * Closed population: v5e did not change during round 4. This holds.
  * Exchangeable occasions: they are NOT. Each lens was told to aim at its own region (identity,
    lifecycle, exam mutation, ...). A finding in a lens's home region is then caught mostly by that lens,
    which inflates singletons (Q1) relative to doubletons (Q2) and pushes the estimate UP.
  * Heterogeneity across findings, with exchangeable occasions, would make Chao2 a lower bound. That is
    the textbook case, and it is not this one.
  * Correct clustering: the dedup was an agent's judgement (candidates_and_dedup.json). A wrong merge
    turns a singleton into a doubleton and pushes the estimate DOWN.
  * Two populations: the confirmed findings are implementation findings AND exam holes (defects of the
    frozen exam, not of v5e). The pooled estimate mixes them, so each is also reported on its own; the
    implementation findings are the ones that decide shipping.
  * Findings, not verified findings: incidence is also counted over all 60 clusters.
The estimate is therefore a rough size for "not dry", not a bound, and not yet a stopping rule. A rule built
on it would first need a defined threshold and a check of the estimator on rounds whose totals are known.

Reads candidates_and_dedup.json and verdicts.json (next to this file). Writes capture_recapture.json.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def chao2(incidence: list[int], m: int) -> dict:
    s_obs = len(incidence)
    q = Counter(incidence)
    q1, q2 = q.get(1, 0), q.get(2, 0)
    a = (m - 1) / m
    f0 = a * q1 * (q1 - 1) / (2 * (q2 + 1))
    est = s_obs + f0
    # variance of the bias-corrected form (Chao 1987; Chao & Chiu 2016), q2 > 0 branch
    if q2 > 0:
        r = q1 / q2
        var = q2 * (a / 2 * r ** 2 + a ** 2 * r ** 3 + a ** 2 / 4 * r ** 4)
    else:
        var = a * q1 * (q1 - 1) / 2 + a ** 2 * q1 * (2 * q1 - 1) ** 2 / 4 - a ** 2 * q1 ** 4 / (4 * est)
    if f0 > 0:
        c = math.exp(1.96 * math.sqrt(math.log(1 + var / f0 ** 2)))
        lo, hi = s_obs + f0 / c, s_obs + f0 * c
    else:
        lo = hi = float(s_obs)
    return {"m_occasions": m, "s_obs": s_obs, "q1_singletons": q1, "q2_doubletons": q2,
            "incidence_frequencies": dict(sorted(q.items())),
            "chao2": round(est, 2), "estimated_unfound": round(f0, 2),
            "ci95": [round(lo, 2), round(hi, 2)],
            "estimated_unfound_ci95": [round(lo - s_obs, 2), round(hi - s_obs, 2)],
            "share_found": round(s_obs / est, 4) if est else None}


def main() -> int:
    cand = json.loads((HERE / "candidates_and_dedup.json").read_text(encoding="utf-8"))
    ver = json.loads((HERE / "verdicts.json").read_text(encoding="utf-8"))
    dd = cand["dedup"]
    fresh = set(dd["fresh_keys"])
    dup = {d["key"]: d["duplicate_of"] for d in dd["duplicates"]}

    def root(k):
        seen = set()
        while k not in fresh and k in dup and k not in seen:
            seen.add(k)
            k = dup[k]
        return k

    lenses = sorted({f["lens"] for f in cand["all"]})
    clusters: dict = defaultdict(set)
    for f in cand["all"]:
        clusters[root(f["key"])].add(f["lens"])
    assert set(clusters) == fresh, "every candidate must resolve to a fresh cluster"
    confirmed = {o["key"] for o in ver["reproducer_and_scope_judge"] if o["confirmed"]}
    confirmed |= {o["key"] for o in ver["exam_hole_verifiers"]
                  if o["mutant_survives_frozen_exam"] and o["witness_separates_mutant_from_original"]
                  and not o["equivalent_or_practically_equivalent"] and not o["refuted"]}
    sev = {f["key"]: f["severity"] for f in cand["fresh"]}
    for o in ver["reproducer_and_scope_judge"]:          # final severity is the scope judge's
        if o.get("scope"):
            sev[o["key"]] = o["scope"]["severity_final"]
    inc_all = [len(v) for v in clusters.values()]
    inc_conf = [len(v) for k, v in clusters.items() if k in confirmed]
    inc_module = [len(v) for k, v in clusters.items() if k in confirmed and sev[k] != "EXAM_HOLE"]
    inc_exam = [len(v) for k, v in clusters.items() if k in confirmed and sev[k] == "EXAM_HOLE"]
    res = {
        "what": "EXPLORATORY capture-recapture (incidence-based Chao2) over red-team round 4's seven lenses: "
                "a rough estimate, bias of unknown direction, of how many distinct findings those lenses left unfound",
        "generator": "papers/first-afference/protocol_v5_redteam/round4/capture_recapture.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "lenses": lenses,
        "all_clusters": chao2(inc_all, len(lenses)),
        "confirmed_only": chao2(inc_conf, len(lenses)),
        "confirmed_module_findings": chao2(inc_module, len(lenses)),
        "confirmed_exam_holes": chao2(inc_exam, len(lenses)),
        "per_cluster_lenses": {k: sorted(v) for k, v in sorted(clusters.items())},
        "reading": ("A rough size for 'not dry', with bias of unknown direction: specialised lenses push it up, "
                    "wrong dedup merges push it down. The implementation findings (the ones that decide shipping) "
                    "look less complete than the pooled number suggests. It is not a bound and not yet a stopping "
                    "rule; a rule would need a frozen threshold and a check on rounds with known totals."),
    }
    (HERE / "capture_recapture.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for k in ("all_clusters", "confirmed_only", "confirmed_module_findings", "confirmed_exam_holes"):
        r = res[k]
        print(f"{k:28s} S_obs {r['s_obs']:3d}  Q1 {r['q1_singletons']:2d} Q2 {r['q2_doubletons']:2d}  "
              f"Chao2 {r['chao2']:6.1f}  unfound {r['estimated_unfound']:5.1f}  95% CI {r['ci95']}  found {r['share_found']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
