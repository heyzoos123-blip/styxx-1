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
if HERE not in sys.path:
    sys.path.append(HERE)
import v5f_tmp      # noqa: E402  temp dirs removed at exit; each child's TMPDIR removed when it returns


def _opt(n, d=None):
    return ARGV[ARGV.index(n) + 1] if n in ARGV else d


REF = os.path.join(HERE, "ref_v5f.py")


def patched(patches):
    s = open(REF, encoding="utf-8").read()
    for a, b in patches:
        if s.count(a) != 1:
            raise SystemExit(f"a control's patch does not apply exactly once: {a[:60]!r}")
        s = s.replace(a, b)
    d = v5f_tmp.workdir("v5f_ctl_")
    p = os.path.join(d, "ref_v5f.py")
    open(p, "w", encoding="utf-8").write(s)
    return p


def control4b(seconds):
    haz = runpy.run_path(os.path.join(HERE, "tools", "runner_mutants_v5f.py"), run_name="runner_mutants")["HAZ"]
    impl = patched(haz["mut_h8_publish_at_entry"][1])
    out = impl + ".sig.json"
    r = v5f_tmp.child_run([sys.executable, os.path.join(HERE, "sigflood_v5f.py"), "--impl", impl, "--seconds", str(seconds),
                           "--out", out], capture_output=True, text=True, timeout=3600)
    try:
        d = json.load(open(out))
    except (OSError, ValueError):
        return {"status": "FIRED", "why": f"sigflood produced no result (rc {r.returncode})"}
    failed = {k: c["fails"][:3] for k, c in d["cells"].items() if c.get("fails")}
    return {"status": "FIRED" if d.get("G_SIG") != "PASS" else "DID_NOT_FIRE", "G_SIG": d.get("G_SIG"),
            "failed_cells": failed, "python": d.get("python")}


def control4a(seconds):
    """Positive control #4 (a): G_SIG's lock cell on the v5e blob must show leaks on 3.12 and 3.13. v5e has no
    _v5_state(), so the cell's poison test does not run there (SPEC_GAPS, Revision 13 follow-ups)."""
    work = v5f_tmp.workdir("v5f_ctl4a_")
    impl = os.path.join(v5e_package(os.path.join(work, "v5e")), "styxx", "protocol.py")
    out = os.path.join(work, "sig.json")
    r = v5f_tmp.child_run([sys.executable, os.path.join(HERE, "sigflood_v5f.py"), "--impl", impl, "--cells", "lock",
                           "--seconds", str(seconds), "--out", out], capture_output=True, text=True, timeout=3600)
    try:
        d = json.load(open(out))
    except (OSError, ValueError):
        return {"status": "DID_NOT_FIRE", "why": f"sigflood produced no result (rc {r.returncode}): {r.stderr[-300:]}"}
    c = d["cells"]["lock"]
    leaked = c.get("leaks", 0) > 0 or bool(c.get("held_at_end"))
    return {"status": "FIRED" if leaked else "DID_NOT_FIRE", "v5e_blob": V5E_COMMIT, "leaks": c.get("leaks"),
            "work": c.get("work"), "held_at_end": c.get("held_at_end"), "poison": c.get("diff"),
            "python": d.get("python"), "seconds": seconds}


V5E_ADAPTER = '''"""controls_v5f.py's v5e adapter (positive control #3): the v5e blob, re-exported, with the fault points and
a _v5_state()-shaped view of its registries that the text names. Fields v5e does not have read as constants
equal to their S0 values (cut, cut_current, tool, tool_ours, global_events; and guard, which the text does not
list)."""
import importlib.util as _u, os as _os, sys as _sys
_spec = _u.spec_from_file_location("v5e_protocol", _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "styxx", "protocol.py"))
_v5e = _u.module_from_spec(_spec)
_sys.modules["v5e_protocol"] = _v5e
_spec.loader.exec_module(_v5e)
for _k in dir(_v5e):
    if not _k.startswith("__"):
        globals()[_k] = getattr(_v5e, _k)


def _v5_faultpoints():
    T = _v5e._CoverageTracer
    return {"_CoverageTracer.__enter__": T.__enter__.__code__, "_CoverageTracer.__exit__": T.__exit__.__code__,
            "_open": T._open.__code__, "_close": T._close.__code__, "run": T.run.__code__,
            "record": T.record.__code__, "_hook": _v5e._hook.__code__, "_resolve_target": _v5e._resolve_target.__code__}


def _v5_state():
    mints = []
    for m in list(_v5e._MINTED.values()):
        mints.append({"target": f"{m.fn.__module__}:{m.fn.__qualname__}", "holders": len(m.tracers),
                      "installed": m.fn.__code__ is m.code, "local_events": 0, "pending": 0})
    mints.sort(key=lambda x: x["target"])
    return {"mints": mints, "anchors": len(_v5e._ANCHORS), "by_fn": len(_v5e._BY_FN), "threads": len(_v5e._THREADS),
            "active": _v5e._ACTIVE, "guard": "free", "cut": 0, "cut_current": True, "tool": None, "tool_ours": False,
            "global_events": 0, "pid": _os.getpid()}
'''


def control3():
    """Positive control #3: crash_sweep_v5f.py on the v5e blob through the adapter above; at least one non-clean point.
    The sweep's callbacks scenario faults v5f's callback-only functions, which v5e does not have, so it is not run
    (SPEC_GAPS, Revision 13 follow-ups)."""
    work = v5f_tmp.workdir("v5f_ctl3_")
    v5e_package(os.path.join(work, "v5e"))
    adapter = os.path.join(work, "v5e", "v5e_adapter.py")
    open(adapter, "w").write(V5E_ADAPTER)
    out = os.path.join(work, "sweep.json")
    scen = "single,two_thread,run_async,generator,hop,background,fork"
    r = v5f_tmp.child_run([sys.executable, os.path.join(HERE, "crash_sweep_v5f.py"), "--impl", adapter, "--scenario", scen,
                           "--out", out], capture_output=True, text=True, timeout=14400)
    try:
        d = json.load(open(out))
    except (OSError, ValueError):
        return {"status": "DID_NOT_FIRE", "why": f"the sweep produced no result (rc {r.returncode}): {r.stderr[-400:]}"}
    unclean = {}
    for sc, roles in d["scenarios"].items():
        for role, x in roles.items():
            if isinstance(x, dict) and (x.get("n_unclean") or "void" in x):
                unclean[f"{sc}/{role}"] = {"n_unclean": x.get("n_unclean"), "void": x.get("void"),
                                           "first": (x.get("unclean") or [None])[0]}
    return {"status": "FIRED" if any(v["n_unclean"] for v in unclean.values()) else "DID_NOT_FIRE",
            "v5e_blob": V5E_COMMIT, "python": d.get("python"), "G_FI": d.get("G_FI"), "unclean": unclean,
            "scenarios": scen, "seconds": d.get("seconds")}


def control5():
    out = os.path.join(v5f_tmp.workdir("v5f_ctl_"), "refcensus.json")
    v5f_tmp.child_run([sys.executable, os.path.join(HERE, "refcensus_v5f.py"), "--impl", REF, "--controls", "--out", out],
                      capture_output=True, text=True, timeout=1800)
    d = json.load(open(out))
    bc = d.get("G_REF_blind_controls", {})
    return {"status": "INCOMPLETE (GAP-51: the 8 shapes of mutation_gate_blindspots.json are not listed in the text)",
            "planted": {k: {"caught": v.get("caught"), "by": v.get("by")} for k, v in bc.items()},
            "all_planted_caught": bool(bc) and all(v.get("caught") for v in bc.values())}


# ---------------------------------------------------------------------------------------------------
# v5e (revision 13, GAP-53): the blob of commit 8b805e26 and its frozen runner, run as they are
# ---------------------------------------------------------------------------------------------------
V5E_COMMIT = "8b805e26"
V5E_SHA256 = "c720250c209bd8facd75d2e7b52e7667ec39743f6c38cab2f3d64c5d1cefa7d9"
DESIGN = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(DESIGN))
V5E_RUNNER = os.path.join(DESIGN, "run_protocol_v5e.py")
V5E_RUNNER_SHA256 = "ef4b4f668bca0b8f72b500dd103d0318786f7e5fc2916b1250f9926287ea3f52"
SPEC13 = os.path.join(DESIGN, "protocol_v5f_design", "rev13", "spec_data")


def _sha(p):
    import hashlib
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def v5e_package(dest):
    """styxx/ as of commit 8b805e26 (git archive), so that protocol.py is the v5e blob, never the working tree."""
    os.makedirs(dest, exist_ok=True)
    a = subprocess.run(["git", "-C", REPO_ROOT, "archive", V5E_COMMIT, "styxx"], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", dest], input=a.stdout, check=True)
    got = _sha(os.path.join(dest, "styxx", "protocol.py"))
    if got != V5E_SHA256:
        raise SystemExit(f"v5e blob sha256 {got} is not {V5E_SHA256}")
    return dest


def census_table():
    """The 63 census mutants (spec data, round4_exam_mutation/mutants.py), as the census script reads them."""
    g = runpy.run_path(os.path.join(SPEC13, "round4_exam_mutation", "mutants.py"), run_name="mutants")
    out = {}
    for name in sorted(k for k in g if k.startswith("MUTANTS")):
        for key, reps in g[name].items():
            out[key] = reps
    return out


def v5e_exam_run(pkg_root, py, timeout=600):
    """One run of v5e's frozen exam in its mutation mode, judged as the census judges it: detected iff the run
    exits non-zero, times out or writes no result, or any violation, valid or residual case is not ok, the P1
    retro is not exact, or a case crashes."""
    out = os.path.join(pkg_root, "result.json")
    if os.path.exists(out):
        os.remove(out)
    env = dict(os.environ, STYXX_V5_IMPORT_ROOT=pkg_root, STYXX_V5_RESULT_OUT=out, PYTHONDONTWRITEBYTECODE="1")
    try:
        p = v5f_tmp.child_run([py, V5E_RUNNER, "--smoke", "--full-battery", "--mutation-mode"], cwd=REPO_ROOT, env=env,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return True, ["timeout"]
    v5f_tmp.check_child(p.stderr, pkg_root)
    if p.returncode != 0 or not os.path.exists(out):
        return True, [f"exit {p.returncode}: {p.stderr.strip()[-160:]}"]
    r = json.load(open(out))
    how = []
    for fam in ("violation_cases", "valid_cases", "residual_cases"):
        bad = sorted(k for k, v in (r.get(fam) or {}).items() if not v.get("ok"))
        if bad:
            how.append(f"{fam}: {bad[:10]}")
    if r.get("p1_retro_exact") != 1.0:
        how.append("p1_retro")
    if r.get("n_crashes"):
        how.append(f"{r['n_crashes']} crashes")
    return bool(how), how


def control1(py, journal, jobs=3):
    """Positive control #1 (SM1 on v5e): every census mutant applied to the v5e blob, v5e's frozen exam run twice in
    its mutation mode; KILLED iff some case fails on both runs, SURVIVED iff none fails on either (otherwise
    NONREPRODUCIBLE). Passes iff exactly the census's 27 are KILLED and its 36 survivors SURVIVED."""
    import concurrent.futures as cf, shutil, threading
    if _sha(V5E_RUNNER) != V5E_RUNNER_SHA256:
        raise SystemExit("run_protocol_v5e.py is not the census's runner")
    census = json.load(open(os.path.join(SPEC13, "round4_exam_mutation", "semantic_mutation_census.json")))
    table = census_table()
    done = {}
    if os.path.exists(journal):
        for ln in open(journal):
            d = json.loads(ln)
            if d.get("python") == sys.version.split()[0] or d.get("py") == py:
                done[d["mutant"]] = d
    lock = threading.Lock()
    work = v5f_tmp.workdir("v5f_ctl1_")
    base = v5e_package(os.path.join(work, "_blob"))

    def one(item):
        name, reps = item
        v5f_tmp.disk_guard(what=name)
        src = open(os.path.join(base, "styxx", "protocol.py"), encoding="utf-8").read()
        for a, b in reps:
            if src.count(a) != 1:
                row = {"mutant": name, "class": "NOT_APPLIED", "why": f"anchor found {src.count(a)} times"}
                break
            src = src.replace(a, b)
        else:
            d = os.path.join(work, name)
            shutil.copytree(base, d)
            if reps:
                open(os.path.join(d, "styxx", "protocol.py"), "w", encoding="utf-8").write(src)
            runs = [v5e_exam_run(d, py) for _ in range(2)]
            shutil.rmtree(d, ignore_errors=True)
            det = [r[0] for r in runs]
            cls = "KILLED" if all(det) else ("SURVIVED" if not any(det) else "NONREPRODUCIBLE")
            row = {"mutant": name, "class": cls, "how": [r[1][:3] for r in runs]}
        row["py"] = py
        with lock, open(journal, "a") as fh:
            fh.write(json.dumps(row) + "\n")
        print("control #1", name, row["class"], flush=True)
        return row
    todo = [("__baseline__", [])] + sorted(table.items())
    with cf.ThreadPoolExecutor(jobs) as ex:
        list(ex.map(one, [x for x in todo if x[0] not in done]))
    rows = {}
    for ln in open(journal):
        d = json.loads(ln)
        if d.get("py") == py:
            rows[d["mutant"]] = d
    want_surv = set(census["survivors"])
    want_kill = {r["mutant"] for r in census["rows"] if r["detected"]}
    killed = {k for k, r in rows.items() if r["class"] == "KILLED" and k != "__baseline__"}
    surv = {k for k, r in rows.items() if r["class"] == "SURVIVED" and k != "__baseline__"}
    res = {"python": py, "v5e_blob": V5E_COMMIT, "v5e_sha256": V5E_SHA256, "runner_sha256": V5E_RUNNER_SHA256,
           "baseline": rows.get("__baseline__", {}).get("class"), "mutants": len(table),
           "killed": len(killed), "survived": len(surv),
           "killed_not_in_census": sorted(killed - want_kill), "census_killed_not_killed": sorted(want_kill - killed),
           "survived_not_in_census": sorted(surv - want_surv), "census_survivors_not_survived": sorted(want_surv - surv),
           "other": {k: r["class"] for k, r in rows.items() if r["class"] not in ("KILLED", "SURVIVED")}}
    res["status"] = ("FIRED" if res["baseline"] == "SURVIVED" and killed == want_kill and surv == want_surv
                     and len(rows) == len(table) + 1 else "DID_NOT_FIRE")
    return res


def main():
    t0 = time.monotonic()
    if "--control1" in ARGV:
        r = control1(_opt("--py", "/usr/bin/python3.11"), _opt("--journal"), int(_opt("--jobs", "3")))
        if _opt("--out"):
            json.dump(r, open(_opt("--out"), "w"), indent=1)
        print(json.dumps(r, indent=1))
        return 0 if r["status"] == "FIRED" else 1
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
    try:
        sys.exit(main())
    finally:
        v5f_tmp.cleanup()
