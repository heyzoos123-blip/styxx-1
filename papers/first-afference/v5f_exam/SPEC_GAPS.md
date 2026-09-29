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

## Revision 9 follow-ups (raised after the revision-9 text; for the spec owner)

These come from two sources. The first is reconciling `rules_v5f.json` with Appendix A's classified lists (revision 9, GAP-27: "The classified lists are spec data"). The second is a read of the revision-9 text for contradictions. The atoms were re-extracted from the revision-9 text with the revision-8 algorithm, and each atom's `rev8_ids` field links it to its revision-8 atom. The reconciliation followed the three rules of Appendix A. Rule 1 was applied only to the wide list, `rev9/appendix_a/wide_claims_classified.json`: the revision-7 list is outside what this author may read (see GAP-30). `rules_v5f.json`'s `meta.reconciliation` states the rule-2 reading used. The verifier's commit 2e8cc8a0 added `rev9/appendix_a/rev9_new_sentences_classified.json` and `.txt` to the branch while this reconciliation ran. The revision-9 text does not name them as spec data (Appendix A names the revision-7 list and the wide list only), so they were neither read nor used here, and the atoms that hold a revision-9 sentence are classed by rule 2. Once the text adopts that list, the reconciliation is re-run with it under rule 1.

**Counts.** 2,478 atoms: P 905, D 203, C 50, G 632, N 260, S 128, H 300. 852 take their class from the wide list (rule 1). 1,626 are classed by rule 2: 67 of these match a wide-list row that defers to the revision-7 list, and 99 contain a sentence of `rev9_new_sentences.json`. Of the 1,158 P, D and C atoms, 814 have a witness. The other **344** have none (P 305, D 39, C 0), and each is a gap below (GAP-W001 to GAP-W344). The wide list's 1,241 sentences: 1,072 fall inside an atom. The rest were changed by revision 9, or split differently by the two extractions, and rule 2 classes the atoms that now hold them.

| gap | section | blocks the freeze? |
|---|---|---|
| GAP-W001 to GAP-W344 | 344 P and D atoms with no witness (Appendix A rule 3) | **yes** (rule 3: "the freeze waits for it") |
| GAP-30 | Rule 1 needs the revision-7 list, which the exam author may not read | **yes** (process: rule 1 is incomplete for 67 atoms) |
| GAP-31 | 40 atoms take a wide-list witness that names no case, property, gate clause or probe | no, unless the owner rules that pointers are not witnesses |
| GAP-28 | Reason codes: the UNSUPPORTED_VERSION row omits revision 9's `_get_running_loop` check | no |
| GAP-29 | X156g says "X65d's shape" but describes another shape | no |

**GAP-28. Reason codes, UNSUPPORTED_VERSION, vs M0 (revision 9, GAP-02).**
- *The contradiction.* The row's "when it fires" cell lists these causes: the interpreter; a `sys.monitoring` function to be bound or already bound in `_MON`; a one-call name that is not the C object it names. It does not list the cause revision 9 added in M0 step 6: `asyncio.events._get_running_loop` is not the builtin of `_asyncio` (case X156g). That refusal fires under M0, and the exam judges it by its code prefix, so the row is incomplete, not wrong about any outcome.
- *Reading taken.* M0 is normative. `ref_v5f.py` raises UNSUPPORTED_VERSION at step 6, with the M0 refusal template.
- *Fix needed.* Add the `_get_running_loop` check to the row. The row's "a `sys.monitoring` function to be bound, or already bound in `_MON`" already covers the seventh function.

**GAP-29. X156g (revision 9) vs X65d.**
- *The contradiction.* X156g "runs X65d's shape", and then describes it as a loop whose `_run_once` runs ready handles' callbacks directly, running *a coroutine that calls f*. X65d's own row describes something else: another thread's `call_soon_threadsafe` job that calls f, through `map(operator.call, …)`. The two differ in who schedules f. Both give NOT_EXERCISED `dispatched {f:1}` unpatched.
- *Reading taken.* `smoke_cases.py` X156g follows X156g's own sentence (a coroutine run by `run_until_complete` on the direct-dispatch loop). It passes on both interpreters: UNSUPPORTED_VERSION under the spec; the control, unpatched, gives NOT_EXERCISED `dispatched {f:1}`. My weakening `mut_grl_nocheck` gives PASS `{f:1}`.
- *Fix needed.* Say which of the two shapes the frozen runner uses, or drop "X65d's shape".

**GAP-30. Appendix A's rule 1 needs the revision-7 list, which the exam author may not read.**
- *What is missing.* Rule 1 says an atom whose sentence is in *either* list takes that list's class and witnesses. The revision-7 list is `protocol_v5f_design/rev7/audit_claims_classified.txt`. The exam author's brief allows only `protocol_v5f_design/rev9/appendix_a/` under that directory, so the revision-7 list was not read. In the wide list, 84 rows have class `old`: they are covered by the revision-7 audit, and their witness field reads only "revision 7 audit". 67 atoms contain such a sentence and no classified one (P 35, G 16, D 8, C 3, S 2, N 2, H 1 after rule 2).
- *Reading taken.* Those atoms are classed by rule 2, and `class_source` marks them `rule2_table_rev7_list_unread`. 9 of them still have no witness and are among the W gaps.
- *Fix needed.* Either commit the revision-7 list into `rev9/appendix_a/` (it holds no code), or give the per-sentence class and witness of the 84 `old` rows in the wide list itself. Then this author re-runs the reconciliation.

**GAP-31. Wide-list witnesses that name nothing checkable.**
- *What is missing.* 53 P, D or C rows of the wide list give a pointer as the witness, not a named case, model property, gate clause or probe. Examples: "the code's cases (Mutation audit code->case rows; Exam cases)", "model (holders read lock-free)", "CPython: a frame runs on one thread; X123" (a C row with a case but no probe), and "the Verified probe named with it". 40 atoms take such a witness under rule 1 (P 31, C 5, D 4). They carry `list_witness_names_id: false`.
- *Reading taken.* Rule 1 is applied as written: these atoms count as witnessed, and they are not W gaps.
- *Fix needed.* Rule whether a pointer is a witness. If it is not, name the case, property or probe in the list, or these 40 become W gaps.

**GAP-W001 to GAP-W344. P and D atoms with no witness (Appendix A, rule 3).**
Each row is one atom of `rules_v5f.json`, and each atom has `needs_witness: true` there. None of them is in either list with a witness. Each names no case, gate clause, invariant, model property or control. Where it cites a revision-9 gap, that gap's row in the Revision 9 table names none either. Its enclosing paragraph, list item or table row names none. Many are steps of a procedure whose case sits in another paragraph; others are definitions that rule 2 read as properties. Either way the text does not tie a witness to the sentence, and rule 3 hands each to the spec owner. "Line" is the line in the revision-9 text.

| gap | atom | line | class | section | sentence |
|---|---|---|---|---|---|
| GAP-W001 | R-DECISIONS_WHERE_THE_DESIGNS_-002 | 51 | P | Decisions where the designs disagree and no judge ruled | question: Fork \| decision: **Pass-through** (D1): in another pid, `run()` just calls fn \| reason: Fork-pool jobs keep working. Child work was never credited. |
| GAP-W002 | R-DECISIONS_WHERE_THE_DESIGNS_-003 | 52 | P | Decisions where the designs disagree and no judge ruled | question: Cache wrappers \| decision: **Accepted through the real callee** (D1/D3), not refused (D2) \| reason: Sound once identity comes from `gc.get_referents`. D2's `… |
| GAP-W003 | R-DECISIONS_WHERE_THE_DESIGNS_-007 | 56 | P | Decisions where the designs disagree and no judge ruled | question: Tool id lifetime \| decision: **Kept for the process** (D1), not released (D3) \| reason: Monotone state has fewer crash prefixes. The cost to other tools is d… |
| GAP-W004 | R-DECISIONS_WHERE_THE_DESIGNS_-011 | 60 | P | Decisions where the designs disagree and no judge ruled | question: Pending-entry key \| decision: `m.pend[id(frame)] = (frame, entry_offset, outcome)`, **holding the frame**, per mint (not D3's global bare-id map) \| reason: W… |
| GAP-W005 | R-TARGET_IDENTITY-002 | 216 | P | Target identity > Rule (one sentence) | Attribution then decides whether a hit is credited, and confirmation decides whether it counts. |
| GAP-W006 | R-TARGET_IDENTITY-011 | 228 | P | Target identity > Resolution (at `__enter__`, every target,… | `_own_dict(obj)` finds the first `'__dict__'` entry among the class dicts of `type(obj)`'s MRO, read with `_TYPE_DICT`/`_TYPE_MRO`. |
| GAP-W007 | R-TARGET_IDENTITY-012 | 228 | P | Target identity > Resolution (at `__enter__`, every target,… | That entry must be a `types.GetSetDescriptorType` or `types.MemberDescriptorType`, and is read with `desc.__get__(obj, type(obj))`. |
| GAP-W008 | R-TARGET_IDENTITY-013 | 228 | P | Target identity > Resolution (at `__enter__`, every target,… | The result must be an exact dict; otherwise `_own_dict` returns None. |
| GAP-W009 | R-TARGET_IDENTITY-014 | 228 | P | Target identity > Resolution (at `__enter__`, every target,… | A Python-level `__dict__` descriptor is never called. |
| GAP-W010 | R-TARGET_IDENTITY-015 | 230 | P | Target identity > Resolution (at `__enter__`, every target,… | **Import.** `mod = importlib.import_module(module)`. |
| GAP-W011 | R-TARGET_IDENTITY-016 | 230 | P | Target identity > Resolution (at `__enter__`, every target,… | Any `Exception` refuses **UNRESOLVED** chained `from e`; see L-ASYNC-EXC for asynchronous exceptions. |
| GAP-W012 | R-TARGET_IDENTITY-017 | 230 | P | Target identity > Resolution (at `__enter__`, every target,… | If `issubclass(type(mod), ModuleType)` is false, refuse **UNRESOLVED** ("the sys.modules entry is not a module"). |
| GAP-W013 | R-TARGET_IDENTITY-018 | 230 | P | Target identity > Resolution (at `__enter__`, every target,… | The module's own dict is `_MOD_DICT.__get__(mod)`. |
| GAP-W014 | R-TARGET_IDENTITY-019 | 231 | P | Target identity > Resolution (at `__enter__`, every target,… | **Steps.** For each `part` of the qualname, with `obj` the object reached so far: |
| GAP-W015 | R-TARGET_IDENTITY-020 | 232 | P | Target identity > Resolution (at `__enter__`, every target,… | **Unwrap first.** If `type(obj) is staticmethod or type(obj) is classmethod`, replace obj by its C `__func__` (D2; this makes `'mod:C.m.__wrapped__'` work for a class-he… |
| GAP-W016 | R-TARGET_IDENTITY-024 | 233 | P | Target identity > Resolution (at `__enter__`, every target,… | If `part` is in the module dict, read it. |
| GAP-W017 | R-TARGET_IDENTITY-025 | 233 | P | Target identity > Resolution (at `__enter__`, every target,… | Otherwise, if `'__getattr__'` is in the module dict (PEP 562), call it **twice**. |
| GAP-W018 | R-TARGET_IDENTITY-026 | 233 | P | Target identity > Resolution (at `__enter__`, every target,… | Each call raising `Exception` refuses **UNRESOLVED** `from e`. |
| GAP-W019 | R-TARGET_IDENTITY-027 | 233 | P | Target identity > Resolution (at `__enter__`, every target,… | If the two products are not the same object, refuse **UNRESOLVED** ("module `__getattr__` returns a new object on each access; declare the function it forwards to"). |
| GAP-W020 | R-TARGET_IDENTITY-029 | 234 | P | Target identity > Resolution (at `__enter__`, every target,… | **`issubclass(type(obj), type)`.** Read `_TYPE_DICT.__get__(obj)`. |
| GAP-W021 | R-TARGET_IDENTITY-031 | 234 | P | Target identity > Resolution (at `__enter__`, every target,… | Found in one, C (the first in MRO order): refuse **INHERITED** ("declare the defining class `<module>:<qualname>`"). |
| GAP-W022 | R-TARGET_IDENTITY-032 | 234 | P | Target identity > Resolution (at `__enter__`, every target,… | `<module>` is `dict.get(_TYPE_DICT.__get__(C), '__module__')` when it is an exact str, and `?` otherwise; `<qualname>` is `_TYPE_QUAL.__get__(C)` (revision 9, GAP-25). |
| GAP-W023 | R-TARGET_IDENTITY-033 | 234 | P | Target identity > Resolution (at `__enter__`, every target,… | Found nowhere: refuse **UNRESOLVED**. |
| GAP-W024 | R-TARGET_IDENTITY-034 | 235 | P | Target identity > Resolution (at `__enter__`, every target,… | **Anything else.** Use `d = _own_dict(obj)`. |
| GAP-W025 | R-TARGET_IDENTITY-036 | 236 | P | Target identity > Resolution (at `__enter__`, every target,… | **Final unwrap.** Unwrap a final staticmethod or classmethod the same way. |
| GAP-W026 | R-TARGET_IDENTITY-038 | 238 | P | Target identity > Resolution (at `__enter__`, every target,… | **`type(D) is FunctionType`.** F_T = D. |
| GAP-W027 | R-TARGET_IDENTITY-043 | 241 | P | Target identity > Resolution (at `__enter__`, every target,… | `stamped = dict.get(_own_dict(D) or {}, '__wrapped__')`. |
| GAP-W028 | R-TARGET_IDENTITY-049 | 243 | P | Target identity > Resolution (at `__enter__`, every target,… | If `callee` is (by identity) a value of the module dict or of the holder namespace, refuse **NOT_A_FUNCTION**: "the body is also bound as `<name>`; declare that name". |
| GAP-W029 | R-TARGET_IDENTITY-052 | 245 | P | Target identity > Resolution (at `__enter__`, every target,… | Otherwise F_T = callee. |
| GAP-W030 | R-TARGET_IDENTITY-053 | 245 | P | Target identity > Resolution (at `__enter__`, every target,… | The target is the cached body: misses count and hits do not. |
| GAP-W031 | R-TARGET_IDENTITY-054 | 246 | P | Target identity > Resolution (at `__enter__`, every target,… | **Anything else** refuses **NOT_A_FUNCTION**, with the v5e list of shapes. |
| GAP-W032 | R-TARGET_IDENTITY-055 | 247 | P | Target identity > Resolution (at `__enter__`, every target,… | **Reserved.** If F_T is one of the two watched bindings, `_HANDLE_DICT[0].get('_run')` or `_LOOP_DICT[0].get('_run_once')`, or `_CUT.get(id(F_T.__code__)) is F_T.__code_… |
| GAP-W033 | R-TARGET_IDENTITY-056 | 247 | P | Target identity > Resolution (at `__enter__`, every target,… | Revision 2: both bindings are read from the class dicts captured by `coverage_trace()` (M1), never from `asyncio.events.Handle` afresh, so the constructor, E2, this step… |
| GAP-W034 | R-TARGET_IDENTITY-058 | 249 | P | Target identity > Resolution (at `__enter__`, every target,… | **(a) The module.** `mf = dict.get(module_dict, '__file__')` must be an exact str not ending in `.pyc` or `.pyo`. |
| GAP-W035 | R-TARGET_IDENTITY-059 | 249 | P | Target identity > Resolution (at `__enter__`, every target,… | Otherwise refuse. |
| GAP-W036 | R-TARGET_IDENTITY-061 | 250 | P | Target identity > Resolution (at `__enter__`, every target,… | **(b) The walk.** It starts at D, visits D plus at most 16 further objects (17 in all), and is cycle-detected by `id`. |
| GAP-W037 | R-TARGET_IDENTITY-063 | 251 | P | Target identity > Resolution (at `__enter__`, every target,… | **FunctionType.** `cur` must be **coherent**, else refuse FOREIGN_DEFINITION: "the code of `<cur module:qualname>` was compiled from `<co_filename>`, not from its module… |
| GAP-W038 | R-TARGET_IDENTITY-064 | 251 | P | Target identity > Resolution (at `__enter__`, every target,… | If `cur.__globals__ is module_dict`, accept. |
| GAP-W039 | R-TARGET_IDENTITY-065 | 251 | P | Target identity > Resolution (at `__enter__`, every target,… | Else step to `dict.get(_own_dict(cur) or {}, '__wrapped__')`. |
| GAP-W040 | R-TARGET_IDENTITY-066 | 252 | P | Target identity > Resolution (at `__enter__`, every target,… | **`_CACHE_WRAPPER`.** Step to its real callee. |
| GAP-W041 | R-TARGET_IDENTITY-067 | 253 | P | Target identity > Resolution (at `__enter__`, every target,… | **Anything else.** Step to `dict.get(_own_dict(cur) or {}, '__wrapped__')`. |
| GAP-W042 | R-TARGET_IDENTITY-072 | 255 | P | Target identity > Resolution (at `__enter__`, every target,… | The message names the innermost FunctionType reached, `inner`, as `n + ':' + inner.__qualname__` ("declare this instead"). |
| GAP-W043 | R-TARGET_IDENTITY-073 | 255 | P | Target identity > Resolution (at `__enter__`, every target,… | Here `n = dict.get(inner.__globals__, '__name__')` when `type(n) is str`, and `inner.__code__.co_filename` otherwise (revision 2, N7). |
| GAP-W044 | R-TARGET_IDENTITY-076 | 256 | P | Target identity > Resolution (at `__enter__`, every target,… | F_T is always the first FunctionType the walk visits, so F_T itself is always checked for coherence. |
| GAP-W045 | R-TARGET_IDENTITY-077 | 256 | P | Target identity > Resolution (at `__enter__`, every target,… | This closes the swapped-wrapper shape that D1 admitted (judge_sound/j_d1_wrapper_swap.py). |
| GAP-W046 | R-TARGET_IDENTITY-078 | 257 | P | Target identity > Resolution (at `__enter__`, every target,… | **Aliases.** Two declared names are aliases iff their declared objects D are identical after the final unwrap. |
| GAP-W047 | R-TARGET_IDENTITY-080 | 257 | P | Target identity > Resolution (at `__enter__`, every target,… | Two declared names that reach one F_T through different declared objects refuse **NOT_A_FUNCTION** ("declare the body once"). |
| GAP-W048 | R-TARGET_IDENTITY-084 | 263 | P | Target identity > Minting (the function `_mint`; under the … | If `F_T.__code__ is not m.code`, refuse **CODE_SWAPPED** before anything is joined. |
| GAP-W049 | R-TARGET_IDENTITY-085 | 263 | P | Target identity > Minting (the function `_mint`; under the … | Otherwise `m.holders = m.holders + (core,)`. |
| GAP-W050 | R-TARGET_IDENTITY-087 | 265 | P | Target identity > Minting (the function `_mint`; under the … | `m = _Mint(F_T)`. |
| GAP-W051 | R-TARGET_IDENTITY-089 | 265 | P | Target identity > Minting (the function `_mint`; under the … | For a cache wrapper F_T is the callee, so this is the callee's module. |
| GAP-W052 | R-TARGET_IDENTITY-090 | 265 | P | Target identity > Minting (the function `_mint`; under the … | `_v5_state()`'s `target` is `m.qualname`. |
| GAP-W053 | R-TARGET_IDENTITY-091 | 266 | P | Target identity > Minting (the function `_mint`; under the … | `m.holders = (core,)`. |
| GAP-W054 | R-TARGET_IDENTITY-092 | 267 | P | Target identity > Minting (the function `_mint`; under the … | `_MINTED[id(m.code)] = m`, then `_BY_FN[F_T] = m`. |
| GAP-W055 | R-TARGET_IDENTITY-095 | 269 | P | Target identity > Minting (the function `_mint`; under the … | `F_T.__code__ = m.code`, last. |
| GAP-W056 | R-TARGET_IDENTITY-097 | 273 | P | Target identity > Tripwires (recorded; each refuses every d… | **CLONE_CALLED.** At an entry event, M_T runs with `f_globals is not m.globals`. |
| GAP-W057 | R-TARGET_IDENTITY-099 | 274 | P | Target identity > Tripwires (recorded; each refuses every d… | **CLONE_ALIVE** (`_clone_alive`). |
| GAP-W058 | R-TARGET_IDENTITY-100 | 274 | P | Target identity > Tripwires (recorded; each refuses every d… | At each holder's exit, for each mint it held: `excess = sys.getrefcount(M_T) - 2 - (F_T.__code__ is M_T)`. |
| GAP-W059 | R-TARGET_IDENTITY-101 | 274 | P | Target identity > Tripwires (recorded; each refuses every d… | If `excess > 0`, the tracer scans `refs = gc.get_referrers(M_T)` and records the problem if either holds: |
| GAP-W060 | R-TARGET_IDENTITY-102 | 275 | P | Target identity > Tripwires (recorded; each refuses every d… | (a) some FunctionType other than F_T is in `refs`; |
| GAP-W061 | R-TARGET_IDENTITY-103 | 276 | P | Target identity > Tripwires (recorded; each refuses every d… | (b) `gc.get_freeze_count() > m.freeze0` and `excess - visible > 0`. |
| GAP-W062 | R-TARGET_IDENTITY-104 | 276 | P | Target identity > Tripwires (recorded; each refuses every d… | Here `visible` counts the references to M_T held by members of `refs` other than the mint, F_T and the scan's own frame and list. |
| GAP-W063 | R-TARGET_IDENTITY-105 | 276 | P | Target identity > Tripwires (recorded; each refuses every d… | Revision 9 (GAP-20) fixes the count: for each member r of `refs` except the mint m, F_T, the scan's own frame (`sys._getframe()` inside `_clone_alive`) and the `refs` li… |
| GAP-W064 | R-TARGET_IDENTITY-106 | 276 | P | Target identity > Tripwires (recorded; each refuses every d… | Message: "gc.freeze() ran while the minted code existed: N references to it cannot be attributed". |
| GAP-W065 | R-TARGET_IDENTITY-107 | 278 | P | Target identity > Tripwires (recorded; each refuses every d… | The test is for a *rise* in the count, not any change. |
| GAP-W066 | R-TARGET_IDENTITY-111 | 278 | P | Target identity > Tripwires (recorded; each refuses every d… | `m.freeze0` is read when the mint is made, so for a mint this tracer joined it can predate this trace (over-blocking #19). |
| GAP-W067 | R-TARGET_IDENTITY-113 | ? | P | Target identity > Tripwires (recorded; each refuses every d… | The swap is left in place. - **CUT_MOVED.** `_cut_ok()` is false at an entry event of any minted code, or at exit. |
| GAP-W068 | R-TARGET_IDENTITY-114 | 282 | P | Target identity > Tripwires (recorded; each refuses every d… | `_cut_ok()` reads the two watched bindings, `h = _HANDLE_DICT[0].get('_run')` and `r = _LOOP_DICT[0].get('_run_once')`. |
| GAP-W069 | R-TARGET_IDENTITY-115 | 282 | P | Target identity > Tripwires (recorded; each refuses every d… | `_HANDLE_DICT[0]` and `_LOOP_DICT[0]` are the class dicts of `asyncio.events.Handle` and `asyncio.base_events.BaseEventLoop`, read through `_TYPE_DICT` by the first `cov… |
| GAP-W070 | R-TARGET_IDENTITY-116 | 282 | P | Target identity > Tripwires (recorded; each refuses every d… | `_cut_ok()` is true iff, for each of h and r, `type(x) is FunctionType` and `_CUT.get(id(x.__code__)) is x.__code__`. |
| GAP-W071 | R-TARGET_IDENTITY-118 | 282 | P | Target identity > Tripwires (recorded; each refuses every d… | So a rebinding of `Handle._run`, or a swap of its `__code__`, that is restored before exit is still caught if any hit happened while it was in place. |
| GAP-W072 | R-TARGET_IDENTITY-130 | 293 | P | Target identity > Why class A cannot reopen, and the doors … | builds a same-globals function and drops it before exit; |
| GAP-W073 | R-TARGET_IDENTITY-131 | 294 | P | Target identity > Why class A cannot reopen, and the doors … | runs `exec(M_T, T.__globals__)`; |
| GAP-W074 | R-TARGET_IDENTITY-132 | 295 | P | Target identity > Why class A cannot reopen, and the doors … | does `U.__code__ = M_T` and swaps it back before exit; |
| GAP-W075 | R-TARGET_IDENTITY-133 | 296 | P | Target identity > Why class A cannot reopen, and the doors … | keeps a live clone frozen while the gc freeze count at exit is not above its value at mint time. |
| GAP-W076 | R-TARGET_IDENTITY-134 | 296 | P | Target identity > Why class A cannot reopen, and the doors … | That happens if frozen objects died, or if `gc.unfreeze()` then `gc.freeze()` ran with fewer tracked objects. |
| GAP-W077 | R-ATTRIBUTION-001 | 308 | P | Attribution > Rule (one sentence) | A hit H is credited to opening O iff all three hold: - at H's entry event (PY_START or PY_RESUME), O's anchor is registered and is met on H's `f_back` chain before the f… |
| GAP-W078 | R-ATTRIBUTION-002 | 313 | P | Attribution > Rule (one sentence) | The anchor is the frame of the module-level `_run(core, …)` call, or the `_run_async` coroutine frame, that opened O. |
| GAP-W079 | R-ATTRIBUTION-020 | 334 | P | Attribution > Sections are calls | result = cov.run(section, fn, /, *args, **kwargs) result = await cov.run_async(section, afn, /, *args, **kwargs) |
| GAP-W080 | R-ATTRIBUTION-021 | 338 | P | Attribution > Sections are calls | Opening and closing happen in one frame, in its `finally`, so they are LIFO per stack by construction. |
| GAP-W081 | R-ATTRIBUTION-022 | 338 | P | Attribution > Sections are calls | An event loop must run outside the section. |
| GAP-W082 | R-ATTRIBUTION-023 | 338 | P | Attribution > Sections are calls | A task inside any loop may open its own `run_async` section. |
| GAP-W083 | R-ATTRIBUTION-029 | 343 | P | Attribution > At open (raised before fn runs; every refusal… | Revision 2 reads `os.getpid()` (about 0.14 µs more than a cached value, `rev2/p8_atfork_abort.py`) instead of a pid cached by the at-fork handler. |
| GAP-W084 | R-ATTRIBUTION-038 | 346 | P | Attribution > At open (raised before fn runs; every refusal… | Sections are matched against *declared sections*, not gate names. |
| GAP-W085 | R-ATTRIBUTION-039 | 347 | P | Attribution > At open (raised before fn runs; every refusal… | **NESTED_SECTION.** A registered opening of the *same* core is on the anchor's `f_back` chain before the cut, and its `loop` is the running loop now (the loop boundary). |
| GAP-W086 | R-ATTRIBUTION-040 | 347 | P | Attribution > At open (raised before fn runs; every refusal… | Openings of other tracers may nest. |
| GAP-W087 | R-ATTRIBUTION-041 | 347 | P | Attribution > At open (raised before fn runs; every refusal… | The walk starts at the anchor frame's `f_back` and runs to the first cut frame or the root; the first same-core opening met whose `loop` is the running loop refuses. |
| GAP-W088 | R-ATTRIBUTION-042 | 347 | P | Attribution > At open (raised before fn runs; every refusal… | Revision 9 (GAP-11): an anchor whose opening's loop is not the running loop is skipped, and the walk goes on; unlike M6's hit walk, it does not end there. |
| GAP-W089 | R-ATTRIBUTION-043 | 347 | P | Attribution > At open (raised before fn runs; every refusal… | This refuses one shape in which a hit would credit only the new opening: a same-core opening with the running loop *below* a foreign-loop anchor, which needs the running… |
| GAP-W090 | R-ATTRIBUTION-044 | 347 | P | Attribution > At open (raised before fn runs; every refusal… | It is an over-block, never an over-credit (over-blocking #23). |
| GAP-W091 | R-ATTRIBUTION-073 | 351 | P | Attribution > At open (raised before fn runs; every refusal… | The release is the opening's own `finally`, on whichever thread runs it: a hopped `run_async` section's `finally` runs on the thread that resumed it (revision 5, N4). |
| GAP-W092 | R-ATTRIBUTION-076 | 353 | P | Attribution > At open (raised before fn runs; every refusal… | The same section may be open any number of times at once on different stacks. |
| GAP-W093 | R-ATTRIBUTION-079 | 358 | P | Attribution > At a hit | CLONE_CALLED check. |
| GAP-W094 | R-ATTRIBUTION-080 | 359 | P | Attribution > At a hit | Walk `f_back` to the cut or the root, collecting registered anchors. |
| GAP-W095 | R-ATTRIBUTION-081 | 359 | P | Attribution > At a hit | An anchor whose opening's `loop` is not the running loop (read once per hit) ends the walk as a cut does. |
| GAP-W096 | R-ATTRIBUTION-082 | 360 | P | Attribution > At a hit | For each holder h with `id(code) in h.by_code`, the outcome is one of: |
| GAP-W097 | R-ATTRIBUTION-083 | 361 | P | Attribution > At a hit | `('c', O)` when exactly one of h's openings was found; |
| GAP-W098 | R-ATTRIBUTION-084 | 362 | P | Attribution > At a hit | `('a', (O1, …))` when two or more were found; |
| GAP-W099 | R-ATTRIBUTION-089 | 366 | P | Attribution > At a hit | Store `m.pend[id(frame)] = (frame, entry_offset, outcomes)`. |
| GAP-W100 | R-ATTRIBUTION-092 | 368 | P | Attribution > At a hit | At PY_RETURN or PY_YIELD, pop the entry. |
| GAP-W101 | R-ATTRIBUTION-094 | 369 | P | Attribution > At a hit | A frame that died at its entry instruction never ran its body. |
| GAP-W102 | R-ATTRIBUTION-095 | 370 | P | Attribution > At a hit | Publishing, for each outcome whose holder still has `id(code) in h.by_code`: `('c', O)` adds one to `O.calls[id(code)]`; `('a', …)` adds one to each opening's `ambiguous… |
| GAP-W103 | R-ATTRIBUTION-096 | 371 | P | Attribution > At a hit | **Never counted.** A `throw()` or `close()` resumption fires only PY_THROW and has no pending entry, so it is never counted, even when a handler in the body runs. |
| GAP-W104 | R-ATTRIBUTION-099 | 375 | P | Attribution > At close and at exit | `end` is `"returned"` or `"raised"`. |
| GAP-W105 | R-ATTRIBUTION-121 | 378 | P | Attribution > At close and at exit | The text is "fn returned a `<type>`; whatever of its body runs after the section closed does not count", with "(its body had not started)" appended when the object has n… |
| GAP-W106 | R-ATTRIBUTION-123 | 378 | P | Attribution > At close and at exit | One shape differs between the verified interpreters: an async generator whose `aclose()` awaitable was created and closed unawaited reads as not started on 3.12.3 and as… |
| GAP-W107 | R-ATTRIBUTION-126 | 382 | P | Attribution > What score credits | A gate is judged on the **union of `calls` over the openings of its declared section**, whatever their `end`. |
| GAP-W108 | R-ATTRIBUTION-127 | 383 | P | Attribution > What score credits | Notes (OPEN_AT_EXIT, LAZY_RESULT, MONITOR_LOST) and `end != "returned"` never refuse. |
| GAP-W109 | R-ATTRIBUTION-128 | 383 | P | Attribution > What score credits | They are printed in the NOT_EXERCISED message. |
| GAP-W110 | R-ATTRIBUTION-129 | 384 | P | Attribution > What score credits | `ambiguous` and `uncredited` never count. |
| GAP-W111 | R-ATTRIBUTION-131 | 285 | P | Attribution > Why class B cannot reopen through the runtime… | The v5e argument stands. |
| GAP-W112 | R-ATTRIBUTION-133 | 390 | P | Attribution > Why class B cannot reopen through the runtime… | It is a copy of the forking thread's stack, anchors included (`rev1/p6_fork_chain.py`). |
| GAP-W113 | R-ATTRIBUTION-135 | 392 | P | Attribution > Why class B cannot reopen through the runtime… | A re-entry into a stdlib loop's dispatch runs `BaseEventLoop._run_once`, whatever handle class, `Handle._run` binding or `TimerHandle` override is in use. |
| GAP-W114 | R-ATTRIBUTION-136 | 392 | P | Attribution > Why class B cannot reopen through the runtime… | A loop class that overrides `_run_once` but dispatches through `handle._run()` runs `Handle._run`. |
| GAP-W115 | R-ATTRIBUTION-137 | 392 | P | Attribution > Why class B cannot reopen through the runtime… | Both codes are in the monotone cut (revision 2), and neither can be minted (RESERVED_TARGET). |
| GAP-W116 | R-ATTRIBUTION-138 | 392 | P | Attribution > Why class B cannot reopen through the runtime… | A rebinding of either, or a swap of its code, is recorded as CUT_MOVED if any hit or the exit sees it. |
| GAP-W117 | R-MECHANISM_AND_LIFECYCLE_M0-042 | 435 | P | Mechanism and lifecycl > M0. Version gate | A refusal at any step binds and captures nothing. |
| GAP-W118 | R-MECHANISM_AND_LIFECYCLE_M1-004 | 476 | P | Mechanism and lifecycl > M1. Module state | The *M1 one-call vocabulary* is exactly the names from `_map` through `_CALLBACKS5` in this block. |
| GAP-W119 | R-MECHANISM_AND_LIFECYCLE_M1-037 | 489 | P | Mechanism and lifecycl > M1. Module state | **`_Mint`**: `fn, qualname, original, code, globals, freeze0, holders, pend`. |
| GAP-W120 | R-MECHANISM_AND_LIFECYCLE_M1-039 | 491 | P | Mechanism and lifecycl > M1. Module state | `pend` maps `id(frame)` to `(frame, entry_offset, outcomes)`. |
| GAP-W121 | R-MECHANISM_AND_LIFECYCLE_M1-042 | 493 | P | Mechanism and lifecycl > M1. Module state | `exp`; |
| GAP-W122 | R-MECHANISM_AND_LIFECYCLE_M1-043 | 494 | P | Mechanism and lifecycl > M1. Module state | `marks`: a monotone dict of `'entering'→_Txn`, `'active'→True`, `'exiting'→_Txn`, `'exited'→True`; |
| GAP-W123 | R-MECHANISM_AND_LIFECYCLE_M1-044 | 495 | P | Mechanism and lifecycl > M1. Module state | `by_code`: `{id(code): names}`, emptied first at exit; |
| GAP-W124 | R-MECHANISM_AND_LIFECYCLE_M1-045 | 496 | P | Mechanism and lifecycl > M1. Module state | `names`: kept for record; |
| GAP-W125 | R-MECHANISM_AND_LIFECYCLE_M1-046 | 497 | P | Mechanism and lifecycl > M1. Module state | `sections`: the declared sections; |
| GAP-W126 | R-MECHANISM_AND_LIFECYCLE_M1-047 | 498 | P | Mechanism and lifecycl > M1. Module state | `openings` (list), `problems` (list), `clone_called` (dict); |
| GAP-W127 | R-MECHANISM_AND_LIFECYCLE_M1-048 | 499 | P | Mechanism and lifecycl > M1. Module state | `uncredited`: `{tid: ({}, {})}`; |
| GAP-W128 | R-MECHANISM_AND_LIFECYCLE_M1-050 | 501 | P | Mechanism and lifecycl > M1. Module state | `flags`: a dict set lock-free by callbacks and closes (`'CUT_MOVED'`, `'UNWIND_LOST'`); |
| GAP-W129 | R-MECHANISM_AND_LIFECYCLE_M1-060 | 506 | P | Mechanism and lifecycl > M1. Module state | **Frames the machinery may retain** belong to module-level functions whose own locals hold the core, never the facade: `_run`'s frame, `_run_async`'s coroutine frame, an… |
| GAP-W130 | R-MECHANISM_AND_LIFECYCLE_M1-061 | 506 | P | Mechanism and lifecycl > M1. Module state | A retained frame that has died still keeps its callers' frames alive, and so possibly the facade; see L-ZOMBIE and L-MONITOR. |
| GAP-W131 | R-MECHANISM_AND_LIFECYCLE_M1-062 | 506 | P | Mechanism and lifecycl > M1. Module state | Revision 4: an opening keeps its anchor frame in `o.frame` until its own `finally` releases it. |
| GAP-W132 | R-MECHANISM_AND_LIFECYCLE_M1-063 | 506 | P | Mechanism and lifecycl > M1. Module state | If that `finally` never finishes (a fault in it, or `_run_async`'s `finally` skipped by #130279), the dead frame stays referenced by the opening until the core is droppe… |
| GAP-W133 | R-MECHANISM_AND_LIFECYCLE_M1-064 | 506 | P | Mechanism and lifecycl > M1. Module state | Revision 3's X3 released it at exit; revision 4 cannot, because a release by any thread other than the owner is what made B1 possible. |
| GAP-W134 | R-MECHANISM_AND_LIFECYCLE_M1-074 | 508 | P | Mechanism and lifecycl > M1. Module state | **`_Txn(tid, fid, code, succ)`** is created by `me = _txn()` from the caller's frame, with `succ` **a fresh dict per token** (revision 5, N6). |
| GAP-W135 | R-MECHANISM_AND_LIFECYCLE_M1-075 | 508 | P | Mechanism and lifecycl > M1. Module state | It is not a default argument: one `succ` dict shared between tokens makes the first claim permanent, and the next `_acquire` walks a cycle. |
| GAP-W136 | R-MECHANISM_AND_LIFECYCLE_M1-077 | 508 | P | Mechanism and lifecycl > M1. Module state | A token is *live* iff some frame f on `sys._current_frames()[tid]`'s `f_back` chain has all three of: `id(f) == fid`, `f.f_code is code`, and `f.f_locals.get('me') is` t… |
| GAP-W137 | R-MECHANISM_AND_LIFECYCLE_M2-010 | 522 | P | Mechanism and lifecycl > M2. The robust mutex | A release skipped for any reason harms nobody: the owner's frame dies with the exception and the next acquirer steals. |
| GAP-W138 | R-MECHANISM_AND_LIFECYCLE_M2-011 | 522 | P | Mechanism and lifecycl > M2. The robust mutex | The loop contains no `try`, so CPython #130279 (a signal at a loop back-edge escapes the enclosing `try` table on 3.13) cannot leave anything held. |
| GAP-W139 | R-MECHANISM_AND_LIFECYCLE_M3-016 | 530 | P | Mechanism and lifecycl > M3. Reconciliation (the first step… | The events and callbacks on the id are whatever its last owner left, because `set_events` on a freed id raises ValueError: `tool 4 is not in use` (`rev2/p3_free_reclaim.… |
| GAP-W140 | R-MECHANISM_AND_LIFECYCLE_M3-017 | 530 | P | Mechanism and lifecycl > M3. Reconciliation (the first step… | After a plain free of styxx's id they are styxx's own, and the steps below clear them as usual. |
| GAP-W141 | R-MECHANISM_AND_LIFECYCLE_M3-020 | 530 | P | Mechanism and lifecycl > M3. Reconciliation (the first step… | Any other global or local events and callbacks that tool left stay on the id, now under styxx's name, until styxx's process exits. |
| GAP-W142 | R-MECHANISM_AND_LIFECYCLE_M3-021 | 530 | P | Mechanism and lifecycl > M3. Reconciliation (the first step… | An id that another tool holds when a write's gate is evaluated is never written by that write. |
| GAP-W143 | R-MECHANISM_AND_LIFECYCLE_M3-022 | 530 | P | Mechanism and lifecycl > M3. Reconciliation (the first step… | The one write that can still land on an id another tool took *after* its gate is a `_register` exchange, when an audit hook lets that happen inside it; at most one excha… |
| GAP-W144 | R-MECHANISM_AND_LIFECYCLE_M3-024 | ? | P | Mechanism and lifecycl > M3. Reconciliation (the first step… | A holder is **dead** iff any of these holds: - its facade weakref is dead; - `'exited'` is in its marks; - its pid differs from `os.getpid()`; - its `'exiting'` token is… |
| GAP-W145 | R-MECHANISM_AND_LIFECYCLE_M3-049 | 551 | P | Mechanism and lifecycl > M3. Reconciliation (the first step… | Revision 5 deletes revision 4's announcement sweep with the announcements themselves. |
| GAP-W146 | R-MECHANISM_AND_LIFECYCLE_M4-001 | 556 | P | Mechanism and lifecycl > M4. `__enter__` (the facade calls … | **E0. Claim.** `me = _txn()`. |
| GAP-W147 | R-MECHANISM_AND_LIFECYCLE_M4-002 | 556 | P | Mechanism and lifecycl > M4. `__enter__` (the facade calls … | If `core.marks.setdefault('entering', me) is not me`, append the REENTRY text to `core.problems` and raise **REENTRY**. |
| GAP-W148 | R-MECHANISM_AND_LIFECYCLE_M4-003 | 557 | P | Mechanism and lifecycl > M4. `__enter__` (the facade calls … | **E1. Version.** The M0 gate, raised. |
| GAP-W149 | R-MECHANISM_AND_LIFECYCLE_M4-004 | 558 | P | Mechanism and lifecycl > M4. `__enter__` (the facade calls … | **E2. The cut (the function `_cut_refresh`; the constructor runs it too).** For each watched binding x in (`_HANDLE_DICT[0].get('_run')`, `_LOOP_DICT[0].get('_run_once')… |
| GAP-W150 | R-MECHANISM_AND_LIFECYCLE_M4-005 | 559 | P | Mechanism and lifecycl > M4. `__enter__` (the facade calls … | if `type(x) is not FunctionType`, raise **CUT_UNAVAILABLE** ("... is not a plain function"); |
| GAP-W151 | R-MECHANISM_AND_LIFECYCLE_M4-007 | 561 | P | Mechanism and lifecycl > M4. `__enter__` (the facade calls … | otherwise the code is new. |
| GAP-W152 | R-MECHANISM_AND_LIFECYCLE_M4-008 | 561 | P | Mechanism and lifecycl > M4. `__enter__` (the facade calls … | Raise **CUT_UNAVAILABLE** if it is *shareable*: `'<locals>' in x.__code__.co_qualname`, which means a factory or decorator can make more functions with it, or some Funct… |
| GAP-W153 | R-MECHANISM_AND_LIFECYCLE_M4-010 | 561 | P | Mechanism and lifecycl > M4. `__enter__` (the facade calls … | Bind a dedicated module-level function". |
| GAP-W154 | R-MECHANISM_AND_LIFECYCLE_M4-011 | 561 | P | Mechanism and lifecycl > M4. `__enter__` (the facade calls … | Otherwise `_CUT.setdefault(id(x.__code__), x.__code__)`. |
| GAP-W155 | R-MECHANISM_AND_LIFECYCLE_M4-056 | 583 | P | Mechanism and lifecycl > M4. `__enter__` (the facade calls … | A failed or abandoned enter leaves a dead entering token without `'active'`. |
| GAP-W156 | R-MECHANISM_AND_LIFECYCLE_M4-057 | 583 | P | Mechanism and lifecycl > M4. `__enter__` (the facade calls … | The next reconciliation prunes it and retires its mints. |
| GAP-W157 | R-MECHANISM_AND_LIFECYCLE_M4-058 | 583 | P | Mechanism and lifecycl > M4. `__enter__` (the facade calls … | The tracer is single-use, so a retry refuses REENTRY. |
| GAP-W158 | R-MECHANISM_AND_LIFECYCLE_M5-030 | 605 | P | Mechanism and lifecycl > M5. `__exit__` (the facade calls `… | A GateSpecError from `_locked` (REENTRANT or MACHINERY_BUSY, raised by `_acquire` before `_exit_txn` starts) is appended to `probs` as `str(e)`, and exit continues with … |
| GAP-W159 | R-MECHANISM_AND_LIFECYCLE_M5-031 | 605 | P | Mechanism and lifecycl > M5. `__exit__` (the facade calls `… | Otherwise `probs.extend(swapped)`. |
| GAP-W160 | R-MECHANISM_AND_LIFECYCLE_M5-032 | 605 | P | Mechanism and lifecycl > M5. `__exit__` (the facade calls `… | The unreleased holdership is pruned at the next reconciliation, because the exit token dies when `_exit` returns. - **X6. Tripwires.** CLONE_ALIVE for each held mint, in… |
| GAP-W161 | R-MECHANISM_AND_LIFECYCLE_M5-033 | 606 | P | Mechanism and lifecycl > M5. `__exit__` (the facade calls `… | Then CUT_MOVED, if `core.flags` has it or `_cut_ok()` is false now. - **X7. Problems.** `core.problems.extend(probs)` in one call. |
| GAP-W162 | R-MECHANISM_AND_LIFECYCLE_M5-034 | 607 | P | Mechanism and lifecycl > M5. `__exit__` (the facade calls `… | If `lost`, `core.lost_note = "[V5:MONITOR_LOST] …"`. |
| GAP-W163 | R-MECHANISM_AND_LIFECYCLE_M5-039 | ? | P | Mechanism and lifecycl > M5. `__exit__` (the facade calls `… | **Interrupted exit.** - *Before X1:* a zombie (L-ZOMBIE). |
| GAP-W164 | R-MECHANISM_AND_LIFECYCLE_M5-040 | 613 | P | Mechanism and lifecycl > M5. `__exit__` (the facade calls `… | `record()` refuses TRACE_ACTIVE, and one call of `__exit__()` completes it. - *After X1:* `record()` refuses TRACE_INCOMPLETE. |
| GAP-W165 | R-MECHANISM_AND_LIFECYCLE_M5-041 | 614 | P | Mechanism and lifecycl > M5. `__exit__` (the facade calls `… | The exit token is dead, so the next reconciliation prunes the core, detaches its openings and retires its mints. |
| GAP-W166 | R-MECHANISM_AND_LIFECYCLE_M6-005 | 649 | P | Mechanism and lifecycl > M6. The event path: tool id 4 or 3… | Its per-holder rule is the one under Attribution. |
| GAP-W167 | R-MECHANISM_AND_LIFECYCLE_M6-006 | 650 | P | Mechanism and lifecycl > M6. The event path: tool id 4 or 3… | **Publishing.** `_publish` re-checks `id(code) in h.by_code` for each outcome, then makes single-key increments. |
| GAP-W168 | R-MECHANISM_AND_LIFECYCLE_M6-008 | 651 | P | Mechanism and lifecycl > M6. The event path: tool id 4 or 3… | **Where callbacks run.** They never run at a C call: the only events are PY_START, PY_RESUME, PY_RETURN and PY_YIELD (local) and PY_UNWIND (global, and from revision 2 s… |
| GAP-W169 | R-MECHANISM_AND_LIFECYCLE_M6-009 | 651 | P | Mechanism and lifecycl > M6. The event path: tool id 4 or 3… | On 3.12.3, INSTRUCTION, JUMP and BRANCH events on a code object make a signal at one of its back-edges skip that code's `finally` and with-exit (7–77 of 100 trials). |
| GAP-W170 | R-MECHANISM_AND_LIFECYCLE_M6-011 | 651 | P | Mechanism and lifecycl > M6. The event path: tool id 4 or 3… | Code run inside any sys.monitoring callback raises no events for any tool (synth/p_syn1.py), so the callbacks cannot re-enter themselves. |
| GAP-W171 | R-MECHANISM_AND_LIFECYCLE_M6-012 | 652 | P | Mechanism and lifecycl > M6. The event path: tool id 4 or 3… | **Exceptions.** An exception raised in a callback propagates as CPython defines (L-DELIVERY). |
| GAP-W172 | R-MECHANISM_AND_LIFECYCLE_M6-013 | 652 | P | Mechanism and lifecycl > M6. The event path: tool id 4 or 3… | The tool is not dropped and the events stay set (D3 p2). |
| GAP-W173 | R-MECHANISM_AND_LIFECYCLE_M7-001 | 655 | P | Mechanism and lifecycl > M7. `_open`, `_commit`, `_run`, `_… | The open checks are listed under Attribution. |
| GAP-W174 | R-MECHANISM_AND_LIFECYCLE_M7-010 | 731 | P | Mechanism and lifecycl > M7. `_open`, `_commit`, `_run`, `_… | def _set_local(t, code, events): # Minting step 4, _retire step 2, a rebinding (E4) # ONE CALL { if get_tool(t) is _TOOL_NAME: set_local_events(t, code, events) } get_to… |
| GAP-W175 | R-MECHANISM_AND_LIFECYCLE_M7-094 | 761 | P | Mechanism and lifecycl > M7. `_open`, `_commit`, `_run`, `_… | Registration cannot be made atomic from Python: the audit event is raised inside `register_callback` itself, before the exchange, and styxx cannot remove it. |
| GAP-W176 | R-MECHANISM_AND_LIFECYCLE_M7-096 | 761 | P | Mechanism and lifecycl > M7. `_open`, `_commit`, `_run`, `_… | Registering once at import and never again was considered: it would leave a replaced callback undetected and unrepaired (X5's test is the detector), and a reclaim after … |
| GAP-W177 | R-MECHANISM_AND_LIFECYCLE_M7-132 | 777 | P | Mechanism and lifecycl > M7. `_open`, `_commit`, `_run`, `_… | Revision 4 tolerated them by making the opener wait for announced clearers. |
| GAP-W178 | R-MECHANISM_AND_LIFECYCLE_M7-133 | 777 | P | Mechanism and lifecycl > M7. `_open`, `_commit`, `_run`, `_… | The wait closed cycles through user code and through sections opened inside a clearer's window (the fifth critic's MF1), and its same-thread exclusion lost calls silentl… |
| GAP-W179 | R-MECHANISM_AND_LIFECYCLE_M7-183 | ? | P | Mechanism and lifecycl > M7. `_open`, `_commit`, `_run`, `_… | *Evidence (revision 5).* - `rev5/t1_onecall_atomic.py`: above. |
| GAP-W180 | R-MECHANISM_AND_LIFECYCLE_M7-185 | 807 | P | Mechanism and lifecycl > M7. `_open`, `_commit`, `_run`, `_… | Each C operation is one step, and each one-call step is one step. |
| GAP-W181 | R-MECHANISM_AND_LIFECYCLE_M8-002 | 840 | P | Mechanism and lifecycl > M8. `record()` is pure | Refuse **TRACE_INCOMPLETE** if `core.pid != os.getpid()` ("inherited across fork: the record belongs to the parent process"). |
| GAP-W182 | R-MECHANISM_AND_LIFECYCLE_M8-007 | 842 | P | Mechanism and lifecycl > M8. `record()` is pure | **Openings.** Each opening's `end, notes = o.fin.get('fin', ('open', ()))`, plus `o.lazy` and `core.lost_note` when set. |
| GAP-W183 | R-MECHANISM_AND_LIFECYCLE_M8-008 | 842 | P | Mechanism and lifecycl > M8. `record()` is pure | The notes list is in that order: the `fin` notes, then `o.lazy`, then `core.lost_note` (revision 9, GAP-22). |
| GAP-W184 | R-MECHANISM_AND_LIFECYCLE_M8-009 | 843 | P | Mechanism and lifecycl > M8. `record()` is pure | **Counts.** Expanded through `core.names`. |
| GAP-W185 | R-MECHANISM_AND_LIFECYCLE_M8-010 | 843 | P | Mechanism and lifecycl > M8. `record()` is pure | `uncredited` is summed across threads. |
| GAP-W186 | R-MECHANISM_AND_LIFECYCLE_M8-011 | 845 | P | Mechanism and lifecycl > M8. `record()` is pure | The schema is v5e's, with the `/3` id and the code sets of the Reason-codes section. |
| GAP-W187 | R-MECHANISM_AND_LIFECYCLE_M9-002 | 848 | P | Mechanism and lifecycl > M9. The at-fork handler | Revision 9 (GAP-24): "no-op" means `_forget_in_child` returns at its first statement iff `_MON[0] is None`. |
| GAP-W188 | R-MECHANISM_AND_LIFECYCLE_M9-003 | 848 | P | Mechanism and lifecycl > M9. The at-fork handler | Revision 9 (GAP-23): the registration runs on every execution of the module, so each `importlib.reload` registers one more handler, and a child runs one per load, oldest… |
| GAP-W189 | R-MECHANISM_AND_LIFECYCLE_M9-004 | 848 | P | Mechanism and lifecycl > M9. The at-fork handler | Every handler reads the same globals (a reload re-runs the module in the same dict), and a second run finds `_ANCHORS`, `_BY_FN` and `_MINTED` already empty and the id's… |
| GAP-W190 | R-MECHANISM_AND_LIFECYCLE_M9-007 | 856 | P | Mechanism and lifecycl > M9. The at-fork handler | CPython ignores an exception raised by an at-fork handler, so a raising audit hook aborts the handler there. |
| GAP-W191 | R-MECHANISM_AND_LIFECYCLE_M9-011 | 856 | P | Mechanism and lifecycl > M9. The at-fork handler | A child tracer that later declares such a function treats M_T as its original, and restores M_T at the end. |
| GAP-W192 | R-MECHANISM_AND_LIFECYCLE_M9-015 | 860 | P | Mechanism and lifecycl > M9. The at-fork handler | The tool id is kept (monotone). |
| GAP-W193 | R-MECHANISM_AND_LIFECYCLE_M10-002 | 864 | P | Mechanism and lifecycl > M10. The introspection interface (… | `"mints"`: a list of `{"target", "holders": int, "installed": bool, "local_events": int, "pending": int}`, one per value of `_MINTED`, sorted by the tuple `(target, hold… |
| GAP-W194 | R-MECHANISM_AND_LIFECYCLE_M10-003 | 864 | P | Mechanism and lifecycl > M10. The introspection interface (… | `target` is the mint's `qualname`, F_T's `module:qualname` by the rule of Minting step 1 (revision 9, GAP-13), and (revision 4, N6) snapshot equality needs a fixed order. |
| GAP-W195 | R-MECHANISM_AND_LIFECYCLE_M10-005 | 865 | P | Mechanism and lifecycl > M10. The introspection interface (… | `"anchors"`: int; |
| GAP-W196 | R-MECHANISM_AND_LIFECYCLE_M10-006 | 866 | P | Mechanism and lifecycl > M10. The introspection interface (… | `"guard"`: `"free" \| "held" \| "dead"`: `"free"` when the last token of the succession chain (M2's walk) has `tid` None, `"held"` when it is live (`_alive`), and `"dead… |
| GAP-W197 | R-MECHANISM_AND_LIFECYCLE_M10-007 | 867 | P | Mechanism and lifecycl > M10. The introspection interface (… | `"cut"`: int; |
| GAP-W198 | R-MECHANISM_AND_LIFECYCLE_M10-011 | 869 | P | Mechanism and lifecycl > M10. The introspection interface (… | `"tool"`: `_TOOL[0]`, an int or None; |
| GAP-W199 | R-MECHANISM_AND_LIFECYCLE_M10-012 | 870 | P | Mechanism and lifecycl > M10. The introspection interface (… | `"tool_ours"`: bool, `_ours()`, and False while `_MON[0]` is None; |
| GAP-W200 | R-MECHANISM_AND_LIFECYCLE_M10-013 | 871 | P | Mechanism and lifecycl > M10. The introspection interface (… | `"global_events"`: int, `_MON[0][1](_TOOL[0])`, and 0 while `_TOOL[0]` or `_MON[0]` is None; |
| GAP-W201 | R-MECHANISM_AND_LIFECYCLE_M10-014 | 872 | P | Mechanism and lifecycl > M10. The introspection interface (… | `"pid"`: int, `os.getpid()`. |
| GAP-W202 | R-MECHANISM_AND_LIFECYCLE_M10-016 | 875 | P | Mechanism and lifecycl > M10. The introspection interface (… | While a self-trace has minted a machinery function, that is the self-trace's M_T, which is the code that actually runs. |
| GAP-W203 | R-MECHANISM_AND_LIFECYCLE_M10-017 | 875 | P | Mechanism and lifecycl > M10. The introspection interface (… | Code captured at import never fires then (`rev2/p6_faultpoint_identity.py`). |
| GAP-W204 | R-MECHANISM_AND_LIFECYCLE_M10-026 | 882 | P | Mechanism and lifecycl > M10. The introspection interface (… | Neither function changes state. |
| GAP-W205 | R-MECHANISM_AND_LIFECYCLE_M10-033 | 886 | P | Mechanism and lifecycl > M10. The introspection interface (… | `_TOOL` (read: `_TOOL[0]` is the id the step acts on); |
| GAP-W206 | R-MECHANISM_AND_LIFECYCLE_M10-035 | 888 | P | Mechanism and lifecycl > M10. The introspection interface (… | `_CONSUME` and `_list` (read: the consumer whose CALL opens the measured interval, compared by identity); |
| GAP-W207 | R-MECHANISM_AND_LIFECYCLE_M10-039 | 890 | P | Mechanism and lifecycl > M10. The introspection interface (… | `_EVENTS5`, `_CALLBACKS5` and `_LOCAL` (read: to restore styxx's callbacks after a case and to pass local event masks); |
| GAP-W208 | R-MECHANISM_AND_LIFECYCLE_M10-040 | 891 | P | Mechanism and lifecycl > M10. The introspection interface (… | `_LOST` (read: `len(_LOST)` is part of the observable state, because `_register` counts inside its call). |
| GAP-W209 | R-MECHANISM_AND_LIFECYCLE_M11-004 | 897 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | **Step 2 (WRONG_TRACER).** `type(t) is not str or t != _TRACER_ID`. |
| GAP-W210 | R-MECHANISM_AND_LIFECYCLE_M11-007 | 898 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | The note and problem code sets are the /3 sets. |
| GAP-W211 | R-MECHANISM_AND_LIFECYCLE_M11-011 | 900 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | **NOT_EXERCISED.** The fixed sentence reads: "work on other threads, pools, executors, child processes or asyncio tasks is credited only to a section that work opens its… |
| GAP-W212 | R-MECHANISM_AND_LIFECYCLE_M11-012 | 901 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | **score() on metrics.** The metric guard wraps `float(_v)`: an OverflowError becomes `GateSpecError("gate G: metric … is too large for a float")`. |
| GAP-W213 | R-MECHANISM_AND_LIFECYCLE_M11-014 | 902 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | **check_metrics.** It never raises for a JSON-shaped result: dicts, lists, str, bool, None, floats and ints of any size. |
| GAP-W214 | R-MECHANISM_AND_LIFECYCLE_M11-015 | 903 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | `smoke = dict.get(result, 'smoke')` if the result is a dict subclass. |
| GAP-W215 | R-MECHANISM_AND_LIFECYCLE_M11-017 | 904 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | (revision 9, GAP-18) Every metric and composition path is walked one key at a time: while the current value `x` has `issubclass(type(x), dict)`, the next is `dict.get(x,… |
| GAP-W216 | R-MECHANISM_AND_LIFECYCLE_M11-018 | 904 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | No `isinstance`, `in` or `[]` is applied to result data. |
| GAP-W217 | R-MECHANISM_AND_LIFECYCLE_M11-019 | 904 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | `score()` is not changed by this: it keeps v4's `_resolve` and v5e's `isinstance(_v, numbers.Real)` guard, and M11's only change to it is the `float()` OverflowError rul… |
| GAP-W218 | R-MECHANISM_AND_LIFECYCLE_M11-020 | 905 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | Usability is `issubclass(type(v), (int, float)) and type(v) is not bool and _finite(v)`. |
| GAP-W219 | R-MECHANISM_AND_LIFECYCLE_M11-022 | 905 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | The note reads "int too large for a float". |
| GAP-W220 | R-MECHANISM_AND_LIFECYCLE_M11-023 | 906 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | `present` uses the NO_TRACE test. |
| GAP-W221 | R-MECHANISM_AND_LIFECYCLE_M11-025 | 907 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | Otherwise it is `str(e)` with " (smoke run: score(smoke=True) does not read coverage)" appended when smoke, so it always starts with the refusal's `[V5:CODE]`. |
| GAP-W222 | R-MECHANISM_AND_LIFECYCLE_M11-026 | 907 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | Revision 9 (GAP-17) states the rule exactly: the note is "smoke run" iff smoke is truthy and `present` is false; in every other refusal it is `str(e)`, with the suffix i… |
| GAP-W223 | R-MECHANISM_AND_LIFECYCLE_M11-027 | 907 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | A trace that is absent in a non-smoke result therefore gives the NO_TRACE text. |
| GAP-W224 | R-MECHANISM_AND_LIFECYCLE_M11-028 | 908 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | For in-process results carrying user objects, it can run two kinds of user method: a `__float__` override on an int or float subclass, and the `__eq__` of a str-subclass… |
| GAP-W225 | R-MECHANISM_AND_LIFECYCLE_M11-029 | 908 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | The second is contrived: a JSON-loaded result has exact-str keys. |
| GAP-W226 | R-MECHANISM_AND_LIFECYCLE_M11-033 | 911 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | `{T}`: a type's name, `_TYPE_QUAL.__get__(type(x))`, the `__qualname__` read through the C descriptor (so no metaclass property runs). |
| GAP-W227 | R-MECHANISM_AND_LIFECYCLE_M11-034 | 911 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | For example `list`, `OrderedDict`, `generator`, `async_generator`, `function`; |
| GAP-W228 | R-MECHANISM_AND_LIFECYCLE_M11-035 | 912 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | `{S}`, `{S1}`, `{S2}`: a section, which is an exact str at that point (At open, step 3), rendered `repr(s)`, for example `'G'`. |
| GAP-W229 | R-MECHANISM_AND_LIFECYCLE_M11-036 | 912 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | S1 is the opening already on the stack; S2 is the section being opened; |
| GAP-W230 | R-MECHANISM_AND_LIFECYCLE_M11-037 | 913 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | `{D}`, `{U}`: `repr()` of a dict of the gate's missing targets (in the gate's `exercises` order) that appear in the trace's `uncredited.dispatched` or `uncredited.unattr… |
| GAP-W231 | R-MECHANISM_AND_LIFECYCLE_M11-038 | 917 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | text: NO_TRACE, first wording \| exact substring: `the result is a {T}, not a dict` |
| GAP-W232 | R-MECHANISM_AND_LIFECYCLE_M11-039 | 918 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | text: NO_TRACE, second wording \| exact substring: `the result has no 'coverage_trace' key` |
| GAP-W233 | R-MECHANISM_AND_LIFECYCLE_M11-040 | 919 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | text: NO_TRACE, third wording \| exact substring: `'coverage_trace' is a {T}, not an exact dict (e.g. loaded with object_pairs_hook)` |
| GAP-W234 | R-MECHANISM_AND_LIFECYCLE_M11-041 | 920 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | text: NESTED_SECTION, same section \| exact substring: `a call there would be on the stack of two openings of section {S}` |
| GAP-W235 | R-MECHANISM_AND_LIFECYCLE_M11-042 | 921 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | text: NESTED_SECTION, different sections \| exact substring: `one call would count for both sections {S1} and {S2}` |
| GAP-W236 | R-MECHANISM_AND_LIFECYCLE_M11-043 | 173 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | text: LAZY_RESULT \| exact substring: `fn returned a {T}; whatever of its body runs after the section closed does not count`, followed immediately, iff the object had no… |
| GAP-W237 | R-MECHANISM_AND_LIFECYCLE_M11-044 | 923 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | text: TRACE_ACTIVE, never entered \| exact substring: `the tracer was never entered` |
| GAP-W238 | R-MECHANISM_AND_LIFECYCLE_M11-045 | 924 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | text: TRACE_ACTIVE, active \| exact substring: `the tracer is active: record() was called inside its with-block, or its __exit__ never started, and then one call of __ex… |
| GAP-W239 | R-MECHANISM_AND_LIFECYCLE_M11-046 | 925 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | text: NOT_EXERCISED, uncredited labels \| exact substring: `dispatched {D}, unattributed {U}` |
| GAP-W240 | R-MECHANISM_AND_LIFECYCLE_M11-047 | 926 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | text: NOT_EXERCISED, fixed sentence \| exact substring: the sentence under NOT_EXERCISED above, verbatim |
| GAP-W241 | R-MECHANISM_AND_LIFECYCLE_M11-048 | 927 | P | Mechanism and lifecycl > M11. Scoring and check_metrics | text: check_metrics overflow note \| exact substring: `int too large for a float` |
| GAP-W242 | R-MECHANISM_AND_LIFECYCLE-001 | 193 | P | Mechanism and lifecycl > What is removed from v5e | `_LOCK`, `_ACTIVE`, `_STOP`, `_THREADS`, `_EPOCH` and the counters; |
| GAP-W243 | R-MECHANISM_AND_LIFECYCLE-002 | 946 | P | Mechanism and lifecycl > What is removed from v5e | the profile hook `_hook`, with its self-removal and last-close removal; |
| GAP-W244 | R-MECHANISM_AND_LIFECYCLE-004 | 948 | P | Mechanism and lifecycl > What is removed from v5e | FOREIGN_PROFILER, PROFILER_LOST and THREAD_HOP; |
| GAP-W245 | R-MECHANISM_AND_LIFECYCLE-005 | 949 | P | Mechanism and lifecycl > What is removed from v5e | the `_own_dict` try/except; |
| GAP-W246 | R-MECHANISM_AND_LIFECYCLE-006 | 950 | P | Mechanism and lifecycl > What is removed from v5e | `isinstance` dispatch in resolution; |
| GAP-W247 | R-MECHANISM_AND_LIFECYCLE-007 | 951 | P | Mechanism and lifecycl > What is removed from v5e | the `__wrapped__`-based cache body; |
| GAP-W248 | R-MECHANISM_AND_LIFECYCLE-008 | 952 | P | Mechanism and lifecycl > What is removed from v5e | `weakref.finalize`; |
| GAP-W249 | R-MECHANISM_AND_LIFECYCLE-010 | 954 | P | Mechanism and lifecycl > What is removed from v5e | the v5e exam as a v5f exam: v5f needs its own prereg and frozen runner. |
| GAP-W250 | R-EXCEPTION_SAFETY_MODEL-001 | 960 | P | Exception-safety model | **Threat.** An exception can land at any bytecode of the machinery. |
| GAP-W251 | R-EXCEPTION_SAFETY_MODEL-002 | 960 | P | Exception-safety model | That includes a function's entry (RESUME) and a loop back-edge. |
| GAP-W252 | R-EXCEPTION_SAFETY_MODEL-003 | 960 | P | Exception-safety model | On 3.13, an exception at a back-edge escapes the enclosing `try` table without running `finally` or a with-block's exit (CPython #130279; round-4 found-after item). |
| GAP-W253 | R-EXCEPTION_SAFETY_MODEL-006 | 960 | P | Exception-safety model | It also includes the machinery's own callbacks: a sys.monitoring callback is Python code with eval-breaker checks. |
| GAP-W254 | R-EXCEPTION_SAFETY_MODEL-007 | 962 | P | Exception-safety model | **Sources:** signal-handler exceptions, KeyboardInterrupt, RecursionError, MemoryError, audit hooks, and a foreign tool raising at an event of one of our frames. |
| GAP-W255 | R-EXCEPTION_SAFETY_MODEL-008 | 962 | P | Exception-safety model | That foreign tool can be a lower-id monitoring tool, or a settrace/setprofile function on the thread. |
| GAP-W256 | R-EXCEPTION_SAFETY_MODEL-013 | 965 | P | Exception-safety model | (revision 8 self-audit, W2) `sys._getframe` in `_run` and `_run_async`, the argument of `_open` (M7), at every open; |
| GAP-W257 | R-EXCEPTION_SAFETY_MODEL-018 | 968 | P | Exception-safety model | `gc.get_referrers` in E2's sharing scan and in CLONE_ALIVE; |
| GAP-W258 | R-EXCEPTION_SAFETY_MODEL-020 | 969 | P | Exception-safety model | A hook that raises there cuts the registration short (M7, "The registration") and propagates out of the transaction (M5's heading). |
| GAP-W259 | R-EXCEPTION_SAFETY_MODEL-039 | 981 | P | Exception-safety model > Invariants preserved by every pref… | (a) at F's entry event, O's anchor was registered and met on F's live chain before the cut, the running loop was `O.loop`, O.core held F's mint, and `id(M_T)` was in `O.… |
| GAP-W260 | R-EXCEPTION_SAFETY_MODEL-040 | 982 | P | Exception-safety model > Invariants preserved by every pref… | (b) F then returned, yielded, or unwound at an offset other than its entry offset; |
| GAP-W261 | R-EXCEPTION_SAFETY_MODEL-041 | 983 | P | Exception-safety model > Invariants preserved by every pref… | (c) at publication, `id(M_T)` was still in `O.core.by_code`, which exit empties in its first store after the claim. |
| GAP-W262 | R-EXCEPTION_SAFETY_MODEL-057 | 997 | P | Exception-safety model > Invariants preserved by every pref… | The mutex owner runs user code inside its transaction that waits for a thread, and that thread is itself waiting for the mutex. |
| GAP-W263 | R-EXCEPTION_SAFETY_MODEL-059 | 997 | P | Exception-safety model > Invariants preserved by every pref… | The waiter's bound breaks the cycle. |
| GAP-W264 | R-EXCEPTION_SAFETY_MODEL-060 | 997 | P | Exception-safety model > Invariants preserved by every pref… | After 10 s it raises MACHINERY_BUSY, its `with` releases the lock, and the owner proceeds (over-blocking #20). |
| GAP-W265 | R-EXCEPTION_SAFETY_MODEL-070 | 1007 | P | Exception-safety model > Invariants preserved by every pref… | A fault never causes any of these: over-credit; a hang; a mint left installed after the next reconciliation, unless its holder is a live zombie (L-ZOMBIE); or a poisoned… |
| GAP-W266 | R-EXCEPTION_SAFETY_MODEL-071 | 1009 | P | Exception-safety model > Invariants preserved by every pref… | A fault never swallows an exception, with one exception. |
| GAP-W267 | R-EXCEPTION_SAFETY_MODEL-082 | 1015 | P | Exception-safety model > Per-transition prefixes | Between E4 and E5: the same. |
| GAP-W268 | R-EXCEPTION_SAFETY_MODEL-083 | 1016 | P | Exception-safety model > Per-transition prefixes | At the facade's return, after E5: a zombie. |
| GAP-W269 | R-EXCEPTION_SAFETY_MODEL-085 | 1018 | P | Exception-safety model > Per-transition prefixes | Before X1: a zombie. |
| GAP-W270 | R-EXCEPTION_SAFETY_MODEL-086 | 1018 | P | Exception-safety model > Per-transition prefixes | `record()` refuses TRACE_ACTIVE, and `__exit__` again completes it. |
| GAP-W271 | R-EXCEPTION_SAFETY_MODEL-093 | 1022 | P | Exception-safety model > Per-transition prefixes | After the append, before the `try` (the rest of `_open`, and `_run` up to its `try`): an unregistered, inert opening that exit finalises as `"open"`. |
| GAP-W272 | R-EXCEPTION_SAFETY_MODEL-094 | 1022 | P | Exception-safety model > Per-transition prefixes | The event is untouched. |
| GAP-W273 | R-EXCEPTION_SAFETY_MODEL-103 | 1025 | P | Exception-safety model > Per-transition prefixes | Before the claim: exit claims it as `("open", OPEN_AT_EXIT)`. |
| GAP-W274 | R-EXCEPTION_SAFETY_MODEL-104 | 1026 | P | Exception-safety model > Per-transition prefixes | After the claim: the cleanups are redone. |
| GAP-W275 | R-EXCEPTION_SAFETY_MODEL-105 | 1027 | P | Exception-safety model > Per-transition prefixes | `_run_async`'s `finally` skipped (a signal at the `await`'s throw-path back-edge on 3.12; M7): the same as "before the claim". |
| GAP-W276 | R-EXCEPTION_SAFETY_MODEL-106 | 1027 | P | Exception-safety model > Per-transition prefixes | The anchor frame is dead. |
| GAP-W277 | R-EXCEPTION_SAFETY_MODEL-117 | 1031 | P | Exception-safety model > Per-transition prefixes | A fault loses at most that one credit and can never add one: an entry killed before its store has no pending entry, and a pending entry killed at its entry offset never … |
| GAP-W278 | R-EXCEPTION_SAFETY_MODEL-118 | 1031 | P | Exception-safety model > Per-transition prefixes | A pending entry whose confirmation never arrives stays until `_retire` clears it. |
| GAP-W279 | R-EXCEPTION_SAFETY_MODEL-119 | 1031 | P | Exception-safety model > Per-transition prefixes | It keeps its frame, and that frame's callers, alive until then (L-MONITOR). |
| GAP-W280 | R-EXCEPTION_SAFETY_MODEL-120 | 1032 | P | Exception-safety model > Per-transition prefixes | **Reconcile and retire.** Idempotent. |
| GAP-W281 | R-EXCEPTION_SAFETY_MODEL-121 | 1032 | P | Exception-safety model > Per-transition prefixes | A second fault inside them is repaired by the next transaction. |
| GAP-W282 | R-EXCEPTION_SAFETY_MODEL-128 | 1034 | P | Exception-safety model > Per-transition prefixes | A `_register` exchange lands on another tool's id when an audit hook on `sys.monitoring.register_callback`, running inside that call before its exchange, lets another to… |
| GAP-W283 | R-EXCEPTION_SAFETY_MODEL-133 | 1036 | P | Exception-safety model > Per-transition prefixes | A `free_tool_id` landing between `_ours()` and `set_events` made that call raise ValueError out of `run()` or its close. |
| GAP-W284 | R-EXCEPTION_SAFETY_MODEL-134 | 1037 | P | Exception-safety model > Per-transition prefixes | A free *and re-take* by another tool in that window made the call succeed on the foreign id. |
| GAP-W285 | R-EXCEPTION_SAFETY_MODEL-143 | 1043 | D | Exception-safety model > Residuals, disclosed | **L-ZOMBIE.** A tracer whose exit never began stays active. |
| GAP-W286 | R-EXCEPTION_SAFETY_MODEL-144 | 1044 | D | Exception-safety model > Residuals, disclosed | Causes: an exception at `__exit__`'s entry; a foreign tool raising at `__enter__`'s return event; or a harness's own `with` body ending in a loop on 3.13, where CPython … |
| GAP-W287 | R-EXCEPTION_SAFETY_MODEL-145 | 1045 | D | Exception-safety model > Residuals, disclosed | `record()` refuses TRACE_ACTIVE. |
| GAP-W288 | R-EXCEPTION_SAFETY_MODEL-146 | 1046 | D | Exception-safety model > Residuals, disclosed | What persists: its equal-code mints stay installed, with their local events. |
| GAP-W289 | R-EXCEPTION_SAFETY_MODEL-149 | 1046 | D | Exception-safety model > Residuals, disclosed | That covers the common case: the fault that made it a zombie happened after the harness's `cov.run` calls returned. |
| GAP-W290 | R-EXCEPTION_SAFETY_MODEL-150 | 1047 | D | Exception-safety model > Residuals, disclosed | How long: until `__exit__()` is called, or until the facade becomes unreachable and some later enter or exit in the process reconciles. |
| GAP-W291 | R-EXCEPTION_SAFETY_MODEL-152 | 1048 | D | Exception-safety model > Residuals, disclosed | If a second fault leaves a stale anchor, the anchor frame's `f_back` chain can keep the facade reachable. |
| GAP-W292 | R-EXCEPTION_SAFETY_MODEL-153 | 1049 | D | Exception-safety model > Residuals, disclosed | **L-DELIVERY.** See Stated limits. |
| GAP-W293 | R-EXCEPTION_SAFETY_MODEL-154 | 1049 | D | Exception-safety model > Residuals, disclosed | Exceptions surfacing inside styxx callbacks take effect at that event. |
| GAP-W294 | R-EXCEPTION_SAFETY_MODEL-155 | 1050 | D | Exception-safety model > Residuals, disclosed | **Re-entry.** A finalizer, audit hook or signal handler that enters or exits a tracer inside another enter or exit on the same thread gets REENTRANT. |
| GAP-W295 | R-EXCEPTION_SAFETY_MODEL-156 | 1050 | D | Exception-safety model > Residuals, disclosed | In a finalizer this is printed as "Exception ignored" and that tracer fails. |
| GAP-W296 | R-EXCEPTION_SAFETY_MODEL-171 | 1054 | D | Exception-safety model > Residuals, disclosed | a `run_async` section opened on the same thread inside the window and left suspended; |
| GAP-W297 | R-EXCEPTION_SAFETY_MODEL-172 | 1055 | D | Exception-safety model > Residuals, disclosed | a greenlet switch inside the window. |
| GAP-W298 | R-VERSION_POLICY-005 | 1072 | P | Version policy | interpreter: CPython 3.14+, free-threaded builds (`Py_GIL_DISABLED`), other implementations \| tracing: **refused** \| scoring: works \| why: Refused until `Handle._run`… |
| GAP-W299 | R-VERSION_POLICY-011 | 1078 | P | Version policy | **The RESUME eval-breaker order.** By D3's reading of its measurements, 3.12's INSTRUMENTED_RESUME checks the eval breaker *after* the instrumentation call, and 3.13 che… |
| GAP-W300 | R-REASON_CODES-003 | 191 | P | Reason codes | code: DECL \| status: same \| when it fires: parse: `exercises` is not a non-empty list of ASCII `module:qualname`, or has duplicates \| effect: raise |
| GAP-W301 | R-REASON_CODES-007 | 194 | P | Reason codes | code: REENTRY \| status: changed \| when it fires: `__enter__` whose atomic claim `marks.setdefault('entering', me)` loses: a second or concurrent entry, or a retry afte… |
| GAP-W302 | R-REASON_CODES-011 | 233 | P | Reason codes | code: INSTANCE_PATH \| status: changed \| when it fires: entry: a module after the colon; a step whose own dict is missing, lacks the name, or is served by a Python-leve… |
| GAP-W303 | R-REASON_CODES-012 | 50 | P | Reason codes | code: NOT_A_FUNCTION \| status: changed \| when it fires: entry: not FunctionType, staticmethod/classmethod of one, or an admissible C cache wrapper. **Also:** a cache w… |
| GAP-W304 | R-REASON_CODES-013 | 185 | P | Reason codes | code: RESERVED_TARGET \| status: **new** \| when it fires: entry: F_T is `Handle._run` or `BaseEventLoop._run_once`, or F_T's code is a cut code \| effect: raise |
| GAP-W305 | R-REASON_CODES-016 | 194 | P | Reason codes | code: REENTRANT \| status: **new** \| when it fires: enter or exit re-entered on the same thread from inside a transition (a finalizer, audit hook or signal handler) \| … |
| GAP-W306 | R-REASON_CODES-017 | 194 | P | Reason codes | code: MACHINERY_BUSY \| status: **new** \| when it fires: another thread held the machinery (the robust mutex) for more than 10 s. Revision 5: an open never waits, so it… |
| GAP-W307 | R-REASON_CODES-021 | 191 | P | Reason codes | code: NESTED_SECTION \| status: changed (text) \| when it fires: open: a registered opening of the same tracer is on the opener's chain before the cut (including an eage… |
| GAP-W308 | R-REASON_CODES-023 | 26 | P | Reason codes | code: CLONE_ALIVE \| status: changed \| when it fires: exit: an unexplained reference to M_T and either (a) gc finds another FunctionType holding it, or (b) the gc freez… |
| GAP-W309 | R-REASON_CODES-024 | 189 | P | Reason codes | code: CUT_MOVED \| status: **new** \| when it fires: at an entry event of minted code, or at exit: `Handle._run` or `BaseEventLoop._run_once` is not a function whose cod… |
| GAP-W310 | R-REASON_CODES-025 | 613 | P | Reason codes | code: TRACE_ACTIVE \| status: changed (text) \| when it fires: `record()` on a tracer that was never entered (its own text), inside its with-block, or a zombie \| effect… |
| GAP-W311 | R-REASON_CODES-026 | 539 | P | Reason codes | code: TRACE_INCOMPLETE \| status: changed \| when it fires: `record()` after an exit that began but did not finish; after a failed enter; or in a process other than the … |
| GAP-W312 | R-REASON_CODES-027 | 173 | P | Reason codes | code: NO_TRACE \| status: changed \| when it fires: score: the result is not a dict subclass; the key is absent; or the trace is not an exact dict (split message) \| eff… |
| GAP-W313 | R-REASON_CODES-029 | 195 | P | Reason codes | code: BAD_TRACE \| status: changed \| when it fires: score: any schema clause fails, with the exact type tested before any hash or compare (`end`, `gates_sha256`, keys, … |
| GAP-W314 | R-REASON_CODES-033 | 78 | P | Reason codes | code: NOT_EXERCISED \| status: changed (text) \| when it fires: score: a declared target is missing from the union of its section's `calls` \| effect: refuse |
| GAP-W315 | R-REASON_CODES-034 | 379 | P | Reason codes | code: note OPEN_AT_EXIT \| status: changed \| when it fires: exit: the opening was still open; also "pruned: the trace's own exit did not run" \| effect: never refuses |
| GAP-W316 | R-REASON_CODES-035 | 1129 | P | Reason codes | code: note LAZY_RESULT \| status: changed \| when it fires: `run()` got an exact generator, coroutine or async generator back; new text; "(its body had not started)" whe… |
| GAP-W317 | R-REASON_CODES-039 | 1133 | P | Reason codes | code: SIGNAL_TIMER (D1), UNSTABLE_ATTRIBUTE and GENERATOR_TARGET (D2), MACHINERY_BROKEN (D3) \| status: never adopted \| when it fires: — \| effect: — |
| GAP-W318 | R-REASON_CODES-040 | 1134 | P | Reason codes | code: RETIRED earlier \| status: carried \| when it fires: SHARED_CODE, NO_CODE, THREAD_OUTLIVES, HOOK_FAILED, PROFILER_REPLACED, EXIT_ORDER, SECTION_CONTEXT, ALIAS, SEC… |
| GAP-W319 | R-OVER_BLOCKING_DISCLOSED-001 | 1274 | D | Over-blocking, disclosed | Each item is a refusal, or a missing credit, that a legitimate harness can meet. |
| GAP-W320 | R-OVER_BLOCKING_DISCLOSED-011 | 1278 | D | Over-blocking, disclosed | **Sections must be calls.** A generator or coroutine returned by fn gets LAZY_RESULT, and whatever of it runs after the close does not count. |
| GAP-W321 | R-OVER_BLOCKING_DISCLOSED-013 | 1279 | D | Over-blocking, disclosed | That includes an eager child's first step. |
| GAP-W322 | R-OVER_BLOCKING_DISCLOSED-014 | 1280 | D | Over-blocking, disclosed | **A swallowed refusal refuses the whole trace.** This applies to any recorded code: REENTRY, TRACE_INACTIVE, UNDECLARED_SECTION, NESTED_SECTION, CLONE_CALLED, CLONE_ALIV… |
| GAP-W323 | R-OVER_BLOCKING_DISCLOSED-017 | 1282 | D | Over-blocking, disclosed | CPython 3.9, 3.10 and 3.11, including the lab's default 3.11, which P1-style harnesses use; |
| GAP-W324 | R-OVER_BLOCKING_DISCLOSED-018 | 1283 | D | Over-blocking, disclosed | 3.14 and later; |
| GAP-W325 | R-OVER_BLOCKING_DISCLOSED-019 | 1284 | D | Over-blocking, disclosed | free-threaded builds; |
| GAP-W326 | R-OVER_BLOCKING_DISCLOSED-020 | 1285 | D | Over-blocking, disclosed | non-CPython implementations. |
| GAP-W327 | R-OVER_BLOCKING_DISCLOSED-025 | 1288 | D | Over-blocking, disclosed | **Remedy:** construct the first tracer before installing the wrapper, or install it after styxx's first `coverage_trace()`, and do not reload `styxx.protocol` while it i… |
| GAP-W328 | R-STATED_LIMITS-007 | 1366 | D | Stated limits | Work another gate supplies as data is credited to the section whose stack runs it: |
| GAP-W329 | R-STATED_LIMITS-008 | 1367 | D | Stated limits | queues drained inline or by a sectioned consumer; |
| GAP-W330 | R-STATED_LIMITS-009 | 1368 | D | Stated limits | `concurrent.futures` done-callbacks; |
| GAP-W331 | R-STATED_LIMITS-010 | 1369 | D | Stated limits | generators and coroutines *created during the trace* elsewhere and resumed there; |
| GAP-W332 | R-STATED_LIMITS-012 | 1371 | D | Stated limits | eager tasks' first steps. |
| GAP-W333 | R-STATED_LIMITS-039 | 1402 | D | Stated limits | An `except` clause for the original exception then does not run. |
| GAP-W334 | R-STATED_LIMITS-045 | 1407 | D | Stated limits | A pending asynchronous exception therefore takes effect only after the handler has started, and the handler's first instructions, up to its first eval-breaker check, alw… |
| GAP-W335 | R-STATED_LIMITS-046 | 1407 | D | Stated limits | The measured consequence is below: 0 lost handlers untraced. |
| GAP-W336 | R-STATED_LIMITS-047 | 1407 | D | Stated limits | With the unwind callback, it can take effect before the handler starts. - `finally` blocks and with-exits still run, for the replacing exception. |
| GAP-W337 | R-STATED_LIMITS-049 | 1413 | D | Stated limits | Measured with that probe's method in `rev2/p4_unwind_scope.py`: a loop raising and catching ValueError in undeclared code, 1M iterations, under a 20 µs SIGALRM flood who… |
| GAP-W338 | R-STATED_LIMITS-051 | 41 | D | Stated limits | : untraced \| 3.12.3: 0 \| 3.13.12: 0 |
| GAP-W339 | R-STATED_LIMITS-054 | 1420 | D | Stated limits | : inside an open section: revision 2 \| 3.12.3: 168,512 \| 3.13.12: 120,255 |
| GAP-W340 | R-STATED_LIMITS-055 | 1422 | D | Stated limits | **Why this is accepted when 3.11's hook was not.** The 3.11 hook skipped C calls, including the `lock.release()` inside a `with` block's exit. |
| GAP-W341 | R-STATED_LIMITS-058 | 1422 | D | Stated limits | It moves the point where an already-pending asynchronous exception takes effect to the start of a handler's matching. |
| GAP-W342 | R-STATED_LIMITS-069 | 1431 | D | Stated limits | Revision 2 keeps PY_UNWIND and narrows it to open sections instead. |
| GAP-W343 | R-STATED_LIMITS-070 | 1431 | D | Stated limits | That meets the measured case, unrelated code outside sections, at a cost of about 3 µs per section. - **L-ZOMBIE (new).** A tracer whose exit never began stays active, a… |
| GAP-W344 | R-STATED_LIMITS-071 | ? | D | Stated limits | The causes: - an exception at `__exit__`'s entry; - a foreign tool raising at `__enter__`'s return; - a harness `with` body ending in a loop on 3.13 hit by a signal at i… |
