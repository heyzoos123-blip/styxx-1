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
  failures, WITNESS_MISMATCH if only others are. A row whose two runs both hit the driver's timeout (600 s) is
  HANG: admitted (no outcome is not the spec outcome) but not KILLED, since the timeout, not the witness, saw
  it (A_txn_shared_succ: the runner hangs in its own snapshot before the case body runs; SPEC_GAPS GAP-64).
  The G_FI reference runs are made once per version and shared by every G_FI row (their verdict does not
  depend on the invariant named).
  Gate: 100% of admitted rows KILLED on every version they are admitted for.

Usage: python weakenings_v5f.py --sm1 PY312 [PY313] [--only id,id] [--deps JSON] [--journal J.jsonl] [--jobs 3]
                                  [--no-crash] [--redo id,id] [--max-load 4] [--out sm1_result.json]
       (resumable through the journal; --redo decides the listed rows again; --max-load holds every crash
        sweep until the 1-min and 5-min load averages are below it. Every G_FI entry records the load averages
        before each sweep and the per-scenario detail; a sweep whose fault-free run passed the 60 s bound
        ("C3: baseline hang") is classed VOID_LOAD, admitted and not killed, to be rerun under low load)
       python weakenings_v5f.py --list
"""
import collections, json, os, runpy, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.append(HERE)
import v5f_tmp      # noqa: E402  temp dirs removed at exit and per row; children's TMPDIR; the disk guard
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


# ---- the Mutation-audit table (each row's rule weakened, with the witness the table names) --------------
COH = "            coherent = cf.startswith('<') or ("
row("A_coh_FT_exempt", "coherence on F_T", "conditions", "X26b", "FOREIGN_DEFINITION", "passes",
    [(COH, "            coherent = cur is D or cf.startswith('<') or (")])
row("A_coh_links_exempt", "coherence on intermediate links", "conditions", "X26d", "FOREIGN_DEFINITION", "passes",
    [(COH, "            coherent = cur.__globals__ is not md or cf.startswith('<') or (")])
row("A_coh_no_file_skip", "the '<' skip widened to \"no __file__\"", "conditions", "X26e", "FOREIGN_DEFINITION", "passes",
    [(COH, "            coherent = cf.startswith('<') or type(gf) is not str or (")])
row("A_module_file_rule", "the module `__file__` rule", "deletion", "X26e", "FOREIGN_DEFINITION", "passes",
    [("    if type(mf) is not str:\n        raise GateSpecError(", "    if False:\n        raise GateSpecError(")])
row("A_sourceless_accepted", "sourceless accepted", "deletion", "X26f", "FOREIGN_DEFINITION", "passes",
    [("    if mf.endswith('.pyc') or mf.endswith('.pyo'):\n        raise GateSpecError(",
      "    if False:\n        raise GateSpecError("),
     (COH, "            coherent = cf.startswith('<') or (type(gf) is str and gf.endswith('.pyc')) or (")])
row("A_fd_by_module", "FOREIGN_DEFINITION by `__module__`", "comparisons", "v5e:X30", "FOREIGN_DEFINITION", "passes",
    [("            if cur.__globals__ is md:\n                return",
      "            if dict.get(cur.__globals__, '__name__') == dict.get(md, '__name__'):\n                return")])
row("A_fd_no_chain", "FOREIGN_DEFINITION without the chain", "scope", "v5e:V11", "PASS {wrapped_entry:1}", "FOREIGN_DEFINITION",
    [("            cur = dict.get(_own_dict(cur) or {}, '__wrapped__')\n        elif", "            cur = None\n        elif")],
    note="also v5e:V06")
row("A_fd_functions_only", "the walk only through functions", "scope", "V38", "PASS {fit:1}", "FOREIGN_DEFINITION",
    [("        else:\n            d = _own_dict(cur)\n            if d is None:\n                break\n            cur = dict.get(d, '__wrapped__')",
      "        else:\n            break")])
for n, bound, wit, sp, wk in (("A_hop_bound_3", 4, "V11c", "PASS {target:1}", "FOREIGN_DEFINITION"),
                              ("A_hop_bound_16", 16, "V11c", "PASS {target:1}", "FOREIGN_DEFINITION"),
                              ("A_hop_bound_18", 19, "X30b", "FOREIGN_DEFINITION", "passes")):
    row(n, f"the hop bound (16) as {n.split('_')[-1]}", "constants", wit, sp, wk,
        [("    for _hop in range(17):", f"    for _hop in range({bound}):")])
row("A_cache_callee_identity", "cache callee identity", "deletion", "X24c", "NOT_A_FUNCTION", "passes",
    [("        if callee is None or callee is not stamped:", "        if callee is None:")], note="also X24c")
row("A_bound_body_module", "bound-body check (the module)", "deletion", "v5e:X25", "NOT_A_FUNCTION", "passes",
    [("        for k, v in md.items():\n            if v is callee:", "        for k, v in ():\n            if v is callee:")])
row("A_bound_body_holder", "bound-body check (the holder's namespace)", "deletion", "v5e:X25b", "NOT_A_FUNCTION", "passes",
    [("        if holder is not None and holder is not md:", "        if False:")], note="also X25d")
row("A_sibling", "sibling check", "deletion", "X24e", "NOT_A_FUNCTION", "passes",
    [("                if w is not D and type(w) is _CACHE_WRAPPER and _cache_callee(w) is callee:", "                if False:")])
row("A_alias_by_name", "alias-by-object rule (by name instead)", "comparisons", "X24d", "PASS", "NOT_A_FUNCTION",
    [("                if w is not D and type(w) is _CACHE_WRAPPER and _cache_callee(w) is callee:",
      "                if k != qual.split('.')[-1] and type(w) is _CACHE_WRAPPER and _cache_callee(w) is callee:")])
row("A_pep562_once", "PEP 562 twice", "deletion", "X13b", "UNRESOLVED", "passes",
    [("                    b = ga(part)\n", "                    b = a\n")])
row("A_module_step_exact", "exact type for the module step", "types", "V10b", "PASS {target:1}", "a refusal",
    [("        if issubclass(type(obj), ModuleType):\n            if i > 0:", "        if type(obj) is ModuleType:\n            if i > 0:")])
row("A_class_step_exact", "the class step", "types", "V45", "PASS", "a refusal",
    [("        elif issubclass(type(obj), type):\n            own = _TYPE_DICT", "        elif type(obj) is type:\n            own = _TYPE_DICT")],
    note="also X14b")
row("A_mro_first_base", "full-MRO INHERITED", "scope", "X14c", "INHERITED", "UNRESOLVED",
    [("                for k in _TYPE_MRO.__get__(obj)[1:]:", "                for k in _TYPE_MRO.__get__(obj)[1:2]:")])
row("A_descriptor_getattr", "descriptor-only reads (getattr reintroduced)", "types", "V40", "PASS {target:1}, no side effects",
    "user code runs", [("            d = _own_dict(obj)\n            if d is None or part not in d:",
                        "            d = getattr(obj, '__dict__', None)\n            if d is None or part not in d:")],
    note="also X17b")
row("A_is_chain_tuple", "an `is` chain replaced by tuple membership", "comparisons", "V40b", "PASS, __eq__ counter 0",
    "__eq__ called", [("        if type(obj) is staticmethod:                # unwrap first, at every step (D2)",
                       "        if type(obj) in (staticmethod,):             # mutant: tuple membership")])
row("A_reserved_target", "RESERVED_TARGET", "deletion", "X34", "RESERVED_TARGET", "passes",
    [("    if (fn is _HANDLE_DICT[0].get('_run') or fn is _LOOP_DICT[0].get('_run_once')\n            or _CUT.get(id(fc)) is fc):",
      "    if False:")], note="also X34b, X34c")
row("A_cut_by_name", "cut by identity (by name instead)", "comparisons", "V44", "PASS {f:1}", "NOT_EXERCISED",
    [("        if _CUT.get(id(c)) is c:\n            cut = True\n            break\n        o = _ANCHORS.get(g)",
      "        if c.co_name in ('_run', '_run_once'):\n            cut = True\n            break\n        o = _ANCHORS.get(g)")])
row("A_cut_cleared", "monotone cut cleared", "claims", "X65b", "NOT_EXERCISED (dispatched {f:2})", "differs",
    [("    core.marks['exited'] = True                      # X8", "    _CUT.clear()                                     # mutant: the cut cleared at exit\n    core.marks['exited'] = True                      # X8")])
row("A_cut_replaced", "monotone cut replaced at each E2", "claims", "V64", "PASS {f:1}", "CUT_MOVED",
    [("def _cut_refresh():\n", "def _cut_refresh():\n    _CUT.clear()                                     # mutant: the cut replaced at each E2\n")])
row("A_cut_moved_at_exit", "CUT_MOVED at exit", "deletion", "X141", "CUT_MOVED", "passes",
    [("    if 'CUT_MOVED' in core.flags or not _cut_ok():", "    if 'CUT_MOVED' in core.flags:")])
row("A_cut_moved_at_hit", "CUT_MOVED at a hit", "deletion", "X141b", "CUT_MOVED", "passes",
    [("    if not _cut_ok():                               # CUT_MOVED: a moved binding seen at a hit", "    if False:")])
row("A_e2_refresh", "E2's refresh", "deletion", "V61", "PASS {f:1}", "CUT_MOVED",
    [("    _cut_refresh()                                   # E2\n", "    pass\n")])
row("A_cut_unavailable", "CUT_UNAVAILABLE (a binding that is not a plain function)", "deletion", "X35", "CUT_UNAVAILABLE", "passes",
    [("        if type(x) is not FunctionType:\n            raise GateSpecError(", "        if False:\n            raise GateSpecError(")])
row("A_run_once_not_cut", "`_run_once` code in the cut", "scope", "X65g", "differs", "differs",
    [("    for label, x in ((\"asyncio.events.Handle._run\", _HANDLE_DICT[0].get('_run')),\n                     (\"asyncio.base_events.BaseEventLoop._run_once\",\n                      _LOOP_DICT[0].get('_run_once'))):",
      "    for label, x in ((\"asyncio.events.Handle._run\", _HANDLE_DICT[0].get('_run')),):")], note="also X65e, X65f")
row("A_cut_ok_no_run_once", "`_run_once` binding in `_cut_ok()`", "deletion", "X141c", "CUT_MOVED", "passes",
    [("    return (type(h) is FunctionType and _CUT.get(id(h.__code__)) is h.__code__\n            and type(r) is FunctionType and _CUT.get(id(r.__code__)) is r.__code__)",
      "    return (type(h) is FunctionType and _CUT.get(id(h.__code__)) is h.__code__)")])
row("A_no_referrer_clause", "shareable-code refusal: the gc-referrer clause", "deletion", "X35c", "CUT_UNAVAILABLE", "passes",
    [("        if '<locals>' in c.co_qualname or twins:", "        if '<locals>' in c.co_qualname:")])

# minting / identity / f_globals
row("A_mint_none", "minting (the original code installed, no mint)", "deletion", "X40", "PASS", "differs",
    [("        self.code = self.original.replace()", "        self.code = self.original")], note="also X41-X44")
row("A_mint_eq", "`is` vs `==` (the minted-code test by equality)", "comparisons", "v5e:X45", "CLONE_CALLED", "differs",
    [("    m = _MINTED.get(id(code))\n    if m is None or m.code is not code: return\n    f = sys._getframe(1)\n    holders",
      "    m = next((x for x in list(_MINTED.values()) if x.code == code), None)\n    if m is None or m.code != code: return\n    f = sys._getframe(1)\n    holders")],
    note="also v5e:X46")
row("A_fglobals", "the `f_globals` check", "deletion", "X55", "CLONE_CALLED", "credited",
    [("    if f.f_globals is not m.globals:                # CLONE_CALLED", "    if False:                                       # CLONE_CALLED")],
    note="also X56")
# CLONE_ALIVE
row("A_clone_alive", "CLONE_ALIVE", "deletion", "v5e:X57", "CLONE_ALIVE", "passes",
    [("        txt = _clone_alive(m)\n", "        txt = None\n")], note="also v5e:X58")
row("A_freeze_clause", "CLONE_ALIVE's freeze clause", "deletion", "X57b", "CLONE_ALIVE", "passes",
    [("    if gc.get_freeze_count() > m.freeze0:", "    if False:")], note="also X58b")
row("A_freeze_gt0", "freeze: \"count > 0\" instead of \"count > baseline\"", "comparisons", "V36b", "PASS", "CLONE_ALIVE",
    [("    if gc.get_freeze_count() > m.freeze0:", "    if gc.get_freeze_count() > 0:")])
row("A_visible_deleted", "freeze: visible accounting deleted", "deletion", "X58b", "PASS", "CLONE_ALIVE",
    [("        if excess - visible > 0:", "        if excess > 0:")])
# per-holder rules
row("A_clone_called_per_holder", "per-holder CLONE_CALLED", "scope", "X55d", "CLONE_CALLED in each", "differs",
    [("        for h in holders: h.clone_called[id(code)] = m.qualname", "        for h in holders[:1]: h.clone_called[id(code)] = m.qualname")])
row("A_clone_alive_per_holder", "per-holder CLONE_ALIVE (only at the last holder's exit)", "scope", "X57c", "CLONE_ALIVE", "passes",
    [("        txt = _clone_alive(m)\n", "        txt = _clone_alive(m) if not m.holders else None\n")])
row("A_swapped_per_holder", "per-holder CODE_SWAPPED (only at the last holder's exit)", "scope", "X59c", "CODE_SWAPPED", "passes",
    [("        if m.fn.__code__ is not m.code:\n            swapped.append(",
      "        if m.fn.__code__ is not m.code and len(m.holders) == 1:\n            swapped.append(")])
# CODE_SWAPPED
row("A_swapped_at_exit", "CODE_SWAPPED at exit", "deletion", "X59", "CODE_SWAPPED", "passes",
    [("        if m.fn.__code__ is not m.code:\n            swapped.append(", "        if False:\n            swapped.append(")])
row("A_swapped_at_entry", "CODE_SWAPPED at entry (E4.3 and the join's check)", "deletion", "v5e:X31", "CODE_SWAPPED", "differs",
    [("        if m is not None and fn.__code__ is not m.code:\n            raise GateSpecError(",
      "        if False:\n            raise GateSpecError("),
     ("        if fn.__code__ is not m.code:\n            raise GateSpecError(\n                f\"[V5:CODE_SWAPPED] declared target {m.qualname}",
      "        if False:\n            raise GateSpecError(\n                f\"[V5:CODE_SWAPPED] declared target {m.qualname}")])
row("A_restore_over_swap", "restore over a swap", "conditions", "X59d", "the swap kept", "the swap undone",
    [("def _retire(m):\n    if m.fn.__code__ is m.code:\n", "def _retire(m):\n    if True:\n")])
row("A_e41_reconcile", "entry CODE_SWAPPED against a holderless mint (reconciliation dropped)", "deletion", "X92b",
    "CODE_SWAPPED", "differs", [("    _reconcile()                                     # E4.1", "    pass                                             # E4.1")])
row("A_reconcile_deleted", "reconciliation deleted", "deletion", "X133", "as stated", "differs",
    [("def _reconcile():\n    _reclaim()", "def _reconcile():\n    return\n    _reclaim()")], note="also X92b; G_FI M2")
# the busy bound (boundary rows: 11 s refused X138, 7 s accepted V65; O7b's x0.5 and x2, and 0.5 s)
for n, v, wit, sp, wk in (("A_busy_x2", "20.0", "X138", "MACHINERY_BUSY", "passes"),
                          ("A_busy_x0_5", "5.0", "V65", "PASS", "MACHINERY_BUSY"),
                          ("A_busy_0_5", "0.5", "V65", "PASS", "MACHINERY_BUSY")):
    row(n, f"the busy bound 10 s as {v} s", "constants", wit, sp, wk, [("_BUSY_SECONDS = 10.0", f"_BUSY_SECONDS = {v}")])
# dispatch cut and loop boundary
row("A_dispatch_cut_attr", "dispatch cut in attribution", "deletion", "X65c", "dispatched", "differs",
    [("        if _CUT.get(id(c)) is c:\n            cut = True\n            break\n        o = _ANCHORS.get(g)",
      "        if False:\n            cut = True\n            break\n        o = _ANCHORS.get(g)")])
row("A_dispatch_cut_nested", "dispatch cut in the NESTED walk", "deletion", "V19b", "PASS", "NESTED_SECTION",
    [("        if _CUT.get(id(c)) is c:\n            break\n        p = _ANCHORS.get(g)", "        if False:\n            break\n        p = _ANCHORS.get(g)")])
row("A_loop_boundary_attr", "loop boundary in attribution", "deletion", "X65d", "dispatched", "differs",
    [("            if o.loop is not loop:                   # the loop boundary", "            if False:                                # the loop boundary")])
row("A_loop_boundary_nested", "loop boundary in the NESTED walk", "deletion", "V63", "PASS", "NESTED_SECTION",
    [("        if p is not None and p.core is core and p.loop is loop:", "        if p is not None and p.core is core:")])
row("A_nested_across_tracers", "NESTED across tracers", "conditions", "V15b", "PASS", "NESTED_SECTION",
    [("        if p is not None and p.core is core and p.loop is loop:", "        if p is not None and p.loop is loop:")])
# the tool and its name
row("A_bare_tool_name", "tool adopted by the bare name `styxx.protocol`", "constants", "X142", "PASS", "differs",
    [("\"styxx.protocol/\" + os.urandom(6).hex()", "sys.intern(\"styxx.protocol\")")],
    note="the bare name, interned so that every loaded copy holds the same name object (v5e's adoption by name)")
row("A_unwind_off_ungated", "events changed on an id that lost its name (`_unwind_off` without the name gate)", "deletion",
    "X137-free", "as stated", "differs",
    [("                    _map(set_events, _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),\n                                               _map(_not, (_ANCHORS,))), _ZERO1)))",
      "                    _map(set_events, _compress((t,), _map(_not, (_ANCHORS,))), _ZERO1)))")])
# confirmation
row("A_unwind_offset", "unwind-offset check deleted", "deletion", "X135", "as stated", "credited",
    [("if p is not None and p[0] is f and offset != p[1]: _publish(code, p[2])", "if p is not None and p[0] is f: _publish(code, p[2])")])
row("A_py_throw_credited", "PY_THROW credited (an entry event)", "scope", "X119", "NOT_EXERCISED", "credited",
    [("_EVENTS5 = (PY_START, PY_RESUME, PY_RETURN, PY_YIELD, PY_UNWIND)", "_EVENTS5 = (PY_START, PY_RESUME, PY_RETURN, PY_YIELD, PY_UNWIND, 8192)"),
     ("\n             _PYU1)))\n", "\n             ((PY_UNWIND | 8192),))))\n"),
     ("_CALLBACKS5 = (_on_entry, _on_entry, _on_exit, _on_exit, _on_unwind)", "_CALLBACKS5 = (_on_entry, _on_entry, _on_exit, _on_exit, _on_unwind, _on_entry)"),
     ("_map(get_tool, _repeat(t, 5))", "_map(get_tool, _repeat(t, 6))")],
    note="PY_THROW is not a legal local event (set_local_events refuses it), so the mutant sets it globally with PY_UNWIND, per section")
row("A_publish_recheck", "credit re-check at publication deleted", "deletion", "v5e:X71", "as stated", "credited",
    [("    for h, kind, x in out:\n        if k in h.by_code:", "    for h, kind, x in out:\n        if True:")])
row("A_one_opening_per_tracer", "exactly-one-opening-per-tracer", "conditions", "v5e:X70", "ambiguous", "credited",
    [("            if len(mine) == 1:", "            if mine:")])
# claims
row("A_enter_claim", "atomic enter claim replaced by check-then-set", "claims", "X32d", "REENTRY", "differs",
    [("    if core.marks.setdefault('entering', me) is not me:", "    if 'entering' in core.marks or core.marks.__setitem__('entering', me):")])
row("A_exit_claim", "exit claim replaced by an unconditional store", "claims", "V52", "PASS", "differs",
    [("    if core.marks.setdefault('exiting', me) is not me:\n        return", "    core.marks['exiting'] = me")])
# fork
row("A_atfork_handler", "at-fork handler", "deletion", "V47", "PASS", "differs",
    [("    os.register_at_fork(after_in_child=_forget_in_child)", "    pass")])
row("A_pid_passthrough", "pid pass-through", "deletion", "V47", "PASS", "differs",
    [("    if core.pid != os.getpid():                      # 1. pass-through in a forked child", "    if False:                                        # 1."),
     ("    if core.pid != os.getpid():                      # X-1", "    if False:                                        # X-1")])
# sections
row("A_section_norm", "section normalization", "deletion", "V39", "PASS", "differs",
    [("            section = str.__str__(section)", "            pass")])
row("A_nonstr_refusal", "non-str refusal", "types", "X78f", "UNDECLARED_SECTION", "differs",
    [("        if issubclass(type(section), str):\n            section = str.__str__(section)", "        if True:\n            pass")])
row("A_open_problem_recorded", "recording open-time refusals", "deletion", "X76", "problem recorded", "not recorded",
    [("            core.problems.append(txt)\n            raise GateSpecError(txt)\n        g = g.f_back",
      "            raise GateSpecError(txt)\n        g = g.f_back")], note="the NESTED_SECTION refusal's record; also X78-X79, X32")
# the refusal codes of the machinery
row("A_monitor_busy", "MONITOR_BUSY", "deletion", "X36", "MONITOR_BUSY", "differs",
    [("    raise GateSpecError(\n        \"[V5:MONITOR_BUSY]", "    return\n    raise GateSpecError(\n        \"[V5:MONITOR_BUSY]")])
row("A_monitor_lost", "MONITOR_LOST", "deletion", "X137", "MONITOR_LOST", "passes",
    [("    if lost:\n        core.lost_note", "    if False:\n        core.lost_note")])
row("A_reentrant", "REENTRANT", "deletion", "X139", "REENTRANT", "differs",
    [("            if r.tid == me.tid:\n                raise", "            if False:\n                raise")], note="also H1")
row("A_machinery_busy", "MACHINERY_BUSY", "deletion", "X138", "MACHINERY_BUSY", "differs",
    [("            elif now - t0 > _BUSY_SECONDS:\n                raise", "            elif False:\n                raise")])
row("A_trace_active", "TRACE_ACTIVE", "deletion", "X90/X91", "TRACE_ACTIVE", "differs",
    [("            raise GateSpecError(\n                \"[V5:TRACE_ACTIVE] the tracer is active",
      "            if False: raise GateSpecError(\n                \"[V5:TRACE_ACTIVE] the tracer is active")], note="also X92c")
row("A_trace_incomplete", "TRACE_INCOMPLETE", "deletion", "v5e:X92", "TRACE_INCOMPLETE", "differs",
    [("            if 'exiting' in mk or ('entering' in mk and 'active' not in mk):", "            if False:")], note="also X133, V52")

# scoring: sections and problems
def _between(a, b):
    i = REF.index(a)
    return REF[i:REF.index(b, i + 1)]
_STALE = _between('        if tr["gates_sha256"] != self.gates_sha256:', '        if sorted(tr["targets"]) != self.coverage_targets:')
_TSET = _between('        if sorted(tr["targets"]) != self.coverage_targets:', '        declared = set(self.coverage_targets)')
_SHAPE = "        _check_trace_shape(name, tr)\n"
_COUNT = _between('        declared = set(self.coverage_targets)', '        problems = tr["problems"]')
_PROB = _between('        problems = tr["problems"]', '        openings = tr["sections"].get(c["section"])')
_ABS = _between('        openings = tr["sections"].get(c["section"])', '        union: dict = {}')
row("A_union_all_sections", "union over the declared section only (over every section instead)", "scope", "X120",
    "NOT_EXERCISED", "PASS",
    [("        for o in openings:\n            for t, n in o[\"calls\"].items():",
      "        for o in [p for ps in tr[\"sections\"].values() for p in ps]:\n            for t, n in o[\"calls\"].items():")],
    note="also V41")
row("A_section_by_gate_name", "declared section, not gate name", "comparisons", "V43", "PASS", "SECTION_ABSENT",
    [("        openings = tr[\"sections\"].get(c[\"section\"])", "        openings = tr[\"sections\"].get(name)")],
    note="also V42, X121, X78g")
row("A_score_ignores_problems", "score reads problems", "deletion", "X55", "CLONE_CALLED", "differs",
    [("        if problems:\n            first = _CODE_RE", "        if False:\n            first = _CODE_RE")], note="also X56-X59")
# scoring: exact types before any hash or compare
row("A_sha_type", "exact type before hash in BAD_TRACE (`gates_sha256`)", "types", "X96d", "BAD_TRACE", "differs",
    [("    if type(tr[\"gates_sha256\"]) is not str:\n        raise", "    if False:\n        raise")])
row("A_tracer_type", "exact type before compare in WRONG_TRACER (tracer)", "types", "X96d", "WRONG_TRACER", "differs",
    [("        if type(tid) is not str or tid != _TRACER_ID:", "        if tid != _TRACER_ID:")])
row("A_trace_keys", "BAD_TRACE: the trace's exact key set", "deletion", "X96c", "BAD_TRACE", "differs",
    [("    if set(tr) != _TRACE_KEYS:\n        raise", "    if False:\n        raise")])
# scoring: step order (each adjacent pair the table names)
row("A_order_stale_targetset", "score step order: STALE_TRACE / TARGET_SET swapped", "order", "X109b", "STALE_TRACE", "TARGET_SET",
    [(_STALE + _TSET, _TSET + _STALE)])
row("A_order_count_problem", "score step order: BAD_COUNT / recorded problem swapped", "order", "X112b", "BAD_COUNT", "UNDECLARED_SECTION",
    [(_COUNT + _PROB, _PROB + _COUNT)])
row("A_order_shape_stale", "score step order: BAD_TRACE / STALE_TRACE swapped", "order", "X96c", "BAD_TRACE", "KeyError",
    [(_SHAPE + _STALE, _STALE + _SHAPE)])
row("A_order_problem_absent", "score step order: recorded problem / SECTION_ABSENT swapped", "order", "X78e", "UNDECLARED_SECTION",
    "SECTION_ABSENT", [(_PROB + _ABS, _ABS + _PROB)])
row("A_order_bar_coverage", "score step order: the bar before coverage (a failing bar skips the coverage check)", "order", "X122",
    "NOT_EXERCISED", "a verdict", [("            if name in self.coverage:\n                covered[name]",
                                   "            if name in self.coverage and op(_v, g[\"value\"]):\n                covered[name]")])
# scoring: NO_TRACE, check_metrics, texts
row("A_notrace_exact_dict", "NO_TRACE dict-subclass rule (an exact dict required of the result)", "types", "V53", "PASS", "NO_TRACE",
    [("        if not issubclass(type(result), dict):\n            raise GateSpecError(\n                f\"[V5:NO_TRACE]",
      "        if type(result) is not dict:\n            raise GateSpecError(\n                f\"[V5:NO_TRACE]")])
row("A_notrace_split", "NO_TRACE split text (the third wording merged into the second)", "conditions", "X93d", "NO_TRACE third wording",
    "second wording", [("        if tr is _MISSING:\n", "        if tr is _MISSING or type(tr) is not dict:\n")])
row("A_cm_overflow", "check_metrics overflow (`_finite` without its OverflowError catch)", "deletion", "X117b",
    "REPORTED", "OverflowError", [("    except OverflowError:\n        return False", "    except ZeroDivisionError:\n        return False")])
row("A_cm_smoke_exact", "check_metrics smoke exact type", "types", "X117c", "__bool__ never called", "called",
    [("        smoke = (ts is bool or ts is int or ts is float or ts is str) and bool(s)", "        smoke = bool(s)")])
row("A_cm_smoke_note", "check_metrics smoke note (the refusal's code no longer leads)", "constants", "X117d", "[V5:NOT_EXERCISED] first",
    "differs", [("                    note = str(e) + \" (smoke run", "                    note = \"smoke run: \" + str(e) + \" (smoke run")])
row("A_bucket_labels", "NOT_EXERCISED bucket labels (swapped)", "constants", "X72b", "dispatched {f:2}", "differs",
    [("f\"dispatched {disp}, unattributed {unat}", "f\"dispatched {unat}, unattributed {disp}")])
row("A_lazy_text", "LAZY_RESULT text (the not-started suffix dropped)", "constants", "X74d", "suffix present", "absent",
    [("(\" (its body had not started)\" if fresh else \"\")", "\"\"")], note="also X74-X74c")
row("A_nested_text", "NESTED_SECTION text (the same-section wording)", "constants", "X76b", "the spec-fixed text", "differs",
    [("f\"the stack of two openings of section {section!r}\")", "f\"the stack of two openings, section {section!r}\")")],
    note="the spec-fixed substring (M11) changed")
row("A_section_decl_empty", "SECTION_DECL non-empty", "conditions", "X07b / X07c", "SECTION_DECL", "differs",
    [("            if not isinstance(sec, str) or not sec or not sec.isascii():", "            if not isinstance(sec, str) or not sec.isascii():")])
row("A_section_decl_ascii", "SECTION_DECL ASCII", "conditions", "X07b / X07c", "SECTION_DECL", "differs",
    [("            if not isinstance(sec, str) or not sec or not sec.isascii():", "            if not isinstance(sec, str) or not sec:")])
row("A_retired_note", "BAD_TRACE: a retired note code accepted (PROFILER_LOST)", "constants", "X105d", "BAD_TRACE", "differs",
    [("_NOTE_CODES = frozenset({\"OPEN_AT_EXIT\", \"LAZY_RESULT\", \"MONITOR_LOST\"})",
      "_NOTE_CODES = frozenset({\"OPEN_AT_EXIT\", \"LAZY_RESULT\", \"MONITOR_LOST\", \"PROFILER_LOST\"})")])
row("A_bad_count_zero", "BAD_COUNT: counts >= 1 (0 accepted)", "comparisons", "X112b", "BAD_COUNT", "differs",
    [("                if t not in declared or type(n) is not int or n < 1:", "                if t not in declared or type(n) is not int or n < 0:")])

# ---- the revision 2-8 lines of the Mutation-audit table --------------------------------------------
_UO_CAP = _between("        _map(_setitem, _map(_FLAGS,", "        _map(set_events,\n             _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),\n                       _map(_is, _map(_ANCHORS.get")
_UO_SET = ("        _map(set_events,\n             _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),\n"
           "                       _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),\n             _PYU1)))")
_UO_SET_NOGATE = "        _map(set_events,\n             _compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),\n             _PYU1)))"
_UO_CAP_AG = ("_compress(_compress(_compress((_ANCHORS,), _map(_is, _map(get_tool, (t,)), _NAME1)),\n"
              "                                _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),\n")
row("A_reclaim_deleted", "unwind scope: reclaim of a freed, unowned id", "deletion", "X137-free", "as stated", "differs",
    [("def _reclaim():\n    \"\"\"", "def _reclaim():\n    return\n    \"\"\"")])
row("A_unwind_on_recheck", "unwind scope: the re-check after the anchor commit (`_unwind_on`'s own-anchor test on the write)", "deletion",
    "X143", "every trial PASS", "differs", [(_UO_SET, _UO_SET_NOGATE)])
row("A_commit_before_try", "revision 3: `_commit` inside `_run`'s try (moved back before it)", "order", "X144", "as stated", "differs",
    [("    end = \"raised\"\n    try:\n        _commit(o)\n        result = fn(*args, **kwargs); end = \"returned\"",
      "    end = \"raised\"\n    _commit(o)\n    try:\n        result = fn(*args, **kwargs); end = \"returned\"")])
row("A_detach_armed", "revision 3: `o.armed` in `_detach`'s check", "deletion", "X143b", "as stated", "UNWIND_LOST",
    [("        if o.armed and not (_MON[0][1](_TOOL[0]) & PY_UNWIND) and _ANCHORS.get(fr) is o:",
      "        if not (_MON[0][1](_TOOL[0]) & PY_UNWIND) and _ANCHORS.get(fr) is o:")])
row("A_detach_anchor", "revision 3: the anchor test in `_detach`'s check", "deletion", "X143c", "as stated", "UNWIND_LOST",
    [("        if o.armed and not (_MON[0][1](_TOOL[0]) & PY_UNWIND) and _ANCHORS.get(fr) is o:",
      "        if o.armed and not (_MON[0][1](_TOOL[0]) & PY_UNWIND):")])
row("A_reconcile_final_off", "revision 3: `_unwind_off` at the end of every reconciliation", "deletion", "X137-free", "global_events 0 after exit",
    "differs", [("    if _TOOL[0] is not None:\n        _unwind_off(None)", "    if False:\n        _unwind_off(None)")])
row("A_detach_releases_frame", "revision 4: `o.frame` released by every `_detach` (revision 3's)", "scope", "X146", "as stated", "differs",
    [("        _unwind_off(fr)                             # one call: pop, then clear iff no anchor is left",
      "        _unwind_off(fr)                             # one call: pop, then clear iff no anchor is left\n        o.frame = None")])
row("A_step8_deleted", "revision 4: step 8's re-check deleted", "deletion", "X146", "TRACE_INACTIVE", "differs",
    [("    if 'fin' in o.fin or 'exiting' in o.core.marks:  # step 8", "    if False:                                        # step 8")])
row("A_step8_exiting", "revision 4: step 8's `'exiting'` test deleted", "deletion", "X146b", "as stated", "differs",
    [("    if 'fin' in o.fin or 'exiting' in o.core.marks:  # step 8", "    if 'fin' in o.fin:                               # step 8")])
row("A_step8_claim", "revision 4: step 8's claim test deleted", "deletion", "X146c", "as stated", "differs",
    [("    if 'fin' in o.fin or 'exiting' in o.core.marks:  # step 8", "    if 'exiting' in o.core.marks:                    # step 8")])
row("A_prune_from_anchors", "revision 4: pruning of cores reached from anchors deleted", "deletion", "X146d", "as stated", "differs",
    [("    for fr, o in list(_ANCHORS.items()):             # prune cores", "    for fr, o in ():                                 # prune cores")])
row("A_detach_anchor_first", "revision 4: `_detach`'s test with the anchor before the event", "order", "X148", "every trial PASS", "differs",
    [("        if o.armed and not (_MON[0][1](_TOOL[0]) & PY_UNWIND) and _ANCHORS.get(fr) is o:",
      "        if o.armed and _ANCHORS.get(fr) is o and not (_MON[0][1](_TOOL[0]) & PY_UNWIND):")])
row("A_named_eq", "revision 4: `_named` by `==`", "comparisons", "X142b", "PASS, __eq__ counter 0", "differs",
    [("def _named(i): return _MON[0][0](i) is _TOOL_NAME", "def _named(i): return _MON[0][0](i) == _TOOL_NAME")])
row("A_facade_async", "revision 5: the facade's `run_async` as an `async def` that awaits `_run_async`", "scope", "X146c", "as stated", "differs",
    [("    def run_async(self, section, afn, /, *args, **kwargs):", "    async def run_async(self, section, afn, /, *args, **kwargs):"),
     ("        return _run_async(self._core, section, afn, args, kwargs)", "        return await _run_async(self._core, section, afn, args, kwargs)")])
row("A_pop_outside", "revision 5: the pop outside `_unwind_off`'s call", "order", "X152", "no trial anchors 0 with events", "differs",
    [("    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),\n", "    _ANCHORS.pop(key, None)\n    _CONSUME(_chain((),\n")])
row("A_unwind_on_before_store", "revision 5: `_unwind_on` before the store", "order", "X143", "every trial PASS", "differs",
    [("    _ANCHORS[o.frame] = o                           # the store\n", "    _unwind_on(o)\n    _ANCHORS[o.frame] = o                           # the store\n"),
     ("    _unwind_on(o)                                   # one call, after the store\n", "")])
row("A_unwind_on_no_own_gate", "revision 5: `_unwind_on` without the own-anchor gate", "deletion", "X146e", "as stated", "differs",
    [(_UO_SET, _UO_SET_NOGATE), (_UO_CAP_AG, "_compress(_compress((_ANCHORS,), _map(_is, _map(get_tool, (t,)), _NAME1)),\n")])
row("A_unwind_on_no_capture", "revision 5: `_unwind_on` without the capture", "deletion", "X137d", "MONITOR_LOST", "differs",
    [("    _CONSUME(_chain(\n" + _UO_CAP, "    _CONSUME(_chain(\n")])
row("A_capture_outside", "revision 5: the capture outside the call that reads and sets the event", "order", "X153", "every trial PASS",
    "differs", [("    _CONSUME(_chain(\n" + _UO_CAP + _UO_SET,
                 "    _CONSUME(_chain(\n" + _UO_CAP.rstrip(",\n") + "))\n    _CONSUME(_chain(\n" + _UO_SET)])
row("A_capture_ungated", "revision 5: the capture not gated on the event being clear", "conditions", "X153", "every trial PASS", "differs",
    [("            _compress(_compress(_compress((_ANCHORS,)", "            _compress(_compress((_ANCHORS,)"),
     ("(o,))),\n                      _map(_not, _map(_and, _map(get_events, (t,)), _PYU1))))))), _LOST_KEY, _TRUE),",
      "(o,))))))), _LOST_KEY, _TRUE),")])
row("A_take_split", "revision 5: `use_tool_id` split from the unowned test", "order", "X155", "every trial as stated", "differs",
    [("    _CONSUME(_map(use_tool_id, _compress((t,), _map(_is, _map(get_tool, (t,)), _NONE1)), _NAME1))",
      "    if get_tool(t) is None:\n        use_tool_id(t, _TOOL_NAME)")])
row("A_ensure_no_reclaim", "revision 5: `_ensure_tool` re-taking its own id without `_reclaim`", "deletion", "X137e", "MONITOR_LOST",
    "differs", [("    if t is not None:\n        _reclaim()\n        if _named(t):\n            return", "    if t is not None:\n        if _named(t):\n            return")])
row("A_mutex_time_calltime", "revision 5: the mutex's clock and sleep read through `time` at call time", "scope", "X138b", "MACHINERY_BUSY",
    "differs", [("            now = _monotonic()", "            now = time.monotonic()"), ("            _sleep(0.0002)", "            time.sleep(0.0002)")])
row("A_txn_shared_succ", "revision 5: `_Txn`'s `succ` shared between tokens", "immutability", "V52", "PASS", "a hang",
    [("class _Txn:\n    __slots__", "_SUCC0 = {}\n\n\nclass _Txn:\n    __slots__"),
     ("        self.succ = {}                       # a fresh dict per token", "        self.succ = _SUCC0                   # mutant: shared")])
row("A_register_no_owner_read", "revision 6: `_register` without the owner read after the last exchange", "deletion", "X154c", "as stated",
    "differs", [("        _map(get_tool, (t,))))\n\n\ndef _set_local", "        (_TOOL_NAME,)))\n\n\ndef _set_local")])
row("A_builtin_check", "revision 6: the builtin check on `_MON` at binding", "deletion", "X156", "UNSUPPORTED_VERSION", "differs",
    [("        if not (type(f) is BuiltinFunctionType and f.__self__ is sm and f.__name__ == nm):", "        if False:")])
row("A_vocab_check", "revision 6: the vocabulary check at binding", "deletion", "X156b", "UNSUPPORTED_VERSION", "differs",
    [("    g = globals()\n    opmod = sys.modules.get(\"_operator\")\n    if bad is None:", "    g = globals()\n    opmod = sys.modules.get(\"_operator\")\n    if False:")])
row("A_verified_widened", "revision 6: `_VERIFIED` widened to every 3.12 and 3.13 patch level", "constants", "X37b", "UNSUPPORTED_VERSION",
    "differs", [("_VERIFIED = ((3, 12, 3), (3, 13, 12))", "_VERIFIED = tuple((3, m, p) for m in (12, 13) for p in range(40))")])
row("A_rebind_no_local", "revision 6: a rebinding without local events for the existing mints", "deletion", "X137g", "PASS", "differs",
    [("                    for m in list(_MINTED.values()):\n                        _set_local(i, m.code, _LOCAL)",
      "                    for m in ():\n                        _set_local(i, m.code, _LOCAL)")])
row("A_final_off_unguarded", "revision 6: the reconciliation's last `_unwind_off(None)` without the `_TOOL[0]` guard", "deletion", "X36",
    "MONITOR_BUSY", "TypeError", [("    if _TOOL[0] is not None:\n        _unwind_off(None)", "    if True:\n        _unwind_off(None)")])
row("A_detach_read_named", "revision 6 (M3): `_detach`'s event read gated on the name", "conditions", "X137f", "MONITOR_LOST", "differs",
    [("        if o.armed and not (_MON[0][1](_TOOL[0]) & PY_UNWIND) and _ANCHORS.get(fr) is o:",
      "        if o.armed and _named(_TOOL[0]) and not (_MON[0][1](_TOOL[0]) & PY_UNWIND) and _ANCHORS.get(fr) is o:")])
row("A_detach_read_named_b", "revision 7 (F14, a second witness): `_detach`'s event read gated on the name", "conditions", "X157c",
    "MONITOR_LOST", "differs",
    [("        if o.armed and not (_MON[0][1](_TOOL[0]) & PY_UNWIND) and _ANCHORS.get(fr) is o:",
      "        if o.armed and _named(_TOOL[0]) and not (_MON[0][1](_TOOL[0]) & PY_UNWIND) and _ANCHORS.get(fr) is o:")])
_REG_COUNT = "        _map(_LOST_APPEND, _map(_is_not, _compress(a, _map(_is_not, b, _CALLBACKS5)), _repeat(None))),\n"
row("A_repair_nocount", "revision 7: a registration's repair of a replaced callback not counted in `_LOST`", "deletion", "X158",
    "MONITOR_LOST", "differs", [(_REG_COUNT, "        (),\n")])
row("A_repair_count_after", "revision 7: the repair counted by X5 after the registration returns", "order", "X158b", "MONITOR_LOST",
    "differs", [(_REG_COUNT, "        _map(bool, _map(_is_not, _compress(a, _map(_is_not, b, _CALLBACKS5)), _repeat(None))),\n"),
                ("    r = _register(t)                                 # X5.2: registration first (revision 6 order)\n",
                 "    r = _register(t)                                 # X5.2: registration first (revision 6 order)\n"
                 "    _LOST.extend([x for x in r[:-1] if x is True])\n")],
    note="the count moved out of the registration's C call into X5, right after `_register` returns")
row("A_retake_nocount", "revision 7: E4's re-take of its own id not counted", "conditions", "X154d", "as stated", "differs",
    [("                if _TOOL[0] is not None:             # a rebinding or a re-take",
      "                if _TOOL[0] is not None and _TOOL[0] != i:  # mutant: a re-take not counted")])
row("A_binding_first_only", "revision 7: the binding check only when `_MON` is first bound", "conditions", "X156c", "UNSUPPORTED_VERSION",
    "differs", [("    if bad is not None:\n        raise GateSpecError(\n            f\"[V5:UNSUPPORTED_VERSION] {bad}",
                 "    if bad is not None and _MON[0] is None:\n        raise GateSpecError(\n            f\"[V5:UNSUPPORTED_VERSION] {bad}")])
row("A_deque_by_name", "revision 7: `_CONSUME`'s deque tested by type name only", "types", "X156d", "UNSUPPORTED_VERSION", "differs",
    [("        if not (type(x) is BuiltinFunctionType and x.__name__ == \"extend\" and type(dq) is type\n"
      "                and dq.__flags__ & (1 << 8) and dq.__module__ == \"collections\"\n"
      "                and dq.__qualname__ == \"deque\" and x.__self__.maxlen == 0):",
      "        if not (type(x) is BuiltinFunctionType and x.__name__ == \"extend\" and dq.__qualname__ == \"deque\"):")])
row("A_version_at_import", "revision 7: the version read at import instead of at call time", "scope", "X37b", "UNSUPPORTED_VERSION",
    "differs", [("_VERIFIED = ((3, 12, 3), (3, 13, 12))", "_VERIFIED = ((3, 12, 3), (3, 13, 12))\n_VI0 = tuple(sys.version_info[:3])"),
                ("    gil = getattr(sys, '_is_gil_enabled', None)      # M0, read at call time (revision 9, GAP-04: no lambda)\n    vi = tuple(sys.version_info[:3])",
                 "    gil = getattr(sys, '_is_gil_enabled', None)      # M0\n    vi = _VI0"),
                ("    gil = getattr(sys, '_is_gil_enabled', None)      # E1: the M0 gate, read at call time\n    vi = tuple(sys.version_info[:3])",
                 "    gil = getattr(sys, '_is_gil_enabled', None)      # E1\n    vi = _VI0")])
row("A_pending_no_anchor", "revision 7 self-audit: a pending entry stored while no anchor is registered", "deletion", "V67", "pending 0",
    "differs", [("    if not _ANCHORS: return                         # no section open anywhere: store nothing\n", "")])
row("A_open_locked", "revision 7 self-audit: an open taking the robust mutex", "scope", "V68", "returns within 1 s", "blocks",
    [("    o = _open(core, section, sys._getframe())\n    if o is None: return fn(*args, **kwargs)",
      "    o = _locked(_open, core, section, sys._getframe())\n    if o is None: return fn(*args, **kwargs)")])
row("A_mon_reread", "revision 7 self-audit: `_MON` re-read from `sys.monitoring` at each `coverage_trace()`", "scope", "V69",
    "PASS, counter 0", "differs", [("    mon = _MON[0]\n    if mon is None:", "    mon = None\n    if mon is None:"),
                                   ("    if _MON[0] is None:                              # M0 step 7", "    if True:                                         # M0 step 7")])
row("A_section_compared_first", "revision 7 self-audit: a non-str section compared before its refusal", "order", "X78f", "counters 0", "differs",
    [("    if type(section) is not str:                     # 3. section type", "    section in core.sections\n    if type(section) is not str:                     # 3. section type")])
row("A_none_prev_nocount", "revision 8: None previous callbacks not counted", "conditions", "X158c", "MONITOR_LOST", "differs",
    [(_REG_COUNT, "        _map(_LOST_APPEND, _map(_is_not, _filter(None, _compress(a, _map(_is_not, b, _CALLBACKS5))), _repeat(None))),\n")])
row("A_pend_bare_id", "revision 8: a pending entry keyed by `id(frame)` without holding the frame", "scope", "V70", "PASS", "differs",
    [("    if out: m.pend[id(f)] = (f, offset, out)", "    if out: m.pend[id(f)] = (None, offset, out)"),
     ("    if p is not None and p[0] is f: _publish(code, p[2])", "    if p is not None: _publish(code, p[2])"),
     ("    if p is not None and p[0] is f and offset != p[1]: _publish(code, p[2])", "    if p is not None and offset != p[1]: _publish(code, p[2])")])
row("A_pend_get", "revision 8 self-audit: a confirmation that reads the pending entry without popping it", "scope", "X137i", "as stated",
    "differs", [("    f = sys._getframe(1); p = m.pend.pop(id(f), None)\n    if p is not None and p[0] is f: _publish",
                 "    f = sys._getframe(1); p = m.pend.get(id(f), None)\n    if p is not None and p[0] is f: _publish")])
row("A_adopt_no_register", "revision 8 self-audit: an adopted id not registered again", "deletion", "X154e", "PASS", "differs",
    [("    for i in (4, 3):\n        if not _named(i):\n            _take(i)\n        if _named(i):\n            r = _register(i)",
      "    for i in (4, 3):\n        adopted = _named(i)\n        if not adopted:\n            _take(i)\n        if _named(i):\n            r = [_TOOL_NAME] if adopted else _register(i)")])
row("A_open_audited_after_append", "revision 8 self-audit: an audited call in `_open` after the append", "order", "V71", "PASS", "differs",
    [("    core.openings.append(o)\n    return o", "    core.openings.append(o)\n    id(o)\n    return o")])
row("A_reload_incall_count", "revision 8 self-audit: the in-call count removed (reload shape)", "deletion", "X158e", "MONITOR_LOST",
    "differs", [(_REG_COUNT, "        (),\n")])

# ---- revision 13 (GAP-54, GAP-61, GAP-62, GAP-64) ---------------------------------------------------------
# The witnesses the Revision 13 section names for the rows their earlier witness did not see; the earlier
# witness stays an exam case and is kept in the row's note.
R13_WITNESS = {
    "A_coh_no_file_skip": "X26g", "A_cache_callee_identity": "X24g", "A_alias_by_name": "V07b", "A_mint_eq": "V74",
    "A_visible_deleted": "V36c", "A_publish_recheck": "X71d", "A_enter_claim": "X32e", "A_exit_claim": "V52b",
    "M5_exit_claim_not_idempotent": "V52b", "A_atfork_handler": "V47b", "A_pid_passthrough": "V47c",
    "A_unwind_on_recheck": "X146e", "A_detach_anchor_first": "X148b", "A_capture_outside": "X153b",
    "A_ensure_no_reclaim": "X137k", "A_open_audited_after_append": "V71b", "M3_register_before_append": "X132b",
    "A_binding_first_only": "X156c", "A_verified_widened": "X37c", "A_txn_shared_succ": "V52s",
}
for _e in CATALOG:
    if _e["id"] in R13_WITNESS:
        _old = _e["witness"]
        _e["witness"] = R13_WITNESS[_e["id"]]
        _e["spec_outcome"], _e["weakened_outcome"] = "as stated", "differs"
        _e["note"] = (_e["note"] + "; " if _e["note"] else "") + f"revision 13: named witness {_e['witness']} (before: {_old})"
row("A_capture_stale_read", "revision 13: revision 5's MF2 form of the capture rule (the event read in a statement of its "
    "own before the one call, the capture gated on that read)", "order", "X153", "as stated", "differs",
    [("    t, get_tool, get_events, set_events = _TOOL[0], _MON[0][0], _MON[0][1], _MON[0][2]\n    _CONSUME(_chain(\n        _map(_setitem",
      "    t, get_tool, get_events, set_events = _TOOL[0], _MON[0][0], _MON[0][1], _MON[0][2]\n    was_clear = not (get_events(t) & PY_UNWIND)\n"
      "    _CONSUME(_chain(\n        _map(_setitem"),
     ("                      _map(_not, _map(_and, _map(get_events, (t,)), _PYU1))))))), _LOST_KEY, _TRUE),",
      "                      (was_clear,)))))), _LOST_KEY, _TRUE),")],
    note="revision 13: X153b kills it too")
# GAP-53: the 47 re-targeted census rows and the 29 kill-shape rows. Each either reuses an existing row's patch
# (the same rule weakened in ref_v5f.py) or has its own patch; the named witness of a kill-shape row is its v5f
# case (the first the spec data lists). Frozen in sm1_census_killshape_rows.json.
_CK = os.path.join(HERE, "sm1_census_killshape_rows.json")
if os.path.exists(_CK):
    _byid = {e["id"]: e for e in CATALOG}
    _ck = json.load(open(_CK, encoding="utf-8"))
    for _r in _ck["census"] + _ck["kill"]:
        _kind, _x = _r["spec"]
        _src = _byid[_x] if _kind == "reuse" else None
        _fam = _src["family"] if _src else _r["family"]
        _pat = [tuple(p) for p in (_src["patches"] if _src else _x)]
        _what = (f"round-4 census mutant {_r['census_id']}" if "census_id" in _r else f"round-4 kill shape {_r['key']}")
        row(_r["id"], f"revision 13 (GAP-53): {_what}" + (f", re-targeted as row {_x}'s patch" if _src else ""),
            _fam, _r["witness"], "as stated", "differs", _pat, note=_r.get("note", ""))
# GAP-62: one row per empty (family, rule region) cell, the generator's first non-TCE mutant there (and O12's
# cell); the patches and the named witnesses are frozen in sm1_gap62_rows.json.
_G62 = os.path.join(HERE, "sm1_gap62_rows.json")
if os.path.exists(_G62):
    for _r in json.load(open(_G62, encoding="utf-8")):
        row(_r["id"], f"revision 13 (GAP-62): {_r['family']} in rule region {_r['rule_region']}: {_r['desc']} "
            f"({_r['mutant']})", _r["family"], _r["witness"], "as stated", "differs",
            [tuple(x) for x in _r["patches"]], note=_r.get("note", ""))

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
    v5f_tmp.disk_guard(what=f"{case} on {impl}")
    try:
        r = v5f_tmp.child_run([py, os.path.join(HERE, "run_protocol_v5f_exam.py"), "--impl", impl, "--mutation", case],
                              capture_output=True, text=True, timeout=600, env=env)
    except subprocess.TimeoutExpired:
        v5f_tmp.disk_guard(what=f"{case} on {impl}")
        return "TIMEOUT"
    v5f_tmp.check_child(r.stderr, f"{case} on {impl}")    # a full disk's failure is not a verdict
    lines = [x for x in r.stdout.splitlines() if x.startswith("MUTATION_RESULT ")]
    if not lines:
        return "CRASH: " + (r.stderr.strip().splitlines() or ["?"])[-1][:160]
    d = json.loads(lines[-1].split(" ", 1)[1])
    if case in d["not_run"]:
        return "NOT_RUN"
    x = d["results"].get(case)
    if x and x.get("timeout"):
        return "TIMEOUT_WITNESS"                     # the witness's own bound expired after it started: a kill
    if x and str(x.get("detail", "")).startswith("NOT_REACHED"):
        return "NOT_REACHED"                         # the runner failed before the witness ran: no outcome of it
    return "PASS" if x and x["ok"] and not x["leftover"] else "FAIL"


def _loadavg():
    try:
        return [round(x, 2) for x in os.getloadavg()]
    except (AttributeError, OSError):
        return None


def wait_load(max_load, what=""):
    """Hold until the 1-min and 5-min load averages are both below max_load (the coordinator's rule for the
    timing-sensitive runs made while other studies share the machine); returns the load at release."""
    if not max_load:
        return _loadavg()
    waited = 0
    while True:
        la = _loadavg()
        if la is None or (la[0] < max_load and la[1] < max_load):
            if waited:
                print(f"  load {la} below {max_load}: {what} starts after {waited} s", flush=True)
            return la
        if waited % 300 == 0:
            print(f"  load {la} at or above {max_load}: {what} waits", flush=True)
        time.sleep(30)
        waited += 30


MAX_LOAD = [None]      # --max-load: hold every G_FI sweep until the load averages are below it
LAST_CRASH_DETAIL = {}


def run_crash(py, impl, invariant):
    """One frozen crash sweep on impl; returns (status, failed_clauses). The per-scenario detail of the last call
    (unclean texts, void reasons, whether a C3 is a baseline hang, the load averages before and after) is left
    in LAST_CRASH_DETAIL[impl] for the journal: a C3 that is "baseline hang" (the 60 s bound on the fault-free run)
    can come from machine load rather than from the implementation, and such a run is not a kill."""
    v5f_tmp.disk_guard(what=f"the crash sweep on {impl}")
    load0 = wait_load(MAX_LOAD[0], f"the crash sweep on {os.path.basename(os.path.dirname(impl)) or impl}")
    with v5f_tmp.scratch("v5f_sm1_sweep_") as sd:
        out = os.path.join(sd, "sweep.json")
        try:
            r = v5f_tmp.child_run([py, os.path.join(HERE, "crash_sweep_v5f.py"), "--impl", impl, "--out", out],
                                  capture_output=True, text=True, timeout=7200)
        except subprocess.TimeoutExpired:
            v5f_tmp.disk_guard(what=f"the crash sweep on {impl}")
            print(f"  crash sweep CRASH (timeout 7200 s) on {impl}", flush=True)
            return "CRASH", []
        v5f_tmp.check_child(r.stderr if r.returncode != v5f_tmp.DISK_LOW_STATUS else "ENOSPC",
                            f"the crash sweep on {impl}")
        try:
            d = json.load(open(out))
        except (OSError, ValueError):
            print(f"  crash sweep CRASH (rc {r.returncode}: {(r.stderr.strip().splitlines() or ['?'])[-1][:160]}) "
                  f"on {impl}", flush=True)
            return "CRASH", []
    fails, detail, baseline_hang = set(), {}, False
    for scn, sc in d["scenarios"].items():
        for role, x in sc.items():
            if isinstance(x, dict):
                texts = [b for _, bad in x.get("unclean", []) for b in bad]
                for b in texts:
                    fails.add(b.split(":", 1)[0].split(" ")[0])
                if role == "C4" and not x.get("ok"):
                    fails.add("C4")
                bh = [b for b in texts if b.startswith("C3: baseline hang")]
                baseline_hang = baseline_hang or bool(bh)
                if texts or x.get("void") or (role == "C4" and not x.get("ok")):
                    detail[f"{scn}/{role}"] = {"n_unclean": x.get("n_unclean"), "void": x.get("void"),
                                               "first": texts[:2], "baseline_hang": bool(bh),
                                               "c4_ok": x.get("ok") if role == "C4" else None}
    LAST_CRASH_DETAIL[impl] = {"detail": detail, "baseline_hang": baseline_hang, "G_FI": d.get("G_FI"),
                               "seconds": d.get("seconds"), "load_before": load0, "load_after": _loadavg()}
    return ("PASS" if d["G_FI"] == "PASS" else "FAIL"), sorted(fails)


# Journal keys (the coordinator's condition for revision 13): every entry carries the sha256 of ref_v5f.py, of
# the runner, of the row's patch and of the witness case's source, as they were when its runs were made; a rerun
# reuses an entry only if all four still match the files on disk, and re-decides every other.
import ast as _ast, hashlib as _hashlib
RUNNER_PATH = os.path.join(HERE, "run_protocol_v5f_exam.py")
SWEEP_PATH = os.path.join(HERE, "crash_sweep_v5f.py")
PORT_PATH = os.path.join(HERE, "v5e_port.py")
_SOURCES = {}


def _h(text):
    return _hashlib.sha256(text.encode("utf-8")).hexdigest()


def _case_sources(runner_text):
    """{case id: the text of its @case function and row, its @sub bodies, and every module-level function or
    class of the runner it reaches by name, transitively}; cached by the runner's text."""
    k = _h(runner_text)
    if k in _SOURCES:
        return _SOURCES[k]
    tree = _ast.parse(runner_text)
    defs = {n.name: n for n in tree.body if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef))}
    cases, subs = {}, collections.defaultdict(list)
    for n in tree.body:
        if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            for d in n.decorator_list:
                if isinstance(d, _ast.Call) and isinstance(d.func, _ast.Name) and d.args and isinstance(d.args[0], _ast.Constant):
                    if d.func.id == "case":
                        cases[d.args[0].value] = (n, " | ".join(str(a.value) for a in d.args if isinstance(a, _ast.Constant)))
                    elif d.func.id == "sub":
                        subs[str(d.args[0].value).split(":")[0]].append(n)

    lines = runner_text.splitlines(keepends=True)
    seg = {nm: "".join(lines[n.lineno - 1:n.end_lineno]) for nm, n in defs.items()}
    direct = {nm: {y.id for y in _ast.walk(n) if isinstance(y, _ast.Name) and y.id in defs} for nm, n in defs.items()}

    def reach(roots):
        seen, stack = set(roots), list(roots)
        while stack:
            for y in direct[stack.pop()]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        return seen
    out = {}
    for cid, (fn, row) in cases.items():
        names = sorted(reach([fn.name] + [n.name for n in subs.get(cid, [])]))
        out[cid] = row + "\n" + "\n".join(seg[nm] for nm in names)
    _SOURCES[k] = out
    return out


def _keys(witness, patches):
    runner = open(RUNNER_PATH, encoding="utf-8").read()
    if witness.startswith("G_FI:"):
        wsrc = open(SWEEP_PATH, encoding="utf-8").read()
    elif witness.startswith("v5e:"):
        wsrc = witness + "\n" + open(PORT_PATH, encoding="utf-8").read()
    else:
        wsrc = _case_sources(runner).get(witness, "<no such case>")
    return {"ref_sha256": _h(open(REF_PATH, encoding="utf-8").read()), "runner_sha256": _h(runner),
            "patch_sha256": _h(json.dumps(patches)) if patches is not None else None, "witness_sha256": _h(wsrc)}


def _journal(path):
    """The journal's entries whose four keys match the files on disk now (the others are re-decided)."""
    rows, refs = {}, {}
    cat = {e["id"]: e for e in CATALOG}
    if path and os.path.exists(path):
        for ln in open(path):
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            if d.get("kind") == "ref":
                if d.get("keys") == _keys(d["witness"], None):
                    refs[(d["ver"], d["witness"])] = d["ref"]
            elif d.get("kind") == "row":
                e = cat.get(d["id"])
                if e is not None and d.get("witness") == e["witness"] and d.get("keys") == _keys(e["witness"], e["patches"]):
                    rows[(d["ver"], d["id"])] = d
    return rows, refs


def _append(path, d, lock):
    with lock:
        with open(path, "a") as fh:
            fh.write(json.dumps(d) + "\n")


def sm1(pys, only=None, deps=None, journal=None, jobs=3, crash=True, redo=None):
    """Resumable: every ref run pair and every row verdict is appended to the journal (JSON lines) as it is
    decided; a rerun with the same journal skips them (the latest entry for a row wins). Crash-sweep rows run one
    at a time (crash=False skips). redo: row ids whose journal entries are ignored, so they are decided again."""
    import threading, concurrent.futures as cf
    journal = journal or os.path.join(HERE, "results_v5f", "sm1_journal.jsonl")
    done, refs = _journal(journal)
    for k in [k for k in done if k[1] in (redo or ())]:
        del done[k]
    lock = threading.Lock()
    work = v5f_tmp.workdir("v5f_sm1_")                 # one patched copy per row, removed when the row is decided
    res = {"rows": {}, "versions": {}, "journal": journal}
    for py in pys:
        ver = subprocess.run([py, "-c", "import sys;print('.'.join(map(str,sys.version_info[:3])))"],
                             capture_output=True, text=True).stdout.strip()
        dp = (deps or {}).get(ver)
        todo = [e for e in CATALOG if (not only or e["id"] in only) and ver in e["versions"]
                and (ver, e["id"]) not in done and (crash or not e["witness"].startswith("G_FI:"))]
        rlocks = collections.defaultdict(threading.Lock)

        def ref_of(w):
            with rlocks[w]:
                if (ver, w) not in refs:
                    shared = [k for k in refs if k[0] == ver and k[1].startswith("G_FI:")] if w.startswith("G_FI:") else []
                    keys = _keys(w, None)
                    if shared:          # the reference sweep's verdict does not depend on the invariant named
                        r = refs[shared[0]]
                    elif w.startswith("G_FI:"):
                        r = [run_crash(py, REF_PATH, w.split(":")[1])[0] for _ in range(2)]
                    else:
                        r = [run_case(py, REF_PATH, w, dp) for _ in range(2)]
                    refs[(ver, w)] = r
                    _append(journal, {"kind": "ref", "ver": ver, "witness": w, "ref": r, "keys": keys}, lock)
                return refs[(ver, w)]

        def one(e):
            v5f_tmp.disk_guard(what=f"row {e['id']} on {ver}")
            keys = _keys(e["witness"], e["patches"])
            src = apply(e)
            d = os.path.join(work, ver, e["id"])
            if src is None:
                row = {"class": "NOT_ADMITTED", "why": "(1) the patch does not apply exactly once"}
            else:
                os.makedirs(d, exist_ok=True)
                impl = os.path.join(d, "ref_v5f.py")
                open(impl, "w").write(src)
                w = e["witness"]
                base = ref_of(w)
                extra = {}
                if w.startswith("G_FI:"):
                    inv = w.split(":")[1]
                    runs, details = [], []
                    for _ in range(2):
                        runs.append(list(run_crash(py, impl, inv)))
                        details.append(LAST_CRASH_DETAIL.get(impl))
                    extra = {"detail": details, "load": [(x or {}).get("load_before") for x in details]}
                    hung = any((x or {}).get("baseline_hang") for x in details)
                    if base != ["PASS", "PASS"]:
                        cls = "NOT_ADMITTED"
                    elif hung:
                        cls = "VOID_LOAD"   # a fault-free run passed the 60 s bound: not the implementation's verdict; rerun under low load
                    elif runs[0] != runs[1]:
                        cls = "NONREPRODUCIBLE"
                    elif runs[0][0] == "PASS":
                        cls = "UNWITNESSED"
                    else:
                        cls = "KILLED" if inv in runs[0][1] else "WITNESS_MISMATCH"
                else:
                    extra = {"load": _loadavg()}
                    runs = [run_case(py, impl, w, dp) for _ in range(2)]
                    if base != ["PASS", "PASS"]:
                        cls = "NOT_ADMITTED"
                    elif runs[0] != runs[1]:
                        cls = "NONREPRODUCIBLE"
                    elif runs[0] == "PASS":
                        cls = "UNWITNESSED"
                    elif runs[0] in ("TIMEOUT", "NOT_REACHED"):
                        cls = "HANG"        # the witness never ran (the driver's timeout, or the runner failed first)
                    else:
                        cls = "KILLED"
                row = {"class": cls, "ref": base, "runs": runs, **extra}
                v5f_tmp.release(d)
            row.update({"kind": "row", "ver": ver, "id": e["id"], "witness": e["witness"], "keys": keys})
            _append(journal, row, lock)
            print(ver, e["id"], row["class"], flush=True)
            return row
        plain = [e for e in todo if not e["witness"].startswith("G_FI:")]
        with cf.ThreadPoolExecutor(jobs) as ex:
            list(ex.map(one, plain))
        for e in todo:
            if e["witness"].startswith("G_FI:"):
                one(e)
    done, _ = _journal(journal)
    vers = sorted({v for v, _ in done})
    for ver in vers:
        rows = {i: {k: x for k, x in d.items() if k not in ("kind", "ver", "id")} for (v, i), d in done.items()
                if v == ver and (not only or i in only)}
        res["rows"][ver] = rows
        adm = [k for k, r in rows.items() if r["class"] in ("KILLED", "WITNESS_MISMATCH", "NONREPRODUCIBLE", "HANG", "VOID_LOAD")]
        killed = [k for k in adm if rows[k]["class"] == "KILLED"]
        want = [e["id"] for e in CATALOG if ver in e["versions"] and (not only or e["id"] in only)]
        res["versions"][ver] = {"rows_decided": len(rows), "rows_in_catalog": len(want),
                                "missing": sorted(set(want) - set(rows)),
                                "admitted": len(adm), "killed": len(killed),
                                "not_killed": sorted(set(adm) - set(killed)),
                                "unwitnessed": sorted(k for k, r in rows.items() if r["class"] == "UNWITNESSED"),
                                "hang": sorted(k for k, r in rows.items() if r["class"] == "HANG"),
                                "void_load": sorted(k for k, r in rows.items() if r["class"] == "VOID_LOAD"),
                                "not_admitted": sorted(k for k, r in rows.items() if r["class"] == "NOT_ADMITTED"),
                                "gate": len(adm) == len(killed) and len(rows) >= len(want)}
    res["gate"] = bool(res["versions"]) and all(v["gate"] for v in res["versions"].values())
    return res


def main(argv):
    if "--list" in argv:
        for e in CATALOG:
            print(e["id"], "|", e["witness"], "|", e["family"], "|", e["rule"])
        print(len(CATALOG), "rows")
        return 0
    if "--sm1" in argv:
        i = argv.index("--sm1")
        pys = []
        for a in argv[i + 1:]:
            if a.startswith("--"):
                break
            pys.append(a)
        only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
        deps = json.loads(argv[argv.index("--deps") + 1]) if "--deps" in argv else None
        out = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(HERE, "sm1_result.json")
        t0 = time.monotonic()
        journal = argv[argv.index("--journal") + 1] if "--journal" in argv else None
        jobs = int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 3
        redo = argv[argv.index("--redo") + 1].split(",") if "--redo" in argv else None
        MAX_LOAD[0] = float(argv[argv.index("--max-load") + 1]) if "--max-load" in argv else None
        try:
            res = sm1(pys, only, deps, journal, jobs, crash="--no-crash" not in argv, redo=redo)
        except v5f_tmp.DiskLow as e:                 # nothing undecided was journaled; rerun with the journal
            return v5f_tmp.stop_disk_low(e, journal or "the default journal")
        res["seconds"] = round(time.monotonic() - t0, 1)
        res["catalog_rows"] = len(CATALOG)
        json.dump(res, open(out, "w"), indent=1)
        print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
        return 0 if res["gate"] else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    finally:
        v5f_tmp.cleanup()
