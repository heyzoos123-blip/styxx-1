import subprocess, json, sys, shutil
P = "styxx/protocol.py"
orig = open(P).read()
M = {
 "M_undeclared_section_check": ("        if name not in self._exp.coverage_sections:", "        if False:"),
 "M_section_type_check": ("            if not isinstance(sec, str) or not sec or not sec.isascii():", "            if False:"),
 "M_builtin_check": ("    if not isinstance(code, types.CodeType):\n        raise", "    if False:\n        raise"),
 "M_list_type_check": ("            if not isinstance(ex, list) or not ex:", "            if not ex:"),
 "M_nonempty_check": ("            if not isinstance(ex, list) or not ex:", "            if not isinstance(ex, list):"),
 "M_no_unwrap": ("    obj = inspect.unwrap(obj) if callable(obj) else obj", "    pass"),
 "M_no_chain": ("            if prev is not None:\n                prev(frame, event, arg)", "            pass"),
 "M_no_thread_hook": ("        threading.setprofile(self._make_hook(self._prev_thr))", "        pass"),
 "M_count_check": ("            if t not in targets or isinstance(n, bool) or not isinstance(n, int) or n < 1:", "            if t not in targets:"),
 "M_missing_check": ("        if missing:\n", "        if False:\n"),
 "M_dup_check": ("            if len(set(ex)) != len(ex):", "            if False:"),
 "M_tracer_id": ("        if tr.get(\"tracer\") != _TRACER_ID:", "        if False:"),
 "M_stale_sha": ("        if tr.get(\"gates_sha256\") != self.gates_sha256:", "        if False:"),
 "M_section_wo_exercises": ("            if \"exercises\" not in g:\n                raise", "            if False:\n                raise"),
 "M_target_set": ("        if not isinstance(targets, dict) or sorted(targets) != self.coverage_targets:", "        if not isinstance(targets, dict):"),
 "M_regex": ("            bad = [t for t in ex if not isinstance(t, str) or not _TARGET_RE.match(t)]", "            bad = []"),
 "M_section_absent": ("        sec = sections.get(c[\"section\"])\n        if not isinstance(sec, dict):", "        sec = sections.get(c[\"section\"], {})\n        if not isinstance(sec, dict):"),
 "M_no_trace_check": ("        if not isinstance(tr, dict):\n            raise GateSpecError(\n                f\"gate {name!r} declares", "        if False:\n            raise GateSpecError(\n                f\"gate {name!r} declares"),
 "M_attr_all_sections": ("                        self._bump(self._sections[sec] if sec is not None\n                                   else self._unsectioned, ts)", "                        [self._bump(b, ts) for b in list(self._sections.values()) + [self._unsectioned]]"),
}
def run():
    r = subprocess.run([sys.executable, "../battery.py"], capture_output=True, text=True)
    try: return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception: return {"CRASH": [None, r.stderr[-300:]]}
base = run()
res = {"BASE": base}
for name, (a, b) in M.items():
    assert orig.count(a) == 1, name
    open(P, "w").write(orig.replace(a, b))
    try: res[name] = run()
    finally: open(P, "w").write(orig)
json.dump(res, open("../mut.json", "w"), indent=1)
viol = [k for k in base if k in __import__('run_protocol_v5', fromlist=['x']).__dict__.get('x', {})] if False else None
for name, out in res.items():
    if name == "BASE": continue
    changed = []
    for k, (r, s) in out.items():
        if k not in base: changed.append(f"{k}: {s}"); continue
        br, bs = base[k]
        if r != br: changed.append(f"FLIPPED {k}: {bs[:40]} -> {s[:70]}")
        elif s[:60] != bs[:60]: changed.append(f"same-outcome-new-reason {k}: {s[:90]}")
    print(f"== {name}"); [print("   ", c) for c in changed] or print("    (no change at all)")
