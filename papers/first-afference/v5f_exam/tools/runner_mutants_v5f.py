"""Run single-rule weakenings of ref_v5f.py against the frozen runner (not the smoke cases).

Two sets:
  * every weakening in tools/mutants_v5f.py (M), run on the runner's cases named as its witnesses;
  * the hazard-sweep detection mutants the text names (H1, H2, H6's M1 and M6, H8, H9 in its revision-12
    while form, H10, M10), each run on its sweep, and revision 12's weakenings for its new and changed
    witnesses (X57b's and R25's CLONE_ALIVE text and premise, X137h, X154, X154b, X158d).

For each mutant the runner is started as `run_protocol_v5f_exam.py --impl <mutant> --only <witnesses>`,
and the mutant is KILLED iff the runner's verdict is FAIL (a failure other than a known spec gap).
The unmutated reference is run first on the union of the witnesses as a control.

Usage: python tools/runner_mutants_v5f.py <python> [<python> ...] [--only name,name] [--hazard-only]
Exit status 0 iff the control passes and every mutant is killed on every interpreter.
"""
import json, os, runpy, subprocess, sys, tempfile

EXAM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = open(os.path.join(EXAM, "ref_v5f.py")).read()
RUNNER = os.path.join(EXAM, "run_protocol_v5f_exam.py")
SMOKE_M = runpy.run_path(os.path.join(EXAM, "tools", "mutants_v5f.py"), run_name="mutants")["M"]


def _cb_except():
    """H2's mutant: the bodies of the three callbacks wrapped in `try: ... except Exception: return None`."""
    a = REF.index("def _on_entry(code, offset):")
    b = REF.index("_CALLBACKS5 = (")
    seg = REF[a:b]
    out = []
    for block in seg.split("\n\n\n"):
        lines = block.rstrip("\n").split("\n")
        if not lines[0].startswith("def "):
            out.append(block)
            continue
        body = ["    " + ln if ln.strip() else ln for ln in lines[1:]]
        out.append("\n".join([lines[0], "    try:"] + body + ["    except Exception:", "        return None"]))
    return [(seg, "\n\n\n".join(out) + "\n\n\n")]


X3_OLD = """    for o in list(core.openings):                    # X3
        _detach(o, ("open", (f"[V5:OPEN_AT_EXIT] section {o.section!r} was still open when the "
                             f"trace exited; only calls confirmed before the exit count",)))"""
X3_WHILE = """    with _M:                                         # H9 mutant (revision 12): X3 as a while loop inside a plain Lock
        _ops = list(core.openings)
        _i = 0
        while _i < len(_ops):
            o = _ops[_i]
            _detach(o, ("open", (f"[V5:OPEN_AT_EXIT] section {o.section!r} was still open when the "
                                 f"trace exited; only calls confirmed before the exit count",)))
            _i += 1"""
X3_NEW = """    with _M:                                         # H9 mutant: X3 inside a plain Lock
     for o in list(core.openings):
        _detach(o, ("open", (f"[V5:OPEN_AT_EXIT] section {o.section!r} was still open when the "
                             f"trace exited; only calls confirmed before the exit count",)))"""

MINT_OLD = """    m = _Mint(fn)                                    # 1. pure
    m.holders = (core,)                              # 2. holder
    _MINTED[id(m.code)] = m                          # 3. register
    _BY_FN[fn] = m
    _set_local(_TOOL[0], m.code, _LOCAL)             # 4. local events, one gated call
    fn.__code__ = m.code                             # 5. install, last"""


REG_OLD = """    a, b = _tee(_map(register_callback,
                     _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
                     _EVENTS5, _CALLBACKS5))
    return _list(_chain(
        _map(_LOST_APPEND, _map(_is_not, _compress(a, _map(_is_not, b, _CALLBACKS5)), _repeat(None))),
        _map(get_tool, (t,))))"""
REG_ONE_GATE = """    n = 0
    if get_tool(t) is _TOOL_NAME:                   # mutant: one name gate before all five exchanges
        for e, cb in zip(_EVENTS5, _CALLBACKS5):
            prev = register_callback(t, e, cb)
            if prev is not cb:
                _LOST_APPEND(prev is not None)
                n += 1
    return [None] * n + [get_tool(t)]"""
REG_DROP_FIRST = """    flags = _list(_map(lambda p, c: p is not c,     # mutant: each previous callback dropped before its count
                       _map(register_callback,
                            _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
                            _EVENTS5, _CALLBACKS5), _CALLBACKS5))
    return _list(_chain(_map(_LOST_APPEND, _compress(_repeat(True), flags)), _map(get_tool, (t,))))"""
SETLOCAL_OLD = "    _CONSUME(_map(set_local_events, _compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)), (code,), (events,)))"
SETLOCAL_SPLIT = """    if get_tool(t) is _TOOL_NAME:                   # mutant: the name test split from the write
        set_local_events(t, code, events)"""
UNWON_OLD = """    t, get_tool, get_events, set_events = _TOOL[0], _MON[0][0], _MON[0][1], _MON[0][2]
    _CONSUME(_chain("""
UNWON_SPLIT = """    t, get_tool, get_events, set_events = _TOOL[0], _MON[0][0], _MON[0][1], _MON[0][2]
    if get_tool(t) is _TOOL_NAME and _ANCHORS.get(o.frame) is o:     # mutant: the name test split from the write
        if not (get_events(t) & PY_UNWIND):
            for p in list(_ANCHORS.values()):
                if p.armed:
                    p.core.flags['UNWIND_LOST'] = True
        set_events(t, PY_UNWIND)
    return
    _CONSUME(_chain("""
UNWOFF_OLD = """    t, get_tool, set_events = _TOOL[0], _MON[0][0], _MON[0][2]
    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),"""
UNWOFF_SPLIT = """    t, get_tool, set_events = _TOOL[0], _MON[0][0], _MON[0][2]
    _ANCHORS.pop(key, None)                         # mutant: the name test split from the write
    if get_tool(t) is _TOOL_NAME and not _ANCHORS:
        set_events(t, 0)
    return
    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),"""


def _plain_lock(kind):
    """The robust mutex replaced by a threading lock (H1: Lock; H6's M1: RLock), acquired and released
    with no try/finally, as the robust mutex is."""
    return [("def _acquire(me):\n    t0 = None\n",
             f"_PLAIN = threading.{kind}()\n\ndef _acquire(me):\n    _PLAIN.acquire(); return\n    t0 = None\n"),
            ("def _release(me):\n    me.succ", "def _release(me):\n    _PLAIN.release(); return\n    me.succ")]


# name -> (runner witnesses, patches, what the text says)
HAZ = {
    "mut_h1_mutex_lock": (["H1"], _plain_lock("Lock"),
                          "H1: the robust mutex replaced by threading.Lock; the sweep must detect a hang"),
    "mut_h2_cb_except": (["H2"], _cb_except(),
                         "H2: the callbacks wrapped in except Exception; propagation must drop below 20/20"),
    "mut_h6_m1_rlock": (["H6"], _plain_lock("RLock"), "H6 / G_FI M1: plain RLock -> C3 (hang)"),
    "mut_h6_m6_install_first": (["H6"], [(MINT_OLD, """    m = _Mint(fn)
    m.holders = (core,)
    fn.__code__ = m.code                             # M6 mutant: install before register
    _MINTED[id(m.code)] = m
    _BY_FN[fn] = m
    _set_local(_TOOL[0], m.code, _LOCAL)""")], "H6 / G_FI M6: install before register -> C5 (code not restored)"),
    "mut_h8_publish_at_entry": (["H8", "X135"], [
        ("    if out: m.pend[id(f)] = (f, offset, out)        # pending: the only store",
         "    if out: _publish(code, out)")],
        "H8: publish at entry; H8 detects it on 3.12, X135 on 3.13"),
    "mut_h9_while_in_lock": (["X140"], [
        (X3_OLD, X3_WHILE),
        ("def _exit(core):\n", "_M = threading.Lock()\n\ndef _exit_txn_m(core):\n    with _M:\n        return _exit_txn(core)\n\n\ndef _exit(core):\n"),
        ("        held, (swapped, lost) = _locked(_exit_txn, core)", "        held, (swapped, lost) = _locked(_exit_txn_m, core)")],
        "H9 (revision 12, GAP-49): X3 as a while loop by index inside `with _M:`, a threading.Lock _exit_txn also takes; X140 must detect it"),
    # retired (revision 12, GAP-49): the for form is not a #130279 shape on either verified interpreter,
    # so it is equivalent for this hazard. Kept here for the record; not run.
    "RETIRED_mut_h9_x3_in_lock": (["X140"], [
        (X3_OLD, X3_NEW),
        ("def _exit(core):\n", "_M = threading.Lock()\n\ndef _exit_txn_m(core):\n    with _M:\n        return _exit_txn(core)\n\n\ndef _exit(core):\n"),
        ("        held, (swapped, lost) = _locked(_exit_txn, core)", "        held, (swapped, lost) = _locked(_exit_txn_m, core)")],
        "H9: X3's loop inside `with _M:`, a threading.Lock that _exit_txn also takes; X140 must detect it"),
    "mut_m10_credit_stop_after_detach": (["X71c"], [(
        "    core.by_code = {}                                # X2: credit stop, one store\n" + X3_OLD,
        X3_OLD + "\n    core.by_code = {}                                # M10 mutant: X2 after X3")],
        "M10 (SM1): credit stop after detach; X71c's port row must see a landed trial credit G"),
    # revision 12: a weakening for each new or changed witness
    "mut_clone_alive_old_text": (["X57b", "R25"], [
        ('            return (f"[V5:CLONE_ALIVE] the gc freeze count rose while the minted code existed: "',
         '            return (f"[V5:CLONE_ALIVE] gc.freeze() ran while the minted code existed: "')],
        "GAP-38: CLONE_ALIVE (b)'s revision-11 text"),
    "mut_freeze_premise_deleted": (["R25"], [
        ("    if gc.get_freeze_count() > m.freeze0:", "    if True:")],
        "R25 (over-blocking #24): clause (b) without its freeze-count premise refuses part (1) on both versions"),
    "mut_rebind_nocount": (["X137h"], [
        ("                    _LOST.append(True)\n                    for m in list(_MINTED.values()):",
         "                    pass\n                    for m in list(_MINTED.values()):")],
        "X137h (GAP-42): E4's rebinding not counted in _LOST"),
    "mut_register_one_gate": (["X154", "X154b"], [(REG_OLD, REG_ONE_GATE)],
        "X154 (_register sweep) and X154b: revision 5's registration, one name gate before all five exchanges"),
    "mut_register_drop_before_count": (["X158d"], [(REG_OLD, REG_DROP_FIRST)],
        "X158d: revision 7's registration, each previous callback dropped before its count"),
    "mut_set_local_split_gate": (["X154"], [(SETLOCAL_OLD, SETLOCAL_SPLIT)],
        "X154 (_set_local sweep): the name test split from the write"),
    "mut_unwind_on_split_gate": (["X154"], [(UNWON_OLD, UNWON_SPLIT)],
        "X154 (_unwind_on sweep): the name test split from the write"),
    "mut_unwind_off_split_gate": (["X154"], [(UNWOFF_OLD, UNWOFF_SPLIT)],
        "X154 (_unwind_off sweep): the name test split from the write"),
    "mut_h10_unwind_mint_scope": (["H10"], [
        ("    _set_local(_TOOL[0], m.code, _LOCAL)             # 4. local events, one gated call",
         "    _set_local(_TOOL[0], m.code, _LOCAL)             # 4. local events, one gated call\n"
         "    _MON[0][2](_TOOL[0], PY_UNWIND)                  # H10 mutant: PY_UNWIND from mint"),
        ("                    _map(set_events, _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),\n"
         "                                               _map(_not, (_ANCHORS,))), _ZERO1)))",
         "                    _map(set_events, _compress(_compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),\n"
         "                                               _map(_not, (_ANCHORS,))), _map(_not, (_MINTED,))), _ZERO1)))"),
        ("    if _MINTED.get(id(m.code)) is m:\n        _MINTED.pop(id(m.code), None)\n",
         "    if _MINTED.get(id(m.code)) is m:\n        _MINTED.pop(id(m.code), None)\n    _unwind_off(None)                                # H10 mutant: cleared at retire\n")],
        "H10: PY_UNWIND set at mint and cleared at retire (revision 1's scope); cell (a) must detect it"),
}


def runner_ids(py):
    r = subprocess.run([py, RUNNER, "--list"], capture_output=True, text=True, timeout=120)
    return set(r.stdout.split()) if r.returncode == 0 else None


def run(py, impl, cases, out):
    cmd = [py, RUNNER, "--impl", impl, "--only", ",".join(cases), "--out", out]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired:
        return "TIMEOUT", [], ""
    try:
        d = json.load(open(out))
    except Exception:                                                   # noqa: BLE001
        return "BROKEN", [], (r.stderr.strip().splitlines() or ["?"])[-1][:160]
    fails = [c for c, x in d["cases"].items() if not x["ok"]]
    skipped = [c for c in cases if c in d.get("not_run", {})]
    if skipped:                                      # a witness that did not run witnesses nothing
        return "NOT_RUN", fails, f"not run: {skipped} (set V5F_DEPS_PATH for greenlet and coverage)"
    return d["verdict"], fails, ""


def main(argv):
    only = None
    if "--only" in argv:
        i = argv.index("--only"); only = argv[i + 1].split(","); del argv[i:i + 2]
    hazard_only = "--hazard-only" in argv
    argv = [a for a in argv if a != "--hazard-only"]
    pys = argv or [sys.executable]
    table = {} if hazard_only else {n: (w, p, "tools/mutants_v5f.py") for n, (w, p) in SMOKE_M.items()}
    table.update({k: v for k, v in HAZ.items() if not k.startswith("RETIRED_")})
    names = [n for n in table if not only or n in only]
    root = tempfile.mkdtemp(prefix="v5f_runner_mutants_")
    bad = 0
    for py in pys:
        ids = runner_ids(py)
        plan = {}
        for n in names:
            w = [c for c in table[n][0] if ids is None or c in ids]
            plan[n] = w
        ctl_cases = sorted({c for w in plan.values() for c in w})
        v, fails, err = run(py, os.path.join(EXAM, "ref_v5f.py"), ctl_cases, os.path.join(root, "control.json"))
        ok = v in ("PASS", "FAIL_ONLY_KNOWN_SPEC_GAPS")
        bad += not ok
        print(f"{'control':28s} {py}: {v} on {len(ctl_cases)} witness cases {fails} {err}", flush=True)
        for n in names:
            w, patches, why = table[n]
            src = REF
            for a, b in patches:
                assert src.count(a) == 1, (n, a[:70])
                src = src.replace(a, b)
            d = os.path.join(root, n); os.makedirs(d, exist_ok=True)
            impl = os.path.join(d, "ref_v5f.py")
            open(impl, "w").write(src)
            if not plan[n]:
                print(f"{n:28s} {py}: NO RUNNER WITNESS among {w}", flush=True)
                bad += 1
                continue
            v, fails, err = run(py, impl, plan[n], os.path.join(d, "out.json"))
            killed = v in ("FAIL", "TIMEOUT") and (v == "TIMEOUT" or bool(fails))
            bad += not killed
            print(f"{n:28s} {py}: {'KILLED' if killed else v} by {fails} (witness {plan[n]}) {err}", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
