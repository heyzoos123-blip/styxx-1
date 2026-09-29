# Builds rev9's probe copies of ref_v5f.py (revision 9's GAP-02 and GAP-03 text applied) and three
# single-rule mutants. usage: python build.py <out dir>. The copies are generated, not committed.
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "../../v5f_exam/ref_v5f.py")).read()
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
def rep(s, a, b, n=1):
    assert s.count(a) == n, (a, s.count(a)); return s.replace(a, b)
# GAP-03: get_local_events is _MON[0][6]
s = rep(src, "sm.register_callback, sm.use_tool_id)", "sm.register_callback, sm.use_tool_id, sm.get_local_events)")
s = rep(s, '''"register_callback",
               "use_tool_id"):''', '''"register_callback",
               "use_tool_id", "get_local_events"):''')
s = rep(s, "gle = sys.monitoring.get_local_events       # GAP-03: not one of _MON's six", "gle = _MON[0][6]")
s = rep(s, "le = sys.monitoring.get_local_events(t, m.code) if", "le = mon[6](t, m.code) if")
# GAP-02: check asyncio.events._get_running_loop after import asyncio; bind nothing until both checks pass
s = rep(s, '''    if _MON[0] is None:
        _MON[0] = mon
    import asyncio
    global _get_running_loop
    _get_running_loop = asyncio.events._get_running_loop
''', '''    import asyncio
    grl = asyncio.events._get_running_loop
    if not (type(grl) is BuiltinFunctionType and grl.__name__ == "_get_running_loop"
            and grl.__self__ is sys.modules.get("_asyncio")):
        raise GateSpecError(
            "[V5:UNSUPPORTED_VERSION] asyncio.events._get_running_loop is not the C builtin (a "
            "wrapper was installed before this coverage_trace()): the loop boundary must read the "
            "running loop in C")
    if _MON[0] is None:
        _MON[0] = mon
    global _get_running_loop
    _get_running_loop = grl
''')
open(os.path.join(OUT, "ref9.py"), "w").write(s)
# mutant: get_local_events read at call time (the author's reading)
open(os.path.join(OUT, "mut_gle_calltime.py"), "w").write(rep(rep(s, "gle = _MON[0][6]", "gle = sys.monitoring.get_local_events"),
    "le = mon[6](t, m.code) if", "le = sys.monitoring.get_local_events(t, m.code) if"))
# mutant: get_local_events bound but not checked
open(os.path.join(OUT, "mut_gle_nocheck.py"), "w").write(rep(s, '''"register_callback",
               "use_tool_id", "get_local_events"):''', '''"register_callback",
               "use_tool_id"):'''))
# mutant: _get_running_loop not checked
open(os.path.join(OUT, "mut_grl_nocheck.py"), "w").write(rep(s, '''    if not (type(grl) is BuiltinFunctionType and grl.__name__ == "_get_running_loop"
            and grl.__self__ is sys.modules.get("_asyncio")):''', '''    if False:'''))
print("built")
# mutant for X59e (GAP-19): X6 records CUT_MOVED before the CLONE_ALIVE texts
a = '''    for m in held:                                   # X6: tripwires, outside the mutex
        txt = _clone_alive(m)
        if txt is not None:
            probs.append(txt)
    if 'CUT_MOVED' in core.flags or not _cut_ok():
        probs.append(
            "[V5:CUT_MOVED] asyncio.events.Handle._run or asyncio.base_events.BaseEventLoop."
            "_run_once was rebound, or its code replaced, while this trace saw it: dispatch through "
            "the moved binding is not cut")
'''
b = '''    if 'CUT_MOVED' in core.flags or not _cut_ok():
        probs.append(
            "[V5:CUT_MOVED] asyncio.events.Handle._run or asyncio.base_events.BaseEventLoop."
            "_run_once was rebound, or its code replaced, while this trace saw it: dispatch through "
            "the moved binding is not cut")
    for m in held:                                   # X6: tripwires, outside the mutex
        txt = _clone_alive(m)
        if txt is not None:
            probs.append(txt)
'''
open(os.path.join(OUT, "mut_order_cut_first.py"), "w").write(rep(s, a, b))
# mutant for X59e: the transaction's CODE_SWAPPED texts recorded before X4's CLONE_CALLED texts
a2 = '''    probs = []                                       # X4
    for cid, q in list(dict(core.clone_called).items()):'''
b2 = '''    probs = []                                       # X4
    early = probs
    for cid, q in list(dict(core.clone_called).items()):'''
m2 = rep(s, a2, b2)
m2 = rep(m2, "    probs.extend(more[0])\n", "    probs[0:0] = more[0]\n")
open(os.path.join(OUT, "mut_order_swapped_first.py"), "w").write(m2)
print("built order mutants")
