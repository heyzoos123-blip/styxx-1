MUTANTS = {
 "N13b_non_dict_empty_report": [('        smoke = bool(result.get("smoke")) if isinstance(result, dict) else False\n',
     '        if not isinstance(result, dict):\n            return {}\n        smoke = bool(result.get("smoke")) if isinstance(result, dict) else False\n')],
 "N18_hook_failed_mislabelled_as_profiler_replaced": [('                f"[V5:HOOK_FAILED] the coverage hook raised', '                f"[V5:PROFILER_REPLACED] the coverage hook raised')],
}
