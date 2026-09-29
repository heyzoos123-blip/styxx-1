# v5f spec gaps found while writing `ref_v5f.py` (exam author, pre-freeze)

Source text: `papers/first-afference/DESIGN_protocol_v5f_DRAFT_2026_09_25.md` (the revision-8 draft plus Appendix A). Each gap names the section, what is missing or contradictory, and the reading `ref_v5f.py` implements. `ref_v5f.py` cites each one as `GAP-nn` where it applies.

The readings were taken from the text alone. No prototype was consulted to settle any of them (see `ATTESTATION.md`). The spec owner should fix the text; `ref_v5f.py` then follows the fix.

**Freeze-blocking** means one of two things. Either a frozen gate or exam check (G_HYG, SM2's normalizer, the leftover check, G_FI's C5) would judge a faithful implementation differently depending on which reading it took, or two normative sentences contradict each other.

## Summary

| gap | section | blocks the freeze? |
|---|---|---|
| GAP-03 | M0 / M1 `_MON` vs M5 X5 and M10 `local_events` | **yes** |
| GAP-07 | Resolution step 4 message vs X24c | **yes** |
| GAP-15 | M11 NO_TRACE wordings, and the placeholders in every spec-fixed text (SM2) | **yes** |
| GAP-02 | M1 / M6 / M7: how `_get_running_loop` is bound (G_HYG's reload list) | **yes** |
| GAP-08 | M10 / G_HYG frozen function set vs `_finite`, `_count_dicts`, the facade's constructor | **yes** |
| GAP-05 | M10 `cut_current` / `_cut_ok()` before the first `coverage_trace()` | **yes** (small) |
| GAP-19 | M5: what `_exit_txn` returns, and the order of problems | yes (small: the first problem's code is observable) |
| GAP-09 | M0: order of the checks in `coverage_trace()` | no |
| GAP-01, 04, 06, 10–14, 16–18, 20–27 | various | no |

## Freeze-blocking gaps

**GAP-03. M0/M1 (`_MON` is exactly six functions) vs M5 X5 and M10 (local events are read).**
- *What is missing.* X5's MONITOR_LOST test says "a held mint's local events on `tool` differ from `_LOCAL`". `_v5_state()["mints"][i]["local_events"]` also reports them. Both need `sys.monitoring.get_local_events`, which is not among `_MON`'s six bound functions (`get_tool, get_events, set_events, set_local_events, register_callback, use_tool_id`).
- *The contradiction.* M0 and V69 claim that "a wrapper installed on `sys.monitoring` after the first binding is neither checked nor called". Any call-time read of `sys.monitoring.get_local_events` breaks that claim. G_HYG freezes each step's `_MON[0]` indices 0 to 5, and G_ATOM's binding check covers exactly six names.
- *Reading taken.* `_exit_txn` and `_v5_state` call `sys.monitoring.get_local_events` at call time. This call is outside every one-call step and makes no write. The M0/V69 claim is therefore false for this one read-only function in `ref_v5f.py`.
- *Fix needed.* Either add `get_local_events` to `_MON` as index 6, with the binding check and the G_HYG index sets updated, or state the exemption and narrow V69's claim.

**GAP-07. Resolution step 4 (the cache-wrapper NOT_A_FUNCTION message) vs X24c.**
- *The contradiction.* The step-4 template reads "the wrapper calls `<callee module:qualname>`; its `__wrapped__` names `<stamped>`; declare the function the wrapper calls". X24c requires "the message names `fast`, never `power_ref`". But `<stamped>` *is* `power_ref` in X24c.
- *Reading taken.* `<stamped>` is rendered by type only: "its `__wrapped__` names a different object (a function)". The message then names the callee and never the stamp. This satisfies X24c and keeps the callee name, which is the only part SM2's normalizer fixes.
- *Fix needed.* Say how `<stamped>` is rendered, or restate X24c's assertion.

**GAP-15. M11 NO_TRACE wordings, and the placeholders in spec-fixed texts (SM2 normalizer).**
SM2 compares "exactly these message substrings" and names the three NO_TRACE wordings, the two NESTED_SECTION texts, the LAZY_RESULT text, the TRACE_ACTIVE texts, and the `dispatched {…}, unattributed {…}` labels. The text does not fix how their placeholders render:
- *NO_TRACE.* "'coverage_trace' is a `` `<type>` ``, not an exact dict" in M11, and "is a `` `OrderedDict` ``" in X93d. Are the backticks literal, or markdown? Is `<type>` the `__name__` or the `__qualname__`?
- *NESTED_SECTION.* How are S, S1 and S2 rendered in "a call there would be on the stack of two openings of section S" and "one call would count for both sections S1 and S2"? Bare, or `repr()` with quotes? In which order do S1 and S2 appear?
- *LAZY_RESULT.* `<type>` in "fn returned a `<type>`".
- *NO_TRACE, first wording.* "the result is a `<type>`, not a dict".

*Readings taken.* No literal backticks. Types are rendered with `type.__qualname__`, read through the C descriptor. Sections are rendered with `repr()` (for example `'G'`). The NESTED order is S1 = the opening already on the stack and S2 = the new section.

*Fix needed.* Write each spec-fixed text as a byte-exact template, because SM2 masks nothing else.

**GAP-02. M1/M6/M7: the binding of `_get_running_loop`.**
- *What is missing.* `_open` (step 5) and `_outcome` call `_get_running_loop()`, which is `asyncio.events._get_running_loop`. M1 has no such name, and asyncio may not be imported at module import (M0). G_HYG requires that "exactly the names M1's reload paragraph lists are bound through `globals().get`". X146b speaks of "its CALL of `asyncio.events._get_running_loop`".
- *Reading taken.* `_get_running_loop` is a module global that every `coverage_trace()` re-binds from `asyncio.events` after its `import asyncio`. At module level it is `globals().get("_get_running_loop")`, so a reload keeps it. This adds one name to the reload list, and the name is not binding-checked.
- *Fix needed.* Name it in M1, choose its reload behaviour, and decide whether M0 checks that it is the C builtin.

**GAP-08. M10 and G_HYG: the frozen function and class set.**
- *What is missing.* M10 and G_HYG say the region defines exactly the frozen functions plus the scoring functions, and that "the facade … and the plain-data classes have no other methods".
  - M11 itself names `_finite`, which is in neither list.
  - v5e's scoring helper `_count_dicts` is not listed.
  - The facade needs its core, but the core needs a weakref to the facade, and no constructor is listed.
- *Readings taken.*
  - `_finite` is a module-level scoring function outside the frozen set.
  - `_count_dicts` is inlined into `_check_coverage`.
  - The facade has no `__init__`. `coverage_trace()` builds it with `_CoverageTracer.__new__` and assigns `_core`.
- *Fix needed.* List `_finite` (and any other scoring helper) in the SM2 region's name set, and state how the facade is constructed.

**GAP-05. M10 `cut_current` and `_cut_ok()` before the first `coverage_trace()`.**
- *What is missing.* `_cut_ok()` reads `_HANDLE_DICT[0].get('_run')`, and `_HANDLE_DICT[0]` is None until the first `coverage_trace()`. `_v5_state()` is specified to return `_cut_ok()`, so a snapshot taken before any tracer exists would raise. That covers G_FI's `S0` in a fresh process, and the leftover snapshot of a subprocess case.
- *Reading taken.* `cut_current` is True while nothing has been captured, meaning no captured binding has moved.
- *Fix needed.* Define the pre-capture value, because the leftover check and C5 compare this field.

**GAP-19. M5 X5 to X7: `held, more` and the order of problems.**
- *What is missing.* `held, more = _locked(_exit_txn, core)` never defines `more`. The order in which CLONE_CALLED (X4), CODE_SWAPPED (X5 step 3), CLONE_ALIVE and CUT_MOVED (X6), and a REENTRANT or MACHINERY_BUSY from `_locked` enter `core.problems` is implied but not stated. It is observable, because score refuses with the *first* problem's code.
- *Reading taken.* `more = (CODE_SWAPPED texts, lost flag)`. The problem order is X4, then the `_locked` error, then X5 step 3, then X6 (CLONE_ALIVE per held mint, then CUT_MOVED).

## Non-blocking gaps (readings recorded)

- **GAP-01 (M1).** The code uses PY_START, PY_RESUME, PY_RETURN, PY_YIELD and PY_UNWIND, but `import styxx.protocol` may not touch `sys.monitoring` (M0), and 3.10 and 3.11 lack it. *Reading:* literal ints 1, 2, 4, 8 and 4096, verified on 3.12.3 and 3.13.12. They are not checked at binding.
- **GAP-04 (M0).** The gate reads `getattr(sys, '_is_gil_enabled', lambda: True)()`, and the lambda is a nested code object, which G_HYG forbids in `coverage_trace` and `_enter`. *Reading:* `getattr(..., None)`, with None read as "GIL enabled".
- **GAP-06 (M1).** `_GUARD = {"hint": _Txn(None, 0, None)}` sits in the block that "precedes every function", but `_Txn` is a class defined later. *Reading:* `_GUARD = globals().get("_GUARD", None)` in the block, and `{"hint": _Txn(None, 0, None)}` assigned right after `_Txn` is defined when it is None.
- **GAP-09 (M0).** The order of checks in `coverage_trace()` is not given: version, the Experiment type check, NOTHING_DECLARED, the binding check, `import asyncio`, the dict capture, E2. *Reading:* that order.
- **GAP-10 (M0).** The refusal text is given only for other 3.12.x and 3.13.x patch levels. *Reading:* one text for every refused interpreter. Only the `[V5:UNSUPPORTED_VERSION]` prefix is fixed.
- **GAP-11 (At open step 5 vs M6).** M6 says an anchor whose loop is not the running loop *ends the attribution walk*. Step 5's NESTED walk says only that a same-core opening counts as nesting if its loop is the running loop, not whether a foreign-loop anchor ends the walk. *Reading:* the NESTED walk continues to the cut or the root. Both readings are fail-closed.
- **GAP-12 (Attribution rule vs M6).** The one-sentence rule does not say that a foreign-loop anchor ends the walk, but M6's walk does (outcome `d`). They differ when an opening with the running loop lies *below* a foreign-loop anchor on one stack. *Reading:* M6.
- **GAP-13 (Minting, M10).** `_Mint.qualname` and `_v5_state()["mints"][i]["target"]` are "F_T's `module:qualname`", but it is not said which module name. *Reading:* F_T's own `__globals__['__name__']` when it is an exact str, else `co_filename` (as Provenance (d)). This matters for a cache wrapper whose callee lives elsewhere.
- **GAP-14 (M1).** It is not said when `_Core.pid` is read. *Reading:* at construction, in `coverage_trace()`.
- **GAP-16 (At open steps 2 and 3).** Formatting a non-str section into a refusal would run user `__repr__`. *Reading:* a non-str section is never formatted; its type's `__qualname__` is named instead. X78f's counters stay 0.
- **GAP-17 (M11 check_metrics).** "'smoke run' only when the trace is absent" does not settle what happens when the trace is absent and the result is not a smoke run. *Reading:* "smoke run" iff smoke and the NO_TRACE test fails. Otherwise `str(e)`, with the smoke suffix when smoke.
- **GAP-18 (M11 check_metrics).** M11 forbids user `get`, `__missing__` and `__bool__`, but does not say to replace v4's `_resolve` (`isinstance`, `in`, `[]`). *Reading:* `check_metrics` walks paths with `issubclass(type(x), dict)` and `dict.get`. `score()` keeps `_resolve` and v5e's `isinstance(_v, numbers.Real)` guard, with only the `float()` OverflowError change M11 names.
- **GAP-20 (CLONE_ALIVE (b)).** "`visible` counts the references to M_T held by members of `refs`…" does not say how a referrer's references are counted. *Reading:* identity occurrences of M_T in `gc.get_referents(r)`, excluding the mint, F_T, the scan's own frame and the `refs` list.
- **GAP-21 (M2).** "After `_BUSY_SECONDS`" does not say from when. *Reading:* from the first observation of a live owner in this `_acquire`.
- **GAP-22 (M8).** The order of an opening's notes is not given: its fin notes, `o.lazy` and `core.lost_note`. *Reading:* that order. The exam should compare notes as a set of codes.
- **GAP-23 (M9).** `register_at_fork` "at import" also runs on every `importlib.reload`, which registers a second, idempotent handler. *Reading:* accepted; noted.
- **GAP-24 (M9).** "a no-op until a tracer has been constructed" does not say how that is detected. *Reading:* `_MON[0] is None`.
- **GAP-25 (Resolution, INHERITED).** It is not said where the module of "declare the defining class `<module>:<qualname>`" comes from. *Reading:* the defining class's own dict `'__module__'` if it is an exact str, else `?`.
- **GAP-26 (exam harness).** The text does not say whether a scoring violation case is judged through `score()` or through `Experiment._check_coverage`/`check_metrics`. `score()` resolves each gate's metric first, and a metric-less result raises an uncoded GateSpecError before NO_TRACE. *For the runner:* judge coverage refusals through the entry point each row implies. X122 implies `score()`; X93d and X103b imply the coverage check or `check_metrics`.
- **GAP-27 (rules_v5f.json).** Appendix A's claim classification lives in scratch files outside what the exam author may read (`rev7/audit_*`, `verify8/*classify*`). *Reading:* the atoms' classes are this author's heuristic by section. Witnesses are the ids each atom names, or those its enclosing paragraph or row names. 531 property and disclosure atoms name no witness in their own paragraph. Many are headings, definitions, or claims whose witness Appendix A gives elsewhere. The spec owner should reconcile these with Appendix A's tables before the freeze.

## Checked and found consistent (no gap)

- The one-call step pipelines of M7, run exactly as written: `_unwind_on`, `_unwind_off`, `_take`, `_set_local` and `_register` in its tee form. None of them has a backward jump on 3.12.3 or 3.13.12, and neither does `_run`, `_commit`, `_detach` or `_named`.
- No region code object has a nested code object (G_HYG MF4). The #130279 rule holds: the only `try … finally` is in `_run` and `_run_async`, and neither try body has a loop.
- The E4 counting rule, M3's reclaim and the rebinding rule are implementable as written. X36 (MONITOR_BUSY) and X142 (a second loaded copy takes id 3, and A has no MONITOR_LOST) behave as stated on both interpreters.
