MUTANTS = {
# ---------------- repairs ----------------
"R01_identity_to_equality": [
  ("        hit = self._codes.get(id(code))\n        if hit is None or hit[0] is not code:",
   "        hit = next((v for v in self._codes.values() if v[0] == code), None)\n        if hit is None:")],
"R01b_drop_is_check_only": [
  ("if hit is None or hit[0] is not code:", "if hit is None:")],
"R02a_no_gc_referrers_check": [("    if len(holders) > 1:\n", "    if False:\n")],
"R02b_no_two_targets_one_code_check": [
  ("            if id(code) in self._codes:\n                raise GateSpecError(",
   "            if False:\n                raise GateSpecError(")],
"R03_inherited_follows_mro": [
  ("                if part not in vars(obj):\n",
   "                if part not in vars(obj) and False:\n"),
  ("                obj = vars(obj)[part]\n", "                obj = getattr(obj, part)\n")],
"R03b_inherited_as_attributeerror": [
  ("                    if any(part in vars(k) for k in obj.__mro__[1:]):",
   "                    if False:")],
"R04a_contextvar_to_process_slot": [
  ('        self._cv = contextvars.ContextVar(f"styxx_v5_section_{id(self)}", default=None)',
   '        self._cv = _Slot()'),
  ("class _CoverageTracer:\n",
   "class _Slot:\n    def __init__(self): self.v = None\n    def get(self): return self.v\n"
   "    def set(self, x):\n        old, self.v = self.v, x\n        return old\n"
   "    def reset(self, tok): self.v = tok\n\n\nclass _CoverageTracer:\n")],
"R04b_contextvar_to_threadlocal": [
  ('        self._cv = contextvars.ContextVar(f"styxx_v5_section_{id(self)}", default=None)',
   '        self._cv = _TL()'),
  ("class _CoverageTracer:\n",
   "class _TL(threading.local):\n    v = None\n    def get(self): return self.v\n"
   "    def set(self, x):\n        old, self.v = self.v, x\n        return old\n"
   "    def reset(self, tok): self.v = tok\n\n\nclass _CoverageTracer:\n")],
"R05_no_thread_start_mapping": [("        if code is _THREAD_START_CODE:\n", "        if False:\n")],
"R05b_thread_start_uses_cv_only": [
  ("                    self._thread_section[th] = self._effective_section()",
   "                    self._thread_section[th] = self._cv.get()")],
"R06_count_after_close": [("            elif self._open.get(sec, 0) > 0:\n", "            elif True:\n")],
"R07_no_thread_outlives": [("        if alive:\n", "        if False:\n")],
"R08_no_profiler_replaced": [("        if self._active and not self._hook_chain_has_self():", "        if False:")],
"R09_no_foreign_profiler": [
  ("            if prev is not None and not isinstance(prev, (types.FunctionType, types.MethodType,\n                                                          _Hook)):",
   "            if False:")],
"R10_no_reentry": [("        if self._active or self._exited:\n", "        if False:\n")],
"R10b_reentry_only_active": [("        if self._active or self._exited:\n", "        if self._active:\n")],
"R11_no_exit_order": [
  ('        raise GateSpecError(\n            "[V5:EXIT_ORDER]', '        return False\n        raise GateSpecError(\n            "[V5:EXIT_ORDER]')],
"R11b_reinstall_exited_hooks": [
  ("    while isinstance(h, _Hook) and h.tracer._exited:", "    while False:")],
"R12_unresolved_narrow_except": [
  ("    except Exception as e:\n        # Round 1 D2", "    except (ImportError, AttributeError) as e:\n        # Round 1 D2")],
"R13a_no_bad_trace_top": [
  ("            if not isinstance(d, dict) or not all(isinstance(k, str) for k in d):",
   "            if not isinstance(d, dict):")],
"R13b_bad_trace_top_targets_only": [
  ('        for label, d in (("targets", targets), ("sections", sections)):',
   '        for label, d in (("targets", targets),):')],
"R13c_no_bad_trace_section": [
  ("        if not isinstance(sec, dict) or not all(isinstance(k, str) for k in sec):",
   "        if False:")],
"R13d_check_metrics_raises": [
  ("                out[key] = {\"path\": _TRACE_KEY, \"present\": True, \"usable\": True, \"note\": None}\n            except GateSpecError as e:",
   "                out[key] = {\"path\": _TRACE_KEY, \"present\": True, \"usable\": True, \"note\": None}\n            except ZeroDivisionError as e:")],
"R14_regex_match_not_fullmatch": [("not _TARGET_RE.fullmatch(t)]", "not _TARGET_RE.match(t)]")],
"R14b_regex_not_ascii": [('(\\.[A-Za-z_]\\w*)*",\n                        re.ASCII)', '(\\.[A-Za-z_]\\w*)*",\n                        0)')],
# ---------------- original checks ----------------
"O_NO_TRACE_skip": [
  ("        if not isinstance(tr, dict):\n            raise GateSpecError(\n                f\"[V5:NO_TRACE]",
   "        if not isinstance(tr, dict):\n            return {}\n            raise GateSpecError(\n                f\"[V5:NO_TRACE]")],
"O_WRONG_TRACER": [('        if tr.get("tracer") != _TRACER_ID:', '        if False:')],
"O_STALE_TRACE": [('        if tr.get("gates_sha256") != self.gates_sha256:', '        if False:')],
"O_TARGET_SET": [("        if sorted(targets) != self.coverage_targets:", "        if False:")],
"O_TARGET_SET_subset_ok": [("        if sorted(targets) != self.coverage_targets:", "        if not set(targets) <= set(self.coverage_targets):")],
"O_SECTION_ABSENT_passes": [
  ("        if sec is None:\n            raise GateSpecError(\n                f\"[V5:SECTION_ABSENT]",
   "        if sec is None:\n            return {}\n            raise GateSpecError(\n                f\"[V5:SECTION_ABSENT]")],
"O_SECTION_ABSENT_removed": [("        if sec is None:\n            raise GateSpecError(\n                f\"[V5:SECTION_ABSENT]", "        if False:\n            raise GateSpecError(\n                f\"[V5:SECTION_ABSENT]")],
"O_BAD_COUNT": [("            if t not in targets or isinstance(n, bool) or not isinstance(n, int) or n < 1:", "            if False:")],
"O_BAD_COUNT_no_bool": [("            if t not in targets or isinstance(n, bool) or not isinstance(n, int) or n < 1:", "            if t not in targets or not isinstance(n, int) or n < 1:")],
"O_BAD_COUNT_no_undeclared_key": [("            if t not in targets or isinstance(n, bool) or not isinstance(n, int) or n < 1:", "            if isinstance(n, bool) or not isinstance(n, int) or n < 1:")],
"O_NO_CODE": [("    if not isinstance(code, types.CodeType):\n", "    if False:\n")],
"O_DECL_nonempty": [("            if not isinstance(ex, list) or not ex:", "            if not isinstance(ex, list):")],
"O_DECL_list": [("            if not isinstance(ex, list) or not ex:", "            if not ex:")],
"O_DECL_string": [("bad = [t for t in ex if not isinstance(t, str) or not _TARGET_RE.fullmatch(t)]", "bad = [t for t in ex if isinstance(t, str) and not _TARGET_RE.fullmatch(t)]")],
"O_DECL_format": [("bad = [t for t in ex if not isinstance(t, str) or not _TARGET_RE.fullmatch(t)]", "bad = [t for t in ex if not isinstance(t, str)]")],
"O_DECL_dup": [("            if len(set(ex)) != len(ex):", "            if False:")],
"O_SECTION_DECL_type": [("            if not isinstance(sec, str) or not sec or not sec.isascii():", "            if False:")],
"O_SECTION_DECL_half": [
  ("            if \"exercises\" not in g:\n                raise GateSpecError(",
   "            if \"exercises\" not in g:\n                continue\n                raise GateSpecError(")],
"O_UNDECLARED_SECTION": [("        if name not in self._exp.coverage_sections:", "        if False:")],
"O_NESTED_SECTION": [("        if outer is not None:\n", "        if False:\n")],
"O_NOTHING_DECLARED": [("        if not experiment.coverage_targets:\n", "        if False:\n")],
"O_NOT_EXERCISED": [("        if missing:\n", "        if False:\n")],
# ---------------- valid-case sensitivity ----------------
"S_no_chaining": [("        if self.prev is not None:\n            self.prev(frame, event, arg)", "        pass")],
"S_no_threading_setprofile": [("        threading.setprofile(self._thr_hook)\n        return self", "        return self")],
"S_no_restore_on_exit": [
  ("            sys.setprofile(_skip_exited(self._prev_sys))\n            threading.setprofile(_skip_exited(self._prev_thr))\n            return False",
   "            sys.setprofile(None)\n            threading.setprofile(None)\n            return False")],
"S_count_ignores_active": [('        if event == "call" and self.tracer._active:', '        if event == "call":')],
}
MUTANTS["R09b_foreign_refused_but_destroyed"] = [
  ("                raise GateSpecError(\n                    f\"[V5:FOREIGN_PROFILER]",
   "                sys.setprofile(None)\n                raise GateSpecError(\n                    f\"[V5:FOREIGN_PROFILER]")]
MUTANTS["R09c_foreign_check_sys_only"] = [
  ('        for where, prev in (("sys", prev_sys), ("threading", prev_thr)):',
   '        for where, prev in (("sys", prev_sys),):')]
