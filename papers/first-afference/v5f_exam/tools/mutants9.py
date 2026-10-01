"""Revision-9 receipt (commit c7de7761): 8 weakenings, whole smoke suite per mutant. Superseded by
tools/mutants_v5f.py, which carries the same mutants and names each one's witness."""

import os, shutil, subprocess, sys
EXAM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(EXAM)
import v5f_tmp      # noqa: E402  removed at exit; each smoke run's TMPDIR when it returns
HERE = v5f_tmp.workdir("v5f_mutants9_")
REF = open(os.path.join(EXAM, "ref_v5f.py")).read()
M = {
 "mut_end_type_not_tested": [("            if type(end) is not str or end not in _ENDS:", "            if end not in _ENDS:")],
 "mut_no_unwind_lost_flag": [("            o.core.flags['UNWIND_LOST'] = True      # the event first, the anchor last", "            pass")],
 "mut_no_unwind_on_in_commit": [("    _unwind_on(o)                                   # one call, after the store", "    pass")],
 # revision 9
 "mut_gle_calltime": [("        gle = _MON[0][6]                             # C3 (GAP-03): the bound get_local_events",
                       "        gle = sys.monitoring.get_local_events"),
                      ("        le = mon[6](t, m.code) if", "        le = sys.monitoring.get_local_events(t, m.code) if")],
 "mut_gle_nocheck": [('               "use_tool_id", "get_local_events"):', '               "use_tool_id"):')],
 "mut_grl_nocheck": [('    if not (type(grl) is BuiltinFunctionType and grl.__name__ == "_get_running_loop"\n            and grl.__self__ is sys.modules.get("_asyncio")):',
                      '    if False:')],
 "mut_order_cut_first": [("""    for m in held:                                   # X6: tripwires, outside the mutex, held order
        txt = _clone_alive(m)
        if txt is not None:
            probs.append(txt)
    if 'CUT_MOVED' in core.flags or not _cut_ok():
        probs.append(
            "[V5:CUT_MOVED] asyncio.events.Handle._run or asyncio.base_events.BaseEventLoop."
            "_run_once was rebound, or its code replaced, while this trace saw it: dispatch through "
            "the moved binding is not cut")""",
"""    if 'CUT_MOVED' in core.flags or not _cut_ok():
        probs.append(
            "[V5:CUT_MOVED] asyncio.events.Handle._run or asyncio.base_events.BaseEventLoop."
            "_run_once was rebound, or its code replaced, while this trace saw it: dispatch through "
            "the moved binding is not cut")
    for m in held:
        txt = _clone_alive(m)
        if txt is not None:
            probs.append(txt)""")],
 "mut_order_swapped_first": [("""    else:
        probs.extend(swapped)""", """    else:
        probs[:0] = swapped""")],
}
vers = sys.argv[1:]
bad = 0
for name, patches in M.items():
    src = REF
    for a, b in patches:
        assert src.count(a) == 1, (name, a[:60])
        src = src.replace(a, b)
    d = os.path.join(HERE, name)
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    open(os.path.join(d, "ref_v5f.py"), "w").write(src)
    shutil.copy(os.path.join(EXAM, "smoke_cases.py"), d)
    for py in vers:
        r = v5f_tmp.child_run([py, os.path.join(d, "smoke_cases.py")], capture_output=True, text=True, timeout=900)
        fails = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("FAIL")]
        tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]
        ok = r.returncode != 0 and fails
        bad += not ok
        print(f"{name:28s} {os.path.basename(os.path.dirname(os.path.dirname(py)))}: {'DETECTED' if ok else 'SURVIVED'} by {fails} ({tail})")
sys.exit(1 if bad else 0)
