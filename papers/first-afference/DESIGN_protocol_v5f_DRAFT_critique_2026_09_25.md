# Completeness critique of the v5f design draft (panel run wf_8d2e6ad5-5a0)

Unaddressed. The next revision must close every item before an exam brief is written.

**Completeness critique of `DESIGN_protocol_v5f.md`**

All 58 round-4 keys appear in the per-finding disposition tables (lines 696–774); none is missing. The problems are in what some dispositions actually close, and in sentences that are false. I checked the four behaviours marked "probe" below on 3.12.3 and 3.13.12, with scripts in `/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/critic_complete/`: `p_free.py`, `p_freeze.py`, `p_meta_eq.py`, `p_execref.py`. The rest is reading the spec against the audit, the verdicts and `run_protocol_v5e.py`.

## (a) Dispositions that do not close their finding

1. **D15 resolution-isinstance-runs-user-code (FIXED, line 734).** Resolution still runs user code.
   - Line 151 ("Unwrap first. If `type(obj) in (staticmethod, classmethod)`"), line 155 and the delta at line 103 test membership in a tuple, which compares with `==`.
   - If the object's class has a metaclass that defines `__eq__`, that `__eq__` runs twice at every path step (probe, `p_meta_eq.py`). If it raises, the raw exception escapes `__enter__`. That is R1-D2 again, and it makes line 138 ("runs no user code except the import and PEP 562") false.
   - The same pattern is at line 464 (`type(result) in _LAZY_TYPES`, inside `_run` after fn returns).
   - V40 and X17b cannot detect it.
   - Fix: use `is` comparisons.
2. **B5 stale-stop-after-mint-of-handle-run (FIXED, line 703).** The cut is only checked at exit.
   - CUT_MOVED is tested only at exit (line 199), and the cut is refreshed only at construction and E2.
   - A harness or library that rebinds `Handle._run`, or swaps its `__code__`, and restores it before exit loses the cut silently in between, with no CUT_MOVED.
   - Line 285 ("it cannot move during a trace without CUT_MOVED") and over-blocking #21 (line 879) are therefore false. X141 restores only after exit, so it cannot catch this.
3. **E5 examhole-stop-read-before-mint (line 750).** Neither X34 nor the `cut_current` leftover check exercises the entry refresh at E2 (line 378).
   - No case replaces `Handle._run` between `coverage_trace()` and `__enter__`.
   - A mutant that deletes E2's `setdefault` survives, and it would falsely refuse CUT_MOVED on such a harness.
   - It needs a valid witness case, or an SM1 row filed before the freeze.
4. **D1 fork-pool-child-nested-refusal-and-hook (line 720).** The row says the "bootstrap frame" sentence is restated, but line 285 still says "forked children … start at their own bootstrap frame". A forked child's main thread is a copy of the forking stack; that is exactly what the finding was about.
5. **S2 gc-freeze-hides-live-clone (line 713).** Clause (b) fires without any freeze or unfreeze call.
   - `gc.get_freeze_count()` goes down when frozen objects are freed (probe, `p_freeze.py`: 5441 → 5430 after `del`).
   - In any process that froze objects before the trace (preforking servers, or 3.12.3's 375 boot-frozen objects), a changing count plus one unexplained reference refuses CLONE_ALIVE. An unexplained reference can be a frame of T executing on another thread at exit (probe, `p_execref.py`: an executing frame's code reference is invisible to gc).
   - #19's heading (line 872) and the message at line 195 ("gc was frozen or unfrozen during the trace") are false. This over-blocking is not disclosed.
6. **E26 (X137 `free_tool_id` variant, line 1044).** The expected outcome is wrong.
   - On 3.12.3 and 3.13.12, `free_tool_id` leaves events and callbacks in place (probe, `p_free.py`), so g is still credited.
   - The expected "NOT_EXERCISED for g" is wrong; the outcome should be PASS plus MONITOR_LOST.
7. **E23 (V28b, line 1056).** "B counts its calls after the hop exactly" conflicts with the attribution rule.
   - After the hop, B and A are openings of the same tracer on one stack.
   - By the rule at line 226, and by v5e's X70, B's post-hop calls are *ambiguous*, not counted.
8. **E21 (V57, line 1077).** V57 says the profiler is installed on the main thread, but line 1116 says V57 runs inside the self-trace, where each case runs on its own thread (line 946). `sys.setprofile` is per-thread, so the case as specified cannot be written.
9. **D3 / X93d (line 1022).** X93d expects "NO_TRACE, second wording". M11 (line 509) gives an `object_pairs_hook` trace the *third* wording.
10. **D10 (line 729)** is marked FIXED, but the import and PEP 562 sites still turn an asynchronous `Exception` into UNRESOLVED (line 921). The row should read FIXED + DISCLOSED_LIMIT.

## (b) Limit or over-blocking sentences that are false for the design

- **I6, line 579:** "A fault never causes … a swallowed exception." L-DELIVERY (line 925) says a fault in the unwind callback *replaces* the exception in flight and drops the original.
- **Line 56:** "no import runs inside enter or exit". E3 (line 379) runs `importlib.import_module` inside `__enter__` (line 149). G_HYG (line 1303), "no import in any function reachable from `_enter`", contradicts the required resolution step.
- **L-MONITOR, line 934, and #7, line 838:** "frees styxx's id … blinds the trace" is false for `free_tool_id` on 3.12 and 3.13.
  - In addition, the MONITOR_LOST repair at line 406 ("re-registering … also repairs it") overwrites the callbacks of another tool that took the freed id.
- **L-WHERE, lines 894–899:** v5e named "uvloop's Cython handles" (v5e line 492); v5f drops them. Under uvloop, line 285 ("Every asyncio task step and callback is run by a `Handle._run`") is false, and so is #2 (line 824, "counts nothing"). #2 also fails when an eager factory is set through `loop_factory`.
- **#19, line 872:** the trigger is any change in the count since the mint, including frozen objects dying. For a mint an earlier tracer made, that change can come from before this trace.
- **L-STUB, line 910:** "proves … compiled from its own module's file" contradicts line 913, where `co_filename` can be forged.
- **Line 884:** "executed for cProfile, `profile`, pure-Python profilers". The listed evidence (lines 74 and 635, D3 `p2_callback`) covers cProfile, pdb, coverage.py and a pure setprofile under D3's adapter. It does not cover the `profile` module, and nothing ran on the v5f machine.
- **M8, line 477:** a never-entered tracer gets TRACE_ACTIVE with "inside its with-block … calling `__exit__` again completes it". Both parts are false for a tracer that was never entered.
- **Line 555:** "exit's `except GateSpecError`" is singular, but X0 (line 395) has a second one.
- **Lines 115 and 520:** "runs no user `__eq__`/`__hash__`" is too strong. A `dict.get` on a user dict whose keys are str subclasses runs their `__eq__` on a hash collision. This is contrived.

## (c) Round 1–3 blocker classes the design reopens

- **R1-D2 (resolution runs user code):** reopened through the metaclass `__eq__` in (a)1.
- **R1-B3 / R2-B2 / R3-B2 / J1-X2 (cross-dispatch attribution):** reopened by a transient `Handle._run` rebind, which has no CUT_MOVED ((a)2). Under uvloop it was disclosed in v5e and is no longer disclosed ((b)).
- **R1-B4 (styxx destroys another tool's instrumentation):** reopened in two ways.
  - Line 406: re-registration at exit clobbers a new owner of a freed id.
  - Line 384: "adopt an id already named ours" lets a second `styxx.protocol` copy in one process overwrite the first copy's callbacks. That covers a reload, or the exec'd-copy pattern the lab itself uses.
- **R2-B3 (instrumentation persisting):** a zombie keeps the process-wide PY_UNWIND callback and its cost indefinitely. L-ZOMBIE (line 928) mentions only the installed mints.

## (d) Parts of G_SEM that need human judgement after the fact

1. **G_COVER pragmas (line 1304):** the implementer writes them after the fact, and only the round-5 red team audits them. The gate can be met by adding pragmas.
2. **SM2 UNDISTINGUISHED (line 1268):** these mutants are presumed equivalent and handed to round 5 for a human decision.
3. **Noise mask:** "N ≥ 5" (lines 29 and 1263) is not a fixed N. Whoever runs it chooses how big the mask gets.
4. **Spec-fixed message substrings (line 1255):** the list is open-ended ("the named remedy …"). The corpus is "round 1–4 repros rewritten against the public API" (line 1252), with no author or freeze point named.
5. **SM1 retirement (line 1216):** "anchor text absent from `ref_v5f.py`" is true for almost every v5e anchor in an independently written reference, so the test decides nothing. The spec names a replacing rule for only four examples.
6. **Positive controls:**
   - #1 (line 1284) gives an "for example" list rather than a fixed one.
   - #2 needs a v5e normalizer over `_v5_state()` fields that v5e does not have.
   - #3 (lines 1286–1288) cites `fault_injection_v5.py` results, not the frozen `crash_sweep_v5f.py`.
7. **G_FI allowed windows (lines 1294–1296):** deciding which fault points fall in "pre-claim exit" or "facade-return" means mapping implementation offsets after the fact, unless the windows are defined purely by outcome.
8. **SM1 rows M1–M8 (line 1222):** the "named witness" is the crash-sweep invariants, not a case id, so WITNESS_MISMATCH is undefined for those rows.
9. **SM2 region (line 1230):** the implementer places the `# -- v5` marker that bounds SM2 and G_COVER.

## (e) Exam cases that cannot be written before the implementation exists (or as specified)

1. **X36 (line 1004):** styxx keeps its tool id for the whole process (lines 52 and 634), and every case runs inside the self-trace (line 946). By then id 4 is already held, so the case cannot hold ids 3 and 4 itself. It needs a subprocess, and the spec does not provide one.
2. **V34 / G0 (lines 974 and 1312) against X57b, X58b and V36:**
   - Those three cases call `gc.freeze()` inside the self-trace.
   - The self-trace declares `_exit`, whose executing frame is an unexplained reference at the self-trace's own exit.
   - Clause (b) then fires on the self-trace. On 3.12.3 that happens even after `unfreeze`, because the count returns to 0, not 375. The result is a G0 failure and a G_XVER split.
   - V34 also requires a `_run` count, but `_run` is not declared.
   - `_resolve_target` is not a name the spec fixes.
3. **Cases tied to implementation internals:**
   - X92b (line 1020) needs "between restore and unregister", i.e. implementation bytecode.
   - X131 (line 1040) needs "a line of the provenance walk", a function the spec never names.
   - X138 and X139 depend on `_exit_txn` and `_enter_txn`.
   - The `_v5_faultpoints()` keys are whatever qualnames the implementer chooses (line 504).
4. **Hazard-sweep mutants:** H1 (Lock), H6 M1–M8, H7 (setprofile source) and H8 (publish-at-entry) (lines 1127–1134) all need patches to internals. Line 948 lets the exam read only the public API plus the two introspection functions. These mutants can only target `ref_v5f.py`, or be written after the implementation exists.
5. **X140 (line 1047):** where the signal lands is timing-dependent. Landing before X1 gives TRACE_ACTIVE and after X8 gives PASS, so "TRACE_INCOMPLETE" is not deterministic.
6. **V52 (line 1073):** in the failed-enter variant, `record()` must refuse TRACE_INCOMPLETE (line 477), not "PASS {f:1}".
7. **Delta table (lines 960–976):** it omits X71c, which reads `P._hook` and rebinds `P._ANCHORS` and cannot be ported under line 948. So G_V5E_DELTA (line 1321) cannot pass as written.
8. **Minor gaps:**
   - The prebuilt `/3` traces for 3.10 and 3.11 (lines 631 and 945) have no stated source.
   - V38 (line 1060) must say that `Memo` stamps `__wrapped__`; otherwise v5f refuses FOREIGN_DEFINITION.