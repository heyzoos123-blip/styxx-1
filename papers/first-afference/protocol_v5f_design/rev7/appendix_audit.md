
---

## Appendix A: self-audit of the normative claims (revision 7)

**Why.** Revisions 5 and 6 each had a blocker of one class: a normative sentence ("the loss is silent only when…", "no one-call step raises an audit event") that no faithful implementation satisfies, and that no case or model property checked. Revision 7 therefore audits every normative absolute in the text, not only the ones a critic named.

**Method.** A script extracted every occurrence of *must*, *never*, *always*, *cannot* and "0 violations" (in any case) from the normative text: everything from the title through "What round 5 should attack first". That is 305 hits. The audit ran on the revision-7 text before this appendix and the Revision 7 section were added (`rev7/audit_claims.json`; the classified list is `rev7/audit_claims_classified.txt`, one line per hit, and `rev7/audit_classify.py` holds the classification as data). Each hit is in one class:

| class | meaning | hits | what counts as its witness |
|---|---|---|---|
| P | a property of the mechanism ("X never happens", "Y always holds") | 104 | a named exam case whose outcome differs if the property fails, or a model-check property, or a static G_HYG clause |
| D | a disclosure: an over-block, a limit or a residual ("never credited", "cannot tell") | 25 | the pinned case or residual that fixes the disclosed outcome |
| C | a fact about CPython the design relies on | 18 | the probe that measured it, or the frozen gate that re-measures it |
| G | a rule that a gate, the harness or the exam author must follow ("the run must fail", "must equal the table") | 81 | the gate's own execution; there is nothing further to test |
| N | a case's own expected outcome ("the body never ran") | 32 | the case itself |
| S | a summary row (Delta table, per-finding disposition, closure) | 18 | the cases its own row names, and the section it summarizes |
| H | history, rationale, a heading, or a quoted earlier claim | 27 | none needed |

"0 violations" in the Revision 1–7 sections are records of runs, not normative claims. Each cites its output file, and the seventh critic re-ran every revision-6 output with the same result (N9). They are not in the 305.

**Result.** Of the 147 P, D and C hits, 127 had a witness before this audit. The other 20 make up twelve findings: A1–A3, A5–A9 and A13–A16. Reading the sentences around each hit found four more, which the keywords do not mark or which sit in a summary row: A4 in the R1-B4 row, A10, A11, and A12 (the critic's B1). Each of the sixteen is resolved below: given a witness, weakened, or corrected. After the audit every P and D claim names a witness, with two exceptions: A13, open under SM1's pre-freeze procedure, and one D claim that cannot be tested in-process (frames that never return). Two C claims rest on probes that no frozen gate re-runs (A14).

**The findings.**

| # | claim (section; audit ids) | before the audit | action |
|---|---|---|---|
| A1 | "If no anchor is registered anywhere, store nothing" and "a hit while no section is open stores nothing" (M6 At a hit; L-DIAG; ids 42, 198) | no case: the rule's only effect is pending entries that nothing pops (frames kept alive) | **V67** (new): 100 raising calls outside every section leave `pending == 0`; the mutant leaves 100 (`rev7/w7_audit.py`). Mutation row added |
| A2 | "`_open`, `_detach`, the callbacks and `record()` never take" the mutex; "opens, closes and callbacks never wait"; MACHINERY_BUSY "an open never waits, so it never raises this" (M2, I5, Reason codes; ids 70, 126, 147, 148) | no case: revision 5's c3 and c8 probes were never made exam cases | **V68** (new): while an exit's transaction is held for 3 s, another thread's open returns at once; with the open taking the mutex it waits and raises MACHINERY_BUSY (`rev7/w7_audit.py`). Mutation row added |
| A3 | "styxx never calls `sys.setprofile`, `threading.setprofile`, `sys.settrace` or `threading.settrace`" (What is removed; FOREIGN_PROFILER row; R1-B4; ids 120, 154) | the leftover checks see only a lasting change, not a set-and-restore | **G_HYG clause** (new): no call or read of those names (and the `*_all_threads` forms) in the region |
| A4 | R1-B4: styxx "never registers callbacks or changes events on an id that lost that name" | **false** since revision 6: the registration residual lands one exchange on such an id | **weakened**: "never changes events or local events"; the one registration exchange is named as the exception (L-MONITOR; X154b) |
| A5 | "a function created after E2 that reuses a cut code … an over-block, never an over-credit"; "toward acceptance, never over-credit" (M4 E2; #21; ids 82, 187, 188) | probes only (`critic3/c8`), no pinned outcome | **R20** (new pinned residual): a clone of a cut code between f and the anchor gives `dispatched {f:1}` (`rev7/w7_audit.py`) |
| A6 | "The identity test cannot tell that tool from styxx" (Tool acquisition prefix; L-MONITOR; ids 137, 196) | a disclosure with no pinned outcome | **R21** (new pinned residual): a hostile re-take under styxx's name object is invisible: PASS `{f:2}`, no MONITOR_LOST (`rev7/w7_audit.py`) |
| A7 | "A `code.replace()` copy of M_T carries no monitoring events and is never observed" (Why class A cannot reopen; id 33) | reading only | **R22** (new pinned residual): such a copy run in a section is in no bucket and records no problem (`rev7/w7_audit.py`) |
| A8 | "the machinery never calls a wrapper installed on `sys.monitoring` after the first binding" (M0; over-blocking #6; id 177) | reading only; revision 6's version was false after a reload (M3) | **V69** (new): a counting wrapper installed after the first `coverage_trace()` is called 0 times while a later trace passes (`rev7/w7_audit.py`); M3's reload hole closed (X156c) |
| A9 | UNDECLARED_SECTION "never compared" (At open step 3; Reason codes; id 149) | X78f used `5`, which runs no user `__eq__`, so the case could not see a comparison | **X78f variant** (new): a section whose class counts `__eq__` and `__hash__`; the counters stay 0 |
| A10 | "A tool left named ours with missing callbacks … is adopted and re-registered at the next enter" (Tool acquisition prefix) | **false** when `_TOOL[0]` is set (a reclaim's registration): the next enter keeps the named id and does not register | **corrected** (F29): the next exit's X5 repairs it; X157b's R shows it |
| A11 | L-MONITOR: "`free_tool_id` … Exit notes MONITOR_LOST because the name is gone"; M3 step 3 "the next reconciliation re-takes and counts the id" | **false** when an audit hook raises inside the reclaim's registration: the re-take is never counted (F25) | **weakened** in L-MONITOR, M3 step 3, the reason row and the prefixes; **X157b** pins the residual, **X157c** shows the lost call is still noted |
| A12 | L-MONITOR: "The loss is silent only when the party … restores it" (B1) | **false** in revision 6 (the seventh critic's B1) | **fixed by mechanism** (the in-call count); **X158**, **X158b**; the `cb2:` model configurations |
| A13 | "While an entry is pending, its frame id cannot be reused" (Decisions: pending-entry key; id 9) | the SM1 catalog already lists "pending entry keyed without frame identity" as expected UNWITNESSED | **open, by the spec's own procedure**: before the freeze the exam author writes a witness or files it EQUIVALENT_BY_SPEC with a signed argument (SM1, "Unwitnessed rows"). The shape a witness needs: a stranded `u`-outcome entry whose frame dies, and a new frame of the same code reusing its id with no anchor registered at its entry; the mutant then publishes a stale uncredited count |
| A14 | "RecursionError cannot land after a step's first write" (M7 One-call steps; id 92) and "gc runs only at eval-breaker checks" (id in the same paragraph) | probes (`critic6/a4`, `a5`, `a6`), not frozen with G_ATOM | **kept, disclosed as probe-only** here and in weakest point 1: G_ATOM's frozen t1 and D2 parts re-measure gc and signals, not recursion |
| A15 | "the body never runs" after a MemoryError in `_unwind_on` (M7 One-call steps; id 93) | reading only | **witnessed by X144**, which faults `_unwind_on` at its return: the same control flow (an exception out of `_commit` before `o.armed` and the body) |
| A16 | "Only its `[V5:UNSUPPORTED_VERSION]` prefix is spec-fixed" against X156's quoted text (M0; N6) | a contradiction (the seventh critic's N6) | **corrected**: X156 and X156b–d check the prefix only |

**The P, D and C claims and their witnesses.** Claims with the same content are merged. "Model" means `m7_modelcheck.py` (property named), and "G_HYG", "G_ATOM" and "G_FI" mean the frozen gates' named clauses.

| section | claim (ids) | class | witness |
|---|---|---|---|
| Grafts | PY_THROW is never used (1) | P | X119; G_HYG (only PY_START, PY_RESUME, PY_RETURN, PY_YIELD, PY_UNWIND named) |
| Grafts | `'<'` code in the module's globals is a pinned residual, never an open door (3) | D | R05b |
| Grafts | CLONE_ALIVE never fires on "count > 0" (4) | P | V36b |
| Decisions | child work is never credited (7); a child never opens or credits a section (49) | P | V47; G_FI C9 |
| Decisions | a second loaded copy never overwrites the first's callbacks (8) | P | X142 |
| Decisions | a pending entry's frame id cannot be reused (9) | P | A13: open under SM1 |
| Decisions | asyncio is never imported at `styxx.protocol` import or inside enter or exit (10, 11) | P | G_HYG import clause |
| Verified | PY_UNWIND cannot be a local event (12) | C | `synth/p_syn1.py` |
| Resolution | no `obj.__class__` read, no tuple-membership type test; `is` chains (16, 90) | P | V40, V40b, X17b; G_HYG |
| Resolution | a Python-level `__dict__` descriptor is never called (17, 24, 146) | P | X17b, X30d |
| Resolution | PEP 562's two products must be identical (18) | P | X13b |
| Resolution | a cache wrapper's callee must be its own-dict `__wrapped__`; never what `__wrapped__` says (19, 36) | P | X24b, X24c |
| Resolution | the module must have an exact-str, non-`.pyc` `__file__` (20, 26) | P | X26e, X26f |
| Resolution | every visited link must be coherent; F_T is always checked (21, 27, 28, 29, 34, 35) | P | X26b, X26c, X26d |
| Resolution | `_own_dict`'s descriptor and exact-dict rules (22, 23) | P | X17b, V38, V40 |
| Resolution, Tripwires | the two bindings are read from the captured class dicts, never afresh or re-read (25, 31) | P | X65f |
| Why class A | a `code.replace()` copy of M_T is never observed (33) | D | R22 (A7) |
| Why class A | the doors that remain are never claimed closed (37) | D | R03, R04, R05, R05b, R06, R13 |
| Attribution | a loop started inside a section never credits it (38, 189) | P | X65d, V63 |
| Attribution | event loops must run outside the section (39, 175) | D | X73 |
| At open | a str subclass section is normalized, never `'Sec.G'` (40) | P | V39 |
| At open | a non-str section refuses without being compared (149) | P | X78f variant (A9) |
| At a hit | nothing is stored while no anchor is registered (42, 198) | P | V67 (A1) |
| At a hit | a frame killed at entry never ran its body and never publishes (43, 123, 133, 134) | P | X135, H8; G_FI C1 |
| At a hit | a `throw()`/`close()` resumption is never counted (44) | P | X119 |
| At close | `get_events` never raises, even on a freed id (45, 136) | C | `rev5/out_freed_id_calls.txt` |
| Score | notes and `end != "returned"` never refuse (46, 65, 151, 152, 153) | P | X137 free variant (PASS with MONITOR_LOST), X147 (ii), X74d |
| Score | `ambiguous` and `uncredited` never count; uncredited is never evidence (47, 199) | P | V28b, X123, X72b |
| Why class B | confirmation never removes a condition (51) | P | X135 (with I1's argument) |
| M0 | the version and build are read at call time, never at import (52, 53) | P | X37b |
| M0, M1 | `import styxx.protocol` never touches `sys.monitoring` or asyncio (54, 63) | P | X37 on 3.10 and 3.11 (no `sys.monitoring` there); G_HYG import clause |
| M0 | `sys.addaudithook` cannot be undone (55) | C | the CPython documentation (PEP 578) |
| M0 | the bound functions must be the C builtins, checked at every `coverage_trace()` (57) | P | X156, X156b, X156c, X156d |
| M0 | Py_TPFLAGS_IMMUTABLETYPE is never set on a class statement's result (59) | C | X156b; the seventh critic's check |
| M1 | `_CALLBACKS5` is never called in a step (62) | P | G_HYG (only as an argument of `_map` and an operand of `_is_not`); G_ATOM (b), (c) |
| M1 | retained frames never hold the facade; a dropped facade dies while its section runs (66, 67) | P | X146c |
| M2 | the mutex is never taken by opens, closes, callbacks or `record()`; opens never wait; no MACHINERY_BUSY at open (70, 126, 147, 148) | P | V68 (A2) |
| M2 | a frozen `time.monotonic` or replaced `time.sleep` cannot remove the bound (71) | P | X138b |
| M2 | #130279 cannot leave anything held (72) | P | X140, H9 |
| M3 | a registration on an id another tool holds cannot be complete (73) | P | model REGSILENT; X154b |
| M3 | after a raising hook in the reclaim, the re-take is never counted (74) | D | X157b (F25) |
| M3 | an id another tool holds at a write's gate is never written by that write (76, 79, 194, 195) | P | X154 (four sweeps); X137b |
| M3 | a dead holder's record is never read again; X8 never runs (77, 78) | P | model (`prune_credit_stop` restored changes nothing); M8's refusals |
| M3 | retirement never leaves the event to clear (80) | P | model STALE; X137 free variant (`global_events == 0`) |
| M3 | the unguarded anchor pop cannot remove another opening's anchor (81) | P | model END, U1 |
| M4 | cut poisoning is an over-block, never an over-credit (82, 187, 188) | D | R20 (A5); `critic3/c8` |
| M4 | an id carrying any other name is never adopted (84) | P | X142, X142b |
| M5 | exit never raises GateSpecError (85) | P | H1 (REENTRANT recorded at exit); the model's `exit(X)+[rec]` |
| M6 | callbacks never run at a C call; styxx never enables INSTRUCTION, LINE, JUMP or BRANCH (87, 88) | P | G_HYG (event names); H7 |
| M6 | callbacks cannot re-enter themselves (89) | C | `synth/p_syn1.py` |
| M7 | `_detach` never assigns `o.frame` (91) | P | G_HYG; X146 |
| M7 | RecursionError cannot land after a step's first write (92) | C | `critic6/a4`, `a5` (probe only, A14) |
| M7 | after a MemoryError in `_unwind_on` the body never runs (93) | P | X144 (A15) |
| M7 | the one-call step never clears after an anchor registered while the event was set: 0 violations (94, 95) | C | t1 part A under G_ATOM's floors |
| M7 | D2: 0 violations for the one-call step (98) | C | D2 under G_ATOM's floors |
| M7 | a repair is never separated from its count (99) | P | X158b; G_ATOM K10 and criterion (c); model `count_after_register` |
| M7 | registration cannot be made atomic; styxx cannot remove the audit event (100, 101) | C | `critic6/a1_audit_monitoring.py` |
| M7 | U1: an armed section's body never runs with S clear (103, 124) | P | model U1, A0; X143, X145; G_FI C8 |
| M7 | a fault never clears S (105); a fault cannot cause UNWIND_LOST (128) | P | model U1, FALSEFLAG with faults; G_FI C8 |
| M7 | a fault cannot land inside a one-call step (106, 131, 139, 200) | C | G_ATOM |
| M7 | `_register` never writes S (107) | P | G_HYG (`set_events` only in the other steps); G_ATOM state criterion (d) |
| M7 | U3: a set S with no anchor never exists (108, 109) | P | model STALE; X152; `rev5/spec_rev5_eventpath.py` |
| M7 | a dead anchor is never on a live chain (122) | P | X146d |
| M8 | TRACE_ACTIVE texts (110, 111, 150) | P | X91, X92c |
| M9 | pass-through is correct even if the at-fork handler never ran (112) | P | G_FI fork scenario, C9 |
| M11 | generator and coroutine objects created before the trace are never credited (116, 179) | D | R14 |
| M11 | `check_metrics` never raises for a JSON-shaped result; its note always starts with `[V5:CODE]` (117, 118) | P | X117b, X103b, X117d |
| Removed | styxx never calls `setprofile`/`settrace`; never touches profilers (120, 154) | P | G_HYG clause (A3); V48, V57 |
| I5 | a skipped release cannot hang anyone (125) | P | model HANG (bounded); H1 |
| I6 | a fault never causes over-credit, a hang, a stale mint or a poisoned later trace; never swallows an exception except L-DELIVERY (129, 130) | P | G_FI C1, C2, C3, C5, C7; H2 |
| Prefixes | fn never runs after a fault in `_commit` (132) | P | X144, X143b |
| Prefixes | a pending entry whose confirmation never arrives stays until retire (135, 197) | D | `critic4/a6_pending_left_fault_free.py`; G_FI C5's exclusion |
| Prefixes, L-MONITOR | a hostile re-take under styxx's name object cannot be told from styxx (137, 196) | D | R21 (A6) |
| L-ZOMBIE | a tracer whose exit never began stays active (138, 193) | D | X92c |
| Version, L-MONITOR | styxx never touches an id another tool took (143, 178) | P | X137b |
| Reason codes | REENTRY always appended to problems (145) | P | X32d, V52 |
| Over-blocking | off-stack work never counts (174) | D | X82, X83, V35; v5e's refused cases (#16) |
| Over-blocking | sections must be calls (176) | D | X74d |
| Over-blocking | a wrapper on `sys.monitoring` after the first binding is never called (177) | P | V69 (A8) |
| Over-blocking | code run inside a trace, profile or monitoring callback is never credited (180, 190) | D | R12 |
| Over-blocking | an inherited tracer cannot exit in the child (181) | P | V47; G_FI C9 |
| Over-blocking | frames that never return, yield or unwind are never counted (182) | D | reading: no confirmation event exists for them (untestable in-process) |
| Over-blocking | references gc cannot see refuse after a freeze rise; dying frozen objects never trigger it (183, 184) | D | V36b; `rev1/p4_freeze.py`, `p5_execref.py` |
| Over-blocking | a clone alive at the first construction never enters the cut (186) | D | `critic3/c9_x34b_fixture_poisons_first_e2.py`; the X34b harness rule |
| L-DELIVERY | the lock-release hazard cannot arise from styxx (191) | P | H7 |
| L-DELIVERY | a handler's first instructions always run untraced (192) | C | the H10 table (0 lost handlers untraced) |

**What the audit shows about the method.** Of the sixteen findings:
- six had no witness because the property was argued rather than tested (A1, A2, A3, A7, A8, A9);
- four were false or overstated sentences carried from an earlier revision after the mechanism changed (A4, A10, A11, A16);
- three were disclosed behaviours with no pinned outcome (A5, A6, A13);
- two rest on probes or on reading (A14, A15);
- one was the critic's B1 (A12).

No critic had raised A1–A11, A13, A14 or A15. The audit is repeatable: `rev7/audit_classify.py` holds the classification, and a later revision should re-run the extraction and classify every new hit before it is frozen.
