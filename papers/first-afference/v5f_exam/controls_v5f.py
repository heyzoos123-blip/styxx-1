"""controls_v5f.py: G_SEM's positive controls, written by the exam author from the v5f text ("Positive controls").

Each control must come out as stated, or G_SEM is void. What this script can run, and what it cannot:

  #1 SM1 on v5e (the 63 round-4 census mutants on v5e's frozen exam; exactly 27 KILLED, the 36 listed SURVIVED).
     Needs v5e's implementation and `protocol_v5_redteam/round4_exam_mutation/mutants.py`, both outside the
     exam author's read scope: NOT RUN (SPEC_GAPS.md GAP-53). --v5e and --census are accepted, and the run is
     refused with that reason rather than guessed.
  #2 SM2 on v5e (instruments (a) and (d); EXAM_HOLE > 0). Needs v5e: NOT RUN (GAP-53).
  #3 the crash sweep on v5e through a v5e adapter (>= 1 non-clean point on 3.12 and 3.13). Needs v5e: NOT RUN (GAP-53).
  #4 G_SIG: (a) v5e leaking on 3.12 and 3.13: needs v5e, NOT RUN (GAP-53); (b) H8's publish-at-entry mutant
     must fail G_SIG on 3.12: RUN here (sigflood_v5f.py on ref_v5f.py + the H8 patch, the credit cell).
  #5 G_REF blind shapes: a planted blind-shape emission must be caught by G_HYG for each of the 8 shapes of
     `mutation_gate_blindspots.json`. That file is outside the read scope (GAP-51); this script runs
     refcensus_v5f.py's planted shapes (the ones the text names in G_HYG) and reports each as caught or not,
     and reports the control as INCOMPLETE until the 8 shapes are listed.

Usage: python controls_v5f.py [--seconds 10] [--out RESULT.json] [--deps DIR]
"""
import json, os, runpy, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ARGV = list(sys.argv)


def _opt(n, d=None):
    return ARGV[ARGV.index(n) + 1] if n in ARGV else d


REF = os.path.join(HERE, "ref_v5f.py")


def patched(patches):
    s = open(REF, encoding="utf-8").read()
    for a, b in patches:
        if s.count(a) != 1:
            raise SystemExit(f"a control's patch does not apply exactly once: {a[:60]!r}")
        s = s.replace(a, b)
    d = tempfile.mkdtemp(prefix="v5f_ctl_")
    p = os.path.join(d, "ref_v5f.py")
    open(p, "w", encoding="utf-8").write(s)
    return p


def control4b(seconds):
    haz = runpy.run_path(os.path.join(HERE, "tools", "runner_mutants_v5f.py"), run_name="runner_mutants")["HAZ"]
    impl = patched(haz["mut_h8_publish_at_entry"][1])
    out = impl + ".sig.json"
    r = subprocess.run([sys.executable, os.path.join(HERE, "sigflood_v5f.py"), "--impl", impl, "--seconds", str(seconds),
                        "--out", out], capture_output=True, text=True, timeout=3600)
    try:
        d = json.load(open(out))
    except (OSError, ValueError):
        return {"status": "FIRED", "why": f"sigflood produced no result (rc {r.returncode})"}
    failed = {k: c["fails"][:3] for k, c in d["cells"].items() if c.get("fails")}
    return {"status": "FIRED" if d.get("G_SIG") != "PASS" else "DID_NOT_FIRE", "G_SIG": d.get("G_SIG"),
            "failed_cells": failed, "python": d.get("python")}


def control5():
    out = tempfile.mktemp(suffix=".json")
    subprocess.run([sys.executable, os.path.join(HERE, "refcensus_v5f.py"), "--impl", REF, "--controls", "--out", out],
                   capture_output=True, text=True, timeout=1800)
    d = json.load(open(out))
    bc = d.get("G_REF_blind_controls", {})
    return {"status": "INCOMPLETE (GAP-51: the 8 shapes of mutation_gate_blindspots.json are not listed in the text)",
            "planted": {k: {"caught": v.get("caught"), "by": v.get("by")} for k, v in bc.items()},
            "all_planted_caught": bool(bc) and all(v.get("caught") for v in bc.values())}


def main():
    t0 = time.monotonic()
    v5e = _opt("--v5e")
    blocked = {"status": "NOT_RUN", "gap": "GAP-53",
               "why": "needs v5e's implementation (and, for #1, the round-4 census mutants), outside the exam "
                      "author's read scope" + (f"; --v5e {v5e} was given and is not used" if v5e else "")}
    res = {"python": sys.version.split()[0], "impl": "ref_v5f.py",
           "control_1_sm1_on_v5e": blocked, "control_2_sm2_on_v5e": blocked, "control_3_crash_sweep_on_v5e": blocked,
           "control_4a_gsig_v5e_leaks": blocked}
    if tuple(sys.version_info[:3]) == (3, 12, 3):
        res["control_4b_h8_fails_gsig_on_3_12"] = control4b(float(_opt("--seconds", "10")))
    else:
        res["control_4b_h8_fails_gsig_on_3_12"] = {"status": "NOT_APPLICABLE", "why": "the text states it for 3.12"}
    res["control_5_blind_shapes"] = control5()
    runnable_ok = (res["control_4b_h8_fails_gsig_on_3_12"]["status"] in ("FIRED", "NOT_APPLICABLE")
                   and res["control_5_blind_shapes"]["all_planted_caught"])
    res["verdict"] = ("INCOMPLETE: the runnable controls fire; #1-#3, #4(a) not run (GAP-53), #5 short of the "
                      "8 listed shapes (GAP-51)") if runnable_ok else "FAIL: a runnable control did not fire"
    res["seconds"] = round(time.monotonic() - t0, 1)
    if _opt("--out"):
        json.dump(res, open(_opt("--out"), "w"), indent=1)
    print(json.dumps(res, indent=1)[:3000])
    return 0 if runnable_ok else 1


if __name__ == "__main__":
    sys.exit(main())
