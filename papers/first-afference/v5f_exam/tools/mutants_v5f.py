"""Single-rule weakenings of ref_v5f.py, written by the exam author from the design text.

Each mutant is one or two exact textual replacements in ref_v5f.py. For each mutant this script
builds a copy of ref_v5f.py and smoke_cases.py in a temporary directory, runs the mutant's named
witness case(s) (SMOKE_ONLY), and reports DETECTED if at least one named witness fails. The
unmutated reference is run first on the same cases as a control (every one must pass).

Usage: python tools/mutants_v5f.py <python> [<python> ...] [--only name,name]
Exit status 0 iff the control passes and every mutant is detected on every interpreter.
"""
import os, shutil, subprocess, sys, tempfile

EXAM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if EXAM not in sys.path:
    sys.path.append(EXAM)
import v5f_tmp      # noqa: E402  the mutant copies are removed at exit; each smoke run's TMPDIR when it returns
REF = open(os.path.join(EXAM, "ref_v5f.py")).read()

# name -> (witness cases, [(old, new), ...])
M = {
 # revision 8 (the first artifacts)
 "mut_end_type_not_tested": (["X103c"], [("            if type(end) is not str or end not in _ENDS:", "            if end not in _ENDS:")]),
 "mut_no_unwind_lost_flag": (["X137c"], [("            o.core.flags['UNWIND_LOST'] = True      # the event first, the anchor last", "            pass")]),
 "mut_no_unwind_on_in_commit": (["V01", "X143c"], [("    _unwind_on(o)                                   # one call, after the store", "    pass")]),
 # revision 9 (the exam author's gaps)
 "mut_gle_calltime": (["V69b", "V69b-v"], [
     ("        gle = _MON[0][6]                             # C3 (GAP-03): the bound get_local_events", "        gle = sys.monitoring.get_local_events"),
     ("        le = mon[6](t, m.code) if", "        le = sys.monitoring.get_local_events(t, m.code) if")]),
 "mut_gle_nocheck": (["X156f"], [('               "use_tool_id", "get_local_events"):', '               "use_tool_id"):')]),
 "mut_grl_nocheck": (["X156g"], [('    if not (type(grl) is BuiltinFunctionType and grl.__name__ == "_get_running_loop"\n            and grl.__self__ is sys.modules.get("_asyncio")):', '    if False:')]),
 "mut_order_cut_first": (["X59e", "X59e-v"], [("""    for m in held:                                   # X6: tripwires, outside the mutex, held order
        txt = _clone_alive(m)
        if txt is not None:
            probs.append(txt)
    if 'CUT_MOVED' in core.flags or not _cut_ok():
        probs.append(
            "[V5:CUT_MOVED] asyncio.events.Handle._run or asyncio.base_events.BaseEventLoop."
            "_run_once was rebound, or its code replaced, while this trace saw it: dispatch through "
            "the moved binding is not cut")""", """    if 'CUT_MOVED' in core.flags or not _cut_ok():
        probs.append(
            "[V5:CUT_MOVED] asyncio.events.Handle._run or asyncio.base_events.BaseEventLoop."
            "_run_once was rebound, or its code replaced, while this trace saw it: dispatch through "
            "the moved binding is not cut")
    for m in held:
        txt = _clone_alive(m)
        if txt is not None:
            probs.append(txt)""")]),
 "mut_order_swapped_first": (["X59e", "X59e-v"], [("    else:\n        probs.extend(swapped)", "    else:\n        probs[:0] = swapped")]),
 # revision 10 (the verifier's findings on revision 9, and the GAP-W triage)
 "mut_sec_repr": (["X78f"], [('            txt = (f"[V5:UNDECLARED_SECTION] a section of type "\n                   f"{_TYPE_QUAL.__get__(type(section))} is not a str;',
                              '            txt = (f"[V5:UNDECLARED_SECTION] a section "\n                   f"{section!r} is not a str;')]),
 "mut_sec_attrqual": (["X78f"], [('            txt = (f"[V5:UNDECLARED_SECTION] a section of type "\n                   f"{_TYPE_QUAL.__get__(type(section))} is not a str;',
                                  '            txt = (f"[V5:UNDECLARED_SECTION] a section of type "\n                   f"{type(section).__qualname__} is not a str;')]),
 "mut_inactive_repr": (["X78h"], [('        shown = repr(section) if type(section) is str else "of type " + _TYPE_QUAL.__get__(type(section))',
                                   '        shown = repr(section)')]),
 "mut_inactive_attrqual": (["X78h"], [('        shown = repr(section) if type(section) is str else "of type " + _TYPE_QUAL.__get__(type(section))',
                                       '        shown = repr(section) if type(section) is str else "of type " + type(section).__qualname__')]),
 "mut_notrace1_attrqual": (["X93e"], [('                f"{_TYPE_QUAL.__get__(type(result))}, not a dict -- run the harness inside "',
                                       '                f"{type(result).__qualname__}, not a dict -- run the harness inside "')]),
 "mut_notrace3_attrqual": (["X93e"], [("{_TRACE_KEY!r} is a {_TYPE_QUAL.__get__(type(tr))}, ", "{_TRACE_KEY!r} is a {type(tr).__qualname__}, ")]),
 "mut_stamp_attrqual": (["X24f"], [("names a different object (a {_TYPE_QUAL.__get__(type(stamped))}); ", "names a different object (a {type(stamped).__qualname__}); ")]),
 "mut_callee_none_text": (["X24f"], [('                cname = "no single Python function"', '                cname = "None"')]),
 "mut_nested_mirror": (["X84"], [("""        p = _ANCHORS.get(g)
        if p is not None and p.core is core and p.loop is loop:""", """        p = _ANCHORS.get(g)
        if p is not None and p.loop is not loop:
            break
        if p is not None and p.core is core and p.loop is loop:""")]),
 "mut_grl_check_once": (["X156h"], [('    if not (type(grl) is BuiltinFunctionType and grl.__name__ == "_get_running_loop"',
                                     '    if globals().get("_get_running_loop") is None and not (type(grl) is BuiltinFunctionType and grl.__name__ == "_get_running_loop"')]),
 "mut_bind_before_asyncio": (["X156i"], [("    import asyncio                                   # M0 step 5 (GAP-09)",
                                          "    if _MON[0] is None:\n        _MON[0] = mon\n    import asyncio")]),
 "mut_cm_resolve": (["X117e"], [("""            for k in path.split("."):
                if not issubclass(type(val), dict):
                    found = False
                    break
                val = dict.get(val, k, _MISSING)
                if val is _MISSING:
                    found = False
                    break
            if not found:
                out[name] = {"path": path""", """            for k in path.split("."):
                if not isinstance(val, dict) or k not in val:
                    found = False
                    break
                val = val[k]
            if not found:
                out[name] = {"path": path""")]),
 "mut_cm_get": (["X117e"], [("""                val = dict.get(val, k, _MISSING)
                if val is _MISSING:
                    found = False
                    break
            if not found:
                out[name] = {"path": path""", """                val = val.get(k, _MISSING)
                if val is _MISSING:
                    found = False
                    break
            if not found:
                out[name] = {"path": path""")]),
 "mut_cm_smoke": (["X117f"], [("                if smoke and not present:\n                    note = \"smoke run\"", "                if not present:\n                    note = \"smoke run\"")]),
 # revision 13: the guard line carries the "cycle" value of M10's total walk; the weakened part is unchanged
 "mut_guard_no_alive": (["V72"], [('"guard": "cycle" if n is not None else ("free" if r.tid is None else ("held" if _alive(r) else "dead")),', '"guard": "cycle" if n is not None else ("free" if r.tid is None else "held"),')]),
 "mut_guard_never_held": (["V72"], [('"guard": "cycle" if n is not None else ("free" if r.tid is None else ("held" if _alive(r) else "dead")),', '"guard": "cycle" if n is not None else ("free" if r.tid is None else "dead"),')]),
 "mut_import_no_chain": (["X10c"], [('            f"{_TYPE_QUAL.__get__(type(e))}") from e\n    if not issubclass(type(mod), ModuleType):',
                                     '            f"{_TYPE_QUAL.__get__(type(e))}") from None\n    if not issubclass(type(mod), ModuleType):')]),
 "mut_getattr_no_chain": (["X10c"], [('                        f"({part!r}) raised {_TYPE_QUAL.__get__(type(e))}") from e',
                                      '                        f"({part!r}) raised {_TYPE_QUAL.__get__(type(e))}") from None')]),
 "mut_inherited_str": (["X14d"], [("(dm if type(dm) is str else '?')", "str(dm)")]),
 "mut_notes_order": (["V73"], [("""            notes = list(notes)
            if o.lazy is not None:
                notes.append(o.lazy)""", """            notes = list(notes)
            if o.lazy is not None:
                notes.insert(0, o.lazy)""")]),
 # revision 11 (the new cases; each a single-rule weakening named by the text or written from its rule)
 "mut_no_locals_clause": (["X35e"], [("        if '<locals>' in c.co_qualname or twins:", "        if twins:")]),
 "mut_cut_before_scan": (["X35e"], [("        twins = [r for r in gc.get_referrers(c) if type(r) is FunctionType and r is not x]",
                                     "        _CUT.setdefault(id(c), c)\n        twins = [r for r in gc.get_referrers(c) if type(r) is FunctionType and r is not x]")]),
 "mut_freeze0_at_join": (["X57d"], [("        m.holders = m.holders + (core,)", "        m.holders = m.holders + (core,)\n        m.freeze0 = gc.get_freeze_count()")]),
 "mut_freeze_ne": (["R24"], [("    if gc.get_freeze_count() > m.freeze0:", "    if gc.get_freeze_count() != m.freeze0:")]),
 "mut_cm_bool": (["X117g"], [("            usable = issubclass(tv, (int, float)) and tv is not bool and _finite(val)",
                              "            usable = issubclass(tv, (int, float)) and tv is not bool and _finite(val) and (bool(val) or True)")]),
 "mut_prune_marks_exited": (["V72b"], [("def _prune(h):\n    for o in list(h.openings):", "def _prune(h):\n    h.marks['exited'] = True\n    for o in list(h.openings):")]),
 "mut_unwind_off_pyu_only": (["X137j"], [("                                               _map(_not, (_ANCHORS,))), _ZERO1)))",
                                          "                                               _map(_not, (_ANCHORS,))),\n"
                                          "                    ((_MON[0][1](t) & ~PY_UNWIND) if t is not None and get_tool(t) is _TOOL_NAME else 0,))))")]),
 # revision 12
 "mut_freeze_premise_deleted": (["R25"], [("    if gc.get_freeze_count() > m.freeze0:", "    if True:")]),
 "mut_rebind_nocount": (["X137h"], [("                    _LOST.append(True)\n                    for m in list(_MINTED.values()):",
                                     "                    pass\n                    for m in list(_MINTED.values()):")]),
 "mut_clone_by_referrers": (["R23"], [("    if f.f_globals is not m.globals:                # CLONE_CALLED: credits nothing",
                                       "    if f.f_globals is not m.globals or [r for r in gc.get_referrers(code) if type(r) is FunctionType and r is not m.fn]:")]),
}


def run(py, d, cases):
    env = dict(os.environ, SMOKE_ONLY=",".join(cases))
    r = v5f_tmp.child_run([py, os.path.join(d, "smoke_cases.py")], capture_output=True, text=True,
                          timeout=900, env=env)
    fails = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("FAIL")]
    passes = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("PASS")]
    return fails, passes, r


def main(argv):
    only = None
    if "--only" in argv:
        i = argv.index("--only"); only = argv[i + 1].split(","); del argv[i:i + 2]
    pys = argv or [sys.executable]
    names = [n for n in M if not only or n in only]
    root = v5f_tmp.workdir("v5f_mutants_")
    bad = 0
    allcases = sorted({c for n in names for c in M[n][0]})
    ctl = os.path.join(root, "control"); os.makedirs(ctl)
    shutil.copy(os.path.join(EXAM, "ref_v5f.py"), ctl); shutil.copy(os.path.join(EXAM, "smoke_cases.py"), ctl)
    for py in pys:
        fails, passes, r = run(py, ctl, allcases)
        ok = not fails and sorted(passes) == allcases
        bad += not ok
        print(f"{'control':26s} {py}: {'PASS' if ok else 'FAIL'} {len(passes)}/{len(allcases)} witness cases {fails}")
    for name in names:
        wit, patches = M[name]
        src = REF
        for a, b in patches:
            assert src.count(a) == 1, (name, a[:70])
            src = src.replace(a, b)
        d = os.path.join(root, name); os.makedirs(d)
        open(os.path.join(d, "ref_v5f.py"), "w").write(src)
        shutil.copy(os.path.join(EXAM, "smoke_cases.py"), d)
        for py in pys:
            fails, passes, r = run(py, d, wit)
            ok = bool(fails)
            bad += not ok
            verdict = "DETECTED" if ok else ("SURVIVED" if passes else "BROKEN (no case ran: " + r.stderr.strip().splitlines()[-1][:120] + ")")
            print(f"{name:26s} {py}: {verdict} by {fails} (witness {wit})")
    shutil.rmtree(root, ignore_errors=True)
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    finally:
        v5f_tmp.cleanup()
