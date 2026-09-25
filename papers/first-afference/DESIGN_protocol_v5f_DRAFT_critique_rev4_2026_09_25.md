# Adversarial critique of `DESIGN_protocol_v5f_DRAFT_2026_09_25.md`, revision 4

**Verdict: NOT_READY.** 0 BLOCKER-for-freeze, 7 MUST-FIX, 8 NOTE.

The core safety claim of revision 4 holds. On every cross-thread interleaving I could build or re-run, no
body runs with PY_UNWIND clear under an armed, registered, crediting anchor, and no anchor outlives an exit.
The Dekker-style argument (line 634) is sound for clearers and openers on different threads. Every revision-4 probe
reproduces on 3.12.3 and 3.13.12. The model check reproduces state for state. I found no over-credit.

The pattern of the last three critiques is only partly broken. The model check enumerates cross-thread pairs, but it
contains no same-thread re-entry, no user code that blocks inside a window, no stack switching and no external
clear. Each of those produces behaviour the spec states wrongly:

- a wait cycle *inside* the machinery, and one through a user lock. I5 says neither can happen (MF1);
- a lost call with no MONITOR_LOST in R19, the greenlet residual and L-MONITOR, each of which says the loss is never
  silent (MF2);
- R19 is wider than stated (MF2).

These fail closed or sit inside disclosed residuals, so none is a BLOCKER. But the invariants and disclosures that
the exam and G_FI are built from are false as written. Separately, four exam items cannot be frozen as written:
- X149 fails a correct implementation under a natural reading (MF3);
- X146c depends on an unpinned facade detail (MF4);
- G_FI's point set is timing-dependent (MF5);
- two revision-4 rules have no SM1 row or witness (MF6).

## How this was checked
- I read revision 4 (2,121 lines), its Revision 4 table and enumeration section, `rev4/m1_pairs_modelcheck.py` in
  full, `rev4/mech4.py` in full, `rev4/w4_rev4_witnesses.py`, and the rev3 critique for its conventions.
- I re-ran the evidence on `rt3/venv3.12` (3.12.3) and `rt3/venv3.13` (3.13.12). Outputs are under
  `scratchpad/v5f/critic5/`.
  - `w4_rev4_witnesses`: sorted output identical to `rev4/out_w4.txt`.
  - `a4r_detach_order`, `m2_split_instruments`, `h4_callee_backedge`: identical to the published tables.
  - `b1_open_races_exit` at 5,000 races: revision 4 left 0 anchors and 0 false flags. Revisions 2 and 3 leaked on
    both versions.
  - `m1_pairs_modelcheck`, revision 4, every configuration and budget (`c6_m1_rerun_rev4.py`, `out_c6.txt`): the state
    counts match the table exactly, with 0 violations. See the end of this file for the triple.
- New probes `c1`–`c10` in `critic5/` run against an unmodified copy of `mech4.py`, except `c5`, which tests CPython
  itself. No implementation exists, so "model" means `mech4.py` or `m1_pairs_modelcheck.py`.
- No tracked file was modified. The probes that ran in `rev4/` ran with `PYTHONDONTWRITEBYTECODE=1`.
- Line numbers refer to the revision-4 document.

## Audit of `m1_pairs_modelcheck.py` (task 1)

**Faithful where it claims to be.** I compared each program counter with the pseudocode at lines 563–624 and
with M3 and M5.
- `_commit`: C_ST, C_CK, C_SN, C_WT, C_OR/C_OS and C_AR, in the spec's order.
- `_detach`: D_CLAIM, D_FR, D_ARM, then D_S before D_A4 (event first, anchor last), D_POP, D_NUL (rev 3 or mutant
  only), D_OFF.
- `_unwind_off`: U_R, U_AN, U_T, U_C, U_WD.
- Exit X1–X3, X5 and X8. Reconciliation's prune, anchor sweep with the credit stop first, token sweep, and final
  `_unwind_off`.
- A fault clears the thread's TOK and TXN registers, which matches a dead frame. Inside `_run`'s try a fault jumps to
  the finally, including from a blocked C_WT. That matches `rev4/h4`.

**Where it merges operations, and why that is harmless.** Five steps are coarser than "every two C operations"
(line 2073):
- C_CK reads `o.fin` and `marks` together;
- C_SN merges `if _CLEARING` with the snapshot;
- C_WT evaluates every token at once;
- R_P stops credit for every dead core and snapshots their openings in one step;
- R_TK pops every dead token at once.

Each merge is benign for the stated properties. The claim test and the `'exiting'` test are each monotone. Tokens,
once withdrawn or dead, stay that way. A snapshot taken later only shrinks the set to wait on. So the claim is
slightly overstated, not wrong.

**What it omits, and what that hides.** The text says re-entrant same-thread transitions and tool-id races are not
enumerated (line 2098). The omissions are wider than that, and each one hides a finding below.
1. *Same-thread re-entry.* Each model thread runs exactly one transition. Nothing can run inside a window, so the
   opener's own-thread skip in `_await_clearers` (line 589) is never exercised. R19 (MF2) and the nested wait cycle
   (MF1) are outside it.
2. *User code that blocks.* A clearer in its window can always step, so HANG (line 2073) cannot see a cycle through a
   user lock (MF1). HANG = 0 is true by construction, not evidence for I5.
3. *External clears.* "No party clears S from outside in this model" (the model's header, END), so detection
   completeness is never tested. U1 excludes external clears; the MONITOR_LOST claims do not (MF2).
4. *No `run_async` suspension or hop.* A section's anchor never outlives its thread's run, which is the precondition
   of R19.
5. *Not modelled at all:* E4 (`_enter_txn`, `_mint`, `_ensure_tool`, `_reclaim`), `_retire` steps 1–5, the per-mint
   step-6 clearer, and the anchor sweep over all of a core's openings (the model detaches only the swept one).
6. *Properties.* There is no over-credit property beyond P8 and U1's "crediting" flag, because hits carry no counts.
   There is no MONITOR_LOST completeness property. There is no bound on how long an opener waits.

The sentence at line 2073, "So the enumeration also covers any instrument that runs Python code between two
machinery bytecodes", should read: it covers any *interleaving* such code causes on another thread. It does not
cover what that code *does*: open a section, block, switch stacks, or clear the event.

---

## MUST-FIX

### MF1. I5's "no cycle of waits" is false: the opener's wait closes cycles inside the machinery and through user locks
I5 (line 783) says: "A clearer never waits for anything, so no cycle of waits exists inside the machinery." The spec
itself says a clearer's window can run a finalizer, a signal handler, a profiler or a lower-id tool callback (lines
634, 836). Such code can do two things revision 3 never waited on.

(a) **It can open a section.** That opener waits for clearers on *other* threads, so the clearer beneath it waits
too. Two threads in that state wait on each other. `c8_nested_wait_cycle.py` holds each thread's clearer at
`off:tested` and runs `tr.run(...)` from inside the window, with the bound at 1 s:
- revision 3: both inner sections return at once;
- revision 4: both wait the full bound, then one raises MACHINERY_BUSY. That happened in 4/4 runs on 3.12.3 and
  3.13.12.

(b) **It can wait on a lock that the opener's thread holds.** Take a gc finalizer that needs a pool or results lock,
while the other thread runs `with results_lock: cov.run(...)`. Untraced, and under revision 3, the finalizer just waits
until the section ends. In `c3_wait_cycle_user_lock.py` under revision 4, T1's open waits for T2's announcement while
T2 waits for T1's lock. The result is a guaranteed stall for the whole bound, then MACHINERY_BUSY, which refuses every
gate of the trace:
- revision 3: `run_A 1`, no wait;
- revision 4: `MACHINERY_BUSY`, 2.0 s at a 2 s bound.

Both versions behave the same. Line 634 also names the cyclic gc as something that runs inside the window, so this is
not deliberate-only.

The effect fails closed (a 10 s stall and a refusal), so it is not a BLOCKER. But I5 is the liveness invariant, and
the model's HANG property is offered as its evidence (line 783), while HANG cannot see either shape (audit items 1
and 2).

**Fix.**
- Restate I5: a wait can close a cycle when a clearer's window runs code that opens a section or waits on an
  opener's thread. The bound breaks it, with MACHINERY_BUSY.
- Add both shapes to over-blocking #20 (line 1114), which today describes only a clearer "held there by user code",
  not one held *by the opener*.
- Optionally, lower the cost. An opener whose own thread already has a live announcement is nested inside a window.
  It could fail fast with a distinct note instead of waiting 10 s.
- Add a case that pins either choice.

### MF2. "The loss is never silent" is false for R19, greenlets and external clears; R19 is also wider than stated
Three disclosures rest on the close's `UNWIND_LOST` test:
- R19 (line 836): "Its close notes MONITOR_LOST ..., so the loss is never silent";
- the greenlet bullet (line 835): "MONITOR_LOST is noted at its close";
- L-MONITOR (line 1209): "Exit detects it and adds the MONITOR_LOST note", which X137c pins (line 1363).

The test reads the event *at close time*. Any section that opens anywhere between the loss and that close re-sets the
event with its own `_unwind_on()`, on any thread and for any tracer. That section's close does not clear it, because
the blinded anchor is still registered. So the blinded close finds the event set and flags nothing.
- `c7_external_clear_masked.py`: X137c's shape, g lost. With no other section: MONITOR_LOST True. With one unrelated
  section of another tracer opened and closed on another thread before G closes: g still lost, MONITOR_LOST
  **False**. Same on both versions.
- `c2b_r19_silent.py`: R19's own shape, the same result: `calls_A None` with MONITOR_LOST True, becoming False when
  another section opens before A's close. R19's own text concedes the loss lasts "until some other opener sets the
  event again". That opener is exactly what erases the evidence.

R19 is also wider than stated. It requires the suspended coroutine to be "resumed on another thread". In
`c2_r19_same_thread_resume.py`, everything runs on one thread and the call is still lost at `off:tested`, on both
versions. Under `eager_task_factory`, one `create_task(cov.run_async(...))` in the interrupting code opens the
section and leaves it suspended, which weakens "deliberate only".

**Fix, in the mechanism.** Make the loss detectable where it is erased. When `_unwind_on()` finds the event clear
while another *armed* anchor of a crediting core is registered, set `UNWIND_LOST` on that core. By U1 this state
arises only from the excluded parties, so it adds no false flag. The model can check this with an "external clear"
thread.

**Otherwise, in the text.** Correct the three disclosures: the loss is silent if any section opens before the
blinded close. Drop "on another thread" from R19, and add U1's third exclusion (NOTE N1).

### MF3. X149, as written, fails a correct implementation and does not kill its mutant (thread-ident reuse)
X149 (line 1383) says: "T2 closes section B ... the id-5 injector raises ... Then T1 runs `cov.run('A', catch_t)`".
The expected outcome includes "`clearing == 0` after it". It is the named witness for "no `_alive` test in
`_await_clearers`" (line 1506). An author who makes T1 a new thread started after T2 has ended hits two problems:
- on Linux, T1 gets T2's ident;
- `_await_clearers` then skips T2's dead token as "own thread" (line 589), and never pops it, because the pop loop
  runs only `while w`.

`c1_x149_ident_reuse.py`, 20 trials per cell, identical on 3.12.3 and 3.13.12:
- T1 a new thread: `same_ident True` 20/20;
- the spec gives `clearing_after_A 1`, contradicting the expected 0;
- the `no_liveness` mutant gives the same record as the spec, so the witness is not isolating;
- with T1 as the main thread (what `w4` actually does), the published outcome holds.

**Fix.** Pin T1 to a thread whose ident differs from T2's: the main thread, or T2 kept alive and parked. Also require
X149b and X150 to state which thread reads the state.

### MF4. X146c depends on whether `cov.run_async` keeps the facade alive, which the spec does not fix
X146c (line 1379) needs the facade to die while T1 is held inside `_run_async`, so that a reconciliation prunes the
core by "facade weakref is dead" (line 447). The spec fixes that the machinery's frames hold no facade (lines 420,
563). It does not fix the facade's `run_async` method. If an implementer writes it as
`async def run_async(self, ...): return await _run_async(self._core, ...)`, the outer coroutine's frame holds `self`
while `asyncio.run(co)` runs on T1. Then:
- the facade never dies and no prune happens;
- step 8 passes and `co` returns af's value;
- the expected TRACE_INACTIVE fails on a correct implementation.

`w4` does not exercise this: it sets `tr.core.facade_dead = True` directly (`w4_rev4_witnesses.py` x146c).

**Fix.**
- Pin the facade: `run` and `run_async` are plain `def`s that return `_run(...)` / `_run_async(...)`, and neither the
  returned coroutine nor any frame the case controls holds the facade.
- Add to X146c: the case uses no `with` statement for this tracer, and T1's target holds no reference to `cov`.
  A `with` statement's pending `__exit__` holds the facade.

### MF5. G_FI's point set is timing-dependent in revision 4, so the frozen enumeration and stride are not reproducible
MF3 of revision 4 (line 1716) defines the point set as the triples `(key, offset, k)` that "a discovery run executed".
It claims determinism because scenarios join before exit. But the two-thread scenario, and the background variant
(lines 1715, 1719, 1740), run sections on two threads concurrently. In revision 4, whether the faulted thread
executes `_await_clearers`, `_alive`, and the wait's back-edge and its k-th iterations depends on whether the other
thread was inside an `_unwind_off` window at that moment. The design's own `rev4/out_b4c.txt` measures this: 0.18–0.82%
of opens waited, varying run to run.

The same holds for whether `_unwind_off` reaches its `set_events` offset, which depends on `_ANCHORS` being empty. So:
- two discovery runs give different point sets;
- the stride-3 subset used by SM2 instrument (b) and G_COVER pass 2 (line 1716) differs between runs;
- a mutant confined to `_await_clearers` is killed or not by chance.

**Fix.** Choose one:
- make every G_FI scenario sequential in its machinery calls, with barriers so that no open overlaps another thread's
  close or transaction, and leave `_await_clearers` to X145, X149, X149b and X150 (as MF3 already does for races);
- or freeze the point set as a committed file produced once at freeze time, and state how points missing from a
  later run are counted.

Either way, G_COVER's claim that `_await_clearers`' lines are reached (line 1803) must name deterministic cases,
which it already does. Keep G_FI out of it.

### MF6. Two revision-4 rules have no SM1 row and no witness
"Every rule has a mutant; each is killed by the named case" (line 1489; D2 graft, line 20). Two revision-4 rules are
missing from the row at line 1506.
- **The opener's own-thread skip** (`t.tid != me`, line 589; I5 "never for its own thread's"). Its mutant (wait on
  every token) turns a same-thread nested open inside a window into a 10 s wait and MACHINERY_BUSY. No case opens a
  section inside a clearer's window on the same thread, so no case kills it. A witness: T2 closes the last section.
  At the CALL of the clear's `set_events` (X145 (a)'s event), the id-3 tool's callback runs `cov.run('C', f)` on T2.
  Spec: `run` returns at once. Mutant: MACHINERY_BUSY after the bound. In `c10_own_thread_skip_witness.py` (bound
  1 s, both versions) the spec returns `1` in 0.0 s and the mutant gives MACHINERY_BUSY after 1.0 s. Code run inside
  a monitoring callback raises no events, so C counts nothing; the witness reads only `run`'s outcome.
- **The anchor sweep's credit stop first** (M3, line 463; F9, line 2116). The model mutant `sweep_no_credit_stop`
  violates U1 (line 2111), but no exam case or SM1 row names it. Either add a witness, for example exit held by the
  id-3 tool between X1 and X2 and faulted there while another tracer's reconciliation sweeps, or argue
  EQUIVALENT_BY_SPEC before the freeze (line 20). As it stands, the row list is incomplete.

### MF7. U1 is stated with "two exclusions" and "whatever Python code runs", but the spec itself names a third
U1 (line 643) holds "whatever Python code other tools run between machinery bytecodes, with two exclusions". The proof
(line 634) says it "holds whatever Python code runs between two machinery bytecodes". The greenlet residual (line 835)
says Python code that switches greenlets inside `_unwind_off`'s window lets a clear land under an armed anchor, which
contradicts both. MF2's same-thread reopening shape is R19 itself, but the "whatever Python code" wording also
contradicts R19's existence. I6 (line 787) repeats "No fault and no instrument clears the event under a registered,
armed anchor". These are the statements the exam cites (C4, C8), so they must be exact.

**Fix.**
- State the exclusions as a closed list: external clears (L-MONITOR), R19 (as widened in MF2), and stack switching
  inside a window (greenlet/gevent, untested scope, line 1218).
- Replace "whatever Python code" with "whatever Python code runs on another thread, or on this thread without opening
  a section or switching stacks".

---

## NOTE

- **N1. A tool-id free *and re-take* inside the window clobbers the other tool.** The Tool-acquisition prefix (lines
  818–822) and L-MONITOR (lines 1212–1213) say a race with another party's `free_tool_id` only makes a call raise
  ValueError, and that "an id another tool took is never touched" (also lines 444, 457, 507, 1024). But if the other
  party frees *and re-takes* the id between `_ours()` and the call, the call succeeds on the foreign id (`c4`, both
  versions):
  - `_unwind_off` clears the new owner's global events (9216 → 0);
  - `_unwind_on` replaces its mask with PY_UNWIND (9216 → 4096), which then stays under the foreign name with
    styxx's callback.

  This is contrived: a hostile tool within a few bytecodes. Disclose it next to the ValueError case.
- **N2. New audit-hook sites.** `_txn()` in every clearing `_unwind_off` raises the `sys._getframe` audit event, and
  `_alive` raises `sys._current_frames` (`c5`, both versions). A hook that raises there makes every clearing close,
  or every waiting open, raise out of `run()`. Line 759 lists as audit-hook sources only `__code__` writes. Add these
  sites (and the callbacks' existing `sys._getframe(1)`). `_current_frames` also costs 3–3.8 µs at 51 threads per
  `_alive` call.
- **N3. The wait's bound reads monkeypatchable time.** `_await_clearers` calls `time.monotonic()` and `time.sleep()`
  through the `time` module at call time (lines 590–599). With `time.monotonic` frozen, as freezegun does (simulated
  in `c9`), the bound vanishes: 3.0 s waited at a 1 s bound, where MACHINERY_BUSY was due at 1.0 s. With gevent,
  `time.sleep` switches greenlets inside the wait. Bind both at import, for `_acquire` too, and add it to G_HYG.
- **N4. "Owning thread" is wrong for `run_async`.** Step 9 (line 315), M7's comment (line 578) and the R2-B3 row say
  only the owning *thread* releases `o.frame`. A hopped coroutine's `finally` runs on another thread (V28b, G_FI's
  hopped variant). The B1 argument needs only "the opening's own `finally`". Reword it.
- **N5. Stale or inconsistent text.**
  - Line 1032 still says "The only `f_locals` read is the mutex's liveness check". `_await_clearers` and the
    announcement sweep now also call `_alive`.
  - Least-sure item 3 (line 1880) gives the model cost as 1.3–1.7 µs per section. The Cost table and
    `rev4/out_b4.txt` give +1.09 to +2.25 µs.
  - The scope-of-testing line (1218) mentions greenlets only for the mutex, not for the clearer's announcement.
- **N6. `_Txn(tid, fid, code, succ={})` (line 422) reads as a mutable default.** An implementer writing from the text
  alone (G_INDEP, line 28) could share one `succ` dict between all tokens, which breaks the mutex chain. Say "a fresh
  dict per token", and that `_Txn` hashes and compares by identity, as `_CLEARING` needs.
- **N7. X142b's counter can be bumped by the harness.** The leftover check "tool ids other than styxx's are in their
  pre-case state" (line 1247) naturally compares names with `==`, which runs `N.__eq__` and breaks "the `__eq__`
  counter is 0" (line 1386). Require the harness to compare with `type(n) is str` first, or read the counter before
  the leftover check. X145 (b)'s "left `_v5_state()["mints"]`" also depends on which registry `_v5_state` reads,
  which M10 does not fix (`_BY_FN` pops at `_retire` step 4, `_MINTED` at step 5). Both happen before step 6, so the
  outcome is unaffected.
- **N8. Model claims to tighten.**
  - Line 2073: "covers any instrument that runs Python code" (see the audit above).
  - Line 2098: re-entrant *opens and closes* inside windows are covered by nothing, not by REENTRANT or H1, which
    concern transactions only.
  - The 49.5 million states figure is for 64-bit state hashes (line 2073). A collision can hide a state; the file's
    header gives about n²/2⁶⁵, negligible here. Say "hashes" in the table caption too.

## What the revision-4 fixes survive (task 2)
| fix | attack | result |
|---|---|---|
| B1 owner-only release, step 8, anchor sweep | `b1` natural races re-run (5,000 per revision per version); `w4` X146–X146d; model re-run | holds: 0 anchors left, 0 false flags; mutants still differ |
| MF1 announcement and wait | four splitting instruments (`m2` re-run); same-thread clearer (`c2`, `c2b`); nested and lock cycles (`c3`, `c8`); ident reuse (`c1`); frozen clock (`c9`) | holds across threads; R19 wider and can be silent (MF2); cycles (MF1); X149 fragile (MF3); bound depends on `time` (N3) |
| MF2 event first, anchor last | `a4r` re-run; external clear plus re-open (`c7`) | no false flag; true flag can be erased (MF2) |
| N1 `_named` | free and re-take in the window (`c4`) | `_named` is fine; the TOCTOU clobbers (N1) |
| #130279 rule | `h4` re-run | holds |

## Can an exam author freeze a deterministic exam from the text alone? (task 3)
Not yet. These items need judgement or fail a correct implementation:
- X149's thread identity (MF3);
- X146c's facade retention (MF4);
- G_FI's point set and stride (MF5);
- the missing SM1 rows (MF6);
- X142b's harness comparison (N7).

The other revision-4 cases are deterministic handshakes with no timeout deciding an outcome, and I could write them
from the text: X145 (a)/(b), X146, X146b, X146d, X147 (an envelope), X148, X149b, X150 and V66. X150 and V66 are
boundary rows around a fixed bound.

## Internal consistency after four revisions (task 4)
- I5 contradicts the reachable cycles (MF1).
- U1's "two exclusions" and line 634 contradict the greenlet residual (MF7).
- R19, the greenlet residual and L-MONITOR claim a note that another opener erases (MF2).
- Owner "thread" versus hopped coroutines (N4).
- Stale text at line 1032, the cost figures at line 1880, and the scope line 1218 (N5).
- The Tool-acquisition prefix and L-MONITOR's "never touched" (N1).

I found no contradiction in the step order between At open (lines 306–315), M7's pseudocode, the prefixes (lines
795–817) and the model.

## Model-check re-run (`critic5/out_c6.txt`)
Revision 4 only, every configuration at its published budgets, `m1_pairs_modelcheck.py` copied unchanged, 3.12.3.
Every pair configuration matches the published state counts exactly with 0 violations. The largest triple matches
at 0 faults (6,187,685 states, ok). With one fault it gives 41,747,051 states, ok. All 41 runs are ok, for 49,508,697 states in total, which matches the published "49.5 million". The result stands for what the model contains; the audit above lists what it does not.
