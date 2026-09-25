# Completeness critique of `DESIGN_protocol_v5f_DRAFT_2026_09_25.md`, revision 1

**Verdict: NOT_READY.** 1 BLOCKER-for-freeze, 12 MUST-FIX, 10 NOTE.

The design is close. Most revision-1 rows do what the first critique asked. There are three kinds of problem:
- One gate cannot be passed as written. G_COVER cannot see any line inside a sys.monitoring callback.
- The loop boundary and the per-hit cut check leave three more over-credit routes besides R17.
- Several exam cases, and the SM2 corpus, depend on timing or on facts the spec leaves open.

## How this was checked

Probes are in `scratchpad/v5f/critic2/`. Each was run on CPython 3.12.3 (`rt3/venv3.12`) and 3.13.12 (`rt3/venv3.13`), and both gave the same result unless a line says otherwise. No tracked file was modified.

- `mech.py` models the M6 event path from the spec text. It covers:
  - minted code with local PY_START, PY_RESUME, PY_RETURN and PY_YIELD, plus a global PY_UNWIND;
  - pending entries that hold their frame;
  - the monotone identity cut, `_cut_ok()` at every entry, and the loop boundary in the attribution walk and the NESTED walk.
- `t_sanity.py` checks the model against the spec's expected outcomes. It reproduces plain credit, X65c, X65d (and shows X65d over-credits once the boundary is removed), V63 and R17.
- The other probes are cited where they are used.

---

## BLOCKER-for-freeze

### BF1. G_COVER = 1.0 cannot be met, and revision 1 removed the only way out
**Where:** G_COVER (line 1446), G_COVER = 1.0 among the process gates (line 1467), revision-1 row (d)1 (line 1545).

The machinery contains `_on_entry`, `_on_exit`, `_on_unwind`, `_outcome` and `_publish`. They run only inside sys.monitoring callbacks. Code inside a callback raises no events for any tool, and legacy settrace is suppressed there too:
- `t_cover_cb.py`: the lines of a PY_START callback are seen by neither settrace nor a sys.monitoring LINE tool. Called directly, the same lines are seen.
- `covt/cbmod.py`: coverage.py 7.16.1 reports the callback body as missing (`Missing 4-5`) under both `COVERAGE_CORE=sysmon` and `ctrace`.

None of G_COVER's three instruments (exam fast mode, crash sweep, fuzzer) can therefore cover these lines. Revision 1 deleted the pragmas and says an unreached line "must be deleted, or folded onto its guard's line". Taken literally, the gate requires deleting attribution and confirmation. In practice someone must grant an exemption after the freeze, which the Objectivity rule forbids.

The spec already knows these facts for other purposes (M6 "Where callbacks run"; the G_FI note at line 668 that the callbacks are unreachable by the injector). G_COVER was not updated to match.

**Fix, before the freeze.** Choose one:
- a frozen, named exemption list: exactly the five callback-only functions, justified by p_syn1;
- a frozen driver that measures them outside monitoring. It would build `FunctionType(code, globals)` from the `_v5_faultpoints()` code objects and call them with a synthetic frame. That needs a spec sentence permitting it.

Also say how `_forget_in_child` is covered. It runs only in forked children (see N5).

---

## MUST-FIX

### M1. The claim "one route is left (R17)" is false: three simpler over-credit routes remain (R1-B3 class)
**Where:**
- class-B paragraph (lines 314–316);
- L-WHERE: "The one asyncio route left is R17" (line 966);
- the R1-B3 / R2-B2 / R3-B2 closure row (line 852);
- the B5 row (line 762);
- revision-1 rows (a)2 and (c)2;
- `_cut_ok()` (line 217).

Probes: `t_attack_cut.py` and `t_attack_a2.py`. Each opens section A inside a task of loop L and re-enters dispatch with `L._run_once()`, which is X65c's and R17's shape. Each credits a callback that another task scheduled, and none records CUT_MOVED.

| route | what the harness does | result, 3.12 and 3.13 |
|---|---|---|
| A1 | `asyncio.TimerHandle._run = reimpl`. Timer callbacks dispatch through it, while `_cut_ok()` reads only `Handle`'s dict. The binding is never restored, not even at exit | `calls {'A': {'f': 1}}`, CUT_MOVED False |
| A2 | `asyncio.events.Handle = MyHandle` (a subclass with its own `_run`). `base_events` looks up `events.Handle` at each `call_soon` | `calls {'A': {'f': 1}}`, CUT_MOVED False |
| A3 | a loop class whose own `_run_once` dispatches without `Handle._run` (X65d's `CDispatchLoop`), re-entered from a section opened in one of its tasks. The loop is the same at open and at the hit, so the boundary cannot help | `calls {'A': {'f': 1}}` |

None of these needs R17's "restores the binding from inside its own running frame". A1 is not caught even at exit.

The spec also reads "Handle" three times, at three moments:
- `_HANDLE_DICT[0]`, captured by `coverage_trace()`;
- E2, which reads `asyncio.events.Handle` afresh;
- RESERVED_TARGET, which reads `vars(asyncio.events.Handle)`.

**Fix.** Add `BaseEventLoop._run_once`'s code to the monotone cut by identity, and include its binding in `_cut_ok()`. Every stdlib re-entry into dispatch passes through that frame, so this closes A1, A2 and R17 at once. The t_attack runs show the hit's chain passes a `_run_once` frame before reaching the anchor. Then:
- make `_cut_ok()` also require that `asyncio.events.Handle` is the class captured by the constructor and that `TimerHandle` has no own `_run`;
- pin A3 as the one remaining residual: a loop class that overrides `_run_once` and is re-entered;

  Probe `t_fix_runonce.py`, same results on 3.12.3 and 3.13.12:
  - adding `BaseEventLoop._run_once`'s code to the cut turns A1, A2 and R17 into `dispatched`;
  - a valid section opened inside a task keeps `{'A': {'f': 1}}`;
  - A3 stays credited, as expected.
- rewrite the closure row, L-WHERE, #21 and round-5 item 10.

### M2. A generic decorator used on `Handle._run` poisons the monotone cut for the rest of the process (undisclosed over-block)
**Where:** E2 (line 412), V61 (line 1174), over-blocking #8 and #21, RESERVED_TARGET (line 182).

Probe `t_attack_cut.py` A5 binds `Handle._run = logged(orig)` before `__enter__`, where `logged` is an ordinary closure decorator. E2 adds `logged.<locals>.inner.__code__` to `_CUT`. Every other function decorated with `logged` shares that code object. As a result:
- a harness helper decorated with `logged` becomes a cut frame, and `f` is recorded as `dispatched`, not credited;
- this persists in a later, unrelated trace long after `Handle._run` was restored, because the cut is monotone;
- any declared target decorated with `logged` refuses RESERVED_TARGET.

**Fix.** Disclose this under #8 and #21. Consider refusing CUT_UNAVAILABLE when the `Handle._run` binding's code is shared by another live function; `gc.get_referrers` on the code at E2 can find them.

### M3. R2-B3 is reopened after a *completed* exit through `free_tool_id`, so the (c)4 rejection's own test is met
**Where:** R2-B3 closure row (line 857), revision-1 row (c)4 (line 1544), L-MONITOR (line 1002), X137 free variant (line 1131: "The freed id's local and global events are not changed by styxx at exit"), `_retire` steps 2 and 6 (lines 403–407).

The rejection says R2-B3 was "a silent leak after a completed exit", and a zombie is not one. Here is one:
1. A party frees styxx's id during a trace.
2. The trace then exits normally.
3. By the spec's own text, exit and `_retire` skip `set_local_events` and `set_events(tool, 0)`.

The process-wide PY_UNWIND callback into `_on_unwind` therefore stays set after a completed exit. It stays until a later styxx enter re-takes the id, or forever if another tool takes it (p3, re-run: `after reuse: ... global events on id 4 still 4096`). No record mentions that it persists. A test fixture that resets ids 0–5 between tests produces exactly this.

**Fix.** At exit, if `get_tool(tool) is None`, the id is freed and has no owner, so touching it clobbers nobody. Re-take it with `use_tool_id(tool, _TOOL_NAME)` and clear its events. If another tool holds it, disclose the leak in the R2-B3 row, not only in L-MONITOR.

### M4. L-DELIVERY is large, reaches unrelated code, and G_SIG's "0 wrong results" does not say whether it counts
**Where:** L-DELIVERY (lines 988–993), G_SIG (line 1436), the Decisions row refusing 3.11 (line 37), round-5 item 2 (line 1481), least-sure #2 (line 1501).

Probe `t_delivery2.py`: a loop raises and catches `ValueError` in *undeclared* code, under a 20 µs SIGALRM flood whose handler raises `Timeout`. It counts ValueErrors that reached `raise` but whose `except ValueError` never ran:

| | 3.12.3 | 3.13.12 |
|---|---|---|
| untraced | **0** of 2M | **0** of 2M |
| any mint registered | **337,863** | **232,374** |

Round-5 item 2 asks whether this can change program behaviour. It can, at this measured rate, on every thread of the process, whenever any mint exists (a zombie included).

The 3.11 refusal was justified by "corrupts the traced program". The spec must say why this corruption is acceptable. The honest distinction is that correct `with`/`finally` code is unaffected, while `except E:` side effects are skipped.

G_SIG requires "0 wrong results". If its frozen harness contains any `except SpecificError` flow, the gate fails by construction; if it contains none, the gate says nothing about L-DELIVERY. Freeze which one it is.

### M5. SM2 never defines "faulted", so timing-dependent corpus entries either make G_SEM fail or need a judgement after the freeze
**Where:** noise mask and "Faulted corpus entries" (line 1402), `corpus_v5f/` contents (lines 1290–1296).

The corpus holds "every exam case program", including outcome-set or timing cases: X140f (PASS, TRACE_ACTIVE or TRACE_INCOMPLETE), X138 (11 s), X32d, and the H-sweeps and G_SIG floods if they are included. The rule works as follows:
- a field that differs across the N = 5 baseline runs is masked;
- if the mask covers a code, end, count, note or problem, the baseline is unclean and "G_SEM fails";
- only "faulted" entries escape equality, through the I6 envelope.

"Faulted" has no frozen definition. Someone must classify X140f and similar entries after the freeze, or G_SEM fails with no remedy but a new prereg.

**Fix.** Freeze a manifest that marks each corpus entry `equality` or `envelope`.

### M6. `_v5_faultpoints()` does not say *which* code object it returns, while the self-trace has minted five of the machinery functions
**Where:** M10 (line 546), V34/G0 (lines 1047 and 1454), the harness placement rules (lines 1015–1018), X92b, X131, X132 (lines 1106, 1126, 1127).

The self-trace declares `_resolve_target`, `_open`, `_exit`, `_run` and `Experiment._check_coverage`. While it is active, those functions run the self-trace's M_T. X131, X132 and X92b run inside the self-trace; they are not in the main-thread list.
- If `_v5_faultpoints()` returns the code captured at import, the id-5 injector on `_open` never fires, and X132 is vacuous for `_open`.
- If it returns `fn.__code__` at call time, the injector also faults the self-trace's own `_open`/`_run` calls, since INSTRUCTION events are per code object and process-wide. G0 then depends on how the injector filters threads.

**Fix.** Say "returns `fn.__code__` at call time". Require the injector to filter by thread ident, or move X131, X132 and X92b to the main thread before the self-trace.

### M7. The X71c port depends on timing
**Where:** the port table, X71c (line 1054).

An interval SIGALRM (0.2 ms) must land inside X3 while G's anchor is still registered. Nothing guarantees that any signal arrives during X3; with 1,000 openings, X3 lasts a fraction of a millisecond. If none lands, `f` is never called, the witness union is `{}`, and the correct implementation fails the case. G1 requires 1.0.

**Fix.** Make the call deterministic, for example with a finalizer released by `_detach`'s `o.frame = None`. Otherwise give X71c an outcome set and say how SM1 treats it.

### M8. X140's "every back-edge of every faultpoint" includes callback code the injector cannot reach
**Where:** X140 (line 1134) and G_FI.

`_on_entry` (`for h in holders`), `_outcome` (the walk) and `_publish` all contain JUMP_BACKWARD. Events are not delivered inside callbacks (p_syn1; `t_cover_cb.py`), so those trials can never fire. The case must either exclude the callback code objects or say that a trial that never fires counts as clean. Without that, the result is either a hang, waiting for a first execution that never comes, or a vacuous pass.

### M9. V36b as worded cannot witness the freeze-rule rows
**Where:** V36b (line 1150), mutation audit (line 1240), SM1 freeze rows (line 1353).

Probe `t_v36b.py`:
- If the worker entered `f` *before* the trace, as "started before the trace, is inside f" can be read, it runs the original code. `excess = 0`, and neither "count > 0" nor "count ≠ baseline" fires.
- Only a worker that enters `f` after `__enter__` gives `excess = 1`. Then both mutants fire and the spec rule does not.

**Fix.** Say "enters f after `__enter__`".

### M10. R17's pinned outcome depends on when W is bound
**Where:** R17 (line 1184).

Probe `t_r17_timing.py`:
- W bound after `__enter__`: `calls {'A': {'f': 1}}`, as pinned.
- W bound "beforehand", before `__enter__`: E2 puts W's code in the cut, and the outcome is `dispatched {'f': 1}`.

**Fix.** Pin "after `__enter__`, with no hit before the section".

### M11. Positive control #2 requires a clean baseline that control #3 requires to be unclean
**Where:** the SM2 gate "clean baseline (every instrument passes the unmutated implementation)" (line 1411), controls #2 and #3 (lines 1424–1425).

Control #3 requires the frozen crash sweep to report non-clean points on v5e. Control #2 runs "SM2's generator and instruments" on v5e, and instrument (b) is that same crash sweep. SM2 on v5e therefore has an unclean baseline by design, and whether control #2 "passes" is left to a person.

**Fix.** Name control #2's instruments as (a), (c) and (d) only, or waive baseline cleanliness for the control in writing.

### M12. The busy bound has a boundary row on only one side
**Where:** graft D2 #1 (line 20: "every quantitative rule gets boundary rows on both sides"), the SM1 boundary rows (line 1357: "the 10 s busy bound (X138 at 11 s)").

There is no row below the bound, in which an owner blocks for, say, 5 s and the waiter must succeed. `_BUSY_SECONDS = 10.0` is a float, so O7 (int ±1) never mutates it. A weakening to 0.5 s survives. X138 must also make the waiter start within 1 s of the block beginning, or the waiter succeeds legitimately.

---

## NOTE

- **N1. The cost of the two revision-1 mechanisms is acceptable.** Probe `t_cost.py`, with the model's full path:
  - revision-1 additions: 260/523 ns per hit on 3.12 and 296/68 ns on 3.13, at depth 5/60, which is at most 7.5% of a 3.6–12 µs hit;
  - isolated: `_cut_ok()` about 0.24 µs, `_get_running_loop()` about 0.02–0.03 µs.

  The whole hit is about 100× an untraced trivial call, so the Cost row's "×8 at depth 11" understates it for small hot targets. PY_UNWIND measured ×1.49/×2.01 (3.12) and ×1.56/×2.17 (3.13) for an unwind through 1 and 6 frames (`t_unwind_cost.py`). The cost grows with depth, slightly above the stated "1.3–2×".
- **N2. Over-blocking #9's "relative `__file__` after chdir" does not occur.** The 3.12/3.13 path finder gives absolute paths, and zipimport gives identical relative strings for both names (`relp/t_rel.py`, `relp/t_zip.py`). What *was* measured is a zip holding both source and a `.pyc` compiled under a build path. Its `__file__` is `z2.zip/zmod2.pyc`, so it refuses with "no source file", although the source is in the zip. That message misleads, and #9's "zip (not measured)" item should say this.
- **N3. L-RUNTIME (line 967) is now false in one case.** "Counts for the section whose stack it lands on" does not hold while a loop started inside the section is running. A signal handler or finalizer landing in that loop's own `_run_once` is no longer credited; v5e credited it. Add the loop-boundary exception.
- **N4. The mutation-audit row "monotone cut (cleared or replaced) → X65b" is half right.** In the model, "cleared" is killed by X65b through CUT_MOVED, not through attribution (`t_attack_cut.py` A4). "Replaced" (the cut reset to the current code at each E2) changes nothing in X65b and survives. It needs a nested-tracer witness with a V61-style rebind between the two enters. Write it now rather than wait for SM1's UNWITNESSED.
- **N5. The at-fork handler can abort partway.** `_retire` restores `__code__` and so fires the `object.__setattr__` audit event. A raising audit hook aborts `_forget_in_child`, since CPython ignores exceptions in at-fork handlers. Steps 4–5 are then skipped, and the child keeps the global PY_UNWIND and stale `_ANCHORS` for its life. "Every step is idempotent" (line 653) does not cover an abort. G_FI has no fork scenario, so these points are never swept.
- **N6. X138's waiter must be synchronised** to start while the block is in progress (see M12).
- **N7. The FOREIGN_DEFINITION message can crash.** Line 190 builds `dict.get(inner.__globals__, '__name__') + ':' + …`. For a function whose globals lack a str `__name__` (anything exec'd into a fresh namespace), this raises TypeError out of `__enter__`, which is R1-D2's class. Make "file as a fallback" the rule whenever `type(name) is not str`.
- **N8. `importlib.reload(styxx.protocol)` behaves worse than the Decisions row says.** It rebinds the registries in the *same* globals dict:
  - a tracer active across the reload loses its mints, which are never retired, so the code is left minted;
  - each reload permanently uses up a tool id under a dead name, so the second reload refuses MONITOR_BUSY for the rest of the process.

  The Decisions row (line 54) presents reload as simply "a second copy".
- **N9. #2 and L-WHERE overstate the boundary.** "Any other loop" holds only for loops that call `_set_running_loop`; the round-5 list already names the rest.
- **N10. Control #1's wording does not match SM1's classes.** It says "report as not killed", but SM1 would classify a census survivor as UNWITNESSED. State the expected classification.

---

## (a) Round-4 keys: do the dispositions close them?

- **B5 is not closed as claimed** (M1). B5 was itself contrived, so A1–A3 are the same class and are MUST-FIX rather than BLOCKER.
- **E17 is weakly witnessed** (N4).
- **S2 is closed, but its V36b witness is under-specified** (M9).
- **B2 is closed** for the C-call-skip mechanism. The L-DELIVERY cost is a separate issue (M4).
- **All other keys close** as dispositioned.

I checked these by reading plus probes:
- X135 holds on both versions: body not run, nothing credited, whether or not the first statement is a call (`t_x135.py`).
- B1 coherence holds.
- B3 callee identity holds.
- B4 confirmation holds.
- D8: holders are dropped before `_retire`, so a fault inside `_retire` leaves a holderless mint that the next reconciliation retires.
- D14 and D15 (`is` chains) hold.

## Were the revision-1 rejections justified?

- **(b)4, the eager `loop_factory` sub-claim: justified.** I re-ran p7: main and the child have `Handle._run` on their chains on both versions. With the loop boundary the point is moot anyway.
- **(c)4, the zombie keeping PY_UNWIND: the zombie argument holds, but the rejection is not sufficient.** Its criterion, a leak after a *completed* exit, is met by the `free_tool_id` route (M3).

## Mutation gate: what still needs judgement after the fact

- BF1: G_COVER is unattainable.
- M5: "faulted" is undefined.
- M11: control #2's baseline.
- G_COVER's "fold onto the guard line" remedy is an implementer's choice after the fact. It is gameable, but it is not a judgement call.

## Exam cases that cannot be written, or are not deterministic, as specified

- **Not deterministic:** M7 (X71c).
- **Depend on facts the spec leaves open:** M6 (the faultpoint code identity), M8 (the callback trials in X140), M9 (V36b), M10 (R17).
- **One-sided boundary:** M12 (X138).

## The two new mechanisms

**Loop boundary.** It does what it claims for loops started inside a section: X65d and V63 reproduce, and X65d over-credits once the boundary is removed. It cannot separate *same-loop* re-entrant dispatch, which is left to the cut, and the cut has the holes in M1.

**Per-hit `_cut_ok()`.** It catches a transient rebind of `Handle._run` itself, but:
- it watches only `Handle`'s class dict (A1, A2);
- it trusts whatever E2 saw, including shared decorator code (M2);
- it cannot see a dispatch that began under another binding (R17).

**Cost.** Both are cheap (N1).
