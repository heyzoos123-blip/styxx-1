# Critique of DESIGN_protocol_v5f_DRAFT_2026_09_25.md, revision 5 (sixth critic)

Target: `papers/first-afference/DESIGN_protocol_v5f_DRAFT_2026_09_25.md` (2,401 lines), revision 5. Line numbers below are that file's. Evidence read: `protocol_v5f_design/rev5/` (mech5.py, m5_modelcheck.py, t1_onecall_atomic.py, w5_witnesses.py, spec_rev5_eventpath.py and their outputs) and `protocol_v5_redteam_audit.json` round_4. Probes: `scratchpad/v5f/critic6/` (`a1`–`a6`, outputs `out_a*.txt`, re-runs `rerun_*.txt`). Interpreters: `rt3/venv3.12` (3.12.3) and `rt3/venv3.13` (3.13.12). No tracked file was modified.

**Counts: 1 BLOCKER-for-freeze, 5 MUST-FIX, 7 NOTE. Verdict: NOT_READY.**

---

## What was attacked, and what held

The brief asked for an attack on revision 5's premise: every read-decide-write on the event or the tool id is one lazy `itertools`/`operator` pipeline consumed by one builtin call, so nothing can come between the test and the write. For `_unwind_on` and `_unwind_off`, the two steps U1 and U3 rest on, the premise **holds** on 3.12.3 and 3.13.12 once `_MON` is really bound to the C functions. The following checks came out clean:

- **`__eq__` and `__hash__`.** Every dict operation in a pipeline uses a frame, str or None key: `_ANCHORS.get`/`pop`, and `setitem` on `core.flags`. Frames have no `tp_richcompare` and hash by address. hash(None) is constant from 3.12. No Python `__eq__` or `__hash__` can run. The only foreign comparison is `get_tool(t) is _TOOL_NAME`, an identity test.
- **`__bool__` and `__index__`.** `compress`, `filter` and `not_` test only bools, ints and `_ANCHORS`. `t` is an exact int.
- **`__getattribute__`.** `attrgetter` reads `armed`, `core` and `flags` on machinery classes. Their exact form is item M4 below.
- **`__del__`.** In every step as specified, the caller still holds each value the step pops or drops (`o`, `fr`, the `list(...)` snapshots). So no reference count reaches zero inside the call, and no finalizer runs there.
- **gc.** Probe `a6`: at threshold 1, with 2,000 GC-tracked allocations inside one consuming call, 0 of about 3,600 gc callbacks and finalizers ran inside the call, on both versions. 3.12 and 3.13 only schedule gc from `_PyObject_GC_Link`.
- **RecursionError.** Every pipeline callable is vectorcall on both versions (`a4`). A C-recursion sweep never raised inside a step after its first write (`a5`).
- **The `sys.monitoring` calls themselves.** `get_tool`, `get_events`, `set_events`, `set_local_events` and `use_tool_id` raise no audit event (`a1`). On GIL builds, `set_events` runs no Python code: the 3.13 stop-the-world is a no-op there. No monitoring or profile callback fires for a call made from C.
- **3.12 against 3.13.** No difference that matters to the pipelines. The audit event below exists on both versions.

The premise **fails** in two places:
- (B1) `sys.monitoring.register_callback` raises an audit event inside the C call;
- (M1) nothing checks that the names the pipelines call are the C builtins.

---

## BLOCKER-for-freeze

### B1. `_register` is not atomic: `register_callback` raises the audit event `sys.monitoring.register_callback` inside the one-call step, so the tool-id race fix (N1, CLOBBER) and several normative sentences are false

**Evidence.**
- `critic6/a1_audit_monitoring.py`, on 3.12.3 and 3.13.12: `register_callback` raises the audit event `sys.monitoring.register_callback`. None of the other five `sys.monitoring` functions styxx calls raises one.
- In `_register` (line 641), the name gate `compress((t,), is_(get_tool(t), NAME))` is evaluated once, when the first callback is pulled. The audit event then fires inside each of the five `register_callback` calls, before each exchange. So Python audit hooks run five times inside the "one C call", after the gate.
- `critic6/a2_register_audit_split.py`, against `rev5/mech5.py`'s `_register_named`, on both versions:
  1. **Thread switch inside the step.** An audit hook blocks briefly on the second registration, as a logging hook doing I/O would, and so releases the GIL. Meanwhile another thread frees id 4, and a foreign tool takes it and registers PY_START, PY_RETURN and PY_UNWIND callbacks. After the step, the foreign tool owns id 4, and its PY_RETURN and PY_UNWIND callbacks are styxx's `_on_exit` and `_on_unwind`. That is exactly the clobber that N1 (line 2262) says is "Closed by mechanism", and that X154 (line 1469) is meant to rule out.
  2. **Fault inside the step.** A sandbox-style hook that raises on the third registration leaves 2 of the 5 callbacks registered. The step is not all-or-nothing.

**Statements this falsifies.**
- Line 654: "none of these calls raises an audit event". Line 657: "Audit events. None, from any one-call step."
- Line 819: "No one-call step raises an audit event". The N2 row (line 2263) says the Sources bullet lists "every audit-event site". It omits `register_callback` at E4 `_ensure_tool`, at M3 step 0 (`_reclaim`) and at X5, which runs on **every exit**, inside the robust mutex.
- Line 678, U1: "a fault cannot land inside a one-call step". Line 821: "nothing at all runs inside one C call".
- Lines 475, 528, 887 and 1286 (L-MONITOR): an id another tool took is "never touched … Revision 5 makes this hold against races too".
- Line 2262: N1 "Closed by mechanism … No race with another tool can make styxx write on a foreign id".
- Lines 899 and #20 (the CYC_TX residual) name only `__code__` writes as the audit-hook site inside a transaction. The five X5 audit events at every exit are a second site. A hook that takes a lock there closes the same 10 s cycle.

**Why the evidence missed it.**
- `t1_onecall_atomic.py` part C (lines 134–143) runs only `off_onecall` and `on_onecall`. `_take`, `_register` and `_set_local` were never probed for audit events.
- `m5_modelcheck.py` does not model callback registration at all (see M2), and it takes the atomicity of one-call steps as an axiom.
- X154's `_register` sweep uses an INSTRUCTION tool, which cannot land inside a C call. So X154 passes, and the frozen exam would certify a guarantee that does not hold.

**Why this blocks the freeze.** `rules_v5f.json` must encode "every normative sentence". The sentences above are normative and no implementation of this spec can satisfy them. An exam author who writes a case from them (an audit hook plus a free and re-take) fails every faithful implementation. An author who leaves it out is exercising judgement. The G_FI fault model also lists audit sites as fault sources (line 813), and that list is incomplete.

**Fix, text only.** The mechanism cannot remove the audit event.
1. List `register_callback` as an audit site at E4, M3 step 0 and X5, in the Sources bullet and in the N2 row.
2. Narrow N1, L-MONITOR (1286), lines 475, 528 and 887, and the model's CLOBBER claim. State the residual: when an audit hook on `sys.monitoring.register_callback` yields the GIL, switches greenlets or raises, and another party frees and re-takes styxx's id meanwhile, styxx can overwrite that tool's callbacks for the events after the switch. A raising hook leaves a partial registration.
3. Amend U1's "a fault cannot land inside a one-call step" to exclude `_register`.
4. Add `register_callback` to #20 and to line 899.
5. State X5's outcome under a hook that raises on `register_callback`. `__exit__` then propagates the hook's error, contrary to the M5 heading "always returns False" (line 514), and X6–X8 are skipped, so `record()` refuses TRACE_INCOMPLETE. Add a pinned-residual case for it.

---

## MUST-FIX

### M1. `_MON` and the one-call names are never checked to be the C builtins; a pass-through Python wrapper on `sys.monitoring.set_events` breaks U1

- Line 405 asserts that "every name is a C callable or a C iterator". Line 412 binds `_MON` "by the first `coverage_trace()`" from `sys.monitoring`. Line 415 says only that a *later* monkeypatch does not reach the machinery.
- Nothing checks the type. Any wrapper installed before the first `coverage_trace()` is captured and then called inside every one-call step. Such wrappers come from a monitoring shim, a debugger, or a test harness that logs `sys.monitoring` calls. The same holds for `map`, `filter`, `itertools` and `operator` patched before import, and for `list` (M4 v).
- `critic6/a3_wrapped_monitoring.py`, against mech5, on both versions:
  - The wrapper does nothing but block briefly in `set_events(t, 0)`.
  - Another thread opens section B inside that window. B stores its anchor, finds S set, arms and enters its body.
  - The wrapper's real clear then lands under B's armed, registered anchor. S is False inside B's body, and B's raising call is lost: `calls['B']` is None.
  - The loss is noted (MONITOR_LOST), but U1 is violated with no party changing the event.
- **Fix.**
  - At binding, require `type(f) is types.BuiltinFunctionType` for each of `_MON`'s six functions. Also check the M1 names against their known C types: `map`, `filter`, `itertools.chain`/`compress`/`repeat`, the `operator` functions, `attrgetter`, `dict.values`, and the `deque.extend` bound method. Otherwise refuse with a coded reason, reusing UNSUPPORTED_VERSION or adding a new code.
  - Add a case in which `sys.monitoring.set_events` is wrapped before the first `coverage_trace()`.
  - Correct line 415.

### M2. `m5_modelcheck.py`'s fidelity and coverage are overstated

1. **No callback registration is modelled.** A grep finds "register" only in comments. E4 (m5 lines 482–515) is `_ensure_tool` → holder → local events → install → credit, with no `_register`. `_reclaim` (R0) re-takes the id with no registration. The model's X5T (lines 457–467) omits both the callback comparison and the "held mint's local events differ from `_LOCAL`" note source. So CLOBBER (header line 38: "events, local events or callbacks") and the spec's "revision 5 has none [CLOBBER]" (line 2262 and the table) cover only global and local events. FALSEFLAG never sees two of X5's note sources.
2. **The premise is an axiom of the model.** "Revision 5's one-call steps are ONE step each" (m5 lines 20–21). The model therefore gives no evidence for the premise, and B1 and M1 are invisible to it. The spec should say that the model's results hold only if the premise does (line 693).
3. **`_TOOL[0]` rebinding is not modelled.** An id held by another tool is "not modelled: refuse" (m5 line 490). The spec does rebind to id 3: X137b's "a second tracer takes id 3", and N1 below.
4. **Budgets.** The ext configurations run only at F0, except `ext: close(X) ∥ rec`. Ext is never combined with re-entry, greenlets, `run_async` or the triples. Each external kind occurs at most once per run (m5 line 672), so free → reclaim → free is never explored. The mutants skip the `open(X) ∥ open(X) ∥ exit…` triples (the `mutants` branch at m5 line ~925). None of this is in "What is still not enumerated" (line 2384).
5. **Configuration count.** Lines 693 and 2334 say 35 configurations. `CONFIGS` has 33, and the outputs hold 33 distinct revision-5 configurations. The 70 runs and 4,922,275 state hashes do check out.

**Fix.** Correct lines 693 and 2334 and the enumeration limits. Either model `_register` (E4, reclaim, X5) with CLOBBER on callbacks and X5's two other note sources, or state that CLOBBER and FALSEFLAG exclude them.

### M3. Internal contradiction: F13, X137e and E4 say the model finds a silent loss that the `_ensure_tool` reclaim rule prevents; the model's own mutant says it does not

- **One side.**
  - Line 500 (E4): "revision 4 re-took it here silently … a section of another trace … lost its raising calls, and that trace's exit … noted nothing (`rev5/m5_modelcheck.py`, `ext: enter(X) || open(Y)`; X137e)".
  - Line 1465 (X137e): "`rev5/m5_modelcheck.py` `ext: enter(X) || open(Y)` finds the silent loss this allows".
  - Line 2387 (F13) says the same.
- **The other side.**
  - `out_m5_mutants.txt` has `ensure_nocount NOT DETECTED by any configuration`.
  - Line 2381 says "its only effect is a missing note on a loss-free free".
  - The MF6 row says 19 of 21 mutants are detected.
- F13's own text shows that the silent loss was closed by F14, the close's event read without a name gate, not by the count.

**Fix.** Rewrite lines 500 and 1465 so that X137e witnesses a note on a loss-free free, which is what `w5` shows (`first_ML False` under the mutant). Credit the LOSTNOTE finding to F14's rule, and give that rule its own mutation row and witness.

### M4. G_HYG, whose gate is G_HYG = 0 (line 1926), contradicts the spec's own code, and cannot establish the property it is used for

Read literally, the lint flags the reference code:

- **(i) Binding form.** Line 1880: "every M1 state name except the four constants is bound through `globals().get`". Line 417 also exempts the one-call names `_map` through `_NAME1`, plus `_monotonic` and `_sleep`. Revision 5's `_monotonic`/`_sleep` clause at line 1879 only partly patches this.
- **(ii) Allowed names.** Line 1876 allows "the M1 one-call names, `_MON[0]`'s functions, `_ANCHORS`, its bound `get` and `pop`, the local `t`, `o`, `o.frame`, `key`, `code` and `events`, and literal tuples". But:
  - `_unwind_on` and `_unwind_off` (lines 609 and 622) bind and use the locals `get_tool`, `get_events` and `set_events`;
  - `_register` (line 641) uses `_repeat`, `_EVENTS5` and `_CALLBACKS5`, which line 652 binds "also" and which are not in M1's `_map` through `_NAME1` range.
- **(iii) Python functions.** "No lambda, generator, comprehension or Python-level function appears in it" is contradicted by `_CALLBACKS5`, a tuple of Python functions passed through `_register`'s pipeline.
- **(iv) Slots.** Line 654 ("`attrgetter` on `__slots__` fields") and line 2397 ("must stay plain slotted classes (M1)") require `__slots__`. M1 (line 439) and G_HYG (line 1876) require only "no Python-level descriptor". mech5 slots `Opening` but not `Core`. The exam author has to pick one.
- **(v) `list`.** `list(...)`, `_register`'s consumer, is read from builtins at call time, unlike `_CONSUME`. That goes against line 415's "bound once" rationale.
- **(vi) Reload.** The reload binding of `_repeat`, `_EVENTS5` and `_CALLBACKS5` is unspecified. If they are bound through `globals().get`, which the literal line 1880 requires for M1 names, then after a reload `_register` re-registers the old functions and X5 compares against them. The reload paragraph's "re-registers the reloaded ones and notes MONITOR_LOST once" (line 417) is then false.

**Scope.** Even corrected, G_HYG is a static check. It cannot detect audit events raised inside a C function (B1), the runtime binding of `_MON` (M1), or the runtime types that `attrgetter` meets.

**Fix.**
- Make the allowed-name list and the binding clause match M1 and M7 exactly. Name `_repeat`, `_EVENTS5` and `_CALLBACKS5` as direct bindings, and allow `_CALLBACKS5` as data. Bind `_list = list` at import. Pick slots or no slots.
- Add a dynamic companion check, objective and frozen, run on `ref_v5f.py` at the freeze and on the implementation. Invoke each of the five one-call functions in each of its gate outcomes, with a global PY_START tool on id 5, an audit hook and a profile function armed. Require zero PY_START events and zero audit events between the consumer's CALL and its C_RETURN. That check would have caught B1.

### M5. The premise is verified on two patch levels, the version gate admits every patch level, and the "re-run the atomicity probe" duty is not a gate

- M0 (line 379) accepts any 3.12.x or 3.13.x. Line 2396 concedes that the premise "is not a documented guarantee, and a patch release could add an audit event … inside a `sys.monitoring` function". `register_callback` already has one (B1). "The prereg must re-run the atomicity probe on every patch level it lists" (line 2396) appears in no process gate (lines 1910–1933) and has no pass criterion.
- `t1` part D cannot serve as such a gate. Its two-statement control also shows 0 violations: 23,301 closes on 3.12.3 and 24,810 on 3.13.12 originally, and 21,261 and 24,289 in my re-run (`critic6/rerun_t1_*.txt`). So part D does not discriminate, and line 658's "0 violations in about 4,600 closes and 27,000 interrupts" is not evidence of anything.
- **Fix.** Add a G_ATOM process gate: the dynamic check from M4, plus t1's parts A, B and E with their controls, which must fail. Then either pin M0 to the verified patch levels, or have the first `coverage_trace()` run the audit and builtin-type self-check and refuse on failure.

---

## NOTE

- **N1. `_TOOL[0]` rebinding while traces are live is unspecified and unmodelled.**
  - Lines 500–505: "If `_TOOL[0]` is set: … keep the id if `_named(_TOOL[0])`. Otherwise, for id 4 then 3". Whether a set but foreign `_TOOL[0]` falls through to the loop appears only in X137b's outcome (line 1438).
  - If it does while another trace is live, a join (Minting, line 235) sets no local events on the new id. The joiner's sections then get no events for that function, and only X5's local-events test notes it. Openers that read the old `t` act on the stale id, and the name gate keeps that safe.
  - State the rule, and state the joiner's outcome (NOT_EXERCISED with MONITOR_LOST).
- **N2. MemoryError can land inside a one-call step.** `set_events` allocates `co_monitoring` data for executing code objects, so it can raise MemoryError after the step's pop or capture. In `_unwind_off` that leaves S set with no anchor, which U3 (line 680) says "never exists", until the next reconciliation. This matters only under OOM; qualify U1 and U3's "a fault cannot land inside" (line 678). RecursionError cannot land there (`a5`).
- **N3. X137d's wording is ambiguous** (line 1464). "call g, whose body raises and is caught" could mean caught inside g. Then g returns through PY_RETURN and is credited, which contradicts the expected NOT_EXERCISED. Write "g raises out of its body; the section body catches it", as X143 does.
- **N4. The revision summary overstates.** It says every read-decide-write on the event is one call, but `_detach`'s blind read (line 631) is a read-decide-write on the event across three statements, by design (FALSEFLAG). `_reclaim`'s `_LOST` decision also follows `_take` in a separate statement. Both are sound, but line 2226 and the brief-level summary should name them as exceptions.
- **N5. The mutant table's scope and provenance** (line 2361). The committed `mutants` branch skips the `open(X) ∥ open(X) ∥ exit…` triples, so "first violations found" is over the pairs, one triple and the extended configurations. The committed `out_m5_mutants.txt` was not produced by the committed script.
  - My re-run on 3.13 (`critic6/rerun_m5_mutants_3.13.txt`) reports `no_exiting_test` at `open(X) ∥ exit(X) ∥ exit(X)` with P8=504, where the committed file shows `open(X)+[exit(X)]` with P8=1.
  - The mutant order differs too.
  - The verdicts agree: 19 of 21 detected, with `ensure_nocount` and `prune_credit_stop` not detected.
  - Regenerate the file from the frozen script.
- **N6. Round-4 closure bookkeeping is complete.** All 58 confirmed round_4 keys, plus `found_after_round_4`, `surfaced_during_verification` and `not_confirmed`, appear in the per-finding disposition (script check). Revision 5 changes none of their dispositions except through the event path.
- **N7. Re-runs reproduce the committed outputs.**
  - `spec_rev5_eventpath.py`: identical on both versions.
  - `w5_witnesses.py`: identical except the timing-dependent `patched_sleep_calls` count.
  - `t1_onecall_atomic.py`: parts A, B, C and F have identical verdicts. The iteration counts of D and E vary; the verdicts are unchanged: one-call 0; two-statement E 169 and 210 clear.
  - `m5_modelcheck.py`: all 132 committed main rows re-run on 3.12 match to the state (`rerun_m5_main_3.12.txt`, `rerun_m5_rest_3.12.txt`). The two revision-5 triples re-run on 3.13 match exactly (537,217 / 3,081,695 / 18,848 / 73,216). The mutants re-run on 3.13 gives the same verdicts, with N5's provenance difference.
  - Running `m5_modelcheck.py main` as documented also runs revision 4's same-tracer triples, whose F0 alone is 9,904,210 states in 174 s. The committed `out_m5_main.txt` omits them, so it was not produced by the documented command.

---

## The brief's five questions

1. **The model check's fidelity and coverage.** Faithful to the M7 pseudocode for the event path and the mutex, but it assumes the premise under attack. It omits callback registration entirely, omits two of X5's note sources, never rebinds the tool id, and runs its outside parties only fault-free and without re-entry or greenlets. The configuration count is misstated (M2). One stated finding contradicts the model's own mutant run (M3).
2. **Re-runs.** Everything reproduces (N7). t1 part D does not discriminate (M5).
3. **Can an independent author freeze a deterministic exam from the text alone?** Not yet.
   - B1 puts normative sentences into `rules_v5f.json` that no implementation can meet.
   - G_HYG as written flags the reference code, so the lint needs a reading chosen by the author (M4).
   - The F13/X137e evidence claims contradict each other (M3).
   - There is no gate for the premise (M5).
   - The remaining case text is deterministic. The instruction-sweep definition, placements, subprocess rules and envelope classes leave no post-freeze judgement, apart from N3's wording.
4. **Internal contradictions.**
   - B1: lines 654, 657, 678, 819, 821, 1286, 2262 and 2263 against CPython.
   - M3: lines 500, 1465 and 2387 against line 2381 and the mutant output.
   - M4: lines 1876 and 1880 against 417, 609, 622, 641 and 652; lines 654 and 2397 against 439.
   - M2: 35 against 33 configurations.
   - B1: the M5 heading "always returns False" against a raising audit hook at X5.
5. **Can G_HYG enforce the pipeline shape objectively?** The shape, yes, once its name lists match the code (M4). The property it is used to certify, that no Python code runs inside a step, no: a static lint cannot see audit events inside C functions or wrappers bound at run time. A dynamic companion gate is needed (M4, M5).

**Verdict: NOT_READY.** One BLOCKER-for-freeze (B1) and five MUST-FIX items (M1–M5). All six are fixable with text, one runtime type check (M1) and one dynamic gate (M4/M5). The core U1 and U3 argument for `_unwind_on` and `_unwind_off` survives the attack once M1's check is in place.
