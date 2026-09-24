"""How often an HONEST null breaches the open-set read's G-O2 bar -- a false-alarm rate, from the
committed receipt's own sizes. Read-only; writes only ``open_set_read_null_arithmetic.json``.

Assumptions, stated because the numbers depend on them: the null's IN and OOV margins are
exchangeable (so AUROC is centred on 0.5 with the Mann-Whitney variance, no ties), the normal
approximation holds at these sizes, and for the any-of-three figure the three targets are
independent -- they are not (all three share one split), so that figure is indicative only.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    rec = json.loads((HERE / "open_set_read_result.json").read_text(encoding="utf-8"))
    n_in, n_oov = int(rec["n_candidates"]), int(rec["n_oov"])
    bar = 0.55
    sd = math.sqrt((n_in + n_oov + 1) / (12.0 * n_in * n_oov))
    z = (bar - 0.5) / sd
    p_single = 0.5 * math.erfc(z / math.sqrt(2.0))
    p_any_3 = 1.0 - (1.0 - p_single) ** 3
    null = {t: rec["targets"][t]["auroc_margin_null_mapper"] for t in sorted(rec["targets"])}
    out = {
        "script": "papers/disjoint-worlds/open_set_read_null_arithmetic.py",
        "assumptions": ["IN and OOV null margins exchangeable (AUROC centred on 0.5)",
                        "Mann-Whitney variance without ties", "normal approximation",
                        "any-of-three figure assumes independent targets; they share one split"],
        "n_candidates": n_in, "n_oov": n_oov, "bar": bar,
        "null_auroc_sd": round(sd, 4),
        "bar_in_null_sd_units": round(z, 4),
        "false_alarm_rate_single_target": round(p_single, 4),
        "false_alarm_rate_any_of_three_if_independent": round(p_any_3, 4),
        "substituted_null_auroc": null,
        "substituted_null_mean_all_three_targets": round(sum(null.values()) / len(null), 4),
        "substituted_null_targets_above_bar": sorted(t for t, v in null.items() if v > bar),
    }
    (HERE / "open_set_read_null_arithmetic.json").write_text(json.dumps(out, indent=2) + "\n",
                                                             encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "assumptions"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
