from mutants_r2 import MUTANTS as R2
M = {}
ADAPT = {
 "R06_count_after_close": [("            elif self._open.get(sec, 0) <= 0:\n", "            elif False:\n")],
 "O_NO_CODE": [("    if not isinstance(code, types.CodeType) or not isinstance(obj, types.FunctionType):\n",
                "    if False:\n")],
 "S_no_restore_on_exit": [
   ("            threading.setprofile(_skip_exited(self._prev_thr))\n", "            threading.setprofile(None)\n"),
   ("            sys.setprofile(_skip_exited(self._prev_sys))\n            return False", "            sys.setprofile(None)\n            return False")],
 "S_count_ignores_active": [('        if event == "call" and t._active:', '        if event == "call":')],
}
for k, v in R2.items():
    M[k] = ADAPT.get(k, v)
M.update({
 "O_NO_CODE_b_function_only": [("    if not isinstance(code, types.CodeType) or not isinstance(obj, types.FunctionType):\n",
                "    if not isinstance(code, types.CodeType):\n")],
 # --- round-3 repairs ---
 "N01_drop_globals_check": [("        genuine = frame.f_globals is g\n", "        genuine = True\n")],
 "N02_drop_freevar_check": [("        if genuine and freevars:\n", "        if False:\n")],
 "N02b_freevar_eq_not_is": [("genuine = all(loc.get(n, _EMPTY) is c for", "genuine = all(loc.get(n, _EMPTY) == c for")],
 "N02c_impostors_counted": [("            if not genuine:\n", "            if False:\n")],
 "N03_drop_close_recount": [("        for t, (fn, code) in self._fns.items():\n            problem = _sharing_problem(t, fn, code)",
                             "        for t, (fn, code) in {}.items():\n            problem = _sharing_problem(t, fn, code)")],
 "N04_drop_close_gc": [("        gc.collect()\n        for t, (fn, code) in self._fns.items():", "        for t, (fn, code) in self._fns.items():")],
 "N04b_drop_entry_gc": [("    gc.collect()      # round 2 nit", "    pass      # round 2 nit")],
 "N04c_drop_both_gc": [("        gc.collect()\n        for t, (fn, code) in self._fns.items():", "        for t, (fn, code) in self._fns.items():"),
                       ("    gc.collect()      # round 2 nit", "    pass      # round 2 nit")],
 "N05_wraps_check_not_at_entry": [
   ("def _sharing_problem(target: str, fn, code) -> str | None:", "def _sharing_problem(target: str, fn, code, cw=True) -> str | None:"),
   ("    wrappers = _wrappers_of(fn)\n", "    wrappers = _wrappers_of(fn) if cw else []\n"),
   ("    problem = _sharing_problem(target, obj, code)\n", "    problem = _sharing_problem(target, obj, code, cw=False)\n")],
 "N06_wraps_check_not_at_close": [
   ("def _sharing_problem(target: str, fn, code) -> str | None:", "def _sharing_problem(target: str, fn, code, cw=True) -> str | None:"),
   ("    wrappers = _wrappers_of(fn)\n", "    wrappers = _wrappers_of(fn) if cw else []\n"),
   ("            problem = _sharing_problem(t, fn, code)\n", "            problem = _sharing_problem(t, fn, code, cw=False)\n")],
 "N06b_wraps_check_nowhere": [("    if len(wrappers) > 1:\n", "    if False:\n")],
 "N07_drop_ambiguous": [('            elif via == "thread" and sum(', '            elif False and sum(')],
 "N07b_ambiguous_ignores_via": [('            elif via == "thread" and sum(', '            elif sum(')],
 "N08_drop_hook_self_removal": [("            if sys.getprofile() is self:\n                sys.setprofile(nxt)",
                                 "            if False:\n                sys.setprofile(nxt)")],
 "N09_thr_clear_only_on_success": [
   ("        if owns_thr:\n            threading.setprofile(_skip_exited(self._prev_thr))\n        if owns_sys:\n",
    "        if owns_sys:\n            if owns_thr:\n                threading.setprofile(_skip_exited(self._prev_thr))\n")],
 "N09b_thr_never_cleared_on_error_or_order": [
   ("        if owns_thr:\n            threading.setprofile(_skip_exited(self._prev_thr))\n        if owns_sys:\n",
    "        if owns_thr and exc_type is None and owns_sys:\n            threading.setprofile(_skip_exited(self._prev_thr))\n        if owns_sys:\n")],
 "N10_instance_path_getattr": [('            else:\n                # Round 2 R2-D1: "default_model.fit"',
                                '            else:\n                obj = getattr(obj, part); continue\n                # Round 2 R2-D1: "default_model.fit"')],
 "N11a_section_context_valueerror_escapes": [("            return True\n            except ValueError:\n                return False",
     "            return True\n            except KeyError:\n                return False")],
 "N11b_section_context_swallowed": [("        if not same_context:\n", "        if False:\n")],
 "N12a_hook_failed_no_catch": [("                t._on_call(frame)\n            except Exception:", "                t._on_call(frame)\n            except ZeroDivisionError:")],
 "N12b_hook_failed_catch_no_flag": [("                t._hook_failed = True\n", "                pass\n")],
 "N12c_hook_failed_no_refusal": [("        if self._hook_failed:\n", "        if False:\n")],
 "N13_check_metrics_non_dict_raises": [('smoke = bool(result.get("smoke")) if isinstance(result, dict) else False',
                                        'smoke = bool(result.get("smoke"))')],
 "N14_thread_start_early_return": [("                    self._thread_section[th] = self._effective_section()\n        hit = ",
                                    "                    self._thread_section[th] = self._effective_section()\n            return\n        hit = ")],
 "N15_close_refusals_not_recorded": [("            self._close_refusals.append(msg)\n", "            pass\n")],
 "N16_exited_before_ownership_read": [
   ("        owns_thr = _thread_profile() is self._thr_hook\n        owns_sys = sys.getprofile() is self._sys_hook\n        self._exited = True\n",
    "        self._exited = True\n        owns_thr = _thread_profile() is self._thr_hook\n        owns_sys = sys.getprofile() is self._sys_hook\n")],
})
MUTANTS = M
