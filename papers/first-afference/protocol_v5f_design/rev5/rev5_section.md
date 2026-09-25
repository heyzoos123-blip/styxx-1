
---

## Revision 5: critique items and their resolution

This section answers `DESIGN_protocol_v5f_DRAFT_critique_rev4_2026_09_25.md` (verdict NOT_READY: 0 BLOCKER-for-freeze, 7 MUST-FIX, 8 NOTE). It first says why the mechanism changed rather than being patched. Then comes one row per item in the critique's order, then the CPython #130279 check, the extended model check the brief asked for, and the findings made while resolving the items.

The "verified" column cites probes under `/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/rev5/`, abbreviated `rev5/`, with outputs in `rev5/out_*.txt`. Each was run on CPython 3.12.3 (`rt3/venv3.12`) and 3.13.12 (`rt3/venv3.13`) with the same outcome unless the row says otherwise. The model check `m5_modelcheck.py` is interpreter-independent and was run once. `rev5/mech5.py` is written from this revision's text, not patched from `mech4.py`, and has each revision-5 rule behind a single-rule mutant (`MUT`). `rev5/spec_rev5_eventpath.py` is M7's pseudocode itself, run as Python. `critic5/` is the fifth critic's probe directory. "Reading" means the resolution follows from the spec text and needed no execution. As before, no v5f implementation or `ref_v5f.py` exists, so every result is of a model or of CPython itself.

### Why the mechanism changed, and what was rejected

The properties the event path must have are three. **U1:** no call is lost silently while a section is open; a loss is noted, or impossible. **U3:** the event is never set with no anchor, beyond a stated bounded window. **I5:** nothing hangs or deadlocks, including when a finalizer or signal handler opens a section, or when user code blocks inside any window.

Each of revisions 2 to 4 met the critique of its day by adding mechanism, and the new mechanism brought failures the evidence did not model:
- revision 3 made the test and the clear adjacent bytecodes, which instruments split (the fourth critic's MF1);
- revision 4 added a clearer's announcement and an opener's wait. The wait closed cycles through sections opened inside a clearer's window and through user locks (MF1). Its same-thread exclusion lost calls, silently once another section opened (MF2, R19). Its liveness test, clock and thread identity became exam hazards (MF3, MF5, N2, N3).

The root cause was the same each time: a decision ("no anchor is registered") and the action it licenses ("clear the event") were two steps, and Python code could run between them. Every fix either narrowed that gap or made the other party wait until it closed. Revision 5 removes the gap. A read-decide-write on the event is built as a lazy `itertools`/`operator` pipeline, whose construction reads nothing, and consumed by one builtin call. The test and the write then happen inside one C call, which no Python code enters, so nothing needs to wait and nothing needs to be announced. `rev5/t1_onecall_atomic.py` tests that premise on CPython with every instrument this spec says coexists, with the cyclic gc and with signals. The same principle then fixes the tool-id races (N1): every write on styxx's id is one call gated on the id's name.

Considered and rejected:
- **Keep the wait, and let an opener nested in a clearer's window fail fast** (MF1's optional fix). This removes one cycle but not the cycle through user locks (`critic5/c3`), which only the 10 s bound breaks. It adds a rule, a note and a case, and keeps every revision-4 hazard (liveness, clock, ident).
- **Prevent nothing and detect everything.** Keep revision 3's adjacent test and clear, and note MONITOR_LOST whenever an opener finds the event clear with another armed section registered (MF2's suggestion, used alone). Under a profiler or a CALL tool, a natural concurrent open would then really lose calls, and the note would appear in fault-free races. X147's, C4's and C8's "no MONITOR_LOST" would become timing-dependent. Losses should be impossible where they can be, and noted only where an outside party causes them.
- **Leave the event conservatively on and clear it only with proof of no anchor and no concurrent opener.** In Python a proof followed by a clear always has a gap between them. The only way to close it without waiting is to make the proof and the clear one C call. That is the chosen design, so this option reduces to it.
- **MF2's suggestion as the critic worded it** ("`_unwind_on` flags a loss if it finds the event clear while another armed anchor is registered"). Taken, but as part of `_unwind_on`'s one call. Read at separate times, it flags an opening armed after the read by a concurrent open that itself set the event: a false note in a fault-free race. X153 witnesses the difference: the split capture notes a section that lost nothing in 20 of 83 trials.
- **No global PY_UNWIND at all (first-LINE confirmation).** It is still the named alternative. It costs a callback per line in declared functions, and it is not needed once the toggle is atomic.

What revision 5 removes:
- `_CLEARING`, `_await_clearers`, the announcement sweep, `_retire` step 6 and `_prune`'s credit stop, which has no observable effect (M3);
- MACHINERY_BUSY at open, R19, the greenlet-clearer residual;
- cases X149, X149b, X150 and V66, and the `"clearing"` field.

What it adds:
- the one-call vocabulary and five one-call functions (`_unwind_on`, `_unwind_off`, `_take`, `_register`, `_set_local`), with `_unwind_on`'s own-anchor gate and its capture of blinded openings;
- `_ensure_tool`'s reclaim of its own id, and `_named` by identity;
- the mutex's clock bound at import;
- the instruction-sweep witness family (Exam harness rules) and cases X137d, X137e, X138b, X146e and X152–X155, with X143, X145 and X148 recast as sweeps.

**Totals.** 16 rows (MF1–MF7, N1–N8, #130279):
- MF1 and MF2 are resolved by removing their mechanism, not by the critique's text fixes. The text fixes are also applied: I5 is restated, #20 lists the remaining cycle shape, and the disclosures are exact. MF2's mechanism suggestion is taken, in a precise form;
- MF3 is resolved by retiring X149 with its rule, plus a harness rule for every case that names a thread by ident;
- MF4–MF7 and N1–N8 are resolved as the critique asked, N1 by mechanism rather than by disclosure alone.

Nothing in the critique is rejected.

| # | critique item | what changed (sections) | how it was verified |
|---|---|---|---|
| MF1 | I5's "no cycle of waits" was false: an opener's wait closed cycles inside the machinery (a section opened inside a clearer's window on two threads) and through user locks | **Removed with its cause.** Nothing waits at open: `_commit` is store, step 8, `_unwind_on(o)` (one call), arm. The robust mutex is the only wait. I5 is restated. The one remaining cycle runs through user code and the mutex: an audit hook or finalizer inside a transaction waits for a lock held by a thread that waits for the mutex. The waiter's 10 s bound breaks it. #20 and "Audit hooks and slow owners" describe that shape; revision 4's MACHINERY_BUSY-at-open item and cases (X150, V66) are retired. Changed: At open step 7, M1, M7, I5, #20, reason codes (MACHINERY_BUSY), the exam placement list | `rev5/w5_witnesses.py`, the critic's c8 and c3 on revision 5: both nested opens return in 0.0 s, and the lock-holding opener returns in 0.0 s at every close point. `rev5/m5_modelcheck.py`: revision 4 shows CYC_OPEN in c8 (28 states), c3 (8) and the lock-around-open shape (4), and in `hang` mode, with the open bound removed, these are true deadlocks (HANG 28 / 4 / 4). Revision 5 has neither in any configuration. Its only cycle is CYC_TX in `with L: exit(X) ∥ exit(Y)+[lock]` (10 states), which is HANG 10 only when the mutex's bound is removed |
| MF2 | "The loss is never silent" was false for R19, greenlets and outside clears: any section opening before the blinded close erased the note; R19 needs no second thread | **The machinery-caused losses are gone, and outside-party losses are noted where they were erased.** No one-call step can be entered, so no clear lands under a registered anchor, whatever runs on any thread (U1). R19 and the greenlet clearer no longer exist. `_unwind_on(o)`, in the same call in which it sets a clear event, notes `UNWIND_LOST` on every armed, registered opening. By U1 only an outside party can have cleared the event under them. So the note is precise, and it cannot be erased by the open that re-sets the event. L-MONITOR, U1 and "What is lost" state the one silent shape exactly: the outside party re-sets the event itself before any machinery step reads it. New cases X137d (the critic's c7 shape) and X153 (the capture is one call). Changed: At open step 7, Close, M7, Residuals, L-MONITOR | `rev5/w5_witnesses.py`: X137d gives MONITOR_LOST under the spec and none without the capture. R19's shape at every point of a close gives `{t:1}` with no note; only a split `_unwind_off` loses t. X153: 0 failing trials of 156 under the spec, 20 of 83 with the capture split, 130 of 146 with it ungated. `rev5/m5_modelcheck.py`: revision 4 has U1 in both R19 configurations and a silent loss (LOSTNOTE) when another opener re-sets the event, and in the outside-party and greenlet configurations. Revision 5 has 0 LOSTNOTE and 0 FALSEFLAG, with every outside-party loss noted or MASKED |
| MF3 | X149 fails a correct implementation when T1 is a new thread (ident reuse), and then does not kill its mutant | **X149 and X149b are retired** with `_await_clearers` and the announcement sweep. The lesson becomes a harness rule. Any case that names a thread by ident keeps it alive until its checks are done, or uses the main thread, and every case states which thread performs each step and read. Changed: Exam harness rules, X149, X149b | Reading; `critic5/c1_x149_ident_reuse.py` (read) |
| MF4 | X146c depends on whether `run_async` keeps the facade alive, which the spec did not fix | M1 pins the facade: `run` and `run_async` are plain `def`s returning `_run(self._core, …)` / `_run_async(self._core, …)`. X146c enters with `cov.__enter__()`, not a `with`; T1's target and `af` hold no reference to `cov`; T1 receives only `co`. The mutation audit gains the row "the facade's `run_async` as an `async def`" → X146c. Changed: M1, X146c, the mutation audit | Reading of the critic's MF4 |
| MF5 | G_FI's point set was timing-dependent, so the frozen enumeration and stride were not reproducible | Every G_FI scenario orders its machinery calls across threads with frozen barriers; bodies may overlap. The discovery run is made twice and must give identical point sets, or the run is void. Revision 5 also removes the loop whose iteration count was the timing-dependent part (`_await_clearers`). Races stay with the model check, the sweeps and X147. Changed: G_FI vocabulary and point definition, C5 | Reading. `rev5/spec_rev5_eventpath.py`: no loop in any event-path function |
| MF6 | Two revision-4 rules had no SM1 row or witness (the own-thread skip; the anchor sweep's credit stop) | Both rules are deleted: the skip goes with the wait. The credit stop has no observable effect: a pruned core's record is never read again (M3 gives the case analysis). The model finds no property that depends on it (mutant `prune_credit_stop`: nothing detected). Every revision-5 rule has a mutation row and a deterministic witness (the revision-5 row). The revision-3 and revision-4 rows are updated, with retired entries listed. Changed: M3, the mutation audit, SM1 | `rev5/w5_witnesses.py`: every revision-5 witness passes under the spec and fails under its mutant, with identical verdicts on both versions. `rev5/m5_modelcheck.py mutants`: 19 of 21 model-level mutants violate a property. The two that do not are `ensure_nocount` (a note only; X137e) and `prune_credit_stop` (the deleted rule) |
| MF7 | U1's "two exclusions" and "whatever Python code runs" contradicted the greenlet residual and R19 | U1 now has one closed exclusion: a party outside the machinery that clears the event, frees styxx's id, or changes its callbacks or local events. "Whatever Python code runs between two machinery steps, on any thread, this one included" is now true: nothing runs inside a one-call step. I6 no longer needs an instrument or re-entry exception. Changed: M7 (U1), I6 | `rev5/t1_onecall_atomic.py`. `rev5/m5_modelcheck.py`: U1 and A0 are 0 for revision 5 in every configuration without an outside party, re-entry and greenlet ones included |
| N1 | A free *and re-take* by another tool between `_ours()` and a call made styxx write on the foreign id | **Closed by mechanism.** Every write styxx makes on its id is one call gated on the name: `_unwind_on`, `_unwind_off`, `_set_local`, `_register`. `use_tool_id` is one call gated on the id being unowned (`_take`). No race with another tool can make styxx write on a foreign id or raise ValueError. A tool that re-takes the id under styxx's own name object is disclosed (L-MONITOR). New cases X154 (four sweeps) and X155. Changed: M3, M4, M5, M7, the Tool acquisition prefix, L-MONITOR, G_HYG | `rev5/w5_witnesses.py` IS-GATE and IS-TAKE: the spec fails 0 trials. The split mutants fail 92/122, 31/65, 12/25, 67/85 and 13/26 trials (3.12.3; the same verdicts on 3.13.12). `rev5/m5_modelcheck.py`: revision 4 has CLOBBER and VALUEERROR in every outside-party configuration; revision 5 has none. `rev5/p_freed_id_calls.py`: only `set_events` and `set_local_events` raise on a freed id |
| N2 | New audit-hook sites (`_txn()` in every clearing close, `_alive` in every waiting open) were not listed | The Exception-safety "Sources" bullet lists every audit-event site: `__code__` writes, `sys._getframe` (`_txn()`, every callback), `sys._current_frames` (`_alive`), `gc.get_referrers`. Revision 5 removes both of revision 4's open- and close-path sites. The one-call steps raise none | `rev5/t1_onecall_atomic.py` part C: no audit event; `critic5/c5_audit_events.py` (read) |
| N3 | The wait's bound read monkeypatchable `time.monotonic`/`time.sleep` | The wait is gone. The mutex's clock and sleep are bound at import (`_monotonic`, `_sleep`; M1, M2), and G_HYG requires it. New case X138b | `rev5/w5_witnesses.py` X138b: with `time.monotonic` frozen, the spec raises MACHINERY_BUSY at the bound (1 s in the model), and the patched sleep was called 0 times. Reading both through `time` at call time waits the owner's full 3 s with about 10,000 patched sleeps |
| N4 | "Owning thread" was wrong for `run_async` (a hopped section's `finally` runs elsewhere) | "The opening's own `finally`", in At open steps 6 and 9, Close, M1 and M7 | Reading |
| N5 | Stale text: line 1032 (`f_locals`), least-sure item 3 (cost), the scope line (greenlets) | All three rewritten. The `f_locals` row names `_alive`'s two callers. Least-sure item 3 is now about the one-call steps, with revision 4's figure corrected to 1.1–2.3 µs. The scope line says what is modelled for greenlets | Reading |
| N6 | `_Txn(…, succ={})` read as a mutable default | M1: a fresh dict per token; `_Txn` hashes and compares by identity. The mutation audit gains the row "`succ` shared" → V52: the second transaction's walk cycles | `rev5/p_txn_shared_succ.py`: with one shared dict the second acquisition's walk does not end |
| N7 | X142b's counter could be bumped by the harness's name comparison; X145 (b)'s `mints` registry | The leftover check compares a tool's name by identity first and by `==` only for an exact str, and X142b reads its counter first. X145 (b) is retired with `_retire` step 6. `_v5_state()["mints"]` reads `_MINTED` (M10 is unchanged) | Reading |
| N8 | The model claims were too broad: "covers any instrument", re-entry "covered by REENTRANT and H1", "states" for hashes | The revision-4 enumeration text is corrected in place. It covers any interleaving such code causes on another thread, not what the code does. Re-entrant opens and closes were covered by nothing. Counts are distinct state hashes, with the collision bound. Revision 5's model covers what was missing (below) | Reading |
| H | CPython #130279: no machinery state may depend on a `finally` or with-exit across a loop back-edge | **Kept, and simpler.** `_run`'s and `_run_async`'s try bodies are unchanged (`_commit(o)` and the call or the one `await`), and so are their `finally`s. No function they call has a loop. Revision 4's `_await_clearers` loop is deleted, and a one-call step iterates in C, not at a bytecode back-edge. The dead-anchor consequence of a skipped `_run_async` `finally` is unchanged (U4) | `rev5/spec_rev5_eventpath.py`, both versions: no backward jump in `_run`, `_commit`, `_unwind_on`, `_unwind_off`, `_detach`, `_take`, `_register`, `_set_local` or `_named`. A KeyboardInterrupt at every instruction of `_commit` (24 trials) and `_unwind_on` (113–117): `_run`'s `finally` ran every time, leaving no anchor and no event. At every instruction of the close path: nothing left, or a dead anchor with the event set (U4), never the event set with no anchor |

### The extended model check (the brief's item 2)

`rev5/m5_modelcheck.py` keeps `rev4/m1_pairs_modelcheck.py`'s granularity: every C operation is one step. It adds what the fifth critic found missing, for revision 4 and revision 5 in one model:
- **Same-thread re-entry.** At every step boundary of every thread, windows and blocked waits included, a nested program may run to completion on that thread before the interrupted one continues. The nested program is a whole section (a finalizer or signal handler calling `cov.run`), a `run_async` section left suspended when the nested code returns (R19's shape), a user-lock acquisition, or a whole transaction.
- **Blocking user code.** A thread may hold user lock L around its section or its exit, and nested code may block on L. The busy bounds are a timeout step that a blocked machinery wait may take at any time. User-lock waits have none.
- **Outside parties.** Between any two steps: clear or set styxx's event, free its id, or take a freed id as another tool.
- **Greenlets.** A thread may hold two greenlets and switch between them at any step boundary. A switched-out greenlet's frames are not on its thread's frame chain, so the liveness test sees them as dead.
- **`run_async`.** An async section may suspend in its body with its anchor registered, and any idle thread may resume it: the same thread, or another (a hop).
- **E4, `_retire`, `_reclaim`.** Enter's transaction (reconcile, `_ensure_tool`, mint join or holder, register, local events, install, credit, activate), `_retire`'s steps, and reconciliation's reclaim.

**Properties.** "Without an outside party" means no outside event has happened in the run.
- **U1:** no hit runs with the event clear while its anchor is registered and its core is crediting and alive, without an outside party. With one, such a hit is a LOST hit.
- **A0:** no state has a live, armed, registered anchor of a crediting, live core with the event clear, without an outside party.
- **STALE:** no state has the event set with no anchor registered, unless an outside party set the event or freed or took the id.
- **FALSEFLAG:** a flag is set only on a core for which an armed, registered anchor was seen with the event clear.
- **LOSTNOTE:** at every end, after repair, every LOST hit of a readable trace is noted (MONITOR_LOST or MACHINERY_BUSY) unless an outside set ended its blind interval first. Such a hit is MASKED, the disclosed residual.
- **CLOBBER:** no styxx write lands on an id another tool holds.
- **VALUEERROR:** styxx never raises ValueError from a race with another tool.
- **P8:** step 8, as in revision 4.
- **HANG:** no reachable state where live work exists and no step at all, timeouts included, is enabled. It is not zero by construction: with a bound removed, it finds revision 4's cycles.
- **CYC_OPEN** and **CYC_TX:** states in which only a timeout of an opener's wait, or of the mutex, lets anything progress.
- **END and REPAIR,** as in revision 4, extended to mints (none registered or installed after repair).

Budgets are F faults, I nested programs, X outside events and W greenlet switches per run. Each cell gives the violations at the largest budget run, or "ok", then the informational counts in brackets. LOST and MASKED are counts of end states in which some core lost a hit, or lost one that an outside set masked. CYC_TX and BUSY_TX count the mutex's bounded waits. BUSY_OPEN counts revision 4's open waits that time out. STALE_rev4 counts revision 4's documented windows (its U3). The state counts per budget are distinct 64-bit hashes.

| configuration | budgets (F / I / X / W) | rev 4 | rev 5 |
|---|---|---|---|
@@M5TABLE@@

**What the enumeration shows.**
- **Revision 5: 0 violations of any property** in 35 configurations and 70 runs (4,922,275 state hashes). That includes the two same-tracer triples of revision 4's check, `open(X) ∥ open(X) ∥ exit(X)` (537,217 / 3,081,695 states at 0 / 1 faults) and `open(X) ∥ exit(X) ∥ exit(X)` (18,848 / 73,216). Its only cycle is CYC_TX, the mutex's through a user lock, broken by the bound. Every LOST hit, all caused by an outside party, is noted or MASKED.
- **Revision 4 in the same model** fails in every class the fifth critic reported:
  - U1 in both R19 configurations;
  - a silent loss (LOSTNOTE) when another opener re-sets the event;
  - CYC_OPEN in c3, c8 and the lock-around-open shape;
  - CLOBBER and VALUEERROR with outside parties;
  - U1 and silent losses with a greenlet switch in a close;
  - one gap the critic did not report, a silent loss when the id is freed between E4's reconciliation and `_ensure_tool` (F13).

  So the new dimensions are not vacuous.

**Hang mode** (`m5_modelcheck.py hang`: the same configurations with one bound removed at a time; `rev5/out_m5_hang.txt`):

| configuration | rev 4, no open bound | rev 4, no mutex bound | rev 5, no mutex bound |
|---|---|---|---|
| c8: two closes, each with a section opened inside | HANG 28 | CYC_OPEN 28 | ok |
| c3: `with L:` open ∥ close with a lock-taking finalizer | HANG 4 | CYC_OPEN 4 | ok |
| `with L:` open ∥ open with a lock-taking finalizer | HANG 4 | CYC_OPEN 4 | ok |
| `with L:` exit ∥ exit with a lock-taking audit hook | ok (CYC_TX 12) | HANG 12 | HANG 10 |
| a close with a section opened inside ∥ open | ok | ok | ok |
| greenlet: [close, open] ∥ open | U1, LOSTNOTE (the greenlet loss) | same | ok |
| greenlet: [exit, rec] ∥ open | ok | ok | ok |

The last-but-two row is the one wait left in revision 5: the robust mutex, whose 10 s bound turns that deadlock into MACHINERY_BUSY (I5, #20).

**Mutants** (`m5_modelcheck.py mutants`, revision 5; `rev5/out_m5_mutants.txt`). The first violations found:

| mutant | first violations |
|---|---|
| `_unwind_off`'s test and clear split | STALE fault-free in open ∥ exit and close ∥ exit; U1 and A0 in open ∥ open |
| the pop outside `_unwind_off`'s call | STALE fault-free in open ∥ exit, close ∥ exit, open ∥ open |
| `_unwind_on` without the own-anchor gate | STALE fault-free in open ∥ exit, the prune configuration, open ∥ exit ∥ rec |
| `_unwind_on` without the capture | LOSTNOTE with outside parties (6 end states) |
| the capture split from the read and set | FALSEFLAG fault-free in open ∥ open, open ∥ open(Y); STALE in open ∥ exit |
| the capture not gated on a clear event | FALSEFLAG fault-free in open ∥ open, open ∥ open(Y), a close with a section opened inside |
| `_unwind_on` before the store (ungated, revision 3's) | U1 and A0 fault-free in open ∥ open, open ∥ open(Y); STALE in open ∥ exit |
| `_unwind_on` deleted | U1 and A0 fault-free in open ∥ exit, open ∥ open, open ∥ open(Y) |
| `_detach`'s anchor test before its event read | FALSEFLAG fault-free in open ∥ exit, close ∥ exit, the prune configuration |
| `_detach`'s test without `o.armed` / without the anchor test | FALSEFLAG in open ∥ exit and more |
| no `_unwind_off(None)` at the end of reconciliation | REPAIR with outside parties |
| a name-gated write split into test and write | CLOBBER and VALUEERROR with outside parties |
| `use_tool_id` split from the unowned test | VALUEERROR with outside parties |
| `o.frame` released by every `_detach` | END (anchor left) fault-free in open ∥ exit, the prune configuration |
| step 8 deleted / its claim test / its `'exiting'` test | P8 in open ∥ exit, the prune configuration, the triples, and a tracer exited from inside its own open |
| pruning of cores reached from anchors deleted | REPAIR with 2 faults in open ∥ exit |
| `_ensure_tool` re-take not counted | not detected: its only effect is a missing note on a loss-free free, which is not a model property (X137e witnesses it) |
| `_prune`'s credit stop restored | not detected: the deleted rule changes nothing (M3) |

**What is still not enumerated.** Two or more nested programs on one thread at once, and budgets above those in the table. Free-threaded interleavings, which the spec refuses. A real greenlet or gevent library: the model's greenlets are abstract. Pending entries and credit counts: hits carry the attribution outcome, not counts, so over-credit is covered by I1's argument and P8 rather than by a count property. The `record()` and scoring layers.

### Found while resolving (not raised by the critique)
- **F13. `_ensure_tool` re-took its own freed id silently.** The extended model check found it (`ext: enter(X) ∥ open(Y)`, revision 4 and the first draft of revision 5: LOSTNOTE 2). The id is freed after E4's reconciliation and before `_ensure_tool`. A section opening meanwhile gets no event, because the name gate is false, and loses its raising calls. `_ensure_tool` then re-takes the id without counting it in `_LOST`. With the close's event read also name-gated, as revision 4 read it, nothing noted the loss. Fixed: `_ensure_tool` re-takes its own id through `_reclaim`, which counts it (X137e), and the close's event read has no name gate (F14).
- **F14. `get_events` never raises on a freed id,** and `register_callback` works on one; only `set_events` and `set_local_events` raise (`rev5/p_freed_id_calls.py`, both versions). The close's read therefore needs no name test. Revision 4's Tool acquisition prefix named `get_events` among the calls a free could make raise; that was wrong.
- **F15. Revision 4's A0 with a fault under re-entry is not a loss.** A section opened inside a clearer's window whose own close is faulted before its pop leaves a dead, armed anchor. The clearer then clears under it (`close(X)+[open(Y)] ∥ open(Y)`, one fault, 556 states under a first draft of the property). Its frame is dead, so nothing can be lost. The model's A0 now counts only anchors whose owner can still run its body.
- **F16. `_prune`'s credit stop had no observable effect** (M3), so it could have no witness. It is deleted rather than kept unwitnessed. Revision 4's F9 (the sweep needs it) followed from a U1 stated for dead cores whose records nobody can read.
- **F17. N6 is not only a reading hazard.** A shared `succ` dict makes the mutex's second acquisition walk a cycle, so every trace's exit would hang (`rev5/p_txn_shared_succ.py`).
- **F18. `free_tool_id` leaves callbacks registered, and they keep firing.** In revision 5's own atomicity probe, stale trial callbacks on id 5 fired in later trials and could have hidden violations. The exam's id-3 and id-5 tools free their ids after each case, so the harness now clears their events and callbacks first (Exam harness rules).
- **F19. Revision 4 set the event for a whole uncredited body.** When exit's X3 popped an opener's anchor after its step 8, revision 4's `_unwind_on` still set the event, with no anchor, until that body's close (its U3 window). Revision 5's own-anchor gate removes it (X146e).

**Weakest points of revision 5, for round 6.**
1. **The one-call premise.** Nothing runs inside a C call that makes no Python-level call. That is how CPython 3.12 and 3.13 work, and `rev5/t1_onecall_atomic.py` tests it for every coexisting instrument, gc and signals. It is not a documented guarantee, and a patch release could add an audit event or a callback inside a `sys.monitoring` function. The prereg must re-run the atomicity probe on every patch level it lists.
2. **Readability of the pipelines.** An implementer can build a pipeline that quietly calls Python code, for example an `attrgetter` on a class with a Python `__getattribute__`, or a lambda. G_HYG pins the shape, and the sweeps catch any split, but a pipeline whose inner call runs Python code without splitting the test from the write would pass both. `_Opening` and `_Core` must stay plain slotted classes (M1).
3. **The outside-party residual.** A party that clears styxx's event and sets it again itself, or that restores changed callbacks or local events before exit, loses calls silently. A hostile tool that re-takes styxx's id under styxx's own name object is taken for styxx.
4. **Cost.** 1.6–3.2 µs more per section than revision 4 in the model (`rev5/b5_cost.py`), because every open and close builds about ten iterator objects even when another section keeps the event set.
5. **The model's abstractions.** Greenlets and `run_async` are abstract. At most one nested program and two outside events run per configuration. Counts are not modelled.
6. **The remaining cycle.** The mutex cycle through user code is bounded, not removed. A harness whose audit hook or finalizer takes a lock held around a tracer's exit stalls for 10 s and gets MACHINERY_BUSY.
