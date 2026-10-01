# v5f spec gaps found while writing `ref_v5f.py` (exam author, pre-freeze)

Source text: `papers/first-afference/DESIGN_protocol_v5f_DRAFT_2026_09_25.md`. GAP-01 to GAP-27 were raised on the revision-8 draft plus Appendix A. Revision 9 resolves all 27 in the text ("Revision 9: spec gaps from the exam author"). The "Revision 9 follow-ups" at the end were raised on the revision-9 text. Each gap names the section, what is missing or contradictory, and the reading `ref_v5f.py` implements. `ref_v5f.py` cites each one as `GAP-nn` where it applies.

The readings were taken from the text alone. No prototype was consulted to settle any of them (see `ATTESTATION.md`). The spec owner should fix the text; `ref_v5f.py` then follows the fix.

**Freeze-blocking** means one of two things. Either a frozen gate or exam check (G_HYG, SM2's normalizer, the leftover check, G_FI's C5) would judge a faithful implementation differently depending on which reading it took, or two normative sentences contradict each other.

## Status after revision 9 (GAP-01 to GAP-27: all resolved and applied)

Revision 9 resolves every gap below in the text; each row gives its section there. `ref_v5f.py` applies each resolution at commit `c7de7761`: C1-C3 of "Required changes to ref_v5f.py", C4's comments, and the GAP-19 return shape. At that commit, `smoke_cases.py` passes 47 of 47 on CPython 3.12.3 and 3.13.12, including the new cases X59e, V69b, X156f and X156g. `rules_v5f.json` is reconciled at `3002c140` (GAP-27). The readings below are kept as they were written, for the record. Where revision 9 differs from a reading, the row says so.

| gap | status | revision-9 resolution | in `ref_v5f.py` | commit |
|---|---|---|---|---|
| GAP-01 | resolved and applied | the literal masks are the first line of M1 | ref matched; unchanged | `c7de7761` |
| GAP-02 | resolved and applied | `_get_running_loop` is an M1 name, checked as `_asyncio`'s builtin after `import asyncio` and re-bound at every `coverage_trace()`; new case X156g | C2 applied | `c7de7761` |
| GAP-03 | resolved and applied | `get_local_events` is `_MON[0][6]`, in the binding check; X5 and `_v5_state()` read it there; new cases V69b, X156f | C1 and C3 applied | `c7de7761` |
| GAP-04 | resolved and applied | `getattr(sys, '_is_gil_enabled', None)` | ref matched; unchanged | `c7de7761` |
| GAP-05 | resolved and applied | `cut_current` is `_HANDLE_DICT[0] is None or _cut_ok()`; the other pre-capture fields stated | ref matched; unchanged | `c7de7761` |
| GAP-06 | resolved and applied | `_GUARD` bound through `globals().get`, set right after `class _Txn` | ref matched; unchanged | `c7de7761` |
| GAP-07 | resolved and applied | the stamp is named by its type only | ref matched; unchanged | `c7de7761` |
| GAP-08 | resolved and applied | the SM2 region names `_finite`; no `_count_dicts`; the facade has no `__init__`; the v4-era set named | ref matched; `_finite`'s docstring updated | `c7de7761` |
| GAP-09 | resolved and applied | the order of `coverage_trace()` is M0 steps 1-10; nothing is bound before every check passes | C2 applied (`_MON` bound after `import asyncio` and the `_get_running_loop` check) | `c7de7761` |
| GAP-10 | resolved and applied | one refusal text for every refused interpreter; only the prefix is fixed | ref matched; unchanged | `c7de7761` |
| GAP-11 | resolved and applied | the NESTED walk skips a foreign-loop anchor (over-blocking #23) | ref matched; unchanged | `c7de7761` |
| GAP-12 | resolved and applied | the one-sentence rule now says a foreign-loop anchor ends the walk (M6) | ref matched; unchanged | `c7de7761` |
| GAP-13 | resolved and applied | `qualname` is F_T's module by Provenance (d)'s rule | ref matched; unchanged | `c7de7761` |
| GAP-14 | resolved and applied | `core.pid` read once, at construction | ref matched; unchanged | `c7de7761` |
| GAP-15 | resolved and applied | M11 "Spec-fixed texts" gives each text byte-exact | ref matched; X93d's smoke case now checks the exact text | `c7de7761` |
| GAP-16 | resolved and applied | a non-str section is named `of type <T>` | ref matched; unchanged | `c7de7761` |
| GAP-17 | resolved and applied | "smoke run" iff smoke and not present; else `str(e)`, suffix iff smoke | ref matched; unchanged | `c7de7761` |
| GAP-18 | resolved and applied | `check_metrics` walks with `issubclass(type(x), dict)` and `dict.get`; `score()` keeps `_resolve` | ref matched; unchanged | `c7de7761` |
| GAP-19 | resolved and applied | `_exit_txn` returns `(held, (swapped, lost))`; the order of problems is normative; new case X59e | applied: the return shape, `held` snapshotted after X5 step 1, and the `_locked`-error-or-`swapped` order | `c7de7761` |
| GAP-20 | resolved and applied | `visible` counts identity occurrences in `gc.get_referents(r)` | ref matched; unchanged | `c7de7761` |
| GAP-21 | resolved and applied | the interval starts at the first live-owner observation | ref matched; unchanged | `c7de7761` |
| GAP-22 | resolved and applied | notes are fin notes, `o.lazy`, `core.lost_note`, in that order | ref matched; unchanged | `c7de7761` |
| GAP-23 | resolved and applied | each import and reload registers one more idempotent handler | ref matched; unchanged | `c7de7761` |
| GAP-24 | resolved and applied | the handler returns at once iff `_MON[0] is None` | ref matched; unchanged | `c7de7761` |
| GAP-25 | resolved and applied | `<module>` is the defining class's own-dict `__module__` if an exact str, else `?` | ref matched; unchanged | `c7de7761` |
| GAP-26 | resolved and applied | the exam's entry points are `score()` and `check_metrics()`; `_check_coverage` is not one | ref unaffected; `smoke_cases.py` now judges scoring cases through `score()` | `c7de7761` |
| GAP-27 | resolved and applied | Appendix A's classified lists are spec data; `rules_v5f.json` is reconciled by the author | applied in `rules_v5f.json`; the new gaps are under "Revision 9 follow-ups" | `3002c140` |

Three resolutions differ from the reading taken, and `ref_v5f.py` changed for each. GAP-02: the reading re-bound `_get_running_loop` without a check; revision 9 adds the builtin check (C2, X156g). GAP-03: the reading used a call-time `sys.monitoring.get_local_events`; revision 9 rejects that (V69b) and binds `_MON[0][6]` (C1, C3). GAP-09: the reading bound `_MON` before `import asyncio`; revision 9 binds it after every check (C2). GAP-19 keeps the reading's order and names the return shape, which the ref now uses literally. Revision 9 adopts every other reading.

## Summary (as raised, before revision 9)

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
*Status: resolved in revision 9 and applied (`c7de7761`).*
- *What is missing.* X5's MONITOR_LOST test says "a held mint's local events on `tool` differ from `_LOCAL`". `_v5_state()["mints"][i]["local_events"]` also reports them. Both need `sys.monitoring.get_local_events`, which is not among `_MON`'s six bound functions (`get_tool, get_events, set_events, set_local_events, register_callback, use_tool_id`).
- *The contradiction.* M0 and V69 claim that "a wrapper installed on `sys.monitoring` after the first binding is neither checked nor called". Any call-time read of `sys.monitoring.get_local_events` breaks that claim. G_HYG freezes each step's `_MON[0]` indices 0 to 5, and G_ATOM's binding check covers exactly six names.
- *Reading taken.* `_exit_txn` and `_v5_state` call `sys.monitoring.get_local_events` at call time. This call is outside every one-call step and makes no write. The M0/V69 claim is therefore false for this one read-only function in `ref_v5f.py`.
- *Fix needed.* Either add `get_local_events` to `_MON` as index 6, with the binding check and the G_HYG index sets updated, or state the exemption and narrow V69's claim.

**GAP-07. Resolution step 4 (the cache-wrapper NOT_A_FUNCTION message) vs X24c.**
*Status: resolved in revision 9 and applied (`c7de7761`).*
- *The contradiction.* The step-4 template reads "the wrapper calls `<callee module:qualname>`; its `__wrapped__` names `<stamped>`; declare the function the wrapper calls". X24c requires "the message names `fast`, never `power_ref`". But `<stamped>` *is* `power_ref` in X24c.
- *Reading taken.* `<stamped>` is rendered by type only: "its `__wrapped__` names a different object (a function)". The message then names the callee and never the stamp. This satisfies X24c and keeps the callee name, which is the only part SM2's normalizer fixes.
- *Fix needed.* Say how `<stamped>` is rendered, or restate X24c's assertion.

**GAP-15. M11 NO_TRACE wordings, and the placeholders in spec-fixed texts (SM2 normalizer).**
*Status: resolved in revision 9 and applied (`c7de7761`).*
SM2 compares "exactly these message substrings" and names the three NO_TRACE wordings, the two NESTED_SECTION texts, the LAZY_RESULT text, the TRACE_ACTIVE texts, and the `dispatched {…}, unattributed {…}` labels. The text does not fix how their placeholders render:
- *NO_TRACE.* "'coverage_trace' is a `` `<type>` ``, not an exact dict" in M11, and "is a `` `OrderedDict` ``" in X93d. Are the backticks literal, or markdown? Is `<type>` the `__name__` or the `__qualname__`?
- *NESTED_SECTION.* How are S, S1 and S2 rendered in "a call there would be on the stack of two openings of section S" and "one call would count for both sections S1 and S2"? Bare, or `repr()` with quotes? In which order do S1 and S2 appear?
- *LAZY_RESULT.* `<type>` in "fn returned a `<type>`".
- *NO_TRACE, first wording.* "the result is a `<type>`, not a dict".

*Readings taken.* No literal backticks. Types are rendered with `type.__qualname__`, read through the C descriptor. Sections are rendered with `repr()` (for example `'G'`). The NESTED order is S1 = the opening already on the stack and S2 = the new section.

*Fix needed.* Write each spec-fixed text as a byte-exact template, because SM2 masks nothing else.

**GAP-02. M1/M6/M7: the binding of `_get_running_loop`.**
*Status: resolved in revision 9 and applied (`c7de7761`).*
- *What is missing.* `_open` (step 5) and `_outcome` call `_get_running_loop()`, which is `asyncio.events._get_running_loop`. M1 has no such name, and asyncio may not be imported at module import (M0). G_HYG requires that "exactly the names M1's reload paragraph lists are bound through `globals().get`". X146b speaks of "its CALL of `asyncio.events._get_running_loop`".
- *Reading taken.* `_get_running_loop` is a module global that every `coverage_trace()` re-binds from `asyncio.events` after its `import asyncio`. At module level it is `globals().get("_get_running_loop")`, so a reload keeps it. This adds one name to the reload list, and the name is not binding-checked.
- *Fix needed.* Name it in M1, choose its reload behaviour, and decide whether M0 checks that it is the C builtin.

**GAP-08. M10 and G_HYG: the frozen function and class set.**
*Status: resolved in revision 9 and applied (`c7de7761`).*
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
*Status: resolved in revision 9 and applied (`c7de7761`).*
- *What is missing.* `_cut_ok()` reads `_HANDLE_DICT[0].get('_run')`, and `_HANDLE_DICT[0]` is None until the first `coverage_trace()`. `_v5_state()` is specified to return `_cut_ok()`, so a snapshot taken before any tracer exists would raise. That covers G_FI's `S0` in a fresh process, and the leftover snapshot of a subprocess case.
- *Reading taken.* `cut_current` is True while nothing has been captured, meaning no captured binding has moved.
- *Fix needed.* Define the pre-capture value, because the leftover check and C5 compare this field.

**GAP-19. M5 X5 to X7: `held, more` and the order of problems.**
*Status: resolved in revision 9 and applied (`c7de7761`).*
- *What is missing.* `held, more = _locked(_exit_txn, core)` never defines `more`. The order in which CLONE_CALLED (X4), CODE_SWAPPED (X5 step 3), CLONE_ALIVE and CUT_MOVED (X6), and a REENTRANT or MACHINERY_BUSY from `_locked` enter `core.problems` is implied but not stated. It is observable, because score refuses with the *first* problem's code.
- *Reading taken.* `more = (CODE_SWAPPED texts, lost flag)`. The problem order is X4, then the `_locked` error, then X5 step 3, then X6 (CLONE_ALIVE per held mint, then CUT_MOVED).

## Non-blocking gaps (readings recorded)

- **GAP-01 (M1).** The code uses PY_START, PY_RESUME, PY_RETURN, PY_YIELD and PY_UNWIND, but `import styxx.protocol` may not touch `sys.monitoring` (M0), and 3.10 and 3.11 lack it. *Reading:* literal ints 1, 2, 4, 8 and 4096, verified on 3.12.3 and 3.13.12. They are not checked at binding. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-04 (M0).** The gate reads `getattr(sys, '_is_gil_enabled', lambda: True)()`, and the lambda is a nested code object, which G_HYG forbids in `coverage_trace` and `_enter`. *Reading:* `getattr(..., None)`, with None read as "GIL enabled". *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-06 (M1).** `_GUARD = {"hint": _Txn(None, 0, None)}` sits in the block that "precedes every function", but `_Txn` is a class defined later. *Reading:* `_GUARD = globals().get("_GUARD", None)` in the block, and `{"hint": _Txn(None, 0, None)}` assigned right after `_Txn` is defined when it is None. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-09 (M0).** The order of checks in `coverage_trace()` is not given: version, the Experiment type check, NOTHING_DECLARED, the binding check, `import asyncio`, the dict capture, E2. *Reading:* that order. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-10 (M0).** The refusal text is given only for other 3.12.x and 3.13.x patch levels. *Reading:* one text for every refused interpreter. Only the `[V5:UNSUPPORTED_VERSION]` prefix is fixed. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-11 (At open step 5 vs M6).** M6 says an anchor whose loop is not the running loop *ends the attribution walk*. Step 5's NESTED walk says only that a same-core opening counts as nesting if its loop is the running loop, not whether a foreign-loop anchor ends the walk. *Reading:* the NESTED walk continues to the cut or the root. Both readings are fail-closed. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-12 (Attribution rule vs M6).** The one-sentence rule does not say that a foreign-loop anchor ends the walk, but M6's walk does (outcome `d`). They differ when an opening with the running loop lies *below* a foreign-loop anchor on one stack. *Reading:* M6. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-13 (Minting, M10).** `_Mint.qualname` and `_v5_state()["mints"][i]["target"]` are "F_T's `module:qualname`", but it is not said which module name. *Reading:* F_T's own `__globals__['__name__']` when it is an exact str, else `co_filename` (as Provenance (d)). This matters for a cache wrapper whose callee lives elsewhere. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-14 (M1).** It is not said when `_Core.pid` is read. *Reading:* at construction, in `coverage_trace()`. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-16 (At open steps 2 and 3).** Formatting a non-str section into a refusal would run user `__repr__`. *Reading:* a non-str section is never formatted; its type's `__qualname__` is named instead. X78f's counters stay 0. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-17 (M11 check_metrics).** "'smoke run' only when the trace is absent" does not settle what happens when the trace is absent and the result is not a smoke run. *Reading:* "smoke run" iff smoke and the NO_TRACE test fails. Otherwise `str(e)`, with the smoke suffix when smoke. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-18 (M11 check_metrics).** M11 forbids user `get`, `__missing__` and `__bool__`, but does not say to replace v4's `_resolve` (`isinstance`, `in`, `[]`). *Reading:* `check_metrics` walks paths with `issubclass(type(x), dict)` and `dict.get`. `score()` keeps `_resolve` and v5e's `isinstance(_v, numbers.Real)` guard, with only the `float()` OverflowError change M11 names. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-20 (CLONE_ALIVE (b)).** "`visible` counts the references to M_T held by members of `refs`…" does not say how a referrer's references are counted. *Reading:* identity occurrences of M_T in `gc.get_referents(r)`, excluding the mint, F_T, the scan's own frame and the `refs` list. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-21 (M2).** "After `_BUSY_SECONDS`" does not say from when. *Reading:* from the first observation of a live owner in this `_acquire`. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-22 (M8).** The order of an opening's notes is not given: its fin notes, `o.lazy` and `core.lost_note`. *Reading:* that order. The exam should compare notes as a set of codes. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-23 (M9).** `register_at_fork` "at import" also runs on every `importlib.reload`, which registers a second, idempotent handler. *Reading:* accepted; noted. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-24 (M9).** "a no-op until a tracer has been constructed" does not say how that is detected. *Reading:* `_MON[0] is None`. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-25 (Resolution, INHERITED).** It is not said where the module of "declare the defining class `<module>:<qualname>`" comes from. *Reading:* the defining class's own dict `'__module__'` if it is an exact str, else `?`. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-26 (exam harness).** The text does not say whether a scoring violation case is judged through `score()` or through `Experiment._check_coverage`/`check_metrics`. `score()` resolves each gate's metric first, and a metric-less result raises an uncoded GateSpecError before NO_TRACE. *For the runner:* judge coverage refusals through the entry point each row implies. X122 implies `score()`; X93d and X103b imply the coverage check or `check_metrics`. *Status: resolved in revision 9 and applied (`c7de7761`).*
- **GAP-27 (rules_v5f.json).** Appendix A's claim classification lives in scratch files outside what the exam author may read (`rev7/audit_*`, `verify8/*classify*`). *Reading:* the atoms' classes are this author's heuristic by section. Witnesses are the ids each atom names, or those its enclosing paragraph or row names. 531 property and disclosure atoms name no witness in their own paragraph. Many are headings, definitions, or claims whose witness Appendix A gives elsewhere. The spec owner should reconcile these with Appendix A's tables before the freeze. *Status: resolved in revision 9 and applied (`3002c140`).*

## Checked and found consistent (no gap)

- The one-call step pipelines of M7, run exactly as written: `_unwind_on`, `_unwind_off`, `_take`, `_set_local` and `_register` in its tee form. None of them has a backward jump on 3.12.3 or 3.13.12, and neither does `_run`, `_commit`, `_detach` or `_named`.
- No region code object has a nested code object (G_HYG MF4). The #130279 rule holds: the only `try … finally` is in `_run` and `_run_async`, and neither try body has a loop.
- The E4 counting rule, M3's reclaim and the rebinding rule are implementable as written. X36 (MONITOR_BUSY) and X142 (a second loaded copy takes id 3, and A has no MONITOR_LOST) behave as stated on both interpreters.

## Revision 9 follow-ups (raised after the revision-9 text; for the spec owner)

*Status: resolved in revision 10.* "Revision 10: verifier findings on revision 9" answers GAP-28 to GAP-31 and GAP-W001 to GAP-W344 through the Revision 10 table and Appendix A's revision-10 data. The reconciliation re-run on that data is in "Revision 10 follow-ups" below.

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

## Revision 10 follow-ups (raised on the revision-10 text; for the spec owner)

`rules_v5f.json` was re-extracted from the revision-10 text (`tools/extract_rules.py`) and reconciled with Appendix A's revision-10 data (`tools/reconcile10.py`). Rule 1 was applied in the stated order of precedence: `rev9_new_sentences_classified_rev10.json`, `wide_old_rows_resolved.json`, the wide list, then the revision-7 list. For the revision-7 list, the witness is taken from Appendix A's own revision-7 tables by audit id, since the list has classes only. Then `pointer_witness_map.json` and `atom_witness_map.json` were applied by atom id. A witness counts only if it names a checkable object, under Appendix A's revision-10 definition. Appendix A's convention that "model" means the model-check file with the property named is applied, so "model U1" counts. "Reading" dispositions (R9-7, F37, F38, and revision 7's untestable D claim) are counted apart. Atoms whose text is unchanged keep their revision-9 ids, which the maps are keyed by. New atoms get `-R10-` ids.

**Counts.** 2,505 atoms (2,468 keep their revision-9 id, 37 are new): P 853, D 166, C 56, G 653, N 272, S 193, H 312.
- P/D/C atoms: 1,075. 1,060 have a checkable witness, 12 are resolved by reading, and **3** have none (GAP-33 to GAP-35).
- Map ids that no longer exist: R-MECHANISM_AND_LIFECYCLE_M10-006, R-REASON_CODES-006. Revision 10 edited both sentences, and the new atoms name their own witnesses (V72; X156g–X156i). No map text mismatched its atom.
- In no list and no map: **1,119** atoms (S 86, C 13, P 258, H 149, D 94, G 348, N 171). 1,017 of them contain none of the lists' keywords. 102 contain one; 33 of all unlisted atoms are new or edited text in revision 10. Every unlisted P, D or C atom has a witness by rule 2 (GAP-32).
- Disputed `definition` rows: 10 (GAP-36).

| gap | section | blocks the freeze? |
|---|---|---|
| GAP-32 | The revised rule 3 ("in no list and no map") vs rule 2: 1,119 atoms are unlisted by construction | **yes**, as the status line reads ("with no atom left unlisted"), until the owner rules |
| GAP-33 | R-MECHANISM_AND_LIFECYCLE_M3-030: its witness names a model mutant and a pointer | **yes** (rule 3) |
| GAP-34 | R-OVER_BLOCKING_DISCLOSED-075: a D claim pinned only by a probe | **yes** (rule 3) |
| GAP-35 | R-OVER_BLOCKING_DISCLOSED-090: the verifier list's witness is stale ("none pinned"); X84 now pins it | no (data fix; the atom's paragraph names X84) |
| GAP-36 | 10 `definition` rows the exam author disputes as D claims with no checkable witness | **yes** if the owner agrees they are D; no if the owner keeps them S |
| GAP-37 | The runner cannot write the v5e cases v5f keeps, or the delta rows V26, V28, X82 and V33, from the v5f text | **yes** (the frozen runner must run every case in the case tables) |

**GAP-32. Rule 3 as revision 10 words it vs rule 2.**
- *The contradiction.* Revision 10's required change says: "An atom that is P, D or C and still has no witness, or that appears in no list and no map, is a new gap". The status line says the freeze waits for `rules_v5f.json` "with no atom left unlisted". But the lists hold only sentences with a list keyword (*must, never, always, cannot, nothing, no, none, only, every*), and the maps hold only the 344 GAP-W atoms and the 40 pointer atoms. Rule 2 ("any other atom is classed by the table") still exists for every other atom. 1,017 unlisted atoms have no keyword, so no list could hold them. The other 102 contain a keyword: text new or edited in revision 10, which no list has seen yet, or table rows and list items split differently from the wide extraction.
- *Reading taken.* Rule 2 classes every unlisted atom, and it takes a witness from the atom, from a revision-9 or revision-10 table row it cites, or from its enclosing paragraph. No unlisted P, D or C atom is left without a witness. Every unlisted atom is marked `listed: false`, so the owner can see each one.
- *Fix needed.* Either say that rule 2 classes unlisted atoms and that only rule 3's witness test applies to them, or extend the lists or maps to every atom. If they are extended, the wide extraction must also be re-run on the revision-10 text, which Appendix A already requires of the frozen text.

**GAP-33. R-MECHANISM_AND_LIFECYCLE_M3-030** (line 539, class P, rule1:rev7_list).
- *Atom.* A dead exiting token means X1 ran and X8 never will, so `record()` refuses TRACE_INCOMPLETE for good.
- *Witness given.* model (`prune_credit_stop` restored changes nothing); M8's refusals
- *What is missing.* Appendix A's revision-7 table gives "model (`prune_credit_stop` restored changes nothing); M8's refusals": a model mutant name and a pointer, with no case and no named property.
- *Fix needed.* Name the case that shows `record()` refusing TRACE_INCOMPLETE for a dead exiting token (an interrupted exit such as X92b), or the model property.

**GAP-34. R-OVER_BLOCKING_DISCLOSED-075** (line 1346, class D, rule1:wide_list).
- *Atom.* While it is enabled, every `coverage_trace()` in the process refuses.
- *Witness given.* critic3/c10_aiodebug_overblock.py (a disclosure pinned by its probe; no exam case)
- *What is missing.* The asyncio-debug over-block is pinned only by `critic3/c10_aiodebug_overblock.py`. Under revision 10's definition a probe witnesses only C claims, and this is a D claim with no exam case.
- *Fix needed.* Add a case: with asyncio debug mode on, `coverage_trace()` refuses. Or file it as reading.

**GAP-35. R-OVER_BLOCKING_DISCLOSED-090** (line 1353, class D, rule1:rev9_new_sentences_classified_rev10).
- *Atom.* An open with a same-core opening of the running loop below such an anchor refuses NESTED_SECTION, although a hit under it would credit only the new opening.
- *Witness given.* none pinned (as #132; verify/p_ref_findings.py FB)
- *What is missing.* The verifier list row still says "none pinned (as #132; verify/p_ref_findings.py FB)". Revision 10 added X84, which pins over-blocking #23, in the next sentence of the same item.
- *Fix needed.* Give the row `witness_rev10: X84`.

**GAP-36. `definition` rows disputed (10).** Revision 10's weakest point 2 invites this. Each row below is a disclosure (a door, a leak or a user-code site the design admits), so class D by Appendix A's table rather than S. Its map witnesses name no checkable object: a limit's name (L-CLONE, L-MONITOR, L-ZOMBIE), "over-blocking #19", a probe (which witnesses only C claims), or nothing. `rules_v5f.json` keeps the map's class and records the dispute in `disputed_by_exam_author`. If the owner agrees, each needs a pinned residual or case, or a reading disposition.

| atom | map gap | map witnesses | the dispute | atom text |
|---|---|---|---|---|
| R-TARGET_IDENTITY-111 | GAP-W066 | over-blocking #19 (definition: disclosure) | D: freeze0 can predate the trace (a disclosure); "over-blocking #19" is a list item, not a pinned case | `m.freeze0` is read when the mint is made, so for a mint this tracer joined it can predate this trace (over-blocking #1… |
| R-TARGET_IDENTITY-130 | GAP-W072 | L-CLONE, R-rows of the residual table (documented residuals… | D: a disclosed door of L-CLONE; "R-rows of the residual table" names no residual id | builds a same-globals function and drops it before exit; |
| R-TARGET_IDENTITY-131 | GAP-W073 | L-CLONE | D: a disclosed door of L-CLONE (exec of M_T); "L-CLONE" names no residual id | runs `exec(M_T, T.__globals__)`; |
| R-TARGET_IDENTITY-132 | GAP-W074 | L-CLONE | D: a disclosed door of L-CLONE (a swap-and-restore); "L-CLONE" names no residual id | does `U.__code__ = M_T` and swaps it back before exit; |
| R-TARGET_IDENTITY-134 | GAP-W076 | L-CLONE, rev1/p4_freeze.py | D: when the freeze count does not rise; a probe witnesses only C claims | That happens if frozen objects died, or if `gc.unfreeze()` then `gc.freeze()` ran with fewer tracked objects. |
| R-MECHANISM_AND_LIFECYCLE_M1-061 | GAP-W130 | L-ZOMBIE, L-MONITOR (definition: disclosure) | D: a dead retained frame keeps its callers alive; limit names only | A retained frame that has died still keeps its callers' frames alive, and so possibly the facade; see L-ZOMBIE and L-MO… |
| R-MECHANISM_AND_LIFECYCLE_M3-020 | GAP-W141 | L-MONITOR (definition: disclosed leak) | D: a foreign tool's events and callbacks stay on the id for the process; "L-MONITOR" only | Any other global or local events and callbacks that tool left stay on the id, now under styxx's name, until styxx's pro… |
| R-MECHANISM_AND_LIFECYCLE_M11-028 | GAP-W224 | rev1/p2_dict_collide.py (definition: disclosure) | D: check_metrics can run two kinds of user method; a probe witnesses only C claims | For in-process results carrying user objects, it can run two kinds of user method: a `__float__` override on an int or … |
| R-MECHANISM_AND_LIFECYCLE_M11-029 | GAP-W225 | (definition: disclosure) | D (or C): "a JSON-loaded result has exact-str keys"; no witness at all | The second is contrived: a JSON-loaded result has exact-str keys. |
| R-EXCEPTION_SAFETY_MODEL-119 | GAP-W279 | L-MONITOR | D: the kept frame keeps its callers alive until then; "L-MONITOR" only | It keeps its frame, and that frame's callers, alive until then (L-MONITOR). |

**GAP-37. The v5e cases v5f keeps are defined only in the v5e design.** (Raised while writing `run_protocol_v5f_exam.py`.)
- *What is missing.* "Every other v5e case keeps its id and its expected outcome" (Exam cases required), and the delta table changes V26, V28, X82 and V33 by id. But their shapes and outcomes are written only in `DESIGN_protocol_v5e_mint_anchor_2026_09_24.md`. The exam author's brief for this revision allows the v5f text and its Appendix A data, not the v5e design, and the v5e runner may be read only for structure. So the runner cannot write these cases from the text it may read. The runner's 14 v5e-kept cases (V01, X40, X55, X59, V07, X33, X73, V18, X76, X60, V14, X109, X32 and X90/X91) are carried over from `smoke_cases.py`. They were written in the first round, when the brief included the v5e design.
- *Reading taken.* The receipt lists the v5e tables, and the delta rows V26, V28 and X82/V33, as not yet covered (`tables_not_yet_covered`, `delta_table_rows`).
- *Fix needed.* Either add the v5e design's case tables to the exam author's reading as spec data, or restate the kept v5e cases, with their v5f placements, in the v5f text.

## Revision 11 follow-ups (raised while writing the runner's remaining tables; for the spec owner)

**All closed by revision 12** (commits fb13294b, e293d3de, f8f252d1, 979fbe97; the design's "Revision 12" section). The exam artifacts apply its required changes; nothing below is left open.

Readings the text does not fix. None is chosen here: each is recorded, and the runner either keeps the rule literal or leaves the row unrun, as the entry says.

| gap | section | blocks the freeze? |
|---|---|---|
| GAP-38 | Tripwires, CLONE_ALIVE (b): on 3.12.3 the gc freeze count rises with no `gc.freeze()`, which gives a false CLONE_ALIVE and different outcomes on the two verified interpreters | **yes** (a false refusal whose message claims `gc.freeze()` ran; G_XVER) |
| GAP-39 | Harness rules, case hygiene: "gc.get_freeze_count() no higher than before the case" vs the same 3.12.3 behaviour | **yes** (the leftover check fails a correct case that follows an unfreezing case) |
| GAP-40 | X154: "none of styxx's five callbacks is registered on the id" vs CPython keeping a freed id's callbacks (p3) | **yes** (the row cannot pass as written; not run) |
| GAP-41 | X154d variant (b): what the hook does at the 2nd register_callback event | no (variant (b) not run; (a) runs) |
| GAP-42 | X137h: P and S open no section, so the score order gives SECTION_ABSENT, not the row's NOT_EXERCISED | **yes** (the row's outcome contradicts the score order) |
| GAP-43 | X154c: "frees styxx's id (from `_v5_state()["tool"]`)" while `tool` is still None at the first acquisition | no (the row's outcome names id 4) |
| GAP-44 | X158d: `ref_v5f.py` gives P CODE_SWAPPED, not the row's PASS `{f:1}` | **yes** (the row's outcome contradicts the mechanism text under greenlets) |
| GAP-45 | G_SIG poison (revision 3, N8) and G_FI C5: "any field but `cut` and `tool`" has no R9-6 exemption for `tool_ours` | **yes** (a correct implementation fails H10/G_SIG when a cell makes the process's first acquisition) |
| GAP-46 | kept v5e rows X72 and X73: their v5e sub-assertion requires v5e's NOT_EXERCISED sentence, which v5f's fixed sentence replaced | **yes** (kept rows that `ref_v5f.py` scores differently; revision 11 calls that a spec defect) |
| GAP-47 | the override for `R-MECHANISM_AND_LIFECYCLE_M3-020` names an atom whose text revision 11 corrected (F39) | no (its two successor atoms are witnessed by X137j under rule 2) |
| GAP-48 | rule 3 (revision 11): 25 D atoms name only a gate, an invariant or a model property, and no case or pinned residual | **yes** (rule 3: "one that does not is a gap, and the freeze waits for it") |
| GAP-49 | H9: X140 cannot detect the SM1 mutant "X3 inside `with _M:`" as the text shapes it; and X140's scenario does not say whether the cancelled `run_async` opening completes | **yes** (an SM1 row whose named witness does not kill it) |

**GAP-38. CLONE_ALIVE (b) reads a freeze-count rise that no `gc.freeze()` caused.**
- *What the text says.* Tripwires: (b) fires when `gc.get_freeze_count() > m.freeze0` and references remain unexplained, with the message "gc.freeze() ran while the minted code existed". The paragraph after it says the count falls with no freeze call, and that `gc.unfreeze()` sets it to 0. It adds that "only a `gc.freeze()` made after the mint can freeze" a clone, "and that call raises the count".
- *What CPython does* (`v5f_exam/tools/probe_freeze_rise.py`). On 3.12.3, after `gc.unfreeze()` (count 0), the next full `gc.collect()` sets the count back to 375, the boot value, with no `gc.freeze()` call. `collect(0)` and `collect(1)` do not. On 3.13.12 the count stays 0.
- *Consequence on `ref_v5f.py`.* A harness that unfroze earlier in the process, then keeps `M_T` in a tuple (`keep = (f.__code__,)`: no function and no clone), and then runs a full collection inside the trace:
  - on 3.12.3, gets **CLONE_ALIVE** with the message "gc.freeze() ran while the minted code existed", where no `gc.freeze()` ran;
  - on 3.13.12, gets PASS `{f:1}`.

  The same program therefore has two outcomes on the two verified interpreters.
- *Fix needed.* Either state and disclose this over-block (and restrict the cases that could meet it), or change the rule's premise.
- *Case hygiene cited, and the mechanism untouched.* The runner's X57b and X58b call `gc.collect()` after their `gc.unfreeze()` (see GAP-39).

**GAP-39. The leftover check's freeze-count clause vs 3.12.3.**
- *What the text says.* "A case that calls `gc.freeze()` calls `gc.unfreeze()` before it returns. The leftover check then requires `gc.get_freeze_count()` to be no higher than before the case."
- *What happens.* On 3.12.3, after such a case the count is 0. The next case that runs a full `gc.collect()` ends with 375, above its "before" 0, and the leftover check fails it. The runner met this with X58b followed by X133, which fails X133 though X133 freezes nothing.
- *What the runner does meanwhile.* The rule stays as written. The unfreezing cases (X57b, X58b) run `gc.collect()` after their `gc.unfreeze()`, so each leaves the count where 3.12.3 settles it. That is a choice of case body, not a reading of the rule, and it hides the problem rather than solving it.
- *Fix needed.* State how the clause treats a rise that no case caused (for example, compare after a full collection on both sides, or exempt the rise to the interpreter's boot count), or drop the clause.

**GAP-40. X154's expected outcome vs CPython keeping a freed id's callbacks.**
- *What the row says.* The interference frees styxx's id; another tool takes it, registers a RAISE callback, and sets its global events to RAISE and its local events on the target's minted code to LINE. "Every trial: afterwards … none of styxx's five callbacks is registered on the id."
- *The conflict.* `sys.monitoring.free_tool_id` keeps the id's callbacks on 3.12.3 and 3.13.12 (the text's own p3; checked again here). After `use_tool_id` by the other tool, styxx's PY_START callback is still registered on both versions. So the stated outcome is false for every trial unless the interference also clears the five callbacks, and the row does not say it does.
- *Readings left open.* Either the interference registers None for the five events after taking the id, or the check means "no callback styxx registered after the take". The two give different witnesses of the name gate.
- *In the runner.* X154 is not run. Its four sweeps would each need one fresh subprocess per trial (harness rule, revision 7, M4).

**GAP-41. X154d variant (b).**
- *What the row says.* "Variant (b): at the 1st event the hook's thread frees the id and another tool takes it, so E4 rebinds to id 3."
- *What is missing.* Variant (a)'s hook acts at the 1st *and* 2nd events. The row does not say whether (b)'s hook still frees "styxx's id" at the 2nd event. If it does, that id is now the other tool's id 4, and freeing it changes the outcome.
- *In the runner.* Variant (a) runs and passes; (b) is not run.

**GAP-42. X137h: NOT_EXERCISED for traces that open no section.**
- *What the row says.* "P refuses NOT_EXERCISED for g with MONITOR_LOST … Q refuses NOT_EXERCISED for h with MONITOR_LOST. S refuses NOT_EXERCISED for g with no MONITOR_LOST." It also says "The other three traces open no section."
- *The contradiction.* M11's score order puts SECTION_ABSENT (step 8) before NOT_EXERCISED (step 9). A trace whose gate's section was never opened refuses SECTION_ABSENT. `ref_v5f.py` gives P and S SECTION_ABSENT, on both versions. For Q, whose declared section is B, the same holds. MONITOR_LOST, which lives in opening notes and in NOT_EXERCISED's message, cannot then appear for P or Q.
- *In the runner.* X137h asserts the row as written. It fails, and the receipt reports it under this gap. The part about R (NOT_EXERCISED for t with MONITOR_LOST) and the tool id holds.
- *Fix needed.* Give P, Q and S the code the score order implies, or give them a section each.

**GAP-43. X154c: the id to free during the first acquisition.**
- *The wording.* X154c uses "X154b's hook with k = 5", and X154b's hook "frees styxx's id (from `_v5_state()["tool"]`)". During the first enter's registration, `_v5_state()["tool"]` is still None, so that read names no id.
- *What fixes it.* X154c's own outcome ("the other tool owns id 4") names the id. The runner frees id 4 when `tool` is None, and X154c passes on both versions.
- *Fix needed.* Say "the id being registered" in X154b's hook.

**GAP-44. X158d: CODE_SWAPPED on P under greenlets.**
- *What the row says.* P PASS `{f:1}` with MONITOR_LOST; Q NOT_EXERCISED with MONITOR_LOST; Q's exit ran inside P's registration.
- *What `ref_v5f.py` gives, on 3.12.3 and 3.13.12 with greenlet 3.5.6.* P refuses **CODE_SWAPPED** ("fx_v5f:f.__code__ was replaced during the trace"); Q's outcome and both MONITOR_LOST notes match; the finalizer ran.
- *Why, by the text.*
  - A token is live iff a frame on `sys._current_frames()[tid]`'s `f_back` chain matches it (M1, `_Txn`). While g2 runs, P's exit frames sit in the suspended main greenlet and are not on that chain.
  - So Q's exit, in g2, finds P's exit token dead and steals the mutex. Its reconciliation prunes P's holdership (an exiting core with a dead token), Q's X5 step 3 empties the mint's holders, and `_retire` restores `f.__code__`.
  - When P's exit resumes, its step 3 finds `m.fn.__code__ is not m.code`, because `held` was snapshotted at step 1, before the finalizer ran, and records CODE_SWAPPED.

  The row's expectation matched the revision-8 prototype, which the exam author may not read. The reference follows the text.
- *Fix needed.* Either change X158d's expected outcome, or state how the liveness test or the exit treats a core pruned during its own exit transaction.

**GAP-45. The poison test (G_SIG, and C5's test in G_FI) vs `tool_ours` at the first acquisition.**
- *What the text says.* G_SIG, "Poison (revision 3, N8)": a cell is poisoned "if `_v5_state()` after it differs from the snapshot taken before the cell in any field but `cut` and `tool` (C5's test)". R9-6 (revision 10) added the `tool_ours` exemption to the *leftover check* only, for the same reason: `tool_ours` goes False to True at the process's first acquisition.
- *What happens.* H10 run first in a process (`--only H10`, or any process where no tracer ran before the cell): cell (a)'s "before" snapshot has `tool` None and `tool_ours` False, and after the cell `tool_ours` is True. The poison test flags cell (a) as poisoned, on 3.12.3 and 3.13.12, with 0 lost handlers and a clean probe cycle. In the full runner, where earlier cases already acquired the id, the test passes. The same wording is used by G_FI's C5, so the frozen `crash_sweep_v5f.py` and `sigflood_v5f.py` meet it wherever their first point or cell makes the first acquisition.
- *Readings left open.* Either the poison test and C5 take R9-6's narrow exemption (`tool_ours` when "before" `tool` is None), or the frozen harnesses must acquire the id before the first snapshot (a warm-up trace), which the text does not state.
- *In the runner.* The test stays as written (`_poisoned`: every field but `cut` and `tool`). When a cell is poisoned *only* by `tool_ours` and its "before" `tool` was None, H10 fails with `KnownGapFailure: GAP-45` after every other check has passed, and the receipt lists it with the known spec gaps. Any other poison is a plain failure.

**GAP-46. Kept rows X72 and X73: the v5e NOT_EXERCISED sentence.**
- *The data.* `rev11/v5e_cases_kept.json` keeps X72 and X73 (status `kept`, v5f outcome NOT_EXERCISED, "every sub-assertion the v5e runner makes for this id, as v5e"). The v5e runner registers both as `msg_case(x7N, NE_WORDING, FIXED_SENTENCE, forbid=("never executed",))`, so the refusal must contain v5e's fixed sentence "work on other threads, pools, executors or asyncio tasks is credited only to a section that work opens itself".
- *The text.* v5f's score step (Scoring, "NOT_EXERCISED") fixes a different sentence: "work on other threads, pools, executors, child processes or asyncio tasks is credited only to a section that work opens itself; …". `ref_v5f.py` uses the v5f sentence.
- *What happens.* On 3.12.3 and 3.13.12 both rows refuse NOT_EXERCISED with the right code, `NE_WORDING`, both counts and the non-returned end; they fail only the v5e sentence substring (`v5e:X72`, `v5e:X73` in the receipts). Revision 11 says a kept row that `ref_v5f.py` scores differently is a spec defect. Not adapted.
- *Fix needed.* Mark the sentence sub-assertion of X72 and X73 as replaced (by v5f's sentence) in the data file, or change the v5f sentence.
- *In the runner.* Both assert the v5e sub-assertions as written and are listed with the known spec gaps.

**GAP-47. An override that names a replaced atom.**
- *What happens.* `atom_witness_overrides_rev11.json` rules on `R-MECHANISM_AND_LIFECYCLE_M3-020` (W141). Revision 11 also corrected that sentence (F39: "M3 is corrected"), so the revision-11 text has no atom with that id's text; the reconciliation gives its two successor sentences new ids (`R-MECHANISM_AND_LIFECYCLE_M3-R11-001`, `-002`).
- *In rules_v5f.json.* The override is reported under `overrides_rev11_not_found` and applied to nothing. Both successors are P under rule 2 and name X137j, which is checkable, so no witness is missing. Carrying the override to the successors would be a reading; it is not done.
- *Fix needed.* Re-key the override to the corrected sentence, or state that it lapses with the text it ruled on.

**GAP-48. Rule 3's sharpened D test leaves 25 D atoms without a witness.**
- *The rule.* Revision 11, rule 3: "A D claim, a disclosure, is witnessed by a case or a pinned residual whose outcome shows the disclosed behaviour, or is filed as reading." A gate, an invariant (U3, I5) or a model property is none of these. The reconciliation (`tools/reconcile11.py`) applies the rule as written: for class D, only a named case id (X, V, R or H) counts.
- *What is left.* 25 D atoms whose own list row, map entry, or enclosing text names only a gate (G_SIG, G_FI, G_ATOM, G3), an invariant (U3, U4, I5) or a model configuration:
  - `R-MECHANISM_AND_LIFECYCLE_M7-033` (rule1:wide_list; named: invariants: U3): "In `_unwind_off` that can leave S set with no anchor after the pop, until the next close that leaves no anchor or the next reconciliation (U…"
  - `R-EXCEPTION_SAFETY_MODEL-157` (rule2_table; named: invariants: I5): "**Audit hooks and slow owners.** An audit hook that blocks inside a transaction holds the mutex, and other threads' transactions raise MACHI…"
  - `R-EXCEPTION_SAFETY_MODEL-160` (rule1:rev9_new_sentences_classified_rev11; named: model lock-taking configuration (any site; W5); I5 bound): "They also run at `_alive`'s `sys._current_frames`, `id()` and `f_code` reads in every reconciliation that tests a holder, which is the first…"
  - `R-EXCEPTION_SAFETY_MODEL-161` (rule2_table; named: invariants: I5; probes: rev5/m5_modelcheck.py): "The waiter's bound breaks it after 10 s (I5; `rev5/m5_modelcheck.py`, `with L: exit(X) // exit(Y)+[lock]`: a true deadlock with the bound re…"
  - `R-EXCEPTION_SAFETY_MODEL-162` (rule2_table; named: invariants: I5): "A hook that raises at `register_callback` inside X5 makes `__exit__` propagate it (M5).…"
  - `R-EXCEPTION_SAFETY_MODEL-181` (rule2_table; named: gates: G_FI): "The v5f machine must pass the same sweep, extended to two threads, `run_async`, generator targets and hopped coroutine sections (G_FI).…"
  - `R-OVER_BLOCKING_DISCLOSED-022` (rule2_table; named: gates: G_ATOM): "This refuses most users' interpreters today; it is the price of not trusting an undocumented CPython property on a patch level where nobody …"
  - `R-OVER_BLOCKING_DISCLOSED-026` (rule1:wide_list; named: G_ATOM build record (id 56)): "(revision 7, N2; a scope note, not a refusal) nothing refuses a different *build* of 3.12.3 or 3.13.12; such a build is accepted but its pre…"
  - `R-OVER_BLOCKING_DISCLOSED-059` (rule1:rev9_new_sentences_classified_rev11; named: model lock-taking configuration; I5 bound (W5)): "The audit-hook sites inside a transaction include `__code__` writes and, as revision 6 corrects (B1), `sys.monitoring.register_callback`, wh…"
  - `R-OVER_BLOCKING_DISCLOSED-060` (rule1:rev9_new_sentences_classified_rev11; named: model lock-taking configuration; I5 bound (W5)): "(Revision 8 self-audit, W5: the reconciliation's holder test, `_alive`, also raises `sys._current_frames`, `builtins.id` and `object.__getat…"
  - `R-STATED_LIMITS-001` (rule2_table; named: gates: G3): "**Carried forward.** Exercised is not tested: one call satisfies a declaration.…"
  - `R-STATED_LIMITS-002` (rule2_table; named: gates: G3): "Transitive calls count.…"
  - `R-STATED_LIMITS-004` (rule2_table; named: gates: G3): "The trace is written by the runner, so forgery is an accepted residual under an honest-but-careless threat model.…"
  - `R-STATED_LIMITS-005` (rule2_table; named: gates: G3): "Hardcoded values (P1's G3) are out of scope.…"
  - `R-STATED_LIMITS-029` (rule2_table; named: invariants: U3, U4): "An asynchronous Exception subclass landing in the declared module's import, or in its PEP 562 `__getattr__`, becomes a chained UNRESOLVED.…"
  - `R-STATED_LIMITS-030` (rule2_table; named: invariants: U3, U4): "An asynchronous exception during that import can also leave importlib's per-module lock inconsistent.…"
  - `R-STATED_LIMITS-031` (rule2_table; named: invariants: U3, U4): "That is CPython's behaviour: D1 observed it on 3.10 and 3.11. It was not measured on 3.12 or 3.13, where the lock's own wait loop is also ex…"
  - `R-STATED_LIMITS-033` (rule2_table; named: invariants: U3, U4): "M7 states the exceptions exactly (U3 and U4).…"
  - `R-STATED_LIMITS-035` (rule2_table; named: invariants: U3, U4): "It lasts until that trace's exit, or until a reconciliation prunes it once the trace is dead.…"
  - `R-STATED_LIMITS-040` (rule2_table; named: gates: G_SIG): "Near the recursion limit, a callback's own frame can raise RecursionError at those same points.…"
  - `R-STATED_LIMITS-043` (rule2_table; named: gates: G_SIG): "G_SIG re-measures this with v5f's full event set.…"
  - `R-STATED_LIMITS-060` (rule2_table; named: gates: G_SIG): "**G_SIG (frozen decision).** L-DELIVERY does not count as a "wrong result" under G_SIG.…"
  - `R-STATED_LIMITS-062` (rule2_table; named: gates: G_SIG; invariants: U3): "Revision 3 (MF2) fixes the cell's shape so the gate does not depend on a fault window.…"
  - `R-STATED_LIMITS-106` (rule1:rev7_list; named: `critic4/a6_pending_left_fault_free.py`; G_FI C5's exclusion): "Revision 4 could raise ValueError out of `run()` or a transaction here. - **Pending entries.** A pending entry whose confirmation never arri…"
  - `R-STATED_LIMITS-109` (rule1:wide_list; named: gates: G_ATOM): "It never sees code inside callbacks or unconfirmed calls, and it is never evidence. - **Scope of testing.** CPython 3.12.3 and 3.13.12, GIL …"
- *Readings left open.* Either rule 3 also admits a gate cell or an invariant for a D claim (as revision 10's definition did), or each of these needs a case, a pinned residual, or a "reading" filing. Some may not be disclosures at all (for example `R-STATED_LIMITS-060`, a frozen G_SIG decision, and `R-STATED_LIMITS-001`/`-002`, carried-forward scope statements); their class comes from the lists and the table, which the exam author does not re-class.

**GAP-49. H9's mutant and X140.**
- *What the text says.* H9: "**Mutant** (an SM1 row): `ref_v5f.py`'s X3 detach loop placed inside `with _M:`, where `_M` is a `threading.Lock` that `_exit_txn` also takes (v5e's shape). X140 must detect it on both versions: the exception raised at the back-edge offset skips the with-exit (p10), and another thread's exit then hangs." X140: "in a scenario with 3 openings (one `run_async`, driven through a thrown-then-handled cancellation)"; "A back-edge in `_exit` gives TRACE_INCOMPLETE".
- *First, the scenario.* X3's loop runs only over openings still open at exit. If the cancelled coroutine completes after handling the cancellation, no opening is open at exit and X3's back-edge is never reached (UNREACHED, counted clean), so no weakening of X3 can be detected. If it stays suspended, X3 runs. The row does not say which. The runner runs both variants, (a) completes and (b) stays suspended through exit, and asserts the row's outcome in each.
- *Second, the mutant.* With the mutant built as the text says (`tools/runner_mutants_v5f.py`, `mut_h9_x3_in_lock`: `with _M:` around the X3 loop, `_exit_txn` run under `with _M:`), variant (b) reaches X3's back-edge (3.12.3: `_exit@348`), and the injector raises KeyboardInterrupt there. But the back-edge lies inside the `with` block's exception-table range on both verified interpreters (3.12.3: `240 to 350 -> 904 [1] lasti`; 3.13.12: the same shape), so the with-exit runs, `_M` is released, and the trial is clean. X140 passes the mutant on 3.12.3 and 3.13.12 in both variants.
- *Readings left open.* The mutant may need a different shape (for example the `with` inside the loop, or a loop in a `try` whose range ends before the back-edge, as in #130279), or the witness may be a different case. The exam author does not choose one.
- *In the runner.* X140 runs both variants; `mut_h9_x3_in_lock` is reported SURVIVED under this gap.


## Revision 12 follow-ups (raised while building the frozen exam artifacts; for the spec owner)

Readings the text does not fix, and inputs outside the exam author's read scope. None is chosen here.

| gap | section | blocks the freeze? |
|---|---|---|
| GAP-50 | G_REF: "the literal census finds 0 coded literals outside a mutable site" — "mutable site" is not defined | **yes** (the census verdict depends on the reading) |
| GAP-51 | positive control #5 (G_REF blind shapes) names `mutation_gate_blindspots.json`, outside the exam author's read scope | **yes** (the control's frozen list is unavailable) |
| GAP-52 | `crash_sweep_v5f.py` is "the lab's `fault_injection_v5.py` and D1's `t_crash_sweep.py` merged and ported"; both are outside the read scope | no (the sweep implements C1-C9 as G_FI writes them) |
| GAP-53 | SM1's required content and positive controls #1 and #2 need files outside the read scope: the 63 census mutants, `semantic_mutation_census.json`, the round-4 kill shapes' mutants, and v5e's implementation | **yes** (SM1 cannot hold the census rows; controls #1 and #2 cannot run) |
| GAP-54 | D1's M3 ("register before append") and M5 ("exit claim not idempotent"), re-targeted, are not caught by C5 on `ref_v5f.py` | **yes** (UNWITNESSED rows need a witness or a signed EQUIVALENT_BY_SPEC argument before the freeze) |
| GAP-55 | `corpus_v5f/` must hold the round 1-4 repros from `protocol_v5_redteam/`, outside the read scope | **yes** (the corpus is incomplete without them) |
| GAP-56 | G_SIG names its measured quantities and the three L-DELIVERY cells, but not its other cells | **yes** (the frozen harness's cell list is the exam author's reading) |
| GAP-57 | the corpus's crash-sweep points are (key, offset, k) triples of one implementation's code; the text does not say how instrument (d) runs them on another implementation or on a mutant | **yes** (instrument (d) does not probe them) |
| GAP-58 | SM2's O12 "tuple rebuild -> in-place mutation": a tuple cannot be mutated in place, and the text gives no form | **yes** (the immutability family has no applied mutant, and SM2's gate needs one per family) |
| GAP-59 | G_ATOM's parts A and E are frozen from prototype files outside the read scope; on the exam author's reading, part A's CALL+C_RETURN floor (25) is out of reach and part E's control finds nothing | **yes** (G_ATOM fails on `ref_v5f.py`) |
| GAP-60 | G_ATOM's hookup control K4: revision 5's `_register` returns no owner element, so the patched copy's first enter refuses MONITOR_BUSY and the matrix cannot run | no (the run fails, as a hookup control must; the text's "12 of 67" cannot be reproduced) |
| GAP-61 | SM1: 17 admitted-on-condition-2 rows are UNWITNESSED on 3.12.3 (their named witness passes under the weakening) | **yes** (each needs a witness or a signed EQUIVALENT_BY_SPEC argument before the freeze) |
| GAP-62 | SM1's "one weakening per operator family below, inside each rule-tagged region of `ref_v5f.py`": the text does not define a rule-tagged region | **yes** (those rows are not written) |
| GAP-63 | `traces_v5f/` holds the prebuilt traces "for the scoring-only cases"; the text does not list those cases | no (the runner's scoring-only cases read three traces, all present and regenerated identical except for fixture paths) |
| GAP-64 | SM1: a weakening that hangs the runner before its named witness runs (`A_txn_shared_succ`) — the text does not say whether a hang seen only by the driver's timeout kills a row | **yes** (the row is HANG in `sm1_result.json`: admitted, not KILLED, so SM1's gate fails on it) |

**GAP-50. What is a mutable site?**
- *What the text says.* G_SEM, SM2 gate: "G_REF: 100% of O13 mutants KILLED, and the literal census finds 0 coded literals outside a mutable site." O13 is an SM2 operator, and SM2 applies its operators inside the Region (the `_v5_faultpoints()` functions, the five scoring functions, and the M1 binding statements).
- *What the census finds on `ref_v5f.py`* (`refcensus_v5f.py`, both versions): 94 coded literals inside region function bodies, and 6 outside them. Five are the DECL and SECTION_DECL raises in `Experiment.__init__` (prereg parsing, a v4-era method outside the Region), and one is the module-level `_CODE_RE` pattern `\[V5:([A-Z_]+)\] ` (a regex that reads codes, not an emission).
- *Readings left open.* (a) A mutable site is a statement inside the SM2 Region: the census fails on the DECL raises, which the text places in the parse. (b) Any statement O13 could replace, anywhere in the module: only `_CODE_RE` is outside, and whether a pattern that reads codes is a "coded literal" is open too. (c) Coded *emissions* only: 0 outside.
- *In the artifact.* The census reports all six and gives G_REF's census verdict as OPEN (GAP-50). G_HYG passes.

**GAP-51. The eight blind shapes.**
- *What the text says.* Positive control #5: "A planted blind-shape emission must be caught by G_HYG, for each of the 8 shapes in `mutation_gate_blindspots.json`." G_HYG's first clause: "0 coded emissions in a blind shape".
- *The problem.* That file is not in the exam author's read scope (the spec text, the exam artifacts, and the named spec-data directories).
- *In the artifact.* `refcensus_v5f.py` checks the shapes the text itself implies (a code prefix split across literals, `str.format`, `%`-formatting, a code from an f-string's formatted value) and plants each as a control; all four are caught on both versions. Whether they are the eight is unknown.
- *Fix needed.* State the eight shapes in the text, or declare the file spec data.

**GAP-52. The crash sweep's provenance.**
- *What the text says.* "`crash_sweep_v5f.py`. The lab's `fault_injection_v5.py` and D1's `t_crash_sweep.py` merged and ported to the v5f interfaces." D1's file is under `crashcons/`, which the exam author attests not to read, and the lab's file is outside the read scope.
- *In the artifact.* The sweep is written from G_FI's text: the injector, C1-C9, the scenario list, K = 2, the twice-made discovery run, the frozen enumeration order and stride. It is clean on `ref_v5f.py` on both versions (about 20,000 points each), and D1's M2, M4 and M7, re-targeted, fail C7 as the text names.
- *Fix needed.* Say whether "merged and ported" constrains anything beyond C1-C9 and the scenario list.

**GAP-53. SM1 content and positive controls outside the read scope.**
- *What the text says.* SM1's required content includes "all 63 round-4 census mutants (`protocol_v5_redteam/round4_exam_mutation/mutants.py`)" (15 retired, 1 adopted, 47 re-targeted, by id) and "the 29 round-4 exam-hole kill shapes, each as a row". Positive control #1 runs SM1's machinery "on v5e's frozen exam with the 63 census mutants applied to v5e unchanged" and compares with `semantic_mutation_census.json`; control #2 runs SM2's generator on v5e.
- *The problem.* The census mutants, the census result, the kill shapes' mutant definitions and v5e's implementation are outside the exam author's read scope, and controls #1 and #2 execute v5e's implementation.
- *In the artifacts.* `weakenings_v5f.py` holds the rows the exam author could write from the text (205 rows at this commit, the Mutation-audit table's included). The 47 re-targeted census rows and the 29 kill-shape rows are not written. `controls_v5f.py` reports controls #1, #2, #3 and #4(a) as NOT_RUN under this gap (#3 and #4(a) also need v5e).
- *Fix needed.* Declare those files spec data (as revision 11 did for the v5e cases), or restate the 47 re-targeted rules and the 29 shapes in the text.

**GAP-54. D1's M3 and M5 against `ref_v5f.py`.**
- *What the text says.* "M3 register before append → C5 (anchors left)"; "M5 exit claim not idempotent → C5 (openings left)".
- *What happens.* Re-targeted as (M3) `_open` storing the anchor before appending the opening and (M5) exit's X1 claim replaced by an unconditional store, the full crash sweep is clean on 3.12.3 for both. For M3, a fault between the store and the append leaves an anchor, but the next reconciliation prunes cores reached from anchors (revision 4, B1), so C5 sees nothing. For M5, no sweep scenario exits one tracer twice concurrently. The Mutation-audit table names V52 for "exit claim replaced by an unconditional store".
- *Readings left open.* Whether M3 and M5 are equivalent under v5f's reconciliation (EQUIVALENT_BY_SPEC needs an argument signed by a reviewer who is neither the exam author nor the implementer), or whether their re-targeted form should be different.

**GAP-55. The corpus's round 1-4 repros.**
- *What the text says.* `corpus_v5f/` holds "the round 1-4 repros, rewritten by the exam author against the public API from `protocol_v5_redteam/round1_module/` through `round4/` and `round4/closure-audit/r1/held_battery.py`".
- *The problem.* Those directories are outside the read scope.
- *In the artifact.* The corpus holds the exam cases (425), the fuzzer's programs (300) and the crash-sweep point sets (10); `manifest.json` lists this part as missing.

**GAP-56. G_SIG's cells.**
- *What the text says.* G_SIG requires "0 user-lock leaks, 0 hangs, 0 poison, 0 wrong results, and credited <= body runs", defines "wrong result" and poison, and fixes three L-DELIVERY cells; "every other G_SIG harness flow uses only with/finally for cleanup and checks results only on iterations in which no asynchronous exception was delivered". It does not list the other flows.
- *In the artifact.* `sigflood_v5f.py` runs three cells for the named quantities (a `with lock:` loop, H8's credit shape, a result check) beside the three L-DELIVERY cells. That cell list is a reading.

**GAP-57. The corpus's crash-sweep points under instrument (d).**
- *What the text says.* `corpus_v5f/` holds "the crash sweep's points"; the manifest classes "every crash-sweep point" as `envelope`; G_FI says of the freeze-time point sets that "the implementation's code differs", so they are committed "as a record, not as the set G_FI uses".
- *The problem.* A point is an offset in one implementation's code object. On the real implementation, and on each SM2 mutant of it, the recorded points name other instructions or none. The text does not say whether instrument (d) re-enumerates the points on the code under probe (which is instrument (b) at stride 1), maps them, or skips them.
- *In the artifacts.* `corpus_v5f/crash/` records `ref_v5f.py`'s point sets on 3.12.3 (10 scenario/thread sets); `diffprobe_v5f.py` lists them as `not_probed` (GAP-57).

**GAP-58. O12 on a tuple.**
- *What the text says.* "immutability | O12 tuple rebuild -> in-place mutation"; SM2's gate needs "at least one applied mutant per family".
- *The problem.* The Region's tuple rebuilds (`m.holders = m.holders + (core,)`, `tuple([h for h in m.holders if h is not core])`) produce tuples, which have no in-place mutation. A mutant needs a representation change (a list) that the text does not give.
- *In the artifact.* `opmut_v5f.py` generates no O12 mutant and reports the family as having none.

**GAP-59. G_ATOM's parts A and E.**
- *What the text says.* Parts A, B and E are `rev5/t1_onecall_atomic.py`'s, D2 is `rev6/t1d2_discriminating.py`'s, "frozen with G_ATOM", with floors: part A at least 40 / 25 / 3 / 40 trials under INSTRUCTION, CALL+C_RETURN, `setprofile` and opcode tracing, each two-statement control at least 1 violation; part E's two-statement control must find the event clear before 50,000 samples.
- *The problem.* The reference pipelines and the part-E harness are defined by those files, outside the read scope. `atom_v5f.py` builds them from the text (a clearing function shaped as M7 writes `_unwind_off`, an opener shaped as `_unwind_on`, 4 threads, a profiler that waits 10 us at each C call of the close path).
- *What happens (both versions).* The 67-case matrix passes, K1-K14 come out exactly as the text's "Result on the prototype" states (K5-K7 24, K8 3, K9 3, K10 12, K11 12, K13 2, K14 1, K12 and K12b 0), parts B, D2 and R pass (part R: n0 = 4,998, 31 full and 30 none per step, K7 one partial trial). Part A's one-call clearing function fires 18 CALL+C_RETURN events (its pipeline makes 9 calls), under the floor of 25; the other three floors are met and every control violates. Part E's one-call form reaches 50,000 samples with none clear, but its two-statement control also finds none on either version (1 in 3 trials on 3.12.3 with `sys.setswitchinterval(1e-5)`). So G_ATOM is FAIL on `ref_v5f.py` under this reading.
- *Fix needed.* Give the part A clearing function and the part E harness in the text (or declare the two files spec data).

**GAP-60. K4 and the binding enter.**
- *What the text says.* K4 (revision 5's `_register`: one name gate, no owner read, no count) "fails all `_register` cases (12 of revision 8's)"; G_ATOM binds the machinery with "one `with coverage_trace(EXP): pass`".
- *What happens.* With K4's patch, `_ensure_tool` never sees its name as the registration's owner, so that first enter refuses MONITOR_BUSY; the matrix cannot run, and the run fails. It fails as a hookup control must, but not in the way the text counts.

**GAP-61. SM1 rows whose named witness does not see the weakening (3.12.3).**
- *What the text says.* A row failing admission condition 3 is UNWITNESSED; before the freeze the exam author writes a witness or files it EQUIVALENT_BY_SPEC with an argument signed by a reviewer who is neither the exam author nor the implementer.
- *The rows, with what the exam author observed (not an equivalence argument):*
  - `A_coh_no_file_skip` (X26e), `A_cache_callee_identity` (X24c), `A_alias_by_name` (X24d): an earlier refusal in the resolution order gives the same code first (the module `__file__` rule; the bound-body check);
  - `A_mint_eq` ("`is` vs `==`", v5e:X45): local events are set only on the minted code and the mint is found by `id(code)`, so an equal copy never reaches a callback;
  - `A_visible_deleted` (X58b): X58b's clone is refused by CLONE_ALIVE's function-referrer clause before the freeze clause; deleting the visible accounting only adds refusals;
  - `A_publish_recheck` (X71): X71's call starts after the credit stop, so no pending entry crosses the exit (a landing trial such as X71c's would cross it);
  - `A_enter_claim` (X32d): no switch landed between the test and the store in 50 barrier repetitions;
  - `A_exit_claim` (V52; also GAP-54's M5): a second exit re-runs X2-X8 with nothing held;
  - `A_atfork_handler`, `A_pid_passthrough` (V47): the children's state is not observed from the parent;
  - `A_unwind_on_recheck` (X143), `A_detach_anchor_first` (X148), `A_capture_outside` (X153), `A_ensure_no_reclaim` (X137e): the named sweep or case gives its stated outcome under the weakening;
  - `A_open_audited_after_append` (V71): V71's hook raises at the *first* event of each kind in one `cov.run`, and the first two `builtins.id` events of a run are `_open`'s cut checks (`_CUT.get(id(c))`), before the append; the added `id(o)` after the append is the third (13 `builtins.id` events per run on the reference, 14 on the mutant), so the hook never fires there. A witness that raises at the k-th event, k swept, would reach it;
  - `A_binding_first_only` (X156c): X156c reloads the module before its second `coverage_trace()`, so that enter binds `_MON` afresh and the first-bind-only check still runs; a replacement made after a first bind, without a reload, would not be checked;
  - `A_verified_widened` (X37b): the row's patch widens `_VERIFIED` to patch levels 0-39, and X37b's `sys.version_info` has micro 99, still outside it (here the row's patch, not the witness, is short of the rule).
- *In the artifact.* `sm1_result.json` lists them per version. The 3.13.12 list and the crash-sweep rows are in that file.

**GAP-62. "Each rule-tagged region of `ref_v5f.py`."**
- *What the text says.* SM1's required content includes "one weakening per operator family below, inside each rule-tagged region of `ref_v5f.py`".
- *The problem.* Neither the text nor `rules_v5f.json` defines a region tag in `ref_v5f.py`; the rule atoms cite sections, not code spans.
- *In the artifact.* No such rows are written; `opmut_v5f.py` can generate every operator site on `ref_v5f.py`, but choosing one per family per region needs the region definition and a named witness per row.

**GAP-63. The scoring-only cases' traces.**
- *What the text says.* "`traces_v5f/`. The prebuilt `/3` traces for the scoring-only cases, generated by `ref_v5f.py` on 3.12.3 at freeze time."
- *In the artifact.* The runner's scoring-only set (the cases run on every interpreter) reads three traces, F, X112B and X122; all three are present, and regenerating them from the current `ref_v5f.py` on 3.12.3 changes only the fixtures' temporary paths in `targets`. That set is the runner's reading of "scoring-only".

**GAP-64. A weakening that hangs the runner before its witness runs.**
- *What the text says.* SM1 admission condition (3): "under ref+W the witness's observable outcome differs from the spec outcome"; an admitted row is KILLED iff its named witness fails on ref+W. Every run is a fresh process, made twice.
- *What happens.* `A_txn_shared_succ` (revision 5: `_Txn`'s `succ` dict shared between tokens; witness V52; the catalog's weakened outcome "a hang"). Once two tokens exist, every chain walk (`_acquire`'s and `_v5_state()`'s `while n is not None: r = n; n = r.succ.get("next")`) follows the shared dict to the same token forever. With the runner's `--mutation V52`, the self-trace's enter takes the first token; `run_in_self` then calls `snap()` -> `P._v5_state()` on the main thread, before the case thread starts, and spins there (a faulthandler dump at 75 s: `_v5_state` line 1899 <- `snap` <- `run_in_self` <- `main`). V52's body never runs, and `--mutation V01` hangs at the same line. Both SM1 runs reach the driver's 600 s timeout on 3.12.3 (`TIMEOUT`, `TIMEOUT`). The crash sweep on the same patch reports `void: baseline failed` for its scenarios (the baseline run hangs), so G_FI fails without naming C3.
- *Readings left open.* (a) "No outcome" differs from the spec outcome and the row is KILLED (what the journal first recorded); (b) the witness never ran, so the row is admitted but not KILLED, and needs a witness that observes a hang with a bounded wait (a fresh-subprocess case with a timeout as its stated outcome, or a C3 crash-sweep row that counts a hung baseline). The exam author does not choose.
- *In the artifact.* `weakenings_v5f.py` classes a row whose two runs both time out as HANG and counts it as admitted and not killed (reading (b), the stricter), so SM1's gate fails on it until the text decides. `sm1_result.json` lists HANG rows per version.

## Revision 13 follow-ups (raised while applying revision 13; for the spec owner)

Revision 13's text is applied as written; each item below is a place where the text and what the exam author
measured or had to choose disagree, or where the text leaves a choice open. Nothing here was worked around: where
an artifact had to choose, the choice is named and the item says so. "Both versions" means 3.12.3 and 3.13.12.

**R13-1. GAP-62's cell count, and where the at-fork registration belongs.**
- *What the text says.* "70 cells over 8 families (O12 had no generator), 45 filled by the catalog's 205 rows, and
  25 to write", and the rule regions: M1 is "the module-level statements that bind the M1 names"; "A Region unit
  ... that is not listed joins the section under whose heading this text specifies it".
- *What the exam author measures* (`opmut_v5f.py` on `ref_v5f.py` sha256 `1d0b06ee…`, the revision-13 reference):
  71 cells counting O12's (70 without it), 44 filled after the two `_v5_state()` guard rows were re-targeted to
  revision 13's walk (42 before), 27 empty: the text's 25, O12's cell, and (deletion, M1). The one disagreement is
  `A_atfork_handler`, whose only patch deletes the module-level `os.register_at_fork(after_in_child=_forget_in_child)`.
  The statement binds no name, so by the M1 definition it is not M1; the text specifies it under M9, so by the
  joining rule it is M9's. Counted that way it fills (deletion, M9), and (deletion, M1) is empty. The text's list
  ("deletion in M9" among the 25 to write) counts it as M1, which fills (deletion, M1) and leaves (deletion, M9).
- *In the artifact.* `weakenings_v5f.py` follows the text's list: the 25 rows plus O12's (`sm1_gap62_rows.json`),
  including `R62_deletion_M9`; no row is written for (deletion, M1). Under the other reading (deletion, M1)'s first
  non-TCE mutant deletes the `if _GUARD is None:` statement, and every case would witness it.
- *Fix needed.* Say which rule region a module-level statement that binds no M1 name (the at-fork registration)
  belongs to, and restate the counts.

**R13-2. Rows SM1 finds UNWITNESSED, with what the exam author found for each.** SM1 on the revision-13 reference
(below, R13-13) gives the same 25 UNWITNESSED rows on both versions: 8 re-targeted census rows, 2 kill-shape rows and
15 GAP-62 rows. The text asks for a witness or an EQUIVALENT_BY_SPEC filing (signed by the fourth reviewer) for each
before the freeze. For the rows below marked *witness shape verified*, the exam author ran the shape on `ref_v5f.py`
and on the row's patch, one fresh process each, on both versions, with identical results
(`tools/r13_shapes/`, `results_v5f/r13_witness_shapes.json`); none is a runner case yet, since a new case is a text
change. The equivalence arguments are the exam author's reading, offered for the reviewer, not filed.
- `C13_E03_clone_alive_counts_fn` (named V36c). *Witness shape verified:* nested tracers on f; the inner section keeps
  a non-function reference to f's minted code (`keep.append(f.__code__)`) past the inner exit. Spec: the inner trace
  PASSes (the reference is not a function); weakened: CLONE_ALIVE (the declared function itself is counted while the
  outer still holds the mint).
- `C13_E06_restore_ignores_other_tracers` (X142). *Witness shape verified:* nested tracers on g; the inner exits
  first, then the outer's section calls g. Spec: outer PASS; weakened: outer NOT_EXERCISED (the inner's exit retired
  the shared mint).
- `C13_H15_walk_from_frame` (V01). Not equivalent: the instruction asked for a candidate EQUIVALENT_BY_SPEC filing,
  and the exam author's argument for one fails. The walk from `f` instead of `f.f_back` differs when `f` is itself an
  anchor frame, which happens when styxx's own `_run_async` is declared (V34 already declares `styxx.protocol:_run`):
  on a PY_RESUME after the commit, `f` is its own opening's anchor. *Witness shape verified:* declare
  `styxx.protocol:_run_async` and f; `asyncio.run(cov.run_async('G', body))` with two awaits. Spec: NOT_EXERCISED,
  `dispatched {'styxx.protocol:_run_async': 2}`; weakened: PASS with `_run_async: 2` credited.
- `C13_H18_globals_equality` (X55). *Witness shape verified:* in the section, call
  `FunctionType(f.__code__, dict(f.__globals__))()` (a clone over an equal copy of the module's globals). Spec:
  CLONE_CALLED; weakened: PASS (`==` finds the copy equal).
- `C13_P04_no_cycle_detection` (V11c). *Witness shape verified:* a two-function `__wrapped__` cycle `a <-> b` of
  distinct functions defined in another module, `a` bound in the declared module. Spec: FOREIGN_DEFINITION naming
  `fxo:b` (the innermost function before the cycle closes); weakened: naming `fxo:a` (the walk runs to the 17-hop bound).
  The named function is a spec-fixed observable (M11), but the text never says which function "innermost" is on a
  cycle; a witness needs that sentence.
- `C13_S04_union_last_wins`, `C13_S05_union_max` (V55). *Witness shape verified:* section G opened twice, each opening
  calling f once. Spec: coverage `{f: 2}`; both weakenings: `{f: 1}`. The verdict's coverage counts must then be a
  stated outcome of the case.
- `C13_S08_msg_counts_all_targets` (X72b). *Witness shape verified:* G declares f and g; the section calls g, and a
  loop inside it dispatches f and g. Spec message: `dispatched {'fxm:f': 1}`; weakened: `{'fxm:f': 1, 'fxm:g': 1}`.
- `KS_exam-mut-double-exit-state-leak` (V52). The row reuses `A_exit_claim`'s patch, which revision 13's V52b KILLS on
  both versions; the kill-shape extract names V52, which does not see it. Proposed: name V52b.
- `KS_exam-mut-profiler-lost-only-if-none` (V60). *Witness shape verified:* during the trace, free styxx's tool id
  and take it under another name (`free_tool_id(t); use_tool_id(t, "intruder")`), then exit. Spec: MONITOR_LOST note;
  weakened: no note (`r[-1]` is a name, not None).
- `R62_comparisons_M1`, `_M2`, `_M3`, `_M9`, `_M10` (`is` <-> `==` against None). *Candidate EQUIVALENT_BY_SPEC:* each
  operand is None or a value whose `==` against None is False: `_GUARD` (a dict), `tok` (a `_Txn`, which defines no
  `__eq__`), `t` (an int tool id), `_MON[0]` (a tuple). No other value reaches those sites.
- `R62_types_M5` (`type(r) is FunctionType` -> `isinstance`). *Candidate EQUIVALENT_BY_SPEC:* `FunctionType` cannot
  be subclassed (CPython raises TypeError), so the two tests agree on every object.
- `R62_deletion_M9` (`_forget_in_child`'s first statement deleted). *Candidate EQUIVALENT_BY_SPEC:* while `_MON[0]`
  is None no `coverage_trace()` has been constructed, so no transaction has run: the guard's hint is the initial free
  token, and `_ANCHORS`, `_MINTED` and `_BY_FN` are empty and `_TOOL[0]` is None. The rest of the function then only
  replaces a free token by a fresh free token. Shape checked: a fork inside a trace with two mints gives identical
  child observables (`results_v5f/r13_witness_shapes.json`).
- `R62_conditions_M10` (`_v5_state`'s local-events read negated). *Witness shape verified:* `_v5_state()` read inside
  a trace: the spec's mints show `local_events` 15; weakened: 0.
- `R62_scope_M10` (`_v5_state`'s mint loop cut to the first). *Witness shape verified:* two declared targets,
  `_v5_state()` inside the trace: two mint rows; weakened: one.
- `R62_scope_M9` (`_forget_in_child` step 4 cut to the first mint). *Witness shape verified:* fork inside a trace
  with two mints; in the child, `sys.monitoring.get_local_events(tool, <second minted code>)`: spec 0; weakened 15.
- `R62_order_M10` (`_v5_state` reads `_MON` before `_TOOL`). Not equivalent: the two reads straddle a first bind. As
  instructed, the proposed witness is an instruction sweep over `_v5_state` with the first enter as interference
  (trial k: a fresh process, `_v5_state()` on one thread, the first `coverage_trace()` enter on another at the k-th
  instruction; spec: the returned `tool` and `tool_ours` are consistent with each other).
- `R62_claims_M2` (`_acquire`'s claim -> unconditional store). Not equivalent under contention: two acquirers that
  both find the tail dead both store `next`, and the first is unlinked. Proposed witness: an instruction sweep over
  `_acquire` with a second thread's enter as interference at each instruction (H1's shape at `_acquire`).
- `R62_order_M3` (`_retire` clears `pend` before the local events). Differs only if an event of the minted code lands
  between the two statements (a frame of the minted code resumed on another thread). What it leaves is a pending
  entry on a retired mint, which no listed observable reads. Needs a decision: a witness through a new observable, or
  EQUIVALENT_BY_SPEC under the closed list.
- `R62_scope_M3` (`_prune` detaches only the first opening). Proposed witness: a trace whose exit never runs while
  two of its openings are open (two threads), reconciled by another trace's transaction; spec: `anchors == 0` after;
  weakened: 1. X146c's shape has one opening.
- `R62_immutability_M3` (O12, `holders` mutated in place). Differs only when a callback's `holders` snapshot is taken
  before a rebuild on another thread and read after it. Proposed witness: an instruction sweep over `_exit_txn`'s
  rebuild with a running callback on the same mint as interference.

**R13-3. Trial and event counts in two revision-13 rows.** X132b's row states 154 trials (spec) and 158 (with
`M3_register_before_append`); the runner counts 204 and 208. V71b states 4 events (spec) and 5 (weakened); the runner
counts 6 and 7. The outcomes match the rows on both versions (every spec trial `anchors == 0`; one opening, none
`"open"`), and both rows KILL their weakening. The counts are of `_open`'s instructions and of the audit events
`_open` raises, so they depend on the implementation's code of `_open` (here `ref_v5f.py`'s), not on the rule; the
text's numbers are its prototype's. Fix needed: state the outcomes without the counts, or say which code the counts
are of.

**R13-4. `_v5_state()`'s walk and the audit events.** Revision 13's total walk calls `id()` once per chain node, so
`_v5_state()` raises `builtins.id` audit events. Checked against V71, V71b, V72 and G_HYG's "no user code" clause:
no conflict found. V71 arms its hook around one `cov.run` and V71b counts only events whose caller is `_open`;
`_v5_state()` is never called inside a `cov.run`, and the leftover snaps run outside the armed window. V72 reads the
guard through `_v5_state()` and gives its stated outcome. Recorded, nothing changed.

**R13-5. A case that never runs in mutation mode.** Under some weakenings the self-trace itself raises before the
self-placed cases run. The text classes a run by its witness's observable outcome and does not say what an unreached
witness is. `run_protocol_v5f_exam.py` records such a case as `NOT_REACHED: the self-trace raised ...`, and
`weakenings_v5f.py` classes two NOT_REACHED runs (or two watchdog timeouts) as HANG, admitted and not KILLED, the
GAP-64 reading (b). Under this SM1 run no row ended HANG.

**R13-6. The deps path is not pinned for numpy.** v5e's ported cases R11 and X118 import numpy. The text pins the
greenlet 3.5.6 and coverage 7.16.1 wheels by sha256, and says nothing about numpy. The runs used numpy 2.5.3 from
PyPI (recorded in ATTESTATION.md and in the runner's `--deps-path` help). Fix needed: pin numpy's wheel, or drop the
dependency from those cases.

**R13-7. Positive control #2 has no Region on v5e.** SM2's generator runs over SM2's Region, which the text defines
by v5f names (the `_v5_faultpoints()` functions of M10, M11's scoring functions, the M1 statements). v5e has almost
none of them, and the text gives no v5e Region. `controls_v5f.py` reports #2 NOT_RUN with this reason. Fix needed:
name v5e's Region for #2 (control #3's fault-point list is one candidate).

**R13-8. Positive control #3's adapter.** The text fixes the adapter's fault points and its `_v5_state()` view for C5
and C7, with `cut`, `cut_current`, `tool`, `tool_ours`, `global_events` read as their S0 values. The adapter
(`controls_v5f.V5E_ADAPTER`) had to choose what the text leaves open:
- `guard`, which the text's list omits: read as `"free"`;
- each mint row's `local_events` and `pending`, which v5e lacks: read as 0; the row's `target` is
  `fn.__module__:fn.__qualname__`;
- the registries the text names but v5f's `_v5_state()` has no key for (`_BY_FN`, `_THREADS`, `_ACTIVE`): added as
  extra keys `by_fn`, `threads` and `active`, which C5 and C7 do not read;
- the sweep's callbacks scenario faults v5f's callback-only functions, which v5e lacks, so it is not run; the other
  scenarios run.
Fix needed: state these four choices, or say they are free.

**R13-9. Positive control #4(a): criterion and source.** The text: "G_SIG must show v5e leaking on 3.12 and 3.13
(D3 sig_sweep: 2521 and 2265 leaks)". `sigflood_v5f.py`'s lock cell on the v5e blob fires, with 1 leak per version in
a 10 s cell. The text does not say whether the control passes on any leak or needs a magnitude near 2521 and 2265.
Those numbers come from D3's `sig_sweep`, a v5f design artifact outside the read scope, whose harness the exam
author has not seen. Fix needed: state the pass criterion (fires, or a magnitude) and whose harness the numbers come
from.

**R13-10. Which directories the corpus covers.** "the round 1-4 repros ... from `protocol_v5_redteam/round1_module/`
through `round4/`". Read as a range of the tree's directories in order, that is round1_module, round2_exam,
round2_module, round3_exam, round3_module and round4. It leaves out round1_exam, which sorts before round1_module,
and round4_exam_mutation (the census), which sorts after round4. The corpus follows that reading.
`corpus_v5f/repro/SOURCES.json` maps all 406 pinned files in the range: 164 rewritten, 40 fixtures, and 202 not
applicable with a reason (outputs, patches, v5e exam tooling, and parts that exercise `cov.section`, which v5f
removed). Fix needed: confirm the range, or list the directories.

**R13-11. The corpus repros' v5f outcomes and their class.**
- (a) The text states no v5f expected outcome for the rewritten repros, and the instruction counts that as a gap.
  The differential probe needs none for an equality entry, since it compares against the unmutated implementation.
  An envelope entry, though, is probed only through a stated outcome. 31 of the 68 repro entries are envelope, and
  only one of them, the re-targeted closure battery, has stated outcomes (G_CLOSURE's rows). The other 30 are not
  probed (`probe()` lists them as `repro_envelope_without_stated_outcome`).
- (b) The manifest rule's clause "a thread race" is defined for exam cases by the list the text gives. For repros
  the exam author reads any started thread, pool, executor or timer, and any cross-thread loop call, as one, along
  with signals, the injector, finalizers, gc thresholds, switch intervals and wall-clock waits
  (`diffprobe_v5f.REPRO_ENVELOPE_TOKENS`). This choice is fail-closed and still the author's. N = 5 validation
  follows.
- (c) Where a repro interrupted v5e at a named line of its private source (round 4's `v_inject.py`, `v_det.py`, the
  `_own_dict` try line, `a04`/`a08`'s `__enter__`/`__exit__` lines), the rewrite raises through the id-5 injector at
  instruction n (1, 3, 5, 10, 25, 30, 100) of the v5f fault-point code objects named in each file. The text does not
  map v5e's lines to v5f points; the n values are the exam author's.
- (d) G_CLOSURE: the battery's rows carry v5e's expectations. Two have no stated v5f expectation. "R1-B4 v:
  pure-Python profiler present at open" expected v5e's FOREIGN_PROFILER, which v5f retires; the exam author reads the
  R1-B4 closure row and "profile-module-refuses-on-312" as PASS with the profiler left installed. "R1-D3 int key in
  targets" targets a key v5f's record does not have, so it is re-targeted to an int key in an opening's calls (BAD_TRACE).
  With those two readings the battery holds 41/41 on `ref_v5f.py` on both versions.
- (e) A count that depends on how deep the implementation's own frames sit (round 3's `hook_failed`: target calls
  before a RecursionError) is reduced to "at least one". Two conforming implementations can differ there.
Fix needed: for (a), state the repros' outcomes, or say that envelope repros are not probed; for (b) and (c), confirm
or replace the readings; for (d), state the two rows' v5f outcomes.

**R13-12. The census rows not re-targeted.** None: all 47 census rows and all 29 kill-shape rows are written
(`sm1_census_killshape_rows.json`). The 10 among them that SM1 finds UNWITNESSED are in R13-2.

**R13-13. SM1 on the revision-13 reference.** See `sm1_result.json` (journal `results_v5f/sm1_journal.jsonl`, each
entry keyed by the sha256 of `ref_v5f.py`, the runner, the patch and the witness's source). Summary on completion
below.
