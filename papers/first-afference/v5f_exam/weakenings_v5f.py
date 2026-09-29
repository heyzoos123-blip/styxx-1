"""weakenings_v5f.py: the SM1 catalog (G_SEM), and SM1's admission and kill procedure.

Each entry is an exact-once text patch against ref_v5f.py and carries: the rule (the Mutation-audit row it
weakens, or the rule the text names), the operator family, the NAMED witness (a runner case id, or a crash-
sweep invariant as "G_FI:C<n>"), the witness's spec outcome, its weakened outcome, and the versions it
applies to.

SM1 (computed at freeze time on ref_v5f.py; "SM1: catalog power"):
  admission on a version: (1) the patch applies exactly once; (2) the named witness scores the spec outcome
  on unpatched ref_v5f.py; (3) under ref+W the witness's observable outcome differs from the spec outcome.
  Every run is a fresh process (the runner's --mutation CASE), made twice; a row counts only when both runs
  agree, else NONREPRODUCIBLE (not killed). An admitted row is KILLED iff its named witness fails on ref+W
  (here, in isolation, condition 3 and the kill test are the same run). A row failing (3) is UNWITNESSED.
  Crash-sweep rows: the witness is crash_sweep_v5f.py on ref+W; KILLED iff the named invariant is among its
  failures, WITNESS_MISMATCH if only others are.
  Gate: 100% of admitted rows KILLED on every version they are admitted for.

Usage: python weakenings_v5f.py --sm1 PY312 PY313 [--only id,id] [--out sm1_result.json]
       python weakenings_v5f.py --list
"""
import json, os, runpy, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
REF_PATH = os.path.join(HERE, "ref_v5f.py")
REF = open(REF_PATH, encoding="utf-8").read()
V = ("3.12.3", "3.13.12")

_smoke = runpy.run_path(os.path.join(HERE, "tools", "mutants_v5f.py"), run_name="mutants")
_haz = runpy.run_path(os.path.join(HERE, "tools", "runner_mutants_v5f.py"), run_name="runner_mutants")

CATALOG = []


def row(id, rule, family, witness, spec, weakened, patches, versions=V, note=""):
    CATALOG.append({"id": id, "rule": rule, "family": family, "witness": witness, "spec_outcome": spec,
                    "weakened_outcome": weakened, "versions": list(versions), "patches": patches, "note": note})


# ---- the rows the exam author wrote for revisions 9-12 (tools/mutants_v5f.py), each with its witness ------
AUDIT_ROW = {
    "mut_end_type_not_tested": ("exact type before hash in BAD_TRACE (`end`)", "types"),
    "mut_no_unwind_lost_flag": ("unwind scope: `UNWIND_LOST` at close", "deletion"),
    "mut_no_unwind_on_in_commit": ("revision 5: `_unwind_on` deleted from `_commit`", "deletion"),
    "mut_gle_calltime": ("revision 9: `get_local_events` read from `sys.monitoring` at call time", "scope"),
    "mut_gle_nocheck": ("revision 9: bound as `_MON[0][6]` but not checked", "deletion"),
    "mut_grl_nocheck": ("revision 9: `_get_running_loop` not checked", "deletion"),
    "mut_order_cut_first": ("revision 9: exit problems in another order (CUT_MOVED before CLONE_ALIVE)", "order"),
    "mut_order_swapped_first": ("revision 9: exit problems in another order (the transaction's texts before X4's)", "order"),
    "mut_sec_repr": ("revision 10: a non-str section rendered by repr() at step 3", "types"),
    "mut_sec_attrqual": ("revision 10: a non-str section's type name by type(x).__qualname__ at step 3", "types"),
    "mut_inactive_repr": ("revision 10: at step 2 (repr)", "types"),
    "mut_inactive_attrqual": ("revision 10: at step 2 (type(x).__qualname__)", "types"),
    "mut_notrace1_attrqual": ("revision 10: in NO_TRACE's first text", "types"),
    "mut_notrace3_attrqual": ("revision 10: in NO_TRACE's third text", "types"),
    "mut_stamp_attrqual": ("revision 10: in step 4's stamp type", "types"),
    "mut_callee_none_text": ("revision 10: step 4's callee-None text changed", "constants"),
    "mut_nested_mirror": ("revision 10: the NESTED walk stopping at a foreign-loop anchor", "conditions"),
    "mut_grl_check_once": ("revision 10: `_get_running_loop` checked only while unbound", "conditions"),
    "mut_bind_before_asyncio": ("revision 10: `_MON` bound before `import asyncio`", "order"),
    "mut_cm_resolve": ("revision 10: `check_metrics` walking by isinstance/in/[]", "types"),
    "mut_cm_get": ("revision 10: `check_metrics` walking by the result's `get`", "scope"),
    "mut_cm_smoke": ("revision 10: \"smoke run\" whenever the trace is absent", "conditions"),
    "mut_guard_no_alive": ("revision 10: `guard` reported without the liveness test", "deletion"),
    "mut_guard_never_held": ("revision 10: `guard` never held", "constants"),
    "mut_import_no_chain": ("revision 10: UNRESOLVED not chained `from e` at the import", "deletion"),
    "mut_getattr_no_chain": ("revision 10: UNRESOLVED not chained `from e` at PEP 562", "deletion"),
    "mut_inherited_str": ("revision 10: INHERITED's non-str `__module__` rendered by str()", "types"),
    "mut_notes_order": ("revision 10: `o.lazy` placed before the fin notes", "order"),
    "mut_no_locals_clause": ("revision 11: the `<locals>` clause deleted", "deletion"),
    "mut_cut_before_scan": ("revision 11: a new cut code stored before the sharing scan", "order"),
    "mut_freeze0_at_join": ("revision 11: `freeze0` re-read at a join", "scope"),
    "mut_freeze_ne": ("revision 11: the freeze clause \"count differs\"", "comparisons"),
    "mut_cm_bool": ("revision 11: `check_metrics` calling `bool()` on a metric", "conditions"),
    "mut_prune_marks_exited": ("revision 11: a prune that marks the core exited", "claims"),
    "mut_unwind_off_pyu_only": ("M3 (revision 11, F39): `_unwind_off(None)` clears every global event, not only PY_UNWIND", "conditions"),
    "mut_clone_by_referrers": ("L-CLONE's swap-and-restore door (R23): a closing rule", "conditions"),
    "mut_freeze_premise_deleted": ("revision 12 (GAP-38): CLONE_ALIVE (b) without its freeze-count premise", "conditions"),
    "mut_rebind_nocount": ("revision 6: a rebinding not counted in `_LOST`", "deletion"),
}
for mid, (wit, patches) in _smoke["M"].items():
    rule, fam = AUDIT_ROW.get(mid, (mid, "?"))
    for w in wit:
        pass
    row(mid, rule, fam, wit[0], "PASS (as its row states)", "the row's outcome differs", patches,
        note=("other witnesses: " + ", ".join(wit[1:])) if len(wit) > 1 else "")

# ---- the hazard and revision-12 rows (tools/runner_mutants_v5f.py) ------------------------------------
HAZ_ROW = {
    "mut_h1_mutex_lock": ("H1: the robust mutex replaced by threading.Lock", "order"),
    "mut_h2_cb_except": ("H2: except Exception in the callbacks", "deletion"),
    "mut_h8_publish_at_entry": ("confirmation deleted (publish at entry)", "order"),
    "mut_h9_while_in_lock": ("H9 (revision 12): X3 as a while loop inside `with _M:`", "order"),
    "mut_m10_credit_stop_after_detach": ("M10: credit stop after detach (emptying `by_code` at exit)", "order"),
    "mut_h10_unwind_mint_scope": ("unwind scope: PY_UNWIND per mint rather than per section", "scope"),
    "mut_clone_alive_old_text": ("revision 12 (GAP-38): CLONE_ALIVE (b)'s text", "constants"),
    "mut_register_one_gate": ("revision 6: `_register` with one name gate before all five exchanges", "order"),
    "mut_register_drop_before_count": ("revision 8: `_register`'s exchanges not read through `_tee`", "order"),
    "mut_set_local_split_gate": ("revision 5: a name-gated write split into a test and a write (_set_local)", "order"),
    "mut_unwind_on_split_gate": ("revision 5: a name-gated write split into a test and a write (_unwind_on)", "order"),
    "mut_unwind_off_split_gate": ("revision 5: `_unwind_off`'s `_ANCHORS` test and clear split", "order"),
}
for mid, (wit, patches, why) in _haz["HAZ"].items():
    if mid.startswith("RETIRED_") or mid.startswith("mut_h6_") or mid in _smoke["M"]:
        continue
    rule, fam = HAZ_ROW.get(mid, (why, "?"))
    row(mid, rule, fam, wit[0], "PASS (as its row states)", "the row's outcome differs", patches,
        note=("other witnesses: " + ", ".join(wit[1:])) if len(wit) > 1 else "")

# ---- D1's crash-consistency weakenings, re-targeted (witness: one invariant of crash_sweep_v5f.py) -------
_lock = _haz["_plain_lock"]
row("M1_plain_rlock", "D1 M1: plain RLock", "order", "G_FI:C3", "every point clean", "a hang (C3)", _lock("RLock"))
row("M2_no_reconciliation", "D1 M2: no reconciliation", "deletion", "G_FI:C7", "every point clean", "C7",
    [("def _reconcile():\n    _reclaim()", "def _reconcile():\n    return\n    _reclaim()")])
row("M3_register_before_append", "D1 M3: register before append", "order", "G_FI:C5", "every point clean",
    "C5 (anchors left)",
    [("    o = _Opening(core, section, fr, threading.get_ident(), loop)   # 6. append\n    core.openings.append(o)",
      "    o = _Opening(core, section, fr, threading.get_ident(), loop)   # 6. append\n    _ANCHORS[fr] = o\n    core.openings.append(o)")])
row("M4_entering_always_live", "D1 M4: entering token always live", "conditions", "G_FI:C7", "every point clean", "C7",
    [("                or ('active' not in mk and not _alive(mk.get('entering')))):\n                _prune(h)",
      "                or ('active' not in mk and not True)):\n                _prune(h)")])
row("M5_exit_claim_not_idempotent", "D1 M5: exit claim not idempotent", "claims", "G_FI:C5", "every point clean",
    "C5 (openings left)",
    [("    if core.marks.setdefault('exiting', me) is not me:\n        return", "    core.marks['exiting'] = me")])
row("M6_install_before_register", "D1 M6: install before register", "order", "G_FI:C5", "every point clean",
    "C5 (code not restored)", _haz["HAZ"]["mut_h6_m6_install_first"][1])
row("M7_exiting_always_live", "D1 M7: exiting token always live", "conditions", "G_FI:C7", "every point clean", "C7",
    [("            if (h.facade() is None or 'exited' in mk or h.pid != pid\n                    or ('exiting' in mk and not _alive(mk['exiting']))",
      "            if (h.facade() is None or 'exited' in mk or h.pid != pid\n                    or ('exiting' in mk and not True)")])
row("atfork_restores_first", "unwind scope: at-fork order (restores last)", "order", "G_FI:C9", "every point clean", "C9",
    [("    _GUARD[\"hint\"] = _Txn(None, 0, None)             # 1.",
      "    for m in list(_MINTED.values()):                 # mutant: restores moved first\n"
      "        if m.fn.__code__ is m.code:\n            m.fn.__code__ = m.original\n"
      "    _GUARD[\"hint\"] = _Txn(None, 0, None)             # 1.")])
row("atfork_cached_pid", "unwind scope: pass-through by `os.getpid()` (a cached pid instead)", "scope", "G_FI:C9",
    "every point clean", "C9",
    [("    if core.pid != os.getpid():                      # 1. pass-through in a forked child",
      "    if core.pid != _PID_AT_IMPORT:                   # mutant: a pid cached at import"),
     ("_VERIFIED = ", "_PID_AT_IMPORT = os.getpid()\n_VERIFIED = ")])


# ---------------------------------------------------------------------------------------------------
# SM1
# ---------------------------------------------------------------------------------------------------
def apply(entry):
    s = REF
    for a, b in entry["patches"]:
        if s.count(a) != 1:
            return None
        s = s.replace(a, b)
    return s


def run_case(py, impl, case, deps):
    env = dict(os.environ)
    if deps:
        env["V5F_DEPS_PATH"] = deps
    try:
        r = subprocess.run([py, os.path.join(HERE, "run_protocol_v5f_exam.py"), "--impl", impl, "--mutation", case],
                           capture_output=True, text=True, timeout=1800, env=env)
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    lines = [x for x in r.stdout.splitlines() if x.startswith("MUTATION_RESULT ")]
    if not lines:
        return "CRASH: " + (r.stderr.strip().splitlines() or ["?"])[-1][:160]
    d = json.loads(lines[-1].split(" ", 1)[1])
    if case in d["not_run"]:
        return "NOT_RUN"
    x = d["results"].get(case)
    return "PASS" if x and x["ok"] and not x["leftover"] else "FAIL"


def run_crash(py, impl, invariant):
    fd, out = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        subprocess.run([py, os.path.join(HERE, "crash_sweep_v5f.py"), "--impl", impl, "--out", out],
                       capture_output=True, text=True, timeout=7200)
        d = json.load(open(out))
    except Exception as e:                            # noqa: BLE001
        return "CRASH", []
    fails = set()
    for sc in d["scenarios"].values():
        for role, x in sc.items():
            if isinstance(x, dict):
                for _, bad in x.get("unclean", []):
                    for b in bad:
                        fails.add(b.split(":", 1)[0].split(" ")[0])
                if role == "C4" and not x.get("ok"):
                    fails.add("C4")
    return ("PASS" if d["G_FI"] == "PASS" else "FAIL"), sorted(fails)


def sm1(pys, only=None, deps=None):
    res = {"rows": {}, "versions": {}}
    work = tempfile.mkdtemp(prefix="v5f_sm1_")
    ref_cache = {}
    for py in pys:
        ver = subprocess.run([py, "-c", "import sys;print('.'.join(map(str,sys.version_info[:3])))"],
                             capture_output=True, text=True).stdout.strip()
        dp = (deps or {}).get(ver)
        rows = {}
        for e in CATALOG:
            if only and e["id"] not in only:
                continue
            if ver not in e["versions"]:
                continue
            src = apply(e)
            if src is None:
                rows[e["id"]] = {"class": "NOT_ADMITTED", "why": "(1) the patch does not apply exactly once"}
                continue
            d = os.path.join(work, ver, e["id"])
            os.makedirs(d, exist_ok=True)
            impl = os.path.join(d, "ref_v5f.py")
            open(impl, "w").write(src)
            w = e["witness"]
            if w.startswith("G_FI:"):
                inv = w.split(":")[1]
                key = (ver, "G_FI")
                if key not in ref_cache:
                    ref_cache[key] = [run_crash(py, REF_PATH, inv)[0] for _ in range(2)]
                base = ref_cache[key]
                runs = [run_crash(py, impl, inv) for _ in range(2)]
                if base != ["PASS", "PASS"]:
                    cls = "NOT_ADMITTED"
                elif runs[0] != runs[1]:
                    cls = "NONREPRODUCIBLE"
                elif runs[0][0] == "PASS":
                    cls = "UNWITNESSED"
                else:
                    cls = "KILLED" if inv in runs[0][1] else "WITNESS_MISMATCH"
                rows[e["id"]] = {"class": cls, "ref": base, "runs": runs}
            else:
                key = (ver, w)
                if key not in ref_cache:
                    ref_cache[key] = [run_case(py, REF_PATH, w, dp) for _ in range(2)]
                base = ref_cache[key]
                runs = [run_case(py, impl, w, dp) for _ in range(2)]
                if base != ["PASS", "PASS"]:
                    cls = "NOT_ADMITTED"
                elif runs[0] != runs[1]:
                    cls = "NONREPRODUCIBLE"
                elif runs[0] == "PASS":
                    cls = "UNWITNESSED"
                else:
                    cls = "KILLED"
                rows[e["id"]] = {"class": cls, "ref": base, "runs": runs}
            print(ver, e["id"], rows[e["id"]]["class"], flush=True)
        res["rows"][ver] = rows
        adm = [k for k, r in rows.items() if r["class"] in ("KILLED", "WITNESS_MISMATCH", "NONREPRODUCIBLE")]
        killed = [k for k in adm if rows[k]["class"] == "KILLED"]
        res["versions"][ver] = {"admitted": len(adm), "killed": len(killed),
                                "unwitnessed": sorted(k for k, r in rows.items() if r["class"] == "UNWITNESSED"),
                                "not_admitted": sorted(k for k, r in rows.items() if r["class"] == "NOT_ADMITTED"),
                                "gate": len(adm) == len(killed)}
    res["gate"] = all(v["gate"] for v in res["versions"].values())
    return res


def main(argv):
    if "--list" in argv:
        for e in CATALOG:
            print(e["id"], "|", e["witness"], "|", e["family"], "|", e["rule"])
        print(len(CATALOG), "rows")
        return 0
    if "--sm1" in argv:
        i = argv.index("--sm1")
        pys = [a for a in argv[i + 1:] if not a.startswith("--")][:2]
        only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
        deps = json.loads(argv[argv.index("--deps") + 1]) if "--deps" in argv else None
        out = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(HERE, "sm1_result.json")
        t0 = time.monotonic()
        res = sm1(pys, only, deps)
        res["seconds"] = round(time.monotonic() - t0, 1)
        res["catalog_rows"] = len(CATALOG)
        json.dump(res, open(out, "w"), indent=1)
        print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
        return 0 if res["gate"] else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
