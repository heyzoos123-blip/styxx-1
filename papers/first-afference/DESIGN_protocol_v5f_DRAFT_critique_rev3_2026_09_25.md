# Adversarial critique of `DESIGN_protocol_v5f_DRAFT_2026_09_25.md`, revision 3

**Verdict: NOT_READY.** 1 BLOCKER-for-freeze, 6 MUST-FIX, 7 NOTE.

Revision 3's own changes reproduce as claimed. `_unwind_off`'s one-line test-and-clear really is atomic against thread
switches in uninstrumented code on 3.12.3 and 3.13.12. `_commit` inside the `try` removes the MF2 fault windows. The
four new witnesses separate the spec from their mutants in the model. The problems are next to those changes:

- the model check and the stress test never run a tracer's exit concurrently with an open or close *of that same
  tracer*. That race, which the spec itself names as supported (lines 145, 304, 1070, 848), has two defects:
  - B1: a permanent `_ANCHORS` leak after a completed exit, fault-free and naturally reachable;
  - MF2: a false MONITOR_LOST;
- the list of instruments that can split the test-and-clear leaves out the ones the spec says coexist: pure-Python
  profilers, cProfile with a Python timer, CALL-event tools, and BRANCH tools on 3.12 (MF1);
- G_FI still leaves the fault-point set and the faulted thread to the exam author, and C5 can fail a correct
  implementation (MF3, MF4, MF6);
- the X145 witness text does not say when the body raises on the mutant path (MF5).

## How this was checked
- I read revision 3 (1,969 lines), the three earlier critiques' conclusions, `rev3/mech3.py` and the rev3 probes, and
  round 4 of `protocol_v5_redteam_audit.json`.
- I re-ran w1, c5r3, c6r3 and c8r3 on `rt3/venv3.12` (3.12.3) and `rt3/venv3.13` (3.13.12). Their sorted output is
  identical to `rev3/out_*.txt`. q1 at 1M iterations: 0 splits for all three shapes, and 84–116 in the control. m1
  reproduces its table exactly. Re-run outputs are in `critic4/rerun/`.
- New probes are in `scratchpad/v5f/critic4/` (a1–a6, outputs `out_a*.txt`). All run against a copy of `mech3.py`,
  except a1 and a5, which test CPython itself. No implementation exists, so "model" means `mech3.py`.
- Line numbers refer to the revision-3 document.

## BLOCKER-for-freeze

### B1. An open racing its tracer's exit leaves `_ANCHORS[None]` registered for the rest of the process: PY_UNWIND is never cleared again
**Where:** `_commit` (lines 560–567, `_ANCHORS[o.frame] = o`); `_detach` (lines 570–577: `fr = o.frame`, then `o.frame = None`); At open step 8 (line 304); #20 (line 1070); I3 (line 739); U3/U4 (lines 600–605); C5 (line 1679); G_SIG poison (lines 1712–1713).

**The interleaving.** No fault is needed.
1. T1 passes `_open` step 2, the tracer not yet exiting, and appends o (step 6).
2. The main thread's exit runs X1, X2 and X3. X3's `_detach(o)` claims o, finds no anchor to pop, and sets
   `o.frame = None`.
3. T1 runs `_commit(o)` and stores `_ANCHORS[o.frame] = o`, which is `_ANCHORS[None] = o`.
4. Step 8's race re-check calls `_detach(o)`. So do the `finally` and any later prune. Each reads `fr = o.frame`,
   which is None, and skips the pop.

After that, `_ANCHORS` is never empty again, so no `_unwind_off()` in the process ever clears PY_UNWIND.

The switch in step 2 needs no fault. It can land at any eval-breaker point between the append and the store: `_run`'s
call of `_commit` (RESUME), or after any of `_unwind_on`'s three C calls. An exam's id-3 tool can also force it
deterministically at PY_START of `_commit`.

`critic4/a3_open_races_exit_leaks_anchor.py`:

| run | 3.12.3 | 3.13.12 |
|---|---|---|
| mech3 hooks at `commit:0`, `commit:1`, `on:read` | leak at all 3 | leak at all 3 |
| the same, with the spec's step 8 added | leak at all 3 (`run()` raises TRACE_INACTIVE) | leak at all 3 (`run()` raises TRACE_INACTIVE) |
| natural, no hooks, 1 µs switch interval | 47 of 20,000 races | 55 of 20,000 races |

In every hooked run, after exit and after a later clean trace, `anchors 1`, the key is `NoneType`, and
`global_events 4096`.

This is not new in revision 3. `critic4/a3b_rev2_same_leak.py` (revision 2, `mech3.REV3=False`) leaks 39 and 43 of
20,000, keyed by a live `_run` frame. It still blocks the freeze:

- **Round-1–3 and round-4 blocker classes reopen, fault-free.**
  - R2-B3, "hook persists after a completed exit": the process-wide PY_UNWIND callback outlives the trace. Revision
    2's reclaim was added to close exactly this for the freed-id path (line 985).
  - Round-4 "async-exception-in-close-leaks-threads-registry": a machinery registry leaks past exit into later
    tracers.
- **Later traces change.**
  - `_on_entry`'s `if not _ANCHORS: return` (line 318) never short-circuits again. Every later hit outside sections
    stores and publishes `'u'`/`'d'` counts, which it would not otherwise do. That is a later trace whose record
    differs from its fault-free record: G_SIG's "poison".
  - L-DELIVERY becomes permanent outside every section. G_SIG cell (a) is gated at 0 lost handlers there, and H10
    asserts `global_events == 0` before arming.
- **The spec's claims about this state are false.** I3's "clear if no anchor is registered", U3, and C5's
  `anchors == 0` are all wrong in this state, and every later leftover snapshot depends on whether the race happened
  earlier in the process.
- **No invariant or witness can catch it.** The model check (`m1`: two sections plus a retire) and the stress (`s1`:
  its fourth thread enters and exits *other* tracers) never run an exit against its own tracer's open.

**Fix (small, mechanism).**
- Stop keying the pop on a field that `_detach` nulls. Either:
  - pass the anchor frame to `_commit` explicitly and have `_detach` pop by a never-nulled `o.anchor`, with the pop
    guarded by `_ANCHORS.get(key) is o`; or
  - in `_detach`, set `o.frame = None` *before* the pop, and in `_commit`, read `fr = o.frame`, refuse if it is None,
    store `_ANCHORS[fr] = o`, then re-test `o.frame is None` and pop plus `_unwind_off()` if so.
- Add a witness: the id-3 tool blocks T1 at PY_START of `_commit` until exit's X3 has run. Expected: TRACE_INACTIVE,
  with `anchors == 0` and `global_events == 0` after exit.
- Add an exit-versus-own-open interleaving to m1.

## MUST-FIX

### MF1. More instruments than the spec lists run Python code inside `_unwind_off`'s test-and-clear, including tools the spec says coexist; U1, "What is lost", I6, C4 and C8 are false with them
**Where:** line 595 ("only loads lie between the test and the call"); U1 (line 598, "on every interleaving"); "What is lost" (line 606); line 608 ("Only an instruction-level instrument does this"); I6 (line 746); C4 (line 1678); C8; coexistence (line 822: "pure-Python setprofile/settrace tools" coexist; V33 cProfile; V48); exception sources (line 719, which itself names setprofile functions).

`critic4/a1_what_splits_test_and_clear.py` puts a callback in the `D or len(D)` shape that pokes D only when it runs
after the test (`f_lasti` past the conditional jump). Splits in 5 trials:

| instrument | 3.12.3 | 3.13.12 |
|---|---|---|
| `sys.setprofile(pure-Python fn)`, the V48 shape (`c_call`) | 5/5 | 5/5 |
| `threading.setprofile_all_threads` | 5/5 | 5/5 |
| `cProfile.Profile(timer=<Python fn>)` | 5/5 | 5/5 |
| sys.monitoring CALL, local or global | 5/5 | 5/5 |
| BRANCH | 5/5 | **0/5** |
| INSTRUCTION, `f_trace_opcodes` (already listed) | 5/5, 4/5 | 5/5, 5/5 |
| LINE (monitoring or settrace), JUMP, C_RETURN with no CALL callback | 0/5 | 0/5 |

The BRANCH row is a real 3.12/3.13 difference.

`critic4/a2_profiler_breaks_U1.py`, deterministic: T2 closes B under a trivial pure-Python profile function. At
`c_call` of `set_events`, T1 commits A and enters its body; at `c_return`, A's body raises t. Result: A `None` (t lost)
and MONITOR_LOST True, on both versions. So U1 is false, and a fault-free record gets MONITOR_LOST, whenever a
profiler is set on a closing thread. The natural rate with the model's slow paths was 0 in about 500 sections per run,
so this is a spec-truth problem, not a frequent one.

**Fix.**
- Replace "instruction-level instrument" everywhere (lines 595, 598, 606, 608, 746, 1678, C8) with "any Python-level
  callback that CPython runs at an instruction inside the expression". Enumerate:
  - INSTRUCTION;
  - CALL (C_RETURN needs CALL enabled; a CALL *callback* splits it);
  - BRANCH on 3.12;
  - `f_trace_opcodes`;
  - a setprofile or `setprofile_all_threads` function;
  - cProfile with a Python timer.
- State U1 conditional on none of these being active on a thread that closes, retires or reconciles, and let I6
  admit MONITOR_LOST under them.
- rules_v5f.json encodes I6 as atoms, and the fuzzer's grammar includes "lower-id fault tools". If any of those tools
  uses CALL events, the current text makes a correct implementation fail.

### MF2. `_detach`'s UNWIND_LOST test reads the anchor before two C calls, so a close racing its tracer's exit sets a false MONITOR_LOST
**Where:** line 573; line 606 ("a false `UNWIND_LOST` needs S clear under an armed, registered anchor, which U1 excludes"); I6 (line 746); M5 X5's flag test.

The test is `o.armed and _ANCHORS.get(fr) is o and _ours() and not (get_events & PY_UNWIND)`. That is revision 2's
`_unwind_off` order, which revision 3 fixed there and not here.
1. T1 closes A and passes the anchor test.
2. A switch lands at `_ours`'s RESUME or after `get_tool`. Exit's X3 on the main thread re-detaches A, pops it, and
   its `_unwind_off()` clears S. That clear is legitimate.
3. T1 reads S clear and flags `UNWIND_LOST`.

`critic4/a4_detach_check_false_lost.py`, with the model's `ours` hook (= PY_START of `_ours`, which the id-3 tool can
also block): spec order MONITOR_LOST True; events-first order False; both versions, fault-free. In the spec, the note
lands only if T1's flag precedes X5's read, so on this supported race (line 1070) the note is timing-dependent.

**Fix.** Read the event first and test the anchor last:
`if o.armed and _ours() and not (get_events(_TOOL[0]) & PY_UNWIND) and _ANCHORS.get(fr) is o:`. A clear read while
the anchor is still registered is a true loss; if the anchor was popped, `get` misses. Add the order to G_HYG and a
mutant row (witness: the a4 interleaving).

### MF3. G_FI's fault-point set and faulted thread are undefined
**Where:** G_FI (line 1650, "on two threads: every fault point is clean"); H6 (line 1428, "each executed instruction, one point per run"); X140 ("the first time that offset executes"); "frozen stride" (lines 1590, 1734, never defined); injector thread filter (line 1207, "the case's own thread"); C2 (line 1671); C6.

An exam author has to decide all of the following, and each changes the gate's power:
- Is a point a static `(code, offset)` or a dynamic occurrence (the k-th execution)? Which occurrence of an offset
  inside a loop?
- What is the stride, and what does it stride over?
- In the two-thread scenario, which thread is faulted? The injector filter admits only "the case's own thread".
- If the worker thread is faulted, the injected exception ends that thread through `threading.excepthook`. C2's three
  alternatives do not include that path, though C6 implies it is allowed.
- The two-thread scenario's own timing (a close or open concurrent with an exit) makes the *baseline*
  nondeterministic (B1, MF2), and C8 compares against it.

**Fix.**
- Define a point as `(faultpoints key, offset, k)`, with k ≤ a frozen bound, on a named thread.
- Define the stride.
- Add a fourth C2 alternative: "a scenario thread ended with it (recorded by a frozen `threading.excepthook`)".
- Require the scenario to join every thread before any exit, so its baseline is deterministic.

### MF4. Generator-expression code objects are outside `_v5_faultpoints()`, so the sweep, X140 and G_HYG are ambiguous about them
**Where:** M5 X5 step 3 (line 495, `tuple(h for h in m.holders if h is not core)`); M10 (lines 665–667, "no nested function, lambda or other class"); G_FI; X140; G_COVER's executable-line set.

On 3.12 and 3.13 a generator expression has its own code object; PEP 709 inlines only list, set and dict
comprehensions. The spec's own pseudocode has one inside exit's transaction. Its bytecode, including a JUMP_BACKWARD,
is:
- never injected, because the injector instruments only `_v5_faultpoints()` code;
- not in X140's back-edge list.

Its lines count as covered through the outer function's line.

The exam author has to decide whether G_HYG's "no nested function" forbids it. **Fix:** either forbid generator
expressions in the region (G_HYG, stated), or define the injector, X140 and G_COVER targets as each faultpoint code
plus its nested code objects, recursively through `co_consts`.

### MF5. X145's text does not fix when the body raises on the mutant path; the model witness uses a 0.2 s timeout
**Where:** X145 (line 1332); `rev3/w1_rev3_witnesses.py` `x145a` (`th2.join(0.2)`, "T2 either finishes (spec) or blocks after its clear (mutant)").

Under the spec, T2 never clears, so nothing tells A's body when to call t. Under the mutant, t must run *after* T2's
clear. The frozen text says only "until A's body has called t". The model witness decides this with a 0.2 s join. On a
loaded machine that can let the mutant survive, and the result is a WITNESS_MISMATCH/UNWITNESSED row that nobody may
reclassify after the freeze.

**Fix.** Have A's body wait until the id-3 tool reports either:
- T2 blocked at the C_RETURN of `set_events`; or
- PY_RETURN of `_unwind_off` on T2.

Apply the same to (b)'s "as in (a)". Also state that the tool registers a C_RETURN callback and **no CALL callback**.
Per a1, a CALL callback runs Python inside the expression, which makes the witness an MF1 instrument.

### MF6. C5 compares `pending` with `S0`, but a fault-free scenario can leave pending entries on the background tracer's mint
**Where:** C5 (line 1679, "`_v5_state()` equals `S0` except `cut` and `tool`"); M10 `pending` (line 656); line 318; line 773 ("stays until `_retire` clears it").

An entry stored while *some* anchor is registered anywhere, for a frame that raises after the last anchor closed (S
clear, so no PY_UNWIND), stays until retire. The background tracer holds the shared mint through the whole sweep, so
it is never retired.

`critic4/a6_pending_left_fault_free.py`: 1 pending entry left, with anchors 0 and events 0, fault-free, on both
versions. The background variant runs the background tracer's sections concurrently with a scenario that has raising
and generator targets. So C5 can fail at every point for a correct implementation.

**Fix.** Either:
- compare `pending` against the baseline's after-state B, not S0; or
- exclude the background mint's `pending` from C5 and require the scenario never to call a target outside its own
  sections.

## NOTE

- **N1. `_ours()` runs a foreign `__eq__`** (line 587; contradicts line 721, "no Python `__hash__` or `__eq__`
  runs").
  - `get_tool(id) == _TOOL_NAME` has the other tool's name object as its left operand. `use_tool_id` accepts a str
    subclass, and its `__eq__` can return True (`critic4/a5_tool_name_eq.py`, both versions).
  - The same test in `_ensure_tool` then adopts a foreign id (L-MONITOR). This is contrived.
  - Fix: `type(n) is str and n == _TOOL_NAME`.
- **N2. U1 (line 598) says only exit's X3 detaches a live section's anchor.** A reconciliation's `_prune` from another
  thread does too (M3). It is harmless for credit, because `by_code` is emptied first, but the sentence should say so.
- **N3. The exception lists disagree.** Line 608 includes "a third-party INSTRUCTION tool"; I6 (line 746) and C4
  (line 1678) omit it, and C4 names only the injector. Unify them with MF1's list.
- **N4. C4's MONITOR_LOST allowance is always granted.** The sweep covers every faultpoint code, `_unwind_off`
  included, so "only if the injector was armed on `_unwind_off` during the sweep" is always true. Evaluate C4 per
  sub-sweep: the points on `_unwind_off` versus the rest.
- **N5. Is step 8's TRACE_INACTIVE recorded?** Line 848 says "recorded if the tracer was entered", and line 296's
  heading says the same. `_commit`'s code (line 566) raises without appending to `core.problems`. An append from a
  racing T1 can land after X7, so the record also depends on timing. Say which, and pin #20's outcome set (line
  1070) as a frozen case with both outcomes allowed.
- **N6. `_v5_state()["mints"]` is "a sorted list" of dicts (line 656), with no sort key.** Snapshot equality in the
  leftover checks and C5 needs one, for example by `target`.
- **N7. "Mutation mode" (lines 1519, 1589) is undefined, and so is process isolation for SM1 admission runs.** The
  cut is process-monotone (MF4 of rev 2). Condition 2 (ref) and condition 3 (ref+W) of a rebinding witness in one
  process reuse the "fresh" wrapper. State that each admission run and each SM2 mutant run is a fresh process.

## Answers to the five questions
1. **Mechanism.**
   - The one-line test-and-clear is atomic on 3.12.3 and 3.13.12 against switches, signals, gc and asynchronous
     exceptions: q1 re-run, and a1's "none" row.
   - It is not atomic under profilers, CALL tools or 3.12 BRANCH tools (MF1).
   - `_commit` inside the `try` is sound for faults. For races it opens B1, because `o.frame` is read at the store.
   - U1 fails under MF1's instruments. U3, U4 and I3 fail under B1. The "no false UNWIND_LOST" claim fails under
     MF2.
   - 3.12 and 3.13 differ only in the BRANCH row. The `await` throw-path difference is already stated.
2. **Definitions.**
   - C1–C9 are close, but the point set, the faulted thread and C2's thread path are open (MF3), and C5's `pending` is
     wrong (MF6).
   - G_COVER's measurement is complete, except for generator-expression code (MF4).
   - Poison and the leftover snapshot are defined, but poison and C5 inherit B1.
   - The rebinding rules are complete for one exam process (N7).
3. **Open classes.**
   - B1 reopens R2-B3, a leak after a completed exit, and round 4's leaked-registry class, fault-free, with no hang
     and no over-credit.
   - No over-credit path was found: `_ANCHORS[None]` is never met on a frame chain.
4. **Contradictions.** Lines 606 and 608 against a1, a2 and a4; line 721 against N1; lines 746 and 1678 against 608
   (N3); line 848 against 566 (N5).
5. **Witnesses.**
   - X143b, X143c and X144 are deterministic as written, with the id-3 PY_START/PY_RETURN tool and the injector's
     `_v5_state()` landing rule.
   - X145 needs MF5's handshake to be deterministic on its mutant path.

## Probes (`scratchpad/v5f/critic4/`)
| file | shows |
|---|---|
| `a1_what_splits_test_and_clear.py` | which instruments run Python inside the `D or call(...)` shape, 3.12.3 vs 3.13.12 (MF1) |
| `a2_profiler_breaks_U1.py` | U1 broken and MONITOR_LOST under a pure-Python profiler on the closer (MF1) |
| `a3_open_races_exit_leaks_anchor.py` | `_ANCHORS[None]` permanent leak: hooked and natural, with and without step 8 (B1) |
| `a3b_rev2_same_leak.py` | the same leak in revision 2, frame-keyed (B1) |
| `a4_detach_check_false_lost.py` | false MONITOR_LOST from `_detach`'s check order, and the fix (MF2) |
| `a5_tool_name_eq.py` | a str-subclass tool name runs `__eq__` in `_ours()` (N1) |
| `a6_pending_left_fault_free.py` | a fault-free pending entry left on a held mint (MF6) |
| `rerun/` | re-runs of w1, c5r3, c6r3, c8r3, q1 and m1; all match revision 3's outputs |
