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
row("A_mint_eq", "`is` vs `==` (the minted-code test by equality)", "comparisons", "X45", "CLONE_CALLED", "differs",
    [("    m = _MINTED.get(id(code))\n    if m is None or m.code is not code: return\n    f = sys._getframe(1)\n    holders",
      "    m = _MINTED.get(id(code))\n    if m is None or m.code != code: return\n    f = sys._getframe(1)\n    holders")],
    note="also X46")
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
row("A_swapped_at_entry", "CODE_SWAPPED at entry (E4.3 and the join's check)", "deletion", "X31", "CODE_SWAPPED", "differs",
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
    [("\"styxx.protocol/\" + os.urandom(6).hex()", "\"styxx.protocol\"")])
row("A_unwind_off_ungated", "events changed on an id that lost its name (`_unwind_off` without the name gate)", "deletion",
    "X137-free", "as stated", "differs",
    [("                    _map(set_events, _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),\n                                               _map(_not, (_ANCHORS,))), _ZERO1)))",
      "                    _map(set_events, _compress((t,), _map(_not, (_ANCHORS,))), _ZERO1)))")])
# confirmation
row("A_unwind_offset", "unwind-offset check deleted", "deletion", "X135", "as stated", "credited",
    [("if p is not None and p[0] is f and offset != p[1]: _publish(code, p[2])", "if p is not None and p[0] is f: _publish(code, p[2])")])
row("A_py_throw_credited", "PY_THROW credited (an entry event)", "scope", "X119", "NOT_EXERCISED", "credited",
    [("_EVENTS5 = (PY_START, PY_RESUME, PY_RETURN, PY_YIELD, PY_UNWIND)", "_EVENTS5 = (PY_START, PY_RESUME, PY_RETURN, PY_YIELD, PY_UNWIND, 8192)"),
     ("_LOCAL = PY_START | PY_RESUME | PY_RETURN | PY_YIELD ", "_LOCAL = PY_START | PY_RESUME | PY_RETURN | PY_YIELD | 8192"),
     ("_CALLBACKS5 = (_on_entry, _on_entry, _on_exit, _on_exit, _on_unwind)", "_CALLBACKS5 = (_on_entry, _on_entry, _on_exit, _on_exit, _on_unwind, _on_entry)"),
     ("_map(get_tool, _repeat(t, 5))", "_map(get_tool, _repeat(t, 6))")])
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
    [("               f\"(declared: {list(core.sections)})\")\n        core.problems.append(txt)\n        raise GateSpecError(txt)\n    loop",
      "               f\"(declared: {list(core.sections)})\")\n        raise GateSpecError(txt)\n    loop")], note="also X78-X79, X32")
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
