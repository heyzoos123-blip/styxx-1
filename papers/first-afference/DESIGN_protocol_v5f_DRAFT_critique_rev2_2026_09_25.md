# Adversarial critique of `DESIGN_protocol_v5f_DRAFT_2026_09_25.md`, revision 2

**Verdict: NOT_READY.** 0 BLOCKER-for-freeze, 8 MUST-FIX, 12 NOTE.

Revision 2 closes what it set out to close. `_run_once` in the cut, the E2 shareable-code refusal, freed-id
reclamation, the section-scoped PY_UNWIND and the G_COVER driver all reproduce as claimed, on 3.12.3 and 3.13.12.
None of them lets a count be over-credited. The problems are in what those fixes leave around them:

- two normative claims about the unwind scope are false: I3, and "in every interleaving an open section ends with
  the event set" (MF1, MF2);
- a new named witness is vacuous where the harness rules place it (MF3);
- the process-monotone cut makes the rebinding cases order-dependent, and one fixture can disable tracing for the
  whole exam process (MF4);
- three gate definitions are left for the exam author to make up: C1–C8, G_COVER's instruments and measurement, and
  G_FI (e) (MF5–MF7);
- one text contradiction left over from revision 1 (MF8).

All but MF1 and MF2 are text fixes. MF1 and MF2 each need one small mechanism change. The exam author cannot settle
any of the eight: under G_INDEP they are spec decisions, and rules_v5f.json has to encode I3 and I6 as rule atoms.
So the brief should wait for one more revision. Nothing here calls for a redesign.

## How this was checked
- I read the whole document (1,798 lines), the rev-1 critique, and round 4 of `protocol_v5_redteam_audit.json`.
- I re-ran the revision-2 probes on `rt3/venv3.12` (3.12.3) and `rt3/venv3.13` (3.13.12): p1, p1b, p2, p3, p13, p14,
  p4b and p4c. Each matches its row, except the one scan-cost figure in N9. The rest of the re-run is in
  `critic3/rerun_rev2_probes.txt`. It was still running when this was written; see "Probe re-run status".
- I wrote 11 new probes, all against the revision-2 event-path model `rev2/mech2.py`, in
  `scratchpad/v5f/critic3/` (listed at the end). "Model" means that model, not an implementation. No implementation
  exists.
- Line numbers refer to the revision-2 document.

## BLOCKER-for-freeze
None. Every gate below can be attained, and every case can be written, once the MUST-FIX text is settled.

## MUST-FIX

### MF1. `_retire` step 6 clears PY_UNWIND with no re-check, so "every interleaving" and I3 are false
**Where:** M3 `_retire` step 6 (line 440); "The unwind scope" (line 573, "In every interleaving an open section ends
with the event set. One window remains …"); I3 (line 689).

Step 6 runs under the mutex. `_unwind_on` never takes the mutex. The interleaving:
1. Tracer X's exit, in `_retire`, sees `_ANCHORS` empty.
2. Tracer Y, still active, opens section B on another thread. Its two `_unwind_on()` calls set the event and
   re-check it.
3. X's step 6 then clears the event.

Nothing re-sets it until the next open or close anywhere in the process. So B runs its whole life without PY_UNWIND.
This is not the single-confirmation window that line 573 describes.

`critic3/c5_retire_step6_race.py`, both versions:
- no race: `{'B': {'t': 1}}`, no MONITOR_LOST;
- step 6 races: `{}`, MONITOR_LOST True, global events 0 while B is open.

The loss is under-credit (NOT_EXERCISED for B's gate) plus a MONITOR_LOST note, so I1 holds. But the two sentences
are false, and so is I3's "set only while some anchor is registered". The rev-2 toggle-race evidence does not cover
this path: `rev2/p4c_toggle_race.py` uses one tracer, so step 6 never runs mid-run. Its own output
(`rev2/out_p4c.txt`) also shows only 880–2,267 clears in 100,000 sections, so it exercised the closer's window about
a thousand times, not 100,000 times.

**Fix.** Give step 6 the same clear-then-re-check as `_unwind_off`, or call `_unwind_off()` there. Then restate
line 573 and I3 with the remaining windows named.

### MF2. A fault in `_open` between the first `_unwind_on()` and the anchor commit brings L-DELIVERY back outside every section, and reconciliation does not repair it
**Where:** OPEN prefix (line 717: "the event is on with no anchor, until the next close or reconciliation clears
it"); I3 (line 689: "a close or reconciliation repairs a stale set"); M3 (line 440); H10 and G_SIG cell (a)
(lines 1098, 1369).

Reconciliation clears the event only inside `_retire`, and `_retire` runs only for a mint that has lost its last
holder. The usual case is an asynchronous exception (a Timeout or KeyboardInterrupt) landing in `_open`, caught by the
harness, which carries on. There the tracer stays active, no mint retires, and the process-wide callback stays on
with `_ANCHORS` empty. It stays until the next section closes anywhere, or until the trace exits: X3 detaches the
inert appended opening, and its `_unwind_off()` clears the event.

`critic3/c7_stale_unwind_after_open_fault.py` uses p4_unwind_scope's 20 µs flood, 300,000 iterations, a trace
active and no section open:

| | 3.12.3 | 3.13.12 |
|---|---|---|
| lost handlers, fault-free | 0 | 0 |
| lost handlers after one such fault | 51,375 | 39,373 |

In both runs `anchors=0` and `global_events=4096` (PY_UNWIND) after the fault.

So revision 2's headline result, "0 lost handlers outside sections", holds only until the first such fault. That
fault is exactly the flood's fault class. I3 as written is false, and "for a while" in the OPEN prefix has no bound.

**Fix.**
- Make every reconciliation end with `_unwind_off()`, which is idempotent and re-checks, not only `_retire`.
- State the true bound: until the next close, open-with-clear, transaction or exit.
- Say in H10/G_SIG that cell (a)'s trace opens no section, so the gate cannot depend on this window.
- Better: order `_open` so that no single fault leaves a set event with no anchor, for example commit first and then
  set, keeping the closer's re-check. Weigh that against the lost confirmation it trades for.

### MF3. X143 is vacuous where the harness rules place it
**Where:** harness placement (lines 1128–1134); X143 (line 1269); the SM1 row "the re-check after the anchor
commit → X143" (line 1386); the leftover snapshot (line 1139).

X143 is not in the main-thread-before-self-trace list, so it runs inside the self-trace as
`cov.run(<gate section>, case)`. That anchor stays registered for the whole case, and `_ANCHORS` is process-global.
So B is never "the last registered anchor". `_unwind_off` returns early, the event is never cleared, and the mutant
with no re-check scores the same as the spec.

`critic3/c6_x143_inside_selftrace.py`, both versions:
- before the self-trace: spec `{'A': {'t': 1}}`, mutant `{}`;
- inside the self-trace: spec `{'A': {'t': 1}}`, mutant `{'A': {'t': 1}}`.

SM1 admission would mark the row UNWITNESSED, but only after the author has already followed the spec's placement.

**Fix.**
- Add X143 to the before-self-trace list. In general, add every case whose premise is "no other section open"
  (X137c for its `global_events` effect, and any H10-like case).
- Say where the leftover snapshot is taken: outside the case's self-trace section. X137c leaves `global_events` 0
  while the self-trace's case anchor is still registered, so a snapshot taken inside that section would fail its
  leftover check.

### MF4. The process-monotone cut makes rebinding cases order-dependent, and X34b's fixture can refuse the whole exam process
**Where:** X34b (line 1207), X35c (line 1211), X141 (line 1265), V61 (line 1305), V64, X65g, X141c, R18(b); harness
hygiene (line 1135); E2 (line 449); the CUT_UNAVAILABLE row (line 787).

1. E2 scans only codes *new to the cut*, and a code stays a cut code for the rest of the process. If an earlier case
   (V61) put a fixture wrapper W's code into the cut, a later case that reuses W flips.
   `critic3/c8_cut_order_dependence.py`, both versions:
   - in a fresh process: X35c gives CUT_UNAVAILABLE and X141 gives CUT_MOVED;
   - after V61 with the same W: X35c is **accepted** and X141 has **no CUT_MOVED**.

   All of these cases run in one process, on the main thread before the self-trace.
2. X34b's fixture is `FunctionType(Handle._run.__code__, vars(fx))`. The stdlib codes are new to the cut at the
   process's first `coverage_trace()`. If the clone is alive then, for example because fixture modules are imported
   at exam start-up, the stdlib `Handle._run` code is "shareable" and never enters the cut. Every later
   `coverage_trace()` in the process then refuses CUT_UNAVAILABLE for as long as the clone lives.
   `critic3/c9_x34b_fixture_poisons_first_e2.py`, both versions: `['ok','ok','ok']` when the clone is made after the
   first call, `['CUT_UNAVAILABLE'] * 3` when it is made before.

   The same holds for any user process holding such a clone at first construction. That is not disclosed.

**Fix.**
- In the harness rules, require every rebinding case to use a wrapper whose code has never been bound or scanned in
  that process: a fresh top-level def per case.
- Require X34b's clone to be created after the process's first `coverage_trace()` and dropped at the end of the case.
- Disclose item 2 under #21 and in the CUT_UNAVAILABLE row.

### MF5. G_FI's invariants C1–C8 are not defined anywhere in the spec
**Where:** G_FI (b) (line 1587); H6 (line 1365); `crash_sweep_v5f.py` (line 1442); the SM1 crash rows (lines
1486–1492: M2/M4/M7 → C7, M3/M5/M6 → C5, M1 → C3).

The only definitions are in D1's `crashcons/t_crash_sweep.py`. They read private names (`V.reconcile_now()`,
`V.leftovers()`, `V._TH`), check `sys.getprofile()`, and assume publish-at-PY_START. The SM1 rows are killed "only if
that invariant is among the sweep's failures", so what each C-number means is load-bearing, and the exam author
would be defining it. MF2 shows that a literal port of I3 into a C-check would be false.

**Fix.** List C1–C9 in outcome terms over the public API, `_v5_state()` and I1–I6, including when the check runs
(before or after dropping the faulted facades), and freeze that list with this spec.

### MF6. G_COVER's instruments and its measurement rule are under-specified
**Where:** G_COVER (lines 1613–1628), the process gate (line 1649).
- "The exam's fast mode" is defined nowhere in v5f.
- The spec does not say whether the measurement covers:
  - the fresh-subprocess cases (X36, the X137 free variant, X137b, X142);
  - the before-self-trace cases.

  `_reclaim`'s body, the MONITOR_BUSY raise and `_ensure_tool`'s id-3 fallback are reached only in those
  subprocesses. The crash sweep and fuzzer never free or take tool ids (their grammar, line 1443). If subprocesses
  are not measured, those spec-required lines must be "folded" to pass.
- "A LINE-event tool and, in a separate process, settrace" (line 1627) does not say whether a line must be seen by
  one measurement or by both.
- If the settrace pass runs the crash sweep, F1 applies: settrace silences the id-5 injector. The sweep's self-check
  then voids the run, and fault-only lines are never reached in that pass.

**Fix.**
- Define the fast mode.
- Say that subprocess and main-thread placements are measured, with the subprocess coverage method named.
- Say that a line counts if the LINE-tool measurement sees it, and restrict the settrace pass to the direct-call
  driver, or drop it.

### MF7. G_FI (e) and I6 exclude outcomes a correct implementation can produce
**Where:** G_FI (e) (line 1590); I6 (line 696).
- **(e)** requires the injected exception to reach "the caller of the facade call". D1's C2, which (e) replaces,
  also allowed CPython's unraisable hook. Suppose a fault lands in `_detach` under `_run_async`'s `finally` while a
  suspended coroutine section is finalized: GeneratorExit from `coro.close()` at dealloc, which a run_async or
  hopped-coroutine scenario can produce. That exception goes to `sys.unraisablehook` and cannot satisfy (e).
- **I6** allows notes ⊆ fault-free ∪ {OPEN_AT_EXIT}. But a fault in `_unwind_off` between `set_events(0)` and its
  re-check, or in `_open` between the commit and the second `_unwind_on()`, together with another thread's
  open or close, can leave an open section without the event. That section's close then sets UNWIND_LOST, which
  gives MONITOR_LOST. Line 573 already admits a *fault-free* false MONITOR_LOST in the toggle window.

**Fix.** Put the unraisable-hook alternative back into (e), and add MONITOR_LOST to I6's allowed notes, or show that
it cannot arise.

### MF8. The version-policy table still says PY_UNWIND is "set only while a mint exists"
**Where:** line 756, against M7 (line 569), I3, L-DELIVERY and the Cost table. That is the revision-1 scope. Replace
it with "only while some section is open".

## NOTE
- **N1. The `<locals>` clause refuses a real library, and gains no soundness there.** aiodebug 2.3.0's
  `log_slow_callbacks.enable()` binds `Handle._run` to `enable.<locals>.instrumented`, which calls the original
  `Handle._run`. With it enabled, every `coverage_trace()` in the process refuses CUT_UNAVAILABLE. Without the check,
  X65c-shaped dispatch is still `dispatched` and B is credited, because dispatch passes the original `Handle._run`
  code and `_run_once` (`critic3/c10_aiodebug_overblock.py`, both versions). The remedy text, "bind a dedicated
  module-level function", cannot be applied to a third-party patch. At least name this shape under #21.
- **N2. E2's gc scan is blind to frozen objects and sees dead ones.** A live twin moved to the permanent generation by
  `gc.freeze()` is not found, so the code is accepted into the cut. A dead twin in an uncollected cycle is found, so
  the result depends on gc timing (`critic3/c1_freeze_hides_twin.py`, both versions). The effect is under-credit or
  a spurious refusal, never over-credit. The CUT_UNAVAILABLE row's "another live function has it" (line 787) is
  inaccurate in both directions.
- **N3. Reclaim's premise can be false.** "The events on the id are styxx's own, left by the free" (line 423) does
  not hold after free → another tool's `use_tool_id` → that tool's free. The reclaimed id then carries the other
  tool's leftover callbacks and local events under styxx's name. Contrived. Reword.
- **N4. "That code is either …" (line 338) overclaims.** A section opened in a task that drains its running loop's
  `_ready` queue inline is credited, with neither R18 shape (`critic3/c11_manual_ready_drain.py`). L-WHERE's "queues
  drained inline" and R02 cover it, so this is a wording fix, not a hole.
- **N5. The injector rules forbid settrace/setprofile but not DISABLE-returning monitoring tools.** With a LINE tool
  returning DISABLE, as coverage.py's sysmon core does and as V50 runs, the id-5 injector misses 3 of 17 (3.12) and
  3 of 15 (3.13) offsets on a code object's first execution (`critic3/c3_line_disable_blinds_injector.py`). The
  styxx event set itself is unaffected by settrace (`critic3/c4_settrace_vs_local_events.py`).
- **N6. X65g must make the job the first handle W dispatches.** W restores the binding at its first dispatch. If any
  other handle runs first, f is dispatched through the original `Handle._run`, and X65g no longer witnesses
  "`_run_once` dropped from the cut". SM1 would flag it UNWITNESSED; say it in the case text.
- **N7. The G_COVER driver needs a trampoline.** `_on_entry` and `_on_exit` read `sys._getframe(1)`. The driver
  must call both from one trampoline frame whose `f_globals` is the target's module dict, or every driver call
  records CLONE_CALLED into the real trace. `rev2/p5_cover_driver.py` does this (`fake_target_frame`), but the spec
  text does not say so.
- **N8. G_SIG's "0 poison" is undefined.** The "wrong result" definition (line 1597) already covers later traces;
  equate the two or define poison.
- **N9. The scan cost is environment-dependent.** `rev2/p2_shared_cut.py` measured 4.0–4.5 ms (100k objects) and
  20.1–21.5 ms (1M) here, against the cited 1.6–2.1 and 13.6–17.1 ms. It is reported, not gated.
- **N10. V47 forks from a multi-threaded process** (the self-trace plus watchdog threads). 3.12+ warns, and a child
  can deadlock on a lock held at fork. Run V47 in a subprocess or before any thread starts.
- **N11. The MONITOR_LOST note after a reload lands on whichever trace exits first.** It can be a trace entered after
  the reload that lost nothing. Notes never refuse; say so in N8's text.
- **N12. G_COVER's "fold onto its guard's line" escape** turns the gate into line-level coverage, where any
  unreached branch passes once reformatted. Accept that in writing, or require branch coverage for the named list.

## The five checks

**(1) The revision-2 resolutions, re-run and attacked.**

| fix | probe re-run | attack | result |
|---|---|---|---|
| `_run_once` in the cut, and its binding in `_cut_ok()` (M1) | p1, p1b: identical on both versions | A1, A2 and R17 are dispatched; regressions hold; manual `_ready` drain (c11); nest_asyncio 1.6.0 source (patches the concrete loop class, dispatches via `handle._run()`) | holds; N4, N6 |
| E2 shareable-code refusal (M2) | p2: identical, cost higher (N9) | frozen twin, dead twin (c1); cut order across cases (c8); X34b clone before first construction (c9); aiodebug (c10) | fail-closed, but MF4, N1, N2 |
| Freed-id reclamation (M3) | p3: identical | free → taken → freed (reading) | holds; N3 |
| Section-scoped PY_UNWIND and its toggle race (M4) | p13, p14, p4b, p4c: identical | `_retire` step 6 race (c5); fault in `_open` before the commit (c7); X143 placement (c6) | MF1, MF2, MF3, MF7 |
| G_COVER driver (BF1) | p5: identical | trampoline requirement; subprocess and settrace measurement; DISABLE interplay (c3) | MF6, N5, N7 |

**(2) Round-4 keys and round 1–3 blocker classes.** No round-4 key is reopened, and no round 1–3 blocker class
reopens as over-credit.
- MF2 re-extends L-DELIVERY after a fault, but only until the next close or the trace's exit, never past a completed
  exit, so R2-B3 stays closed.
- The R1-B3 attribution class stays closed up to R18, and N4 is L-WHERE.

**(3) Gates needing judgement after the freeze.** None as written. Three are under-defined *before* the freeze, and
the exam author would otherwise define them: G_FI via C1–C8 (MF5), G_COVER's instruments (MF6), and G_SIG "poison"
(N8).

**(4) Cases that cannot be written or run deterministically.**
- X143 as placed (MF3).
- X35c, X141 and X34b depend on order in one process (MF4).
- X65g depends on dispatch order (N6).
- V47 depends on fork safety (N10).
- The rest are deterministic or have a frozen outcome set (X140f, X71c's landing rule, X138/V65 margins).

**(5) Internal contradictions.**
- Line 756 against M7 (MF8).
- Line 573 and I3 against M3 step 6 (MF1).
- Line 717 and I3 against M3 (MF2).
- I6 against line 573 (MF7).
- Line 787 against E2 (N2).
- Line 423 (N3).
- Line 338 against L-WHERE (N4).

## What would make it READY_FOR_EXAM_BRIEF
1. MF1 and MF2: a re-check in step 6, an unconditional `_unwind_off()` in every reconciliation, and a true I3.
2. MF3 and MF4: harness-rule text on placement, the leftover snapshot point, fresh wrapper codes, and the X34b
   timing.
3. MF5–MF7: C1–C9, G_COVER's instruments and measurement, and (e) and I6.
4. MF8: one-line fix.

## Probes (`scratchpad/v5f/critic3/`, run on 3.12.3 and 3.13.12 with identical outcomes)

| probe | shows |
|---|---|
| `c1_freeze_hides_twin.py` | E2 accepts a code whose live twin is frozen, and refuses one whose twin is dead but uncollected (N2) |
| `c2_settrace_blinds_pystart.py` | after settrace, another tool's PY_START/PY_RETURN still fire (control for N5) |
| `c3_line_disable_blinds_injector.py` | a DISABLE-returning LINE tool makes the INSTRUCTION injector miss first-execution offsets (N5) |
| `c4_settrace_vs_local_events.py` | styxx's event set is unaffected by settrace, whether it returns None or itself (control) |
| `c5_retire_step6_race.py` | `_retire` step 6 clears PY_UNWIND under an open section: `{}` and MONITOR_LOST (MF1) |
| `c6_x143_inside_selftrace.py` | X143's spec and mutant agree inside the self-trace (MF3) |
| `c7_stale_unwind_after_open_fault.py` | after one fault in `_open`, 51,375 / 39,373 lost handlers outside sections (MF2) |
| `c8_cut_order_dependence.py` | after V61, X35c is accepted and X141 has no CUT_MOVED (MF4) |
| `c9_x34b_fixture_poisons_first_e2.py` | a clone alive at the first `coverage_trace()` makes every later one refuse (MF4) |
| `c10_aiodebug_overblock.py` | aiodebug's real closure patch refuses CUT_UNAVAILABLE; without the check, attribution is still sound (N1) |
| `c11_manual_ready_drain.py` | an inline `_ready` drain in a section is credited (N4) |
| `rerun_rev2_probes.txt` | re-run of p4b, p4c, p5, p6, p8, p9, p10 and p12 |

**Probe re-run status.** p1, p1b, p2, p3, p13, p14 and p4b completed and match their rows (p2's cost excepted,
N9). p4c was re-run with its default arguments (2 and 4 threads × 50,000 sections, a 1 µs switch interval), which is
slower than the committed run (4 threads × 10,000). The committed `rev2/out_p4c.txt` shows 100,000 of 100,000 and
40,000 of 40,000 counted. p5's committed output (`rev2/out_p5.txt`) was read and matches the row.
