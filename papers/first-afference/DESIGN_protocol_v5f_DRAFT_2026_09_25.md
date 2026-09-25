# protocol v5f: claim-and-reconcile mint-and-anchor on sys.monitoring, with confirmed-entry credit (synthesis)

**Basis.** Both judges chose the "claim-and-reconcile" design (D1), and this spec starts from it. Judge 1 restricted it to its sys.monitoring adapter on CPython 3.12/3.13. Judge 2 kept it whole and asked the panel to decide 3.11 explicitly. From D1 this spec keeps:

- the crash-consistent state machine: single GIL-atomic claims, idempotent cleanups, a robust mutex that steals from dead owners, and reconciliation at the next transaction;
- its resolution changes and its per-finding plan;
- its monotone dispatch cut, its fork pass-through and its SM1/SM2 semantic-mutation gate.

The grafts the judges named are taken as listed below. Where the judges disagree, or where the designs disagree and no judge ruled, the decision and its reason are stated.

**Grafts taken from "steward-and-monitor" (D3).**
1. **Version policy.** Tracing refuses UNSUPPORTED_VERSION everywhere except CPython 3.12 and 3.13 GIL builds. D1's setprofile adapter is deleted, and with it FOREIGN_PROFILER, PROFILER_LOST, THREAD_HOP, SIGNAL_TIMER, install epochs and the f_lasti rule.
2. **Confirmed-entry credit.** PY_START and PY_RESUME compute the attribution and hold it *pending*. A pending entry is published only at PY_RETURN or PY_YIELD, or at a PY_UNWIND whose offset is past the entry offset. PY_THROW is never used. `_retire`, reconciliation and the at-fork handler drop a mint's pending entries. The deterministic "died at entry" case (t_confirm_det3 / cr_det3) is frozen as X135, and a signal-flood gate asserts credited ≤ body runs (H8).
3. **Coherence on every visited link, F_T included.** Cases X26b, X26c and X26d cover it.
4. **Interfaces and coexistence.** The frozen `_v5_state()` introspection interface, the MONITOR_LOST note, and coexistence cases for cProfile, pure-Python profilers, pdb, and coverage.py's ctrace and sysmon cores. The real-callee identity for cache wrappers (from `gc.get_referents`) was already in D1.
5. **Mutation-gate additions.** The G_SEM positive control (the gate must fail on v5e with v5e's frozen exam); the every-site generic operator catalog, where a mutant that compiles byte-identical (TCE) counts as equivalent by construction; and the G_FI and G_SIG companion gates with named allowed windows.
6. **Not grafted:** the steward thread (a reproduced shutdown hang and a cross-thread finalizer deadlock), and D3's "≤3% unseparated" gate. Both judges rejected both.

**Grafts taken from "narrow" (D2).**
1. **Named isolating witnesses.** Every SM1 catalog row is killed only by its own NAMED, isolating witness. Detection by some other case is WITNESS_MISMATCH and fails the row. EQUIVALENT_BY_SPEC may be argued only before the freeze, and every quantitative rule gets boundary rows on both sides.
2. **Sourceless and fileless modules.** A declared module without an exact-str `__file__`, or a sourceless one, refuses FOREIGN_DEFINITION. `'<'`-compiled code in the module's own globals is a pinned residual (R05b), never an open door.
3. **CLONE_ALIVE under gc.freeze.** It fires on a *rise* in the freeze count since the mint was made, together with D1's visible-referrer accounting, never on "count > 0". The draft said "delta"; revision 1 makes it a rise, because frozen objects dying lower the count. The 3.12.3 interpreter here boots with 375 frozen objects (3.13.12: 0; synth/p_syn1.py).
4. **Exact type before hash or compare.** Every hash or comparison in `score` and `check_metrics` is preceded by an exact-type test.
5. **Remedy-bearing refusal texts,** including the `'module:name.__wrapped__'` remedy. D2's rule that a staticmethod or classmethod is unwrapped at *every* path step is taken so that the remedy works for class-held caches. Probe p_syn1.py shows that a 3.12/3.13 staticmethod's own `__dict__` has no `__wrapped__`.
6. **Gates.** G_REF (refusal deletion by coded literal) and G_COVER (line coverage). Revision 1 removes G_COVER's pragmas; see G_COVER.

**Own-gate repairs from judge 2, all adopted.**
- `ref_v5f.py` is written from this spec's text alone, not from any prototype.
- SM2's differential probe compares only spec-fixed observables, listed exhaustively under SM2. Its noise mask is built from exactly N = 5 unmutated runs per version, may not cover a code, count, end, note or problem, and its size is reported (revision 1).
- v5e case ids and the leftover harness are reused wherever the semantics did not change.
- The ported v5e cases are run against `ref_v5f.py` at freeze time, and their delta must equal the "v5e cases whose outcome changes" table.

### Decisions where the judges disagree

| question | judge 1 | judge 2 | decision and reason |
|---|---|---|---|
| Keep 3.11 (setprofile adapter)? | Refuse 3.11; one adapter | "Put the panel question on the record": refuse 3.11 if L-SIGNAL-311 is py310-class | **Refused.** L-SIGNAL-311 is py310-class. A Python-level profile hook turns every C call on a sectioned thread into a point where CPython *skips the call* when an asynchronous exception lands there. That corrupts the traced program: the harness's own `with lock:` release is skipped and other threads hang. It was measured on D1's 3.11 adapter at 3606/50385 SIGALRM timeouts (D1), 2238/31329 (judge 2) and 1458 leaks in 4 s (judge 1), against 0 untraced. This is the mechanism of round-4 BLOCKER hook-exception-leaves-lock-held, whose fix sketch was "no profile hook when a C lock method is called", and no 3.11 hook can meet that. SIGNAL_TIMER covers only the detectable precondition: SIGINT, handlers installed mid-section and pthread_kill remain. The cost is real and disclosed as over-blocking #6: 3.11 is the lab's default interpreter, and the P1 retro and the exam move to 3.12/3.13. |
| 3.11 f_lasti pairing for every target (judge 2 graft 1) | — | Required if 3.11 is kept | Moot, because 3.11 is refused. |
| A test-only fault hook (judge 2 graft 2) | Not asked | "plus a test-only fault hook" | **No hook in production code.** A test branch in the hot path would itself be mutation surface. Instead a frozen, read-only `_v5_faultpoints()` returns `{qualname: code}` for every machinery function. The frozen injector (sys.monitoring INSTRUCTION/LINE events on tool id 5) and the exam's lower-id fault tool (id 3, PY_START) take their targets from it. This meets judge 2's aim: the exam and the SM instruments read no private name except `_v5_state()` and `_v5_faultpoints()`. |
| SM2 attainability | UNDISTINGUISHED reported, not gated; D3's ≤3% not adopted | EXAM_HOLE = 0 attainable only with a normalizer restricted to spec-fixed observables; mask N ≥ 5 | **Both are adopted** (revision 1: exactly N = 5, and UNDISTINGUISHED is never judged equivalent). The two positions do not conflict. An exam frozen before the implementation can only assert what the spec fixes, so SM2 compares only spec-fixed observables. Anything else a mutant changes is UNDISTINGUISHED, reported with its diff and handed to round 5. |

### Decisions where the designs disagree and no judge ruled

| question | decision | reason |
|---|---|---|
| PEP 562 attribute whose product differs between two calls | **UNRESOLVED** (D3). Not D1's NOT_A_FUNCTION, not D2's UNSTABLE_ATTRIBUTE | The name does not resolve to one object. NOT_A_FUNCTION stays about the *kind* of object, and no new code is needed. |
| Fork | **Pass-through** (D1): in another pid, `run()` just calls fn | Fork-pool jobs keep working. Child work was never credited. |
| Cache wrappers | **Accepted through the real callee** (D1/D3), not refused (D2) | Sound once identity comes from `gc.get_referents`. D2's `.__wrapped__` remedy is kept for the refusals. |
| Generator and coroutine targets | **Supported with confirmed credit** (D1/D3), not refused (D2) | Confirmation makes their counts sound on 3.12/3.13 (synth/p_confirm_frame.py; D3 p1/p4). |
| `'<'` co_filename | **Accepted, pinned residual R05b** (D1, judge 1), not refused (D2) | Refusing would refuse every dataclass `__init__` (V05) for a deliberate-only residual. |
| THREAD_HOP note | **Retired** (D3) | With no per-thread hook there is no post-hop blind spot to report. |
| Tool id lifetime | **Kept for the process** (D1), not released (D3) | Monotone state has fewer crash prefixes. The cost to other tools is disclosed. |
| Tool id preference | **4, then 3** (D3) | Callbacks for one event run in ascending tool-id order. Leaving 3 free lets a lower-id tool (the exam's fault tool, a debugger) act first; X135 depends on this. |
| Tool name (revision 1) | `_TOOL_NAME = "styxx.protocol/" + os.urandom(6).hex()`, drawn once per loaded copy of the module | `_ensure_tool` adopts only an id that carries *this copy's* name. A second copy of `styxx.protocol` in one process, such as an exec'd copy as the lab's runners use, takes the other id or refuses MONITOR_BUSY. It never overwrites the first copy's callbacks (R1-B4). **Revision 2 (N8):** `importlib.reload(styxx.protocol)` is not a second copy. It re-runs the module in the same globals, and M1's state is bound with `globals().get(...)` semantics, so the reload keeps the registries, the tool id and this name. Revision 1's plain bindings lost held mints and used up a tool id per reload (`rev2/p10_reload.py`). |
| Per-thread registry (`_TH`) | **Deleted** | With no hook to install, it served only the 3.11 adapter and diagnostic parity. Uncredited diagnostics are now counted on every thread. |
| Pending-entry key | `m.pend[id(frame)] = (frame, entry_offset, outcome)`, **holding the frame**, per mint (not D3's global bare-id map) | While an entry is pending, its frame id cannot be reused. Retiring a mint drops its entries in one `clear()`. |
| Where asyncio is imported | In `coverage_trace()` (the constructor), never at `styxx.protocol` import and never inside `__enter__` or `__exit__` | Scoring-only users do not pay for the import, and no *machinery* import runs inside enter or exit. The one import inside `__enter__` is the declared module's, at E3: resolution, outside the mutex, before anything global is touched, and a documented user-code site (L-ASYNC-EXC). D1 showed that an interrupted `import asyncio.events` inside `__enter__` leaves importlib's module lock held on 3.11. |

### Verified in scratch, and what was not

**Evidence reused from the designs and judges.** Paths are under `/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/`.

*D1 (`crashcons/`):*
- t_func 18/18 on 3.12.3 and 3.13.12.
- t_crash_sweep: an exception at every machinery bytecode. With the monitoring adapter: 6337 points on 3.12 and 6283 on 3.13, 0 failures, and a background tracer sharing the mint stays exact.
- run_mutants: M1–M8 detected; M9 and M10 survive as designed.
- t_sigalrm on the robust mutex: 233k/228k cycles, 26k timeouts, 0 holds left and 0 worker hangs on 3.12/3.13.
- t_lsignal: 0 user-lock leaks out of 51,075 (3.12) and 52,456 (3.13) under monitoring.
- t_lifecycle: re-entry race 50/50 exactly one entry; audit-hook failure mid-mint; fork pool.
- Probes p_prov, p_resolve_c, p_cache_callee, t_freeze.

*D3 (`monitor/`):*
- p1_events and p4_confirm: 0 body-less credits in about 9M calls and about 1,100 timeouts per version.
- t_confirm_det3: NOT_EXERCISED under confirmation; a false PASS under the publish-at-start mutant `mut_pubstart/`.
- t_coexist: coverage.py 7.16 ctrace and sysmon cores, and pdb.
- t_eager, p5_resolution.
- semmut_gen: 1,093 mutants on v5e. A 240-mutant sample detected 157 and let 83 survive.

*D2 (`narrow/proto/`):*
- The ledger demo: 24/24 rows killed by their named case, and the non-isolating control survives.
- lock_exit_path.py.

*Judges:*
- `judge_sound/j_bodyless_cc.py`: D1's publish-at-entry over-credits 30/50/27 in an 8 s flood on 3.11/3.12/3.13.
- `judge_sound/j_d1_wrapper_swap.py`: D1 provenance admits a foreign wraps wrapper whose `__code__` was swapped.
- `judge_testability/cr_det3.py`: a false PASS on D1 on 3.12.3 and 3.13.12.
- `judge_sound/j_mon_ulock.py`: 0 user-lock leaks under monitoring.

**Synthesizer probes** (`synth/`, run on 3.12.3 and 3.13.12, identical output):
- **p_confirm_frame.py.** Confirmation with frame-holding pending entries, local PY_START|PY_RESUME|PY_RETURN|PY_YIELD and a global PY_UNWIND. Results: plain 1; a call raising in its body 1; a 2-yield generator consumed 3; an unstarted generator dropped, closed or thrown into 0; `next()` then `close()` 1; `asyncio.run` of a one-await coroutine 2; killed at PY_START by a lower-id tool 0 (the body did not run); killed by a higher-id tool after the pending entry was stored 0; 0 pending entries left.
- **p_syn1.py.** Events are not delivered, to any tool, for code run inside a sys.monitoring callback. A staticmethod's own `__dict__` has no `__wrapped__`. PY_UNWIND cannot be a local event (ValueError). `gc.get_freeze_count()` at start is 375 on 3.12.3 and 0 on 3.13.12.
- **p_deliver.py.** An exception raised in a PY_RETURN callback makes a completed call raise in its caller. An exception raised in a PY_UNWIND callback *replaces* the exception being unwound, and its `__context__` is None. This is the basis of L-DELIVERY.
- **p_r16.py.** A lower-id tool raising at the target's PY_RETURN, and an exception raised inside styxx's own PY_RETURN callback before its pop, both leave the call counted once. It is confirmed by PY_UNWIND at the return offset, and no pending entry is left. This is residual R16.

**Revision 1 probes** (`rev1/`, run on 3.12.3 and 3.13.12, and on 3.11.15 where noted; each is cited where it is used; the table at the end lists them):
- `p1_meta_eq`: a metaclass `__eq__` runs under tuple membership. It does not run under an `is` chain or under `issubclass`.
- `p2_dict_collide`: a str-subclass key collision.
- `p3_free`: what `free_tool_id` leaves in place.
- `p4_freeze`: the freeze count falls when frozen objects die.
- `p5_execref`: an executing frame's code reference is invisible to gc.
- `p6_fork_chain`: a forked child's frame chain.
- `p7_eager_loop_factory`: eager factories set through `loop_factory`.
- `p8_cdispatch` and `p9_uvloop` (uvloop 0.22.1 on 3.12.3): dispatch with no cut frame.
- `p10`–`p13` and `p19`: the #130279 back-edge hazard.
- `p14` and `p16`: where signal handlers run.
- `p20`: `sys.setprofile` is per-thread, and nesting under `object_pairs_hook`.
- `p17`: re-entrant dispatch.
- `p18`: a transient `Handle._run` rebind.

**Revision 2 probes** (`rev2/`, run on 3.12.3 and 3.13.12; each is cited where it is used, and the Revision 2 table lists them). Most run against `rev2/mech2.py`. That is the second critic's event-path model (`critic2/mech.py`, written from the revision-1 text), extended with the revision-2 changes behind switches, so each probe compares revision 1 with revision 2 in one run:
- `p1_runonce_cut`, `p1b_runonce_binding`: `BaseEventLoop._run_once` in the cut; the routes A1, A2, A3 and old R17; the regression cases; the N4 witness.
- `p2_shared_cut`: a shared-code `Handle._run` binding, and the cost of the sharing scan.
- `p3_free_reclaim`: a callback outliving a completed exit after `free_tool_id`.
- `p4_unwind_scope`, `p4b_disable_kept`, `p4c_toggle_race`: the scope of L-DELIVERY, what per-section toggling costs, its effect on other tools' `DISABLE`, and its thread race.
- `p5_cover_driver`, `p5b_settrace_blinds_injector`: the direct-call coverage driver, and a settrace function silencing an INSTRUCTION injector.
- `p6_faultpoint_identity`: which code object an injector must instrument while the self-trace has minted it.
- `p7_x71c_landing`: how often X71c's signal lands in X3.
- `p8_atfork_abort`: an at-fork handler aborted by an audit hook.
- `p9_foreign_msg`, `p10_reload`, `p11_cost`, `p12_busy_bound`.

**Not verified: the v5f combination as a whole.** No prototype yet combines D1's machine with confirmation, coherence on every link, the freeze clause, `_v5_state()`/`_v5_faultpoints()`, the callback re-registration check in MONITOR_LOST, the deletion of `_TH`, and uncredited counting on every thread. Every D1 measurement above was taken with publish-at-PY_START and must be re-run on the v5f implementation (G_FI, G_SIG, G_XVER). Also not run: the frozen v5e exam, which reads v5e's private names.

---

## Delta from v5e, section by section

| v5e section | v5f change |
|---|---|
| **Target identity: rule** | Unchanged in meaning: `f_code is M_T` and `f_globals is F_T.__globals__`. A frame now *counts* only once confirmed (Attribution). |
| **Resolution** | Branches on the real type (`issubclass(type(obj), ModuleType / type)`, `type(obj) is staticmethod or type(obj) is classmethod`) and never reads `obj.__class__`. No type test is a tuple membership: `in` compares with `==`, which runs a metaclass `__eq__` (revision 1). Own dicts are read only through C descriptors; a Python-level `__dict__` descriptor stops the step or walk and is never called. staticmethod and classmethod are unwrapped at every step. PEP 562 `__getattr__` is called twice and the two products must be identical (else UNRESOLVED). INHERITED searches the whole MRO. A `sys.modules` entry that is not a ModuleType refuses UNRESOLVED. Only the import and the PEP 562 calls have an `except Exception` (chained UNRESOLVED); nothing else has a handler. |
| **F_T selection** | For a C cache wrapper, F_T is its *real callee* (the unique FunctionType among `gc.get_referents(wrapper)`), which must be the own-dict `__wrapped__`. Also refused: a callee bound by name in the module or the holder, and a sibling cache wrapper of the same callee there. New: RESERVED_TARGET for `Handle._run`, `BaseEventLoop._run_once`, or any function whose code is a cut code (revision 2 adds `_run_once`). |
| **Provenance** | The declared module must have an exact-str, non-`.pyc`/`.pyo` `__file__`. Every FunctionType link the walk visits, F_T included, must be *coherent*: its `co_filename` starts with `'<'`, or its realpath/normcase equals that of its own globals' `__file__`. The walk steps through the own-dict `__wrapped__` of *any* object, and from a cache wrapper to its real callee. It stays bounded at the object plus 16 hops and cycle-detected. The FOREIGN_DEFINITION message names the innermost `module:qualname`. |
| **Aliases** | Accepted only when the declared *objects* are identical. Different declared objects that reach one F_T refuse NOT_A_FUNCTION. |
| **Minting** | Under the robust mutex, in a prefix-consistent order: holder, then register, then local events, then install last. Each mint records `gc.get_freeze_count()`. Entry CODE_SWAPPED fires only against a mint that still has a live holder (reconciliation runs first). |
| **Tripwires** | CLONE_CALLED and CODE_SWAPPED are checked for *every* holder. CLONE_ALIVE adds the freeze clause: the gc freeze count *rose* since the mint was made. New tripwire: CUT_MOVED, checked at every entry event of minted code and at exit, on both watched bindings (`Handle._run` and, from revision 2, `BaseEventLoop._run_once`). |
| **Attribution: rule** | Unchanged anchor rule, but evaluated at the frame's entry event and credited only on confirmation. The cut is a monotone identity map of every `Handle._run` and `BaseEventLoop._run_once` code object seen (`_run_once` from revision 2). New in revision 1: the loop boundary. An opening is visible to a hit only while the thread's running asyncio loop is the one that was running when it opened. |
| **At open** | FOREIGN_PROFILER is retired. A str-subclass section is normalized with `str.__str__`; any other non-str section refuses UNDECLARED_SECTION without being compared. The NESTED_SECTION text now distinguishes a same-section opening from a different-section one. An open racing the tracer's exit refuses TRACE_INACTIVE. |
| **Close and exit** | THREAD_HOP and PROFILER_LOST are retired. Closing is one claim (`o.fin.setdefault`) plus idempotent cleanups. Exit is a claim, then a credit stop, detach, a transaction under the mutex, the tripwires, and a final commit. |
| **Mechanism** | `_LOCK`, `_ACTIVE`, `_STOP`, `_THREADS`, `_EPOCH` and the profile hook are deleted. New: the robust mutex (`_GUARD` and `_Txn` tokens), per-tracer monotone `marks`, reconciliation, sys.monitoring tool id 4 or 3 under a per-copy tool name (local events on minted code; global PY_UNWIND only while some section is open, from revision 2), per-mint pending entries, the at-fork handler, `_v5_state()` and `_v5_faultpoints()`. A freed, unowned tool id is re-taken at the next transaction (revision 2). The fork pass-through reads `os.getpid()` (revision 2). |
| **record() and schema** | Tracer id `/3`. The notes set is {OPEN_AT_EXIT, LAZY_RESULT, MONITOR_LOST}. The recorded set is {REENTRY, TRACE_INACTIVE, UNDECLARED_SECTION, NESTED_SECTION, CLONE_CALLED, CLONE_ALIVE, CODE_SWAPPED, CUT_MOVED, REENTRANT, MACHINERY_BUSY}. The key layout is unchanged. |
| **score()** | Same step order. NO_TRACE accepts a dict-subclass result (read with `dict.get`), with a split message. WRONG_TRACER and BAD_TRACE test the exact type before any hash or compare. An overflowing metric gives GateSpecError, not OverflowError. The fixed sentence names generator objects created before the trace. |
| **check_metrics** | Runs no user `__bool__`, `get` or `__missing__`. It runs no user `__eq__` or `__hash__`, except those of a str-subclass key stored in a user dict whose hash collides with a key it looks up (contrived; M11). An overflowing int is reported, not raised. "smoke run" is used only when the trace is absent; otherwise the note starts with the refusal's `[V5:CODE]`. |
| **Versions** | Tracing on CPython 3.12 and 3.13 GIL builds only. Everything else refuses UNSUPPORTED_VERSION. Scoring works on every version. |
| **Reason codes** | New: UNSUPPORTED_VERSION, RESERVED_TARGET, CUT_UNAVAILABLE, CUT_MOVED, MONITOR_BUSY, REENTRANT, MACHINERY_BUSY, and the note MONITOR_LOST. Retired: FOREIGN_PROFILER, PROFILER_LOST, THREAD_HOP. See the full table. |
| **Removed** | See "What is removed from v5e" in Mechanism. |
| **Finding closure** | Rows R1-B4, R1-D1, R1-D2, R1-D3, R2-B3, R2-D4, R3-B3, R3-D3, J1-X1, "R3 nit: PEP 562", "R3 nit: f_locals cost" and "J2: PROFILER_LOST" are restated. No round 1–3 blocker class is reopened. R1-B4, R2-B3 and R3-D3 now close with no profile hook and no lock at all, instead of by a refusal, a hook-removal rule or an RLock. |
| **P1 retro** | Identical expected record, run on 3.12 and 3.13 instead of 3.10–3.13. |
| **Over-blocking** | #6 (profilers) and #7 (hook loss) are removed. New items: interpreters, sys.monitoring, confirmation, provenance files, cache and PEP 562 shapes, lifecycle refusals, cut, freeze and section types. |
| **Stated limits** | New: L-DELIVERY, L-ZOMBIE and L-MONITOR. L-ASYNC-EXC is rewritten as the envelope I6. L-STUB, L-CACHE and L-RUNTIME are widened, L-WHERE is narrowed (uvloop is now closed by the loop boundary, not disclosed), and L-BLIND is retired. Revision 2 closes revision 1's residual R17 (now case X65g) and pins R18. |
| **Exam** | Runs on 3.12 and 3.13; 3.10 and 3.11 run the refusal and scoring subset. New cases cover all 29 exam holes and every fixed or disclosed finding. The exam reads only `_v5_state()` and `_v5_faultpoints()`. Hazards H6–H9 are added, and H10 in revision 2. |
| **Gates** | New: G_SEM (SM1, SM2, positive controls), G_REF, G_HYG, G_COVER, G_FI, G_SIG, G_XVER, G_INDEP and G_N. |

---

## Target identity

### Rule (one sentence)
A frame is a *hit* of declared target T iff `frame.f_code is M_T` and `frame.f_globals is F_T.__globals__`, where:
- F_T is T's traced function;
- M_T is a fresh code object the tracer created at entry with `F_T.__code__.replace()`, published only by assigning it to `F_T.__code__`, and given sys.monitoring local events.

Attribution then decides whether a hit is credited, and confirmation decides whether it counts.

### Resolution (at `__enter__`, every target, before anything global is touched; the function `_resolve_target`)
The grammar `module:Q.u.a.l` is unchanged: `_TARGET_RE.fullmatch`, ASCII only, no duplicates (DECL). Resolution runs no user code except the import and a module's PEP 562 `__getattr__`, apart from the contrived str-subclass dict-key collision noted in M11. It uses these primitives, all C:

- `_MOD_DICT = types.ModuleType.__dict__['__dict__']`
- `_TYPE_DICT = type.__dict__['__dict__']`
- `_TYPE_MRO = type.__dict__['__mro__']`
- `_TYPE_QUAL = type.__dict__['__qualname__']`
- `_SM_FUNC = staticmethod.__dict__['__func__']`
- `_CM_FUNC = classmethod.__dict__['__func__']`

`_own_dict(obj)` finds the first `'__dict__'` entry among the class dicts of `type(obj)`'s MRO, read with `_TYPE_DICT`/`_TYPE_MRO`. That entry must be a `types.GetSetDescriptorType` or `types.MemberDescriptorType`, and is read with `desc.__get__(obj, type(obj))`. The result must be an exact dict; otherwise `_own_dict` returns None. A Python-level `__dict__` descriptor is never called.

1. **Import.** `mod = importlib.import_module(module)`. Any `Exception` refuses **UNRESOLVED** chained `from e`; see L-ASYNC-EXC for asynchronous exceptions. If `issubclass(type(mod), ModuleType)` is false, refuse **UNRESOLVED** ("the sys.modules entry is not a module"). The module's own dict is `_MOD_DICT.__get__(mod)`.
2. **Steps.** For each `part` of the qualname, with `obj` the object reached so far:
   - **Unwrap first.** If `type(obj) is staticmethod or type(obj) is classmethod`, replace obj by its C `__func__` (D2; this makes `'mod:C.m.__wrapped__'` work for a class-held cache). Every type test in the machinery is an `is` chain, or `issubclass(type(x), T)` with a builtin T. Tuple membership such as `type(obj) in (staticmethod, classmethod)` is forbidden: `in` compares with `==`, and when obj's class has a metaclass that defines `__eq__`, that `__eq__` runs, and whatever it raises escapes (`rev1/p1_meta_eq.py`, on 3.11.15, 3.12.3 and 3.13.12; `issubclass` ran no user hook).
   - **`issubclass(type(obj), ModuleType)`.** Allowed only as the first step; a module reached later refuses **INSTANCE_PATH**. If `part` is in the module dict, read it. Otherwise, if `'__getattr__'` is in the module dict (PEP 562), call it **twice**. Each call raising `Exception` refuses **UNRESOLVED** `from e`. If the two products are not the same object, refuse **UNRESOLVED** ("module `__getattr__` returns a new object on each access; declare the function it forwards to"). With no `__getattr__`, refuse **UNRESOLVED** with a message naming unimported submodules.
   - **`issubclass(type(obj), type)`.** Read `_TYPE_DICT.__get__(obj)`. If `part` is absent, search every class in `_TYPE_MRO.__get__(obj)[1:]`. Found in one: refuse **INHERITED** ("declare the defining class `<module>:<qualname>`"). Found nowhere: refuse **UNRESOLVED**.
   - **Anything else.** Use `d = _own_dict(obj)`. If `d` is None or `part not in d`, refuse **INSTANCE_PATH**, naming the class to declare.
3. **Final unwrap.** Unwrap a final staticmethod or classmethod the same way.
4. **Choose F_T** from the declared object D:
   - **`type(D) is FunctionType`.** F_T = D. Nothing is unwrapped: a `functools.wraps` wrapper *is* the target.
   - **`type(D) is _CACHE_WRAPPER`** (C `lru_cache`/`cache`):
     - `callee` = the unique FunctionType among `gc.get_referents(D)`, which is the C `func` slot, verified on 3.10–3.13 (D1 p_cache_callee.py, D3 p5). None if there is not exactly one.
     - `stamped = dict.get(_own_dict(D) or {}, '__wrapped__')`.
     - If `callee is None or callee is not stamped`, refuse **NOT_A_FUNCTION**: "the wrapper calls `<callee module:qualname>`; its `__wrapped__` names `<stamped>`; declare the function the wrapper calls".
     - If `callee` is (by identity) a value of the module dict or of the holder namespace, refuse **NOT_A_FUNCTION**: "the body is also bound as `<name>`; declare that name". The holder namespace is the class dict or instance dict that held D; it is None for a PEP 562 product.
     - If another `_CACHE_WRAPPER` value `w` of the module dict or the holder has `_cache_callee(w) is callee`, refuse **NOT_A_FUNCTION**: "two cache wrappers call one body; declare `'<module>:<name>.__wrapped__'` to count every execution of the body".
     - Otherwise F_T = callee. The target is the cached body: misses count and hits do not.
   - **Anything else** refuses **NOT_A_FUNCTION**, with the v5e list of shapes.
5. **Reserved.** If F_T is one of the two watched bindings, `_HANDLE_DICT[0].get('_run')` or `_LOOP_DICT[0].get('_run_once')`, or `_CUT.get(id(F_T.__code__)) is F_T.__code__`, refuse **RESERVED_TARGET**. Revision 2: both bindings are read from the class dicts captured by `coverage_trace()` (M1), never from `asyncio.events.Handle` afresh, so the constructor, E2, this step and `_cut_ok()` read the same two classes.
6. **Provenance (FOREIGN_DEFINITION; the function `_provenance`).**
   - **(a) The module.** `mf = dict.get(module_dict, '__file__')` must be an exact str not ending in `.pyc` or `.pyo`. Otherwise refuse. The message has two forms (revision 2, N2): with no exact-str `__file__`, "the declared module has no source file to tie its code to"; with a `.pyc`/`.pyo` `__file__`, "the declared module was loaded from compiled code `<__file__>`, not from source (a zip archive holding a `.pyc` does this); import it from its `.py` source".
   - **(b) The walk.** It starts at D, visits D plus at most 16 further objects (17 in all), and is cycle-detected by `id`. At each object `cur`:
     - **FunctionType.** `cur` must be **coherent**, else refuse FOREIGN_DEFINITION: "the code of `<cur module:qualname>` was compiled from `<co_filename>`, not from its module's file `<__file__>`: its `__code__` was replaced". If `cur.__globals__ is module_dict`, accept. Else step to `dict.get(_own_dict(cur) or {}, '__wrapped__')`.
     - **`_CACHE_WRAPPER`.** Step to its real callee.
     - **Anything else.** Step to `dict.get(_own_dict(cur) or {}, '__wrapped__')`. A None own dict stops the walk.
   - **(c) Coherent.** `cf = cur.__code__.co_filename`. Coherent iff `cf.startswith('<')` (generated code: residual R05b), or `gf = dict.get(cur.__globals__, '__file__')` is an exact str, does not end in `.pyc` or `.pyo`, and `normcase(realpath(cf)) == normcase(realpath(gf))`.
   - **(d) No accept.** If the walk ends without accepting, refuse FOREIGN_DEFINITION. The message names the innermost FunctionType reached, `inner`, as `n + ':' + inner.__qualname__` ("declare this instead"). Here `n = dict.get(inner.__globals__, '__name__')` when `type(n) is str`, and `inner.__code__.co_filename` otherwise (revision 2, N7). A function exec'd into a fresh namespace has no `'__name__'`, and concatenating None raised TypeError out of `__enter__` (`rev2/p9_foreign_msg.py`). A str subclass also takes the fallback, so no user `__add__` runs.
   - F_T is always the first FunctionType the walk visits, so F_T itself is always checked for coherence. This closes the swapped-wrapper shape that D1 admitted (judge_sound/j_d1_wrapper_swap.py).
7. **Aliases.** Two declared names are aliases iff their declared objects D are identical after the final unwrap. Aliases share one mint, and every credited hit credits all of their names. Two declared names that reach one F_T through different declared objects refuse **NOT_A_FUNCTION** ("declare the body once").
8. **Resolve everything, then touch anything.** If any target refuses, nothing is minted (X33).

### Minting (the function `_mint`; under the robust mutex, after reconciliation; see Mechanism M4)
For each distinct F_T:

- **An existing mint.** If `m = _BY_FN.get(F_T)` exists, reconciliation has left it only live holders. If `F_T.__code__ is not m.code`, refuse **CODE_SWAPPED** before anything is joined. Otherwise `m.holders = m.holders + (core,)`.
- **A new mint.** Otherwise, in this exact order:
  1. `m = _Mint(F_T)`. This is pure: `original = F_T.__code__`, `code = original.replace()`, `globals = F_T.__globals__`, `freeze0 = gc.get_freeze_count()`, `pend = {}`.
  2. `m.holders = (core,)`.
  3. `_MINTED[id(m.code)] = m`, then `_BY_FN[F_T] = m`.
  4. `set_local_events(tool, m.code, PY_START|PY_RESUME|PY_RETURN|PY_YIELD)`. The global PY_UNWIND is not set here: revision 2 sets it only while a section is open (At open, step 6; M7).
  5. `F_T.__code__ = m.code`, last.
- **Release.** The original is restored when the last live holder leaves, and only if `F_T.__code__ is m.code` (`_retire`).

### Tripwires (recorded; each refuses every declaring gate)
- **CLONE_CALLED.** At an entry event, M_T runs with `f_globals is not m.globals`. Every holder of the mint records it, and the call credits nothing.
- **CLONE_ALIVE** (`_clone_alive`). At each holder's exit, for each mint it held: `excess = sys.getrefcount(M_T) - 2 - (F_T.__code__ is M_T)`. If `excess > 0`, the tracer scans `refs = gc.get_referrers(M_T)` and records the problem if either holds:
  - (a) some FunctionType other than F_T is in `refs`;
  - (b) `gc.get_freeze_count() > m.freeze0` and `excess - visible > 0`. Here `visible` counts the references to M_T held by members of `refs` other than the mint, F_T and the scan's own frame and list. Message: "gc.freeze() ran while the minted code existed: N references to it cannot be attributed".

  The test is for a *rise* in the count, not any change. The count also falls with no freeze or unfreeze call, when frozen objects die (`rev1/p4_freeze.py`: −11 after deleting 10 frozen objects, on 3.11–3.13), and `gc.unfreeze()` sets it to 0 (3.12.3 boots with 375 frozen objects). A clone can hide from `gc.get_referrers` only while it is frozen. Only a `gc.freeze()` made after the mint can freeze it, and that call raises the count by every tracked object at that moment, the clone included. `m.freeze0` is read when the mint is made, so for a mint this tracer joined it can predate this trace (over-blocking #19).

  The exit code itself holds no other reference to M_T while it counts; the constant 2 is `m.code` plus `getrefcount`'s argument.
- **CODE_SWAPPED.** At each holder's exit, `F_T.__code__ is not M_T`. The swap is left in place.
- **CUT_MOVED.** `_cut_ok()` is false at an entry event of any minted code, or at exit. `_cut_ok()` reads the two watched bindings, `h = _HANDLE_DICT[0].get('_run')` and `r = _LOOP_DICT[0].get('_run_once')`. `_HANDLE_DICT[0]` and `_LOOP_DICT[0]` are the class dicts of `asyncio.events.Handle` and `asyncio.base_events.BaseEventLoop`, read through `_TYPE_DICT` by the first `coverage_trace()` of the process and never re-read. `_cut_ok()` is true iff, for each of h and r, `type(x) is FunctionType` and `_CUT.get(id(x.__code__)) is x.__code__`. At an entry event, a false result sets `flags['CUT_MOVED']` on every holder of the mint, and exit records it. So a rebinding of `Handle._run`, or a swap of its `__code__`, that is restored before exit is still caught if any hit happened while it was in place. `rev1/p18_transient_rebind.py` shows the case on 3.12.3 and 3.13.12: no cut frame lies between the dispatched call and the anchor, the binding at the hit is the moved one, and the binding at exit is restored.

### Why class A cannot reopen, and the doors that remain
The v5e argument stands. A frame is tied to its function only by its code object and globals. M_T is in no `co_consts`, so factories, closures, decorators, per-call siblings, dataclass siblings, vendored or exec'd copies, pre-trace clones, `copy`/`deepcopy` and pickle all run *other* code objects. A `code.replace()` copy of M_T carries no monitoring events and is never observed. Two things are new:

- **The pre-trace swap is closed.** F_T's own code must have been compiled from its module's file, and so must every link the walk visits. A stub from another file installed by `__code__` assignment or by `FunctionType(stub_code, module_globals)` refuses (X26b, X26c, X26d).
- **The cache body is what the wrapper calls,** never what its writable `__wrapped__` says (X24b).

**The doors that remain are never claimed closed:**

- **L-CLONE (during the trace).** Code reads M_T and does one of these:
  - builds a same-globals function and drops it before exit;
  - runs `exec(M_T, T.__globals__)`;
  - does `U.__code__ = M_T` and swaps it back before exit;
  - keeps a live clone frozen while the gc freeze count at exit is not above its value at mint time. That happens if frozen objects died, or if `gc.unfreeze()` then `gc.freeze()` ran with fewer tracked objects.
- **L-STUB (before the trace).** A stub bound at the name that is either:
  - defined in the declared module (R05);
  - wraps-stamped (R06);
  - compiled with a `'<'` filename, or with `co_filename` forged to the module's file (R05b). Only a deliberate harness builds these.
- **L-CACHE.** A sibling cache wrapper of the body held outside the scanned namespaces (R13).

---

## Attribution

### Rule (one sentence)
A hit H is credited to opening O iff all three hold:
- at H's entry event (PY_START or PY_RESUME), O's anchor is registered and is met on H's `f_back` chain before the first frame whose `f_code` is in the cut `_CUT` (every `Handle._run` and `BaseEventLoop._run_once` code seen), the thread's running asyncio loop is `O.loop` (the *loop boundary*), and no other registered opening of O's tracer that meets its own loop boundary is met there;
- H then *confirms*, meaning its frame returns, yields, or unwinds at an offset other than its entry offset;
- at that confirmation, O's tracer is still crediting (`id(M_T) in core.by_code`).

The anchor is the frame of the module-level `_run(core, …)` call, or the `_run_async` coroutine frame, that opened O.

**The loop boundary (revision 1).** `O.loop` is `asyncio.events._get_running_loop()`, read at O's open. It is a C function and runs no user code. An event loop started inside a section therefore never credits that section, whatever its dispatch runs through, provided the loop registers itself as the running loop through `asyncio.events._set_running_loop`. Every stdlib loop and uvloop does (revision 2, N9). A loop that does not, such as a scheduler that drives coroutines by hand, is not an asyncio loop for this rule; it falls under L-WHERE's non-asyncio schedulers. The probes show why the cut alone is not enough:
- **uvloop.** There is no Python dispatch frame at all. In `rev1/p9_uvloop.py` (uvloop 0.22.1, 3.12.3), a `call_soon_threadsafe` job from another thread ran with the section's anchor on its chain and no `Handle._run` frame.
- **A pure-Python loop that overrides `_run_once`.** It can run callbacks without `Handle._run` (`rev1/p8_cdispatch.py`).

In both, the running loop at the hit is the loop started inside the section, not `O.loop`. The cut is still needed when dispatch is re-entered on the *same* running loop, such as `loop._run_once()` inside a section opened in a task (`rev1/p17_reentrant_dispatch.py`; X65c).

**Why the cut holds two codes (revision 2).** With `Handle._run` alone, three routes re-entered stdlib dispatch without a cut frame and without CUT_MOVED:
- A1: an override of `TimerHandle._run`;
- A2: `asyncio.events.Handle` rebound to a subclass with its own `_run`;
- revision 1's R17.

Every re-entry into the stdlib loop's dispatch runs `BaseEventLoop._run_once`, so its code is now a cut code too. `rev2/p1_runonce_cut.py` turns A1, A2 and R17 into `dispatched {f:1}` on 3.12.3 and 3.13.12, with R17's W bound either before or after `__enter__`. Plain credit, a section opened inside a task, X65c, X65d, V19b, V61 and V63 keep their outcomes.

`Handle._run` stays in the cut. A loop class with its own `_run_once` that dispatches through `handle._run()` (nest_asyncio's shape) passes no `BaseEventLoop._run_once` frame, and `Handle._run` stops the walk there (`rev2/p2_shared_cut.py`). Neither code stops R18: dispatch through code that is neither of them, re-entered on the same loop.

### Sections are calls
Unchanged from v5e:

```python
result = cov.run(section, fn, /, *args, **kwargs)
result = await cov.run_async(section, afn, /, *args, **kwargs)
```

Opening and closing happen in one frame, in its `finally`, so they are LIFO per stack by construction. An event loop must run outside the section. A task inside any loop may open its own `run_async` section.

Under `asyncio.eager_task_factory` (3.12+), a child task created on the stack of an open opening runs its first synchronous step on that stack. A section the child opens in that step is therefore same-stack nesting, and it refuses **NESTED_SECTION** for the whole trace (X83). The remedy is `await asyncio.sleep(0)` before `cov.run_async` in the child (V35), or not using the eager factory.

### At open (raised before fn runs; recorded when the tracer was entered)
1. **Pass-through.** If `core.pid != os.getpid()`, return None, and `run` just calls fn. This is a forked child: no section, no credit, no refusal. Revision 2 reads `os.getpid()` (about 0.14 µs more than a cached value, `rev2/p8_atfork_abort.py`) instead of a pid cached by the at-fork handler. The pass-through then no longer depends on that handler having run (N5).
2. **TRACE_INACTIVE.** `'active'` is not in `core.marks`, or `'exiting'` is.
3. **Section type.** If `type(section) is not str`: a str subclass becomes `str.__str__(section)`, an exact str (never `'Sec.G'`). Anything else refuses **UNDECLARED_SECTION** without being compared.
4. **UNDECLARED_SECTION.** No gate declares this section. Sections are matched against *declared sections*, not gate names.
5. **NESTED_SECTION.** A registered opening of the *same* core is on the anchor's `f_back` chain before the cut, and its `loop` is the running loop now (the loop boundary). Openings of other tracers may nest. The message reads "a call there would be on the stack of two openings of section S" when `o.section == section`, and "one call would count for both sections S1 and S2" otherwise.
6. **Commit.** `o = _Opening(..., loop=_get_running_loop())`, then `core.openings.append(o)`, then `_unwind_on()`, then `_ANCHORS[anchor] = o`, then `_unwind_on()` again (revision 2, M4). `_unwind_on()` sets the global PY_UNWIND on styxx's id if the id carries `_TOOL_NAME` and the event is not already set. The second call repairs a clear that raced this commit (M7, "The unwind scope").
7. **Race re-check.** If `'exiting'` is now in `core.marks`, `_detach(o, ('open', (OPEN_AT_EXIT,)))` and refuse **TRACE_INACTIVE**.

The same section may be open any number of times at once on different stacks.

### At a hit
- **Entry (PY_START or PY_RESUME of a minted code object).**
  - CUT_MOVED check: if `_cut_ok()` is false, set `flags['CUT_MOVED']` on every holder.
  - CLONE_CALLED check.
  - Walk `f_back` to the cut or the root, collecting registered anchors. An anchor whose opening's `loop` is not the running loop (read once per hit) ends the walk as a cut does.
  - For each holder h with `id(code) in h.by_code`, the outcome is one of:
    - `('c', O)` when exactly one of h's openings was found;
    - `('a', (O1, …))` when two or more were found;
    - `('d', tid)` when none was found and the walk hit the cut or a loop boundary;
    - `('u', tid)` when none was found and the walk reached the root.
  - If no anchor is registered anywhere (`_ANCHORS` is empty), store nothing and return (revision 2). No section is open, so no count can result, and PY_UNWIND is off, so a pending entry for a frame that later raises would never be popped.
  - Store `m.pend[id(frame)] = (frame, entry_offset, outcomes)`. That is the only store.
- **Confirmation.**
  - At PY_RETURN or PY_YIELD, pop the entry.
  - At PY_UNWIND, pop it and publish only if the unwind offset differs from the entry offset. A frame that died at its entry instruction never ran its body.
  - Publishing, for each outcome whose holder still has `id(code) in h.by_code`: `('c', O)` adds one to `O.calls[id(code)]`; `('a', …)` adds one to each opening's `ambiguous`; `('d'|'u', tid)` adds one to `h.uncredited[tid][0|1]`.
- **Never counted.** A `throw()` or `close()` resumption fires only PY_THROW and has no pending entry, so it is never counted, even when a handler in the body runs. Names are expanded only in `record()`.

### At close and at exit
- **Close.** In `_run`'s `finally`, on return and on raise: `_detach(o, (end, ()))`.
  - `end` is `"returned"` or `"raised"`.
  - `_detach` claims once with `o.fin.setdefault('fin', value)`, then pops the anchor, then sets `o.frame = None`, then calls `_unwind_off()` (revision 2). Every step is idempotent.
  - Before the pop, if the opening is still anchored, the id carries `_TOOL_NAME` and the global events lack PY_UNWIND, `_detach` sets `o.core.flags['UNWIND_LOST']`. Some party cleared the event while the section was open, so exit notes MONITOR_LOST (X137c).
  - `run()` sets `o.lazy` only when the result's exact type is a generator, coroutine or async generator. The text is "fn returned a `<type>`; whatever of its body runs after the section closed does not count", with "(its body had not started)" appended when the object has not started.
- **Exit.** The claim, then the credit stop (`core.by_code = {}`), then detaching every opening still open with end `"open"` and the note OPEN_AT_EXIT, then the tripwires, then the `'exited'` commit (M5).

### What score credits
- A gate is judged on the **union of `calls` over the openings of its declared section**, whatever their `end`.
- Notes (OPEN_AT_EXIT, LAZY_RESULT, MONITOR_LOST) and `end != "returned"` never refuse. They are printed in the NOT_EXERCISED message.
- `ambiguous` and `uncredited` never count.
- Every entry in `problems` refuses every declaring gate, whether or not the harness swallowed the exception.

### Why class B cannot reopen through the runtime, and the door that stays open
The v5e argument stands. The `f_back` chain holds only frames on the same thread that are executing and waiting on this call.
- **Threads.** Threads, pools, executors and daemon threads start at their own bootstrap frame.
- **Forked children.** A forked child's thread is not a bootstrap frame. It is a copy of the forking thread's stack, anchors included (`rev1/p6_fork_chain.py`). The at-fork handler excludes it: in the child it clears `_ANCHORS` and retires every mint, and the pid pass-through means a child never opens a section or credits one.
- **Asyncio, a loop started inside the section.** Its work fails the loop boundary, whatever it dispatches through, uvloop included.
- **Asyncio, a loop already running when the section opened.** Its work can reach the section's stack only by re-entering the loop's dispatch. A re-entry into a stdlib loop's dispatch runs `BaseEventLoop._run_once`, whatever handle class, `Handle._run` binding or `TimerHandle` override is in use. A loop class that overrides `_run_once` but dispatches through `handle._run()` runs `Handle._run`. Both codes are in the monotone cut (revision 2), and neither can be minted (RESERVED_TARGET). A rebinding of either, or a swap of its code, is recorded as CUT_MOVED if any hit or the exit sees it.

One route is left, and only a deliberate harness builds it (R18). A section opened in a task of a running loop re-enters that loop's dispatch through code that is neither cut code. That code is either a loop class whose own `_run_once` runs callbacks without calling `Handle._run`, or a replacement of `BaseEventLoop._run_once` that restores the original binding before the hit and dispatches without `Handle._run`. The harness must also call that `_run_once` itself from inside the section. No library we know of does both: nest_asyncio dispatches through `Handle._run`, and uvloop exposes no re-entrant dispatch. Revision 1's R17 (a self-restoring `Handle._run`) is closed: its dispatch passes a `BaseEventLoop._run_once` frame (X65g).

Confirmation adds one more condition and never removes one, so it can only lose credit (I1).

L-WHERE is unchanged: the stack shows *where* code ran, not who asked for it (R01, R02, R09, R10).

---

## Mechanism and lifecycle

### M0. Version gate
`coverage_trace(exp)` raises **UNSUPPORTED_VERSION** and constructs nothing unless all three hold:
- `sys.implementation.name == 'cpython'`;
- `sys.version_info[:2] in ((3, 12), (3, 13))`;
- the build is not free-threaded (`sysconfig.get_config_var('Py_GIL_DISABLED')` is falsy and `getattr(sys, '_is_gil_enabled', lambda: True)()` is true).

`__enter__` re-checks this. `import styxx.protocol` never touches `sys.monitoring` or asyncio, so scoring works on every version. The tracer id is `"styxx.protocol.coverage_trace/3"`.

### M1. Module state
Every piece of shared state is one of three kinds:
- a registry changed only by single GIL-atomic C operations;
- an immutable value replaced by one store;
- a monotone map changed only by `setdefault`.

```python
_TRACER_ID = "styxx.protocol.coverage_trace/3"
_CACHE_WRAPPER = type(functools.lru_cache(None)(lambda: 0))
_BY_FN   = {}   # F_T -> _Mint            (the key holds F_T; functions hash by identity)
_MINTED  = {}   # id(M_T) -> _Mint        (the mint holds M_T, so the id cannot be reused)
_ANCHORS = {}   # anchor frame -> _Opening (the key holds the frame, so no id reuse)
_CUT     = {}   # id(code) -> code: every Handle._run and BaseEventLoop._run_once code seen; setdefault only
_GUARD   = {"hint": _Txn(None, 0, None)}   # head of the robust-mutex succession chain
_TOOL    = [None]                          # sys.monitoring tool id; re-validated at every enter
_TOOL_NAME = "styxx.protocol/" + os.urandom(6).hex()   # per loaded copy of the module; the only name adopted
_HANDLE_DICT = [None]                      # asyncio.events.Handle's class dict, read by the first coverage_trace()
_LOOP_DICT = [None]                        # asyncio.base_events.BaseEventLoop's class dict, read with it
_LOST    = [0]                             # count of freed ids re-taken (M3); changed only under the mutex
_BUSY_SECONDS = 10.0
_LOCAL   = PY_START | PY_RESUME | PY_RETURN | PY_YIELD       # local, on minted code only
```
**Reload (revision 2, N8).** Every name above except `_TRACER_ID`, `_CACHE_WRAPPER`, `_BUSY_SECONDS` and `_LOCAL` is bound as `X = globals().get("X", <initial>)`, and `_TOOL_NAME` as `globals().get("_TOOL_NAME") or <fresh name>`. So `importlib.reload(styxx.protocol)`, which re-runs the module in the same globals dict, keeps the registries, the cut, the tool id and the tool name. Rebinding them instead had two effects in `rev2/p10_reload.py`: a mint held across the reload was lost and never retired, and each reload used up a tool id under a new name, so the second reload refused MONITOR_BUSY for the rest of the process. After a reload, the callbacks registered on the id are the old function objects, which read the same globals. The first exit's MONITOR_LOST test (M5 X5) finds a callback that is not the current function, re-registers the reloaded ones, and notes MONITOR_LOST once. A copy loaded under another module name has its own globals and stays a second copy (X142).

The objects:

- **`_Mint`**: `fn, qualname, original, code, globals, freeze0, holders, pend`.
  - `holders` is a tuple, rebuilt only under the mutex and read lock-free by callbacks.
  - `pend` maps `id(frame)` to `(frame, entry_offset, outcomes)`. Only the thread running a frame writes that frame's entry.
- **`_Core`**, one per tracer; it is what the registries reference:
  - `exp`;
  - `marks`: a monotone dict of `'entering'→_Txn`, `'active'→True`, `'exiting'→_Txn`, `'exited'→True`;
  - `by_code`: `{id(code): names}`, emptied first at exit;
  - `names`: kept for record;
  - `sections`: the declared sections;
  - `openings` (list), `problems` (list), `clone_called` (dict);
  - `uncredited`: `{tid: ({}, {})}`;
  - `lost_note`: None or the MONITOR_LOST text;
  - `flags`: a dict set lock-free by callbacks and closes (`'CUT_MOVED'`, `'UNWIND_LOST'`);
  - `facade`: a `weakref.ref` with **no callback**;
  - `pid`, `prov`;
  - `lost0`: `_LOST[0]` read at E4, under the mutex (revision 2).
- **The facade.** The user-facing `_CoverageTracer` is a thin facade holding its core.
- **Frames the machinery may retain** belong to module-level functions whose own locals hold the core, never the facade: `_run`'s frame, `_run_async`'s coroutine frame, and target frames in `m.pend`. A retained frame that has died still keeps its callers' frames alive, and so possibly the facade; see L-ZOMBIE and L-MONITOR.
- **`_Opening`**: `core, section, frame, tid, loop, calls{}, ambiguous{}, fin{}, lazy`. `loop` is the running asyncio loop at open, or None.
- **`_Txn(tid, fid, code, succ={})`** is created by `me = _txn()` from the caller's frame. It is *live* iff some frame f on `sys._current_frames()[tid]`'s `f_back` chain has all three of: `id(f) == fid`, `f.f_code is code`, and `f.f_locals.get('me') is` the token. The check is exact, holds no frame, and needs no callback.

### M2. The robust mutex
It serializes enter and exit transactions only. `_open`, `_detach`, the callbacks and `record()` never take it.

```python
def _locked(fn, *args):
    me = _txn(); _acquire(me); out = fn(*args); _release(me); return out   # no try/finally, by design
```
`_acquire` walks from `_GUARD['hint']` along `succ['next']` to the last token r:
- **r live on this thread:** raise **REENTRANT**.
- **r live on another thread:** sleep 0.2 ms and retry. After `_BUSY_SECONDS`, raise **MACHINERY_BUSY**.
- **Otherwise (free or dead):** claim with `r.succ.setdefault('next', me) is me`. On a win, store the hint; on a loss, walk again.

`_release(me)` is `me.succ.setdefault('next', _Txn(None, 0, None))`. A release skipped for any reason harms nobody: the owner's frame dies with the exception and the next acquirer steals. The loop contains no `try`, so CPython #130279 (a signal at a loop back-edge escapes the enclosing `try` table on 3.13) cannot leave anything held.

### M3. Reconciliation (the first step of every transaction, under the mutex)
**Step 0, reclaim (revision 2, M3; the function `_reclaim`).** If `_TOOL[0]` is not None and `get_tool(_TOOL[0]) is None`, the id was freed and nobody owns it. Then, in order:
1. `use_tool_id(_TOOL[0], _TOOL_NAME)`;
2. register the five callbacks;
3. `_LOST[0] = _LOST[0] + 1`.

No owner exists, so nobody is clobbered. The events on the id are styxx's own, left by the free, because `set_events` on a freed id raises ValueError: `tool 4 is not in use` (`rev2/p3_free_reclaim.py`). The steps below then clear them as usual. An id that another tool now holds is never touched (L-MONITOR).

For every distinct mint in `_BY_FN.values()` ∪ `_MINTED.values()`, taken from `list(...)` snapshots, `keep` is its live holders. A holder is **dead** iff any of these holds:
- its facade weakref is dead;
- `'exited'` is in its marks;
- its pid differs from `os.getpid()`;
- its `'exiting'` token is dead;
- `'active'` is absent and its `'entering'` token is dead.

For each dead holder h, `_prune(h)` sets `h.by_code = {}` and detaches every opening of h with `('open', ("[V5:OPEN_AT_EXIT] pruned: the trace's own exit did not run",))`. Then `m.holders = keep`, and if `keep` is empty, `_retire(m)`.

`_retire(m)` is idempotent and consistent at every prefix:
1. If `m.fn.__code__ is m.code`, restore `m.original`.
2. If `get_tool(tool) == _TOOL_NAME`: `set_local_events(tool, m.code, 0)`. An id that no longer carries this copy's name is never touched (L-MONITOR).
3. `m.pend.clear()`.
4. Pop `_BY_FN[m.fn]` if its value is m.
5. Pop `_MINTED[id(m.code)]` if its value is m.
6. If `_ANCHORS` is empty and the id carries `_TOOL_NAME`, `set_events(tool, 0)`, which clears the global PY_UNWIND. Revision 2 ties PY_UNWIND to open sections, not to mints (M7). This step is a repair for a close whose `_unwind_off()` was skipped by a fault.

### M4. `__enter__` (the facade calls `_enter(core)`)
- **E0. Claim.** `me = _txn()`. If `core.marks.setdefault('entering', me) is not me`, append the REENTRY text to `core.problems` and raise **REENTRY**.
- **E1. Version.** The M0 gate, raised.
- **E2. The cut (the function `_cut_refresh`; the constructor runs it too).** For each watched binding x in (`_HANDLE_DICT[0].get('_run')`, `_LOOP_DICT[0].get('_run_once')`), read from the class dicts that the first `coverage_trace()` captured (asyncio was imported there):
  - if `type(x) is not FunctionType`, raise **CUT_UNAVAILABLE** ("... is not a plain function");
  - if `_CUT.get(id(x.__code__)) is x.__code__`, x's code is already a cut code: nothing more;
  - otherwise the code is new. Raise **CUT_UNAVAILABLE** if it is *shareable*: `'<locals>' in x.__code__.co_qualname`, which means a factory or decorator can make more functions with it, or some FunctionType other than x is in `gc.get_referrers(x.__code__)`. The message is "`<binding>` is bound to `<qualname>`, whose code other functions share; every function with that code would stop attribution for the rest of the process. Bind a dedicated module-level function". Otherwise `_CUT.setdefault(id(x.__code__), x.__code__)`.

  Revision 2 (M2): the cut is monotone and by identity. Before this check, a generic decorator's inner function bound as `Handle._run` put a code object into the cut that every other function with that decorator shares. Each of those functions then stopped attribution, in that trace and in every later trace of the process (`rev2/p2_shared_cut.py`, reproducing the second critic's A5). The scan runs once per code new to the cut. It is 1.6–2.1 ms with 100k extra tracked objects and 14–17 ms with 1M (p2). A function created *after* E2 that reuses a cut code is not caught. That is an over-block, never an over-credit (#21).
- **E3. Resolve.** Resolve every target, outside the mutex. The declared module's import here is the only import inside enter or exit.
- **E4. `_locked(_enter_txn, core, resolved)`,** which runs:
  1. reconcile;
  2. `_ensure_tool()`:
     - If `_TOOL[0]` is set and `get_tool(_TOOL[0]) == _TOOL_NAME`, keep it.
     - Otherwise, for id 4 then 3:
       - adopt the id if `get_tool(id) == _TOOL_NAME`. That is this copy's own id, left by a fault before `_TOOL[0]` was stored;
       - or `use_tool_id(id, _TOOL_NAME)` if `get_tool(id)` is None;
       - then register the five callbacks, and store `_TOOL[0]` last.
     - An id carrying any other name is never adopted. That includes another loaded copy's `styxx.protocol/…` name.
     - Neither id usable: raise **MONITOR_BUSY**.
  3. the entry CODE_SWAPPED check for all F_T;
  4. join or mint every F_T in the Minting order;
  5. `core.names = …; core.prov = …; core.lost0 = _LOST[0]; core.by_code = dict(core.names)`.
- **E5. Activate.** `core.marks['active'] = True`, after the mutex is released. Until then the entering token is live (E0's frame is executing), so no reconciler prunes the core.

A failed or abandoned enter leaves a dead entering token without `'active'`. The next reconciliation prunes it and retires its mints. The tracer is single-use, so a retry refuses REENTRY.

### M5. `__exit__` (the facade calls `_exit(core)`; it never raises GateSpecError and always returns False)
- **X-1.** If `core.pid != os.getpid()`, return: an inherited tracer is inert.
- **X0.** If `'active'` is not in marks, run `_locked(_reconcile)` and return. A GateSpecError from `_locked` is ignored here. This completes any abandoned enter, and makes an exit after a failed enter a no-op.
- **X1. Claim.** `me = _txn()`. If `core.marks.setdefault('exiting', me) is not me`, return: a second exit is a no-op.
- **X2. Credit stop.** `core.by_code = {}`, in one store.
- **X3. Detach.** For `o` in `list(core.openings)`: `_detach(o, ('open', ("[V5:OPEN_AT_EXIT] …",)))`.
- **X4. Clone problems.** `probs` = the CLONE_CALLED texts from `dict(core.clone_called)`.
- **X5. The exit transaction.** `held, more = _locked(_exit_txn, core)`, which runs:
  1. reconcile. This core is exiting with a live token, so it is kept.
  2. MONITOR_LOST test. The loss is noted if any of these holds:
     - `_LOST[0] != core.lost0`: an id was freed during this trace and step 1's reconciliation re-took it (revision 2);
     - `get_tool(tool) != _TOOL_NAME`: the id was freed and then taken by another tool. In that case nothing below is tested, and the id is never touched again: no callback is registered on it and no event is changed;
     - a held mint's local events differ from `_LOCAL`;
     - `core.flags` has `'UNWIND_LOST'`: a close found the global PY_UNWIND cleared while its section was open (M7; revision 2 replaces revision 1's test at exit, because with section scoping the event is legitimately off by X5);
     - re-registering one of our callbacks returns a different previous callback. This test runs only while the id still carries this copy's name. It can therefore overwrite only a callback some party placed on styxx's own id, and it repairs that callback for later traces.
  3. For each mint m holding the core: CODE_SWAPPED if `m.fn.__code__ is not m.code`; then `m.holders = tuple(h for h in m.holders if h is not core)`; then `_retire(m)` if the tuple is empty.

  A GateSpecError from `_locked` (REENTRANT or MACHINERY_BUSY) is appended to `probs`, and exit continues. The unreleased holdership is pruned at the next reconciliation, because the exit token dies when `_exit` returns.
- **X6. Tripwires.** CLONE_ALIVE for each held mint, outside the mutex. Then CUT_MOVED, if `core.flags` has it or `_cut_ok()` is false now.
- **X7. Problems.** `core.problems.extend(probs)` in one call. If a loss was noted, `core.lost_note = "[V5:MONITOR_LOST] …"`.
- **X8. Commit.** `core.marks['exited'] = True`.

**Interrupted exit.**
- *Before X1:* a zombie (L-ZOMBIE). `record()` refuses TRACE_ACTIVE, and one call of `__exit__()` completes it.
- *After X1:* `record()` refuses TRACE_INCOMPLETE. The exit token is dead, so the next reconciliation prunes the core, detaches its openings and retires its mints.

**Interrupted enter.**
- *Before E4:* nothing global has changed.
- *Inside E4 or before E5:* the dead entering token is pruned at the next reconciliation.
- *At the facade's return:* a zombie.

### M6. The event path: tool id 4 or 3, callbacks with no handler, no lock and no DISABLE
```python
def _on_entry(code, offset):                    # PY_START, PY_RESUME (local, minted code only)
    m = _MINTED.get(id(code))
    if m is None or m.code is not code: return
    f = sys._getframe(1)
    holders = m.holders
    if not _cut_ok():                           # CUT_MOVED: a moved Handle._run or _run_once seen at a hit
        for h in holders: h.flags['CUT_MOVED'] = True
    if f.f_globals is not m.globals:            # CLONE_CALLED: credits nothing
        for h in holders: h.clone_called[id(code)] = m.qualname
        return
    if not _ANCHORS: return                     # no section open anywhere: nothing to credit, PY_UNWIND off (rev. 2)
    out = _outcome(f, code, holders, threading.get_ident())   # the walk: stops at a cut code or a loop boundary
    if out: m.pend[id(f)] = (f, offset, out)   # pending: the only store

def _on_exit(code, offset, value):              # PY_RETURN, PY_YIELD (local)
    m = _MINTED.get(id(code))
    if m is None or m.code is not code: return
    f = sys._getframe(1); p = m.pend.pop(id(f), None)
    if p is not None and p[0] is f: _publish(code, p[2])

def _on_unwind(code, offset, exc):              # PY_UNWIND (global, set only while a section is open; rev. 2)
    m = _MINTED.get(id(code))
    if m is None or m.code is not code: return
    f = sys._getframe(1); p = m.pend.pop(id(f), None)
    if p is not None and p[0] is f and offset != p[1]: _publish(code, p[2])
```
- **The walk.** `_outcome` reads `loop = _get_running_loop()` once, then tests `_CUT.get(id(g.f_code)) is g.f_code` for the cut, `_ANCHORS.get(g)` for anchors, and `o.loop is loop` for the loop boundary. Its per-holder rule is the one under Attribution.
- **Publishing.** `_publish` re-checks `id(code) in h.by_code` for each outcome, then makes single-key increments. Every per-opening counter has a single writer: an opening's anchor is on one stack at a time, and entry and confirmation of one resumption run on one thread.
- **Where callbacks run.** They never run at a C call: the only events are PY_START, PY_RESUME, PY_RETURN and PY_YIELD (local) and PY_UNWIND (global, and from revision 2 set only while some section is open). styxx never enables INSTRUCTION, LINE, JUMP or BRANCH events. On 3.12.3, INSTRUCTION, JUMP and BRANCH events on a code object make a signal at one of its back-edges skip that code's `finally` and with-exit (7–77 of 100 trials). Uninstrumented, or under styxx's own event set, 3.12.3 skipped 0 (`rev1/p11_backedge_timer.py`, `p12_backedge_under_styxx_events.py`, `p13_backedge_line_branch.py`). 3.13.12 skips in uninstrumented code too; that is CPython #130279 itself, not styxx. Code run inside any sys.monitoring callback raises no events for any tool (synth/p_syn1.py), so the callbacks cannot re-enter themselves.
- **Exceptions.** An exception raised in a callback propagates as CPython defines (L-DELIVERY). The tool is not dropped and the events stay set (D3 p2).

### M7. `_open`, `_run`, `_run_async`, `_detach` (no mutex)
The open checks are listed under Attribution. The rest:
```python
def _run(core, section, fn, args, kwargs):      # module level: its frame is the anchor, its locals hold no facade
    o = _open(core, section, sys._getframe())
    if o is None: return fn(*args, **kwargs)    # forked child: pass-through
    end = "raised"
    try:
        result = fn(*args, **kwargs); end = "returned"
    finally:
        _detach(o, (end, ()))                   # no loop in the try body (CPython #130279)
    t = type(result)                            # `is` chain, never `in` (see Resolution)
    if t is GeneratorType or t is CoroutineType or t is AsyncGeneratorType: o.lazy = _lazy_text(result)
    return result

def _detach(o, fin):
    o.fin.setdefault("fin", fin)                # one claim: first finaliser wins
    fr = o.frame
    if fr is not None:
        if _ours() and not (get_events(_TOOL[0]) & PY_UNWIND): o.core.flags['UNWIND_LOST'] = True
        _ANCHORS.pop(fr, None)
    o.frame = None
    _unwind_off()                               # revision 2

def _unwind_on():                               # _open: before the anchor commit, and again after it
    if _ours() and not (get_events(_TOOL[0]) & PY_UNWIND): set_events(_TOOL[0], PY_UNWIND)

def _unwind_off():                              # after an anchor pop: clear, then re-check and re-set
    if _ANCHORS or not _ours() or not (get_events(_TOOL[0]) & PY_UNWIND): return
    set_events(_TOOL[0], 0)
    if _ANCHORS: set_events(_TOOL[0], PY_UNWIND)
```
`_ours()` is `_TOOL[0] is not None and get_tool(_TOOL[0]) == _TOOL_NAME`. styxx's global event set is only ever PY_UNWIND or nothing.

`_run_async` has the same shape, with `result = await afn(*args, **kwargs)` as its try body. That `await` compiles to a SEND loop. Its throw-then-return path is taken when a thrown exception is handled by the awaited object, which then returns. On that path, the closing jump after CLEANUP_THROW lies outside the try's exception-table range on 3.12.3 and 3.13.12. On 3.12 it is a JUMP_BACKWARD, which checks the eval breaker, so a signal landing there skips the `finally` (`rev1/p19_run_async_throw_path.py`). On 3.13 it is JUMP_BACKWARD_NO_INTERRUPT, which only an injected fault reaches. Nothing depends on that `finally`. The opening's anchor frame is dead, so it is on no live chain, and exit's X3 or reconciliation finalises the opening as `('open', OPEN_AT_EXIT)`, inside I6. `_run`'s try body has no loop, and no signal position skipped its `finally` (p10).

**The unwind scope (revision 2, M4).** The global PY_UNWIND is set only while some anchor is registered in this copy, so only while some section is open anywhere in the process. Revision 1 set it while any mint existed, which included a whole trace, zombies, and a freed id after exit. The protocol has no lock:
- the opener sets the event before its anchor commit and checks again after it;
- the closer clears only when `_ANCHORS` is empty, then checks again and re-sets if an anchor appeared.

In every interleaving an open section ends with the event set. One window remains: an opener can commit between a closer's emptiness test and its clear, and a declared frame in the new section can then unwind before the closer's re-check re-sets the event. That loses one confirmation, never adds one (I1). The same window can make the close check in `_detach` see the event cleared and set a false `UNWIND_LOST`, which only adds a MONITOR_LOST note. `rev2/p4c_toggle_race.py` found no loss in 100,000 raising calls in sections opened and closed by 2 threads, nor in 40,000 by 4 threads, with a 1 µs switch interval (3.12.3, 3.13.12).

What scoping costs:
- 2.5–3.2 µs more per section (`rev2/p4_unwind_scope.py`);
- each toggle bumps the interpreter's monitoring version, so every code object that then runs is re-instrumented once, about 0.05–0.10 µs per distinct function per section (p4);
- other tools' `DISABLE`d locations stay disabled: no location fired more than twice in 1,000 toggling sections, and a location firing twice is a line that spans two offsets (`rev2/p4b_disable_kept.py`).

### M8. `record()` is pure
- **Refusals first.**
  - Refuse **TRACE_INCOMPLETE** if `core.pid != os.getpid()` ("inherited across fork: the record belongs to the parent process").
  - If `'exited'` is not in marks: refuse **TRACE_INCOMPLETE** when `'exiting'` is present, or `'entering'` is present without `'active'`. Refuse **TRACE_ACTIVE** with "the tracer was never entered" when `'entering'` is absent (v5e's X91, unchanged). Otherwise refuse **TRACE_ACTIVE** with "the tracer is active: record() was called inside its with-block, or its `__exit__` never started, and then one call of `__exit__()` completes it".
- **Openings.** Each opening's `end, notes = o.fin.get('fin', ('open', ()))`, plus `o.lazy` and `core.lost_note` when set.
- **Counts.** Expanded through `core.names`. `uncredited` is summed across threads.

The schema is v5e's, with the `/3` id and the code sets of the Reason-codes section.

### M9. The at-fork handler
`os.register_at_fork(after_in_child=_forget_in_child)` is registered at import on every version; it is a no-op until a tracer has been constructed. Revision 2 (N5) orders the steps so that every step that runs no user code comes before any step that can:
1. replace `_GUARD['hint']` with a free token;
2. `_ANCHORS.clear()`;
3. `set_events(tool, 0)` if the tool is ours;
4. for each mint m in a `list(_MINTED.values())` snapshot: `set_local_events(tool, m.code, 0)` if ours, and `m.pend.clear()`;
5. clear `_BY_FN` and `_MINTED`;
6. last, for each mint in the snapshot: if `m.fn.__code__ is m.code`, restore `m.original`.

Step 6 is the only one that runs user code: a `__code__` write raises the `object.__setattr__` audit event. CPython ignores an exception raised by an at-fork handler, so a raising audit hook aborts the handler there. Revision 1 ran the restores first, and such an abort left the child with its anchors, its registered mints and the global PY_UNWIND for its whole life. In revision 2 the child keeps only the minted code still installed on the remaining functions (`rev2/p8_atfork_abort.py`, both versions). That code has no events and runs as the original would, since M_T is an equal copy. A child tracer that later declares such a function treats M_T as its original, and restores M_T at the end.

The pass-through no longer depends on this handler. `run()`, `__exit__`, `record()` and reconciliation compare `core.pid` with `os.getpid()`, so they are correct even if the handler never ran or was aborted at any step. G_FI's fork scenario sweeps this handler (Companion gates).

The tool id is kept (monotone). Inherited cores have another pid: `run()` passes through, `__exit__` is a no-op, and `record()` refuses.

### M10. The introspection interface (frozen with the prereg; the only private surface the exam may read)
- **`_v5_state()`** returns a fresh dict:
  - `"mints"`: a sorted list of `{"target", "holders": int, "installed": bool, "local_events": int, "pending": int}`;
  - `"anchors"`: int;
  - `"guard"`: `"free" | "held" | "dead"`;
  - `"cut"`: int;
  - `"cut_current"`: bool, `_cut_ok()` (both watched bindings are plain functions whose code is in `_CUT`; revision 2);
  - `"tool"`: int or None;
  - `"tool_ours"`: bool;
  - `"global_events"`: int;
  - `"pid"`: int.
- **`_v5_faultpoints()`** returns `{qualname: fn.__code__}`, reading each function's `__code__` **at call time** (revision 2, M6), for injectors and the exam's lower-id fault tool. While a self-trace has minted a machinery function, that is the self-trace's M_T, which is the code that actually runs. Code captured at import never fires then (`rev2/p6_faultpoint_identity.py`). Its key set is frozen here (revision 1; revision 2 adds `_cut_refresh`, `_reclaim`, `_unwind_on`, `_unwind_off` and `_ours`), so exam cases can name machinery functions before the implementation exists:
  - `coverage_trace`;
  - the facade methods `_CoverageTracer.__enter__`, `__exit__`, `run`, `run_async` and `record`;
  - the module-level functions `_enter`, `_exit`, `_enter_txn`, `_exit_txn`, `_resolve_target`, `_own_dict`, `_cache_callee`, `_provenance`, `_ensure_tool`, `_mint`, `_retire`, `_reconcile`, `_prune`, `_locked`, `_acquire`, `_release`, `_txn`, `_alive`, `_open`, `_detach`, `_run`, `_run_async`, `_lazy_text`, `_cut_ok`, `_cut_refresh`, `_reclaim`, `_unwind_on`, `_unwind_off`, `_ours`, `_clone_alive`, `_on_entry`, `_on_exit`, `_on_unwind`, `_outcome`, `_publish`, `_forget_in_child`, `_v5_state` and `_v5_faultpoints`.

  The v5 machinery is exactly these functions, plus the M1 names and the scoring functions of M11. It has no nested function, lambda or other class; the facade and the plain-data classes `_Mint`, `_Core`, `_Opening` and `_Txn` have no other methods. G_HYG checks this.

Neither function changes state.

### M11. Scoring and check_metrics
- **`_check_coverage` step 1 (NO_TRACE).** Accepts a result iff `issubclass(type(result), dict)`, and reads it only with `dict.get`. The message is split three ways: "the result is a `<type>`, not a dict"; "no 'coverage_trace' key"; "'coverage_trace' is a `<type>`, not an exact dict (e.g. loaded with object_pairs_hook)".
- **Step 2 (WRONG_TRACER).** `type(t) is not str or t != _TRACER_ID`.
- **Step 3 (BAD_TRACE).** Every clause tests the exact type before any hash, membership or comparison. `end` is tested with `type(end) is not str or end not in _ENDS`; the same applies to `gates_sha256` (exact str), every dict key, and every note or problem string before its regex. The note and problem code sets are the /3 sets.
- **Steps 4–9 unchanged in order.** STALE_TRACE, TARGET_SET, BAD_COUNT, recorded problem, SECTION_ABSENT, NOT_EXERCISED. Coverage is checked for **every declaring gate, whatever its bar** (X122). The recorded-problem step has one site per recorded code (G7), with CUT_MOVED, REENTRANT and MACHINERY_BUSY added and FOREIGN_PROFILER removed.
- **NOT_EXERCISED.** The fixed sentence reads: "work on other threads, pools, executors, child processes or asyncio tasks is credited only to a section that work opens itself; generator and coroutine objects created before the trace are never credited; a call counts only when it returns, yields or raises from inside its body while the tracer is active".
- **score() on metrics.** The metric guard wraps `float(_v)`: an OverflowError becomes `GateSpecError("gate G: metric … is too large for a float")`. This is a v3-path error and carries no [V5] code.
- **check_metrics.** It never raises for a JSON-shaped result: dicts, lists, str, bool, None, floats and ints of any size.
  - `smoke = dict.get(result, 'smoke')` if the result is a dict subclass. It is truthy only for exact bool, int, float or str with a truthy value, so no user `__bool__` runs.
  - Usability is `issubclass(type(v), (int, float)) and type(v) is not bool and _finite(v)`. `_finite` catches **OverflowError only**, so asynchronous exceptions still propagate. The note reads "int too large for a float".
  - `present` uses the NO_TRACE test.
  - The coverage note is "smoke run" only when the trace is absent. Otherwise it is `str(e)` with " (smoke run: score(smoke=True) does not read coverage)" appended when smoke, so it always starts with the refusal's `[V5:CODE]`.
  - For in-process results carrying user objects, it can run two kinds of user method: a `__float__` override on an int or float subclass, and the `__eq__` of a str-subclass key stored in a user dict whose hash collides with a key it looks up (`rev1/p2_dict_collide.py`). The second is contrived: a JSON-loaded result has exact-str keys.

### Cost
The figures below come from the designs' prototypes. The implementation re-measures them in H4, and they are reported, not gated.

| operation | figure |
|---|---|
| non-target code, anywhere | about ×1.0 (local events only: D1 t_cost) |
| per hit | Entry walk plus confirmation, plus `_cut_ok()` on two bindings and one `_get_running_loop()`. In the event-path model a hit of a trivial target costs about 4.2–4.3 µs at depth 5 and 12.1 µs at depth 60, which is ×116–×117 and ×300–×356 an untraced trivial call (`rev2/p11_cost.py`, 3.12.3 and 3.13.12; the second critic measured 3.6–12 µs). That is far above D1's "×8 at depth 11", which was relative to a non-trivial target; for small hot targets the per-hit figure is what matters. `_cut_ok()` costs about 0.24 µs; revision 2's second binding adds 0.16–0.42 µs per hit in the model; `_get_running_loop()` costs 0.02–0.03 µs (critic2/t_cost.py, p11) |
| walk | linear in stack depth per hit, so a declared target recursing to depth n costs O(n²) (NOTE recursion-walk-quadratic: about 3 s at depth 8000 under v5e; to be re-measured) |
| global PY_UNWIND callback | Only while some section is open (revision 2). Inside a section, an exception unwinding through 1 frame costs ×1.43–×1.57 and through 6 frames ×2.01–×2.23, anywhere in the process; it grows with the frames unwound. Outside every section, ×0.99–×1.04: no callback (`rev2/p11_cost.py`; critic2/t_unwind_cost.py measured ×1.49–×2.17 under revision 1's always-on scope) |
| section open and close | 2.5–3.2 µs more than revision 1 for the PY_UNWIND toggle, plus one re-instrumentation of each distinct code object run in the section, about 0.05–0.10 µs each (`rev2/p4_unwind_scope.py`). The pass-through's `os.getpid()` adds about 0.14 µs (p8) |
| `coverage_trace()` | imports asyncio the first time it is called. The first call, and any E2 that meets a code new to the cut, scans `gc.get_referrers` once per new code: 1.6–2.1 ms with 100k extra tracked objects, 14–17 ms with 1M (`rev2/p2_shared_cut.py`) |
| enter or exit | reconciliation is linear in live mints; CLONE_ALIVE's `gc.get_referrers` scan runs only when the refcount gate fires (about 17–19 ms on a 1M-object heap under v5e) |

### What is removed from v5e
- `_LOCK`, `_ACTIVE`, `_STOP`, `_THREADS`, `_EPOCH` and the counters;
- the profile hook `_hook`, with its self-removal and last-close removal;
- every `sys.setprofile` call; styxx never calls `sys.setprofile`, `threading.setprofile`, `sys.settrace` or `threading.settrace`;
- FOREIGN_PROFILER, PROFILER_LOST and THREAD_HOP;
- the `_own_dict` try/except;
- `isinstance` dispatch in resolution;
- the `__wrapped__`-based cache body;
- `weakref.finalize`;
- tracer id `/2`: committed v5e traces keep their verdicts as history and refuse WRONG_TRACER under v5f (X95b);
- the v5e exam as a v5f exam: v5f needs its own prereg and frozen runner.

---

## Exception-safety model

**Threat.** An exception can land at any bytecode of the machinery. That includes a function's entry (RESUME) and a loop back-edge. On 3.13, an exception at a back-edge escapes the enclosing `try` table without running `finally` or a with-block's exit (CPython #130279; round-4 found-after item). `rev1/p11_backedge_timer.py` measured this under SIGALRM on 3.13.12. The finally or with-exit was skipped in 400/400 trials for a `while` loop and 188/400 for a `for` loop whose body ends in an `if`. 3.11.15 and 3.12.3 skipped 0. On 3.12.3 the same skip appears at back-edges of code that carries INSTRUCTION, JUMP or BRANCH events (p12, p13), and at the throw-path back-edge of an `await` (p19). **Rule:** no machinery state may depend on a `finally` or with-exit running across a loop, `await` loops included. It also includes the machinery's own callbacks: a sys.monitoring callback is Python code with eval-breaker checks.

- **Sources:** signal-handler exceptions, KeyboardInterrupt, RecursionError, MemoryError, audit hooks refusing a `__code__` write (user code that runs inside E4 and `_retire`), and a foreign tool raising at an event of one of our frames. That foreign tool can be a lower-id monitoring tool, or a settrace/setprofile function on the thread.
- **The GIL is assumed.** That is why free-threaded builds refuse.
- **Commits are single C operations:** dict setitem, `setdefault`, `pop` and `get` with str, int, frame, function or `_Core` keys (identity or str hashing, so no Python `__hash__` or `__eq__` runs); `list.append`; `set.clear`; one STORE_ATTR or STORE_SUBSCR; one `sys.monitoring` call.
- **No `try … finally`, no `with` statement and no threading lock** exist anywhere in the machinery, with one exception: `_run`/`_run_async`'s single `try … finally` around fn.
  - `_run`'s try body contains no loop.
  - `_run_async`'s try body is one `await`, whose compiled SEND loop has a throw-path back-edge outside the try range (M7). No machinery state depends on that `finally` running.
  - The only `try … except` clauses are the two user-code sites (the import and PEP 562), which chain into UNRESOLVED, and exit's two `except GateSpecError` clauses around `_locked`, at X0 and X5.

### Invariants preserved by every prefix of every transition
- **I1: no over-credit.** A count is added to opening O for a frame F of M_T only if all three hold:
  - (a) at F's entry event, O's anchor was registered and met on F's live chain before the cut, the running loop was `O.loop`, O.core held F's mint, and `id(M_T)` was in `O.core.by_code`;
  - (b) F then returned, yielded, or unwound at an offset other than its entry offset;
  - (c) at publication, `id(M_T)` was still in `O.core.by_code`, which exit empties in its first store after the claim.

  A registered anchor whose frame died (an interrupted close, or an exception between the anchor commit and `try`) can never be on a live chain. A frame killed at its entry never publishes (X135, H8).
- **I2: mint integrity.** `fn.__code__ is m.code` only while m is registered with at least one holder that is active or has a live token. The exceptions are inside E4, X5 and `_retire`, and there the next reconciliation repairs the state: holder before register, register before events, events before install; restore before unregister, each step checked by identity.
- **I3: reconciled registries.** After any reconciliation:
  - every registered mint has only live holders;
  - no mint without a live holder stays registered;
  - a retired mint has no local events and no pending entries;
  - global PY_UNWIND is set only while some anchor is registered (revision 2); a close or reconciliation repairs a stale set;
  - no freed, unowned tool id still carries styxx's events or callbacks: step 0 re-takes it (revision 2).
- **I4: single finalisation.** Each opening is finalised exactly once, by `o.fin.setdefault`. Every cleanup is idempotent and unconditional. After its core exits or is pruned, an opening holds no anchor.
- **I5: no blocking state held by the dead.** The only exclusion is the robust mutex. A dead owner is stolen; a live owner on the same thread gives REENTRANT instead of a wait; a live owner on another thread is waited on for at most 10 s (MACHINERY_BUSY). No threading lock exists, so a skipped release cannot hang anyone.
- **I6: the envelope.** A fault inside the machinery can change a trace's record only within these bounds:
  - counts ≤ the fault-free counts;
  - each `end` ∈ {fault-free end, `"raised"`, `"open"`};
  - notes ⊆ fault-free notes ∪ {OPEN_AT_EXIT};
  - problems ⊆ fault-free problems ∪ {REENTRANT, MACHINERY_BUSY when the fault itself enters or exits a tracer inside a transition};
  - or else `record()` refuses TRACE_INCOMPLETE or TRACE_ACTIVE.

  A fault never causes any of these: over-credit; a hang; a mint left installed after the next reconciliation, unless its holder is a live zombie (L-ZOMBIE); or a poisoned later trace.

  A fault never swallows an exception, with one exception. An asynchronous exception delivered inside the PY_UNWIND callback, which exists only while some section is open (revision 2), replaces the exception being unwound; its `__context__` is None, so the original is lost (L-DELIVERY; `synth/p_deliver.py`, re-run in revision 1 on 3.12.3 and 3.13.12 with the same result). The only other conversions are at the two documented user-code sites, the declared-module import and a PEP 562 `__getattr__`, each giving a chained UNRESOLVED.

### Per-transition prefixes
- **ENTER.**
  - Before E4: nothing global has changed.
  - Inside E4 (including an audit hook refusing the install): the core is a holder without `'active'`, and its entering token dies with the exception. The next reconciliation prunes it and retires the mints it alone held.
  - Between E4 and E5: the same.
  - At the facade's return, after E5: a zombie.
- **EXIT.**
  - Before X1: a zombie. `record()` refuses TRACE_ACTIVE, and `__exit__` again completes it.
  - After X1: `record()` refuses TRACE_INCOMPLETE. The exiting token dies, so the next reconciliation prunes the core, detaches its openings and retires its mints. Partial X3 or X5 work is completed idempotently. A signal at X3's loop back-edge on 3.13 is an "after X1" fault (X140).
- **OPEN.**
  - Before the append: nothing has changed.
  - After the append: an unregistered, inert opening that exit finalises as `"open"`.
  - After the anchor commit but before `try`: a dead anchor that exit or reconciliation pops.
  - Around the two `_unwind_on()` calls (revision 2). Killed after the first set and before the commit: the event is on with no anchor, until the next close or reconciliation clears it. That widens L-DELIVERY's scope for a while and changes no count. Killed after the commit and before the second set: a concurrent clear can leave this section without PY_UNWIND, so its raising calls lose confirmation. That is a lost count, within I6.
- **CLOSE.**
  - Before the claim: exit claims it as `("open", OPEN_AT_EXIT)`.
  - After the claim: the cleanups are redone.
  - `_run_async`'s `finally` skipped (a signal at the `await`'s throw-path back-edge on 3.12; M7): the same as "before the claim". The anchor frame is dead.
  - After the pop, before `_unwind_off()` finishes (revision 2): the event may stay on with no anchor until the next close or reconciliation (`_retire` step 6). Scope only, no count.
- **Callbacks.** Their only writes are `m.pend[...]` stores and pops, single-key increments and clone flags. A fault loses at most that one credit and can never add one: an entry killed before its store has no pending entry, and a pending entry killed at its entry offset never publishes. A pending entry whose confirmation never arrives stays until `_retire` clears it. It keeps its frame, and that frame's callers, alive until then (L-MONITOR).
- **Reconcile and retire.** Idempotent. A second fault inside them is repaired by the next transaction.
- **Tool acquisition.** The callbacks are registered before `_TOOL[0]` is stored. A tool left named ours with missing callbacks is adopted and re-registered at the next enter.
  - Two races with other tools become faults of this model. No handler catches them, because a handler could swallow an asynchronous ValueError:
    - `_ensure_tool` and `_reclaim` (revision 2) test `get_tool(id) is None`, then call `use_tool_id`. Another tool taking the id between the two makes `use_tool_id` raise ValueError. At enter it propagates from `__enter__`, and the enter is reconciled. Inside exit's transaction it is an "after X1" fault: TRACE_INCOMPLETE, then reconciliation.
    - A `free_tool_id` on another thread landing between `_ours()` and `get_events` in `_unwind_on`, `_unwind_off` or `_detach` makes that call raise ValueError ("tool N is not in use") out of `run()` or its close.

    Both need another thread acting on the id within a few bytecodes (L-MONITOR).
- **At-fork.** It runs in the child's only thread, and every step is idempotent. Only its last step runs user code (M9, revision 2). The pass-through reads `os.getpid()`, so it holds whatever prefix of the handler ran.

### Residuals, disclosed
- **L-ZOMBIE.** A tracer whose exit never began stays active.
  - Causes: an exception at `__exit__`'s entry; a foreign tool raising at `__enter__`'s return event; or a harness's own `with` body ending in a loop on 3.13, where CPython #130279 skips `__exit__`.
  - `record()` refuses TRACE_ACTIVE.
  - What persists: its equal-code mints stay installed, with their local events. From revision 2 the process-wide PY_UNWIND callback persists only while one of its sections is still open. A zombie whose sections closed normally leaves no global callback. That covers the common case: the fault that made it a zombie happened after the harness's `cov.run` calls returned.
  - How long: until `__exit__()` is called, or until the facade becomes unreachable and some later enter or exit in the process reconciles. With no later transaction, that is until the process exits.
  - If a second fault leaves a stale anchor, the anchor frame's `f_back` chain can keep the facade reachable.
- **L-DELIVERY.** See Stated limits. Exceptions surfacing inside styxx callbacks take effect at that event.
- **Re-entry.** A finalizer, audit hook or signal handler that enters or exits a tracer inside another enter or exit on the same thread gets REENTRANT. In a finalizer this is printed as "Exception ignored" and that tracer fails.
- **Audit hooks and slow owners.** An audit hook that blocks on `__code__` writes holds the mutex, and other threads' transactions raise MACHINERY_BUSY after 10 s.
- **Greenlets.** Untested. A greenlet switch made from inside a transition (by a finalizer, audit hook or signal handler) makes the owner look dead, so it is stolen.
- **Interpreter shutdown.** Exit during finalization runs inline (there is no helper thread). It is untested.

**Evidence and what must be re-run.** D1's crash sweep, run with its monitoring adapter, injected an exception at every machinery bytecode: 6337 points on 3.12 and 6283 on 3.13, 0 failures on invariants C1–C8, with the C7 check using live facades. D1's mutants M1–M8 were detected. That machine published at PY_START and gated on per-thread sets. The v5f machine must pass the same sweep, extended to two threads, `run_async`, generator targets and hopped coroutine sections (G_FI). Injection uses sys.monitoring INSTRUCTION events on the code objects from `_v5_faultpoints()`. The callbacks' own bytecode is not reachable by that injector while it runs as a callback, because events are not delivered inside callbacks (synth/p_syn1.py). Revision 2 (BF1, M8) reaches it another way: the frozen direct-call driver `cover_driver_v5f.py` calls the five callback-only functions outside any callback, as `FunctionType(code, vars(styxx.protocol))` built from `_v5_faultpoints()` code objects. Under the driver, a LINE tool, settrace and the INSTRUCTION injector all see their lines and back-edges (`rev2/p5_cover_driver.py`: 0 lines seen as real callbacks, 38 of the 49 body lines seen under a five-call driver, with back-edges in `_outcome` and `_publish` hit). The callbacks are also covered by X135/R16 (a lower-id tool raising at their events) and by the G_SIG floods.

---

## Version policy

| interpreter | tracing | scoring | why |
|---|---|---|---|
| CPython 3.9, 3.10 | **refused** (UNSUPPORTED_VERSION at `coverage_trace()` and `__enter__`) | works | There is no sys.monitoring. 3.10's `call_trampoline` runs FastToLocals/LocalsToFast around every Python profile callback. That reverts closure writes made by other threads and keeps deleted locals alive (round-4 BLOCKER), and no Python hook avoids it. D1 also found `importlib.import_module` hanging workers under SIGALRM on 3.10 (8/8). The "3.9 expected like 3.10" line is deleted. |
| CPython 3.11 | **refused** | works | There is no sys.monitoring. Any Python-level profile hook makes every C call on a sectioned thread skippable, and it leaked the harness's own lock in about 7% of SIGALRM timeouts (see Decisions). This is py310-class corruption of the traced program. Refusing it costs the lab's default interpreter; the P1 retro and the exam run on 3.12/3.13. |
| CPython 3.12, 3.13 (GIL builds) | **supported**, one mechanism | works | sys.monitoring local events on minted code. The global PY_UNWIND is set only while a mint exists. No profile or trace function is ever installed. Validated on 3.12.3 and 3.13.12; the prereg lists the exact patch levels executed, and results produced on other patch levels are reported as unvalidated. |
| CPython 3.14+, free-threaded builds (`Py_GIL_DISABLED`), other implementations | **refused** | works | Refused until `Handle._run`, the frame model, sys.monitoring semantics (the RESUME eval-breaker order, PY_UNWIND offsets) and the GIL atomicity argument are re-validated. |

**One mechanism, no version-keyed cases.** Every exam case has the same expected outcome on 3.12 and 3.13 (G_XVER). No enumerated difference remains. D3's probes and the synthesizer's probes checked the three candidates below:

- **Eager tasks.** `eager_task_factory` exists on both versions, so X82 and X83 are unkeyed.
- **cProfile.** It runs on sys.monitoring on both versions and coexists (V33).
- **The RESUME eval-breaker order.** By D3's reading of its measurements, 3.12's INSTRUMENTED_RESUME checks the eval breaker *after* the instrumentation call, and 3.13 checks it before. So publish-at-entry is over-credited under signals on 3.12 only. D3 p3 measured 181 body-less credits in 8 s on 3.12 and 0 on 3.13. The difference is designed out by confirmation (0 on both, D3 p4).

A lower-id tool raising at PY_START makes publish-at-entry unsound on *both* versions. Judge 2's cr_det3 gave a false PASS on 3.12.3 and 3.13.12; that is X135.

**The refused interpreters in the exam.** On 3.10 and 3.11 the exam runs the refusal cases (X37) and every scoring-only case with a prebuilt `/3` trace. Their outcomes must be identical to those on 3.12 and 3.13.

**sys.monitoring coexistence.**
- **Tool ids.** styxx takes tool id 4, or 3 if 4 is taken, under the per-copy name `_TOOL_NAME`, and holds it until the process exits. Other tools asking for that id get CPython's ValueError. If ids 3 and 4 are both held under other names, enter refuses MONITOR_BUSY. That includes another loaded copy of `styxx.protocol`.
- **A freed id.** If a party calls `free_tool_id` on styxx's id, CPython 3.12.3 and 3.13.12 leave its events and callbacks in place (`rev1/p3_free.py`), so the trace keeps counting. `set_events` on the freed id raises ValueError, so nothing can clear it without re-taking it (`rev2/p3_free_reclaim.py`). Revision 2 (M3): while the id has no owner, the next transaction re-takes it under `_TOOL_NAME`, which clobbers nobody, and clears its events. That transaction is normally this trace's own exit. Exit notes MONITOR_LOST. In p3, after a free inside a section and a normal exit, revision 1 left 1,000 unwind callbacks for 1,000 unrelated raises, and revision 2 left 0 with the id's events cleared. If another tool takes the freed id first, styxx never touches it, and styxx's PY_UNWIND callback keeps firing there for the events styxx had set, until that tool changes them (p3: 1,000 of 1,000). That is disclosed under L-MONITOR and in the R2-B3 row.
- **Tools that coexist.** cProfile (PROFILER_ID 2), coverage.py's sysmon core (id 1) and ctrace core (settrace), pdb (settrace), and pure-Python setprofile/settrace tools. D3's t_coexist ran coverage.py 7.16 and pdb. yappi, pyinstrument and debugpy (id 0) are expected to coexist but were not executed.

---

## Reason codes

Status: **new**, **changed** (trigger or text), **same**, or **retired**. Every code is a literal at its own emission site (G7) and must survive the literal-census refusal gate (G_REF).

| code | status | when it fires | effect |
|---|---|---|---|
| DECL | same | parse: `exercises` is not a non-empty list of ASCII `module:qualname`, or has duplicates | raise |
| SECTION_DECL | same (now pinned: X07b, X07c) | parse: `section` without `exercises`, or not a non-empty ASCII str | raise |
| NOTHING_DECLARED | same | `coverage_trace(exp)` when no gate declares `exercises` | raise |
| UNSUPPORTED_VERSION | **new** | `coverage_trace()` or `__enter__` on anything but CPython 3.12/3.13 GIL builds | raise; nothing constructed |
| REENTRY | changed | `__enter__` whose atomic claim `marks.setdefault('entering', me)` loses: a second or concurrent entry, or a retry after a failed enter | raise; always appended to problems |
| CUT_UNAVAILABLE | **new** | construction or entry: `Handle._run` or `BaseEventLoop._run_once` is not a plain function (mocked or C-replaced); or (revision 2) either is bound to a function whose code is new to the cut and shareable (`<locals>` in its qualname, or another live function has it) | raise; nothing minted |
| UNRESOLVED | changed | entry: the import raised; the `sys.modules` entry is not a module; the name is absent with no module `__getattr__`; the module `__getattr__` raised; **its two products differ**; a class lacks the name in its whole MRO | raise; chained `from e` where an exception caused it |
| INHERITED | changed | entry: a class step whose name exists only in some class of the MRO after the first (not only the direct bases) | raise; names the defining class |
| INSTANCE_PATH | changed | entry: a module after the colon; a step whose own dict is missing, lacks the name, or is served by a Python-level `__dict__` descriptor (never called) | raise |
| NOT_A_FUNCTION | changed | entry: not FunctionType, staticmethod/classmethod of one, or an admissible C cache wrapper. **Also:** a cache wrapper whose real callee is not its own-dict `__wrapped__`; whose callee is bound by name in the module or holder; with a sibling cache wrapper of the same callee there; two different declared objects reaching one F_T | raise; the message names the remedy (`declare <name>` or `'<module>:<name>.__wrapped__'`) |
| RESERVED_TARGET | **new** | entry: F_T is `Handle._run` or `BaseEventLoop._run_once`, or F_T's code is a cut code | raise |
| FOREIGN_DEFINITION | changed | entry: the declared module has no exact-str, non-`.pyc` `__file__`; a visited function link is incoherent (its `co_filename` is not its module's file); or no visited link has the module's globals | raise; names the innermost `module:qualname`, or `co_filename:qualname` when the globals' `__name__` is not an exact str; a `.pyc` `__file__` gets its own text |
| MONITOR_BUSY | **new** | entry: sys.monitoring tool ids 4 and 3 are both held under names other than this copy's `_TOOL_NAME`: other tools, or another loaded copy of `styxx.protocol` | raise; nothing minted |
| REENTRANT | **new** | enter or exit re-entered on the same thread from inside a transition (a finalizer, audit hook or signal handler) | enter: raise. Exit: recorded |
| MACHINERY_BUSY | **new** | another thread held the machinery for more than 10 s | enter: raise. Exit: recorded |
| CODE_SWAPPED | changed | entry: a mint with a live holder is no longer `T.__code__`. Exit: `T.__code__ is not M_T`, checked by **every** holder; the swap is left in place | entry: raise. Exit: recorded |
| TRACE_INACTIVE | changed | `run`/`run_async` on a tracer that is not active or is exiting, including an open that races exit | raise; recorded if the tracer was entered |
| UNDECLARED_SECTION | changed | open: no gate declares the section, **or the section is not a str** (never compared). Str subclasses are normalized first | raise + recorded |
| NESTED_SECTION | changed (text) | open: a registered opening of the same tracer is on the opener's chain before the cut (including an eager child's first step) | raise + recorded |
| CLONE_CALLED | changed | entry event: M_T running with foreign globals; recorded by **every** holder | recorded at exit |
| CLONE_ALIVE | changed | exit: an unexplained reference to M_T and either (a) gc finds another FunctionType holding it, or (b) the gc freeze count *rose* since the mint was made and references remain that visible referrers do not explain | recorded |
| CUT_MOVED | **new** | at an entry event of minted code, or at exit: `Handle._run` or `BaseEventLoop._run_once` is not a function whose code is in the cut | recorded at exit |
| TRACE_ACTIVE | changed (text) | `record()` on a tracer that was never entered (its own text), inside its with-block, or a zombie | raise |
| TRACE_INCOMPLETE | changed | `record()` after an exit that began but did not finish; after a failed enter; or in a process other than the one that entered it | raise |
| NO_TRACE | changed | score: the result is not a dict subclass; the key is absent; or the trace is not an exact dict (split message) | refuse |
| WRONG_TRACER | changed | score: the tracer is not exactly the str `/3` (every `/1` and `/2` trace refuses) | refuse |
| BAD_TRACE | changed | score: any schema clause fails, with the exact type tested before any hash or compare (`end`, `gates_sha256`, keys, codes); unknown or retired note or problem codes | refuse |
| STALE_TRACE, TARGET_SET, BAD_COUNT | same | as in v5e; order pinned by X109b and X112b | refuse |
| *(recorded code)* | changed set | score: `problems` is non-empty | every declaring gate refuses with the first problem's code |
| SECTION_ABSENT | same | score: no opening of the gate's *declared* section | refuse |
| NOT_EXERCISED | changed (text) | score: a declared target is missing from the union of its section's `calls` | refuse |
| note OPEN_AT_EXIT | changed | exit: the opening was still open; also "pruned: the trace's own exit did not run" | never refuses |
| note LAZY_RESULT | changed | `run()` got an exact generator, coroutine or async generator back; new text; "(its body had not started)" when unstarted | never refuses |
| note MONITOR_LOST | **new** | exit: our tool id was freed during the trace (re-taken if unowned, revision 2) or freed and taken; a held mint's local events were changed; the global PY_UNWIND was found cleared at a close while its section was open; or a callback on our id was replaced | never refuses; appended to every opening of the trace |
| FOREIGN_PROFILER | **retired** | styxx never touches profilers; every profiler coexists | a `/3` trace carrying it refuses BAD_TRACE |
| note PROFILER_LOST, note THREAD_HOP | **retired** | there is no hook to lose and no post-hop blind spot | BAD_TRACE if present |
| SIGNAL_TIMER (D1), UNSTABLE_ATTRIBUTE and GENERATOR_TARGET (D2), MACHINERY_BROKEN (D3) | never adopted | — | — |
| RETIRED earlier | carried | SHARED_CODE, NO_CODE, THREAD_OUTLIVES, HOOK_FAILED, PROFILER_REPLACED, EXIT_ORDER, SECTION_CONTEXT, ALIAS, SECTION_UNFINISHED, SECTION_FORM, CARRY_OUTSIDE, NESTED_CODE, SHARED_ROUTE | — |

---

## Per-finding disposition (all 58 confirmed round-4 findings)

Dispositions:
- **FIXED**: a mechanism change.
- **REFUSED_NOW**: the shape refuses with a coded, remedy-bearing message, disclosed as over-blocking.
- **SPEC_TEXT_FIX**: the behaviour is kept and the text is made true.
- **DISCLOSED_LIMIT**: a new or widened limit or residual.
- **EXAM_CASE_ONLY**: the rule already holds and the exam now pins it.
- **RULE_RETIRED**: the rule no longer exists in v5f; a regression case pins the successor behaviour.

### Blockers (6)
| # | key | disposition | v5f change | exam |
|---|---|---|---|---|
| B1 | pretrace-code-swap-stub-passes-provenance | FIXED | Coherence on every visited function link, F_T included. The declared module must have a source `__file__`. L-STUB and the J1-X1 row are rewritten. Residual R05b covers `'<'` or forged filenames (deliberate only). | X26b, X26c, X26d, X26e, X26f; R05b |
| B2 | hook-exception-leaves-lock-held | FIXED (structural) | No threading lock and no profile or trace function anywhere. Transitions exclude each other through the robust mutex (dead owners stolen, REENTRANT, MACHINERY_BUSY), and the callbacks never run at a C call. 3.11 is refused because its only mechanism re-creates the user-code form of this bug. | H6, H7, X138, X139, X140 |
| B3 | cache-wrapper-body-from-writable-wrapped | FIXED | F_T is the wrapper's real callee (`gc.get_referents`) and must be its own-dict `__wrapped__`, else NOT_A_FUNCTION naming the real callee. The provenance walk also steps to the real callee. Step 4, L-CACHE and "nothing is unwrapped" are corrected. | X24b, X24c |
| B4 | unstarted-generator-credited-py310-311 | FIXED | Confirmed-entry credit: PY_THROW is never used, and a frame killed at entry never publishes. 3.10 and 3.11 are refused. | X119, X135, H8 |
| B5 | stale-stop-after-mint-of-handle-run | FIXED | A monotone identity cut, captured before resolution. RESERVED_TARGET, CUT_UNAVAILABLE, CUT_MOVED. `_STOP` and its reset are gone. Spec lines 155/201 are superseded. Revision 1 has two changes. CUT_MOVED is checked at every entry event of minted code as well as at exit, so a transient rebind is caught. The loop boundary makes a loop started inside a section unable to credit it, uvloop included. Revision 2 has two changes. `BaseEventLoop._run_once`'s code joins the cut, and its binding joins `_cut_ok()`, which closes A1, A2 and revision 1's R17. E2 refuses a shareable binding code (M2). Residual R18 (deliberate only). | X34, X34b, X34c, X35, X35b, X35c, X65b, X65c, X65d, X65e, X65f, X65g, X141, X141b, X141c, V44, V61, V62, V63, V64; `cut_current` leftover invariant |
| B6 | py310-hook-reverts-closure-writes | REFUSED_NOW | UNSUPPORTED_VERSION below 3.12. v5f installs no Python-level profile or trace function on any version. | X37 (3.10/3.11) |

### Spec-false (7)
| # | key | disposition | v5f change | exam |
|---|---|---|---|---|
| S1 | eager-task-child-section-nested-refusal | SPEC_TEXT_FIX | The rule is kept (it fails closed). "Sections are calls" and over-blocking #1/#4 disclose the refusal and its remedy. Task-aware NESTED was rejected because it would change the rule for no soundness gain. | X83, V35 (unkeyed) |
| S2 | gc-freeze-hides-live-clone | FIXED | The CLONE_ALIVE clause (b): a *rise* in the freeze count since the mint was made, plus visible-referrer accounting. Revision 1: a rise, not a change, because frozen objects dying lower the count. The over-block is disclosed (#19). | X57b, X58b, V36, V36b |
| S3 | pep562-message-no-module | FIXED | The FOREIGN_DEFINITION message names the innermost `module:qualname` reached, using descriptor reads only. | X29b |
| S4 | call-tracing-credits-trace-callback-code | SPEC_TEXT_FIX | #14 is rewritten. Code run directly inside a trace, profile or monitoring callback is never credited; code run through `sys.call_tracing` (pdb `debug`) is credited where it lands (L-RUNTIME). Identical on 3.12 and 3.13 (D3 t_coexist). | R12 (unkeyed) |
| S5 | check-metrics-overflow-raises | FIXED | `_finite` catches OverflowError only. score raises a GateSpecError. smoke is read with exact types. | X117b, X117c |
| S6 | two-cache-wrappers-share-one-mint | FIXED + DISCLOSED_LIMIT | Refuses both-declared and same-namespace siblings. The remaining sibling-held-elsewhere route is L-CACHE. The line-72 sentence gains the L-CACHE exception. | X24d, X24e; R13 |
| S7 | interrupted-exit-stays-active | FIXED + DISCLOSED_LIMIT | Claims replace `_ACTIVE`, and reconciliation prunes. The only window left is before exit's claim (L-ZOMBIE), and `__exit__` again completes it. Lines 262/504 are superseded. | X92c, X140 |

### Defects (15)
| # | key | disposition | v5f change | exam |
|---|---|---|---|---|
| D1 | fork-pool-child-nested-refusal-and-hook | FIXED | An at-fork handler plus pid pass-through. #15 and R2-B3 are restated. Revision 1: the class-B argument now says that a forked child's thread is a copy of the forking stack, and that the at-fork handler and the pid pass-through exclude it. | V47 |
| D2 | pretrace-generator-objects-never-credited | DISCLOSED_LIMIT | #12 extended, L-WHERE narrowed, and the NOT_EXERCISED fixed sentence names it. Crediting the original code would reopen R1-B1/X48. | R14 |
| D3 | dict-subclass-result-no-trace | FIXED | `issubclass(type(result), dict)` plus `dict.get`, with a split NO_TRACE message. | V53, X93d |
| D4 | hook-self-removal-uninstalls-chaining-profiler | FIXED (structural) | styxx never calls `sys.setprofile`. | V37 |
| D5 | wraps-over-class-wrapper-overblock | FIXED | The walk steps through the own-dict `__wrapped__` of any object, read through a C descriptor. | V38 |
| D6 | str-subclass-section-bad-trace | FIXED | `str.__str__` normalization; a non-str section gives UNDECLARED_SECTION without being compared. | V39, X78f |
| D7 | unhashable-end-typeerror | FIXED | The exact type is tested before membership, as a general rule. | X103b |
| D8 | interrupted-exit-poisons-later-entries | FIXED | Reconciliation retires holderless mints. Entry CODE_SWAPPED fires only against live holders. | X92b |
| D9 | check-metrics-smoke-masks-refusal | FIXED | "smoke run" only when the trace is absent; otherwise the note starts with the code. | X117d |
| D10 | resolution-swallows-signal-exception | FIXED + DISCLOSED_LIMIT | Descriptor reads with no handler. Only the import and PEP 562 keep `except Exception`, as a chained UNRESOLVED (L-ASYNC-EXC). | X131 |
| D11 | async-exception-in-close-leaks-threads-registry | FIXED (structural) | No per-thread registry exists. Close is a claim plus idempotent cleanup, and exit and reconciliation detach everything. | X132, G_FI |
| D12 | enter-failure-after-mint-leaks | FIXED | The cut is validated and asyncio imported before resolution; nothing is imported in a transition. Holder before install. A dead entering token is reconciled, and the tracer is single-use. "Interrupted enter" is specified. | X35, X133 |
| D13 | pep562-fresh-product-false-refusal | REFUSED_NOW | `__getattr__` is called twice; differing products give UNRESOLVED with the remedy. Over-blocking #8 is updated. | X13b |
| D14 | reentry-race-double-entry | FIXED | The atomic claim is `__enter__`'s first statement. | X32d |
| D15 | resolution-isinstance-runs-user-code | FIXED | Real-type branching with `is` comparisons only, and C-descriptor reads. Revision 1: tuple-membership type tests are removed, because they run a metaclass `__eq__`. The docstring and R1-D2 row are made true. | V40, V40b, X17b |

### Note (1)
| # | key | disposition | v5f change | exam |
|---|---|---|---|---|
| N1 | nested-and-lazy-texts-misstate | FIXED | The NESTED_SECTION text is per case. LAZY_RESULT fires for exact types only, with the new text and the unstarted suffix. | X76b, X74d |

### Exam holes (29)
Each row's case implements the verifier's `exam_case_that_would_kill_it`. "Adapted" marks the five whose rule is retired in v5f; each is replaced by a regression case that pins the successor behaviour. The kill texts are quoted in "Exam cases required".

| # | key | disposition | exam |
|---|---|---|---|
| E1 | exam-mut-section-decl-clauses | EXAM_CASE_ONLY | X07b, X07c |
| E2 | examhole-clone-alive-single-tracer | EXAM_CASE_ONLY | X57c |
| E3 | examhole-clone-called-first-tracer | EXAM_CASE_ONLY | X55d |
| E4 | examhole-code-swapped-single-tracer | EXAM_CASE_ONLY | X59c |
| E5 | examhole-stop-read-before-mint | EXAM_CASE_ONLY (rule replaced by a cut captured before resolution) | X34 plus the `cut_current` invariant checked in every case. V61 is the named witness for E2's refresh: `Handle._run` is replaced between `coverage_trace()` and `__enter__` |
| E6 | examhole-union-over-all-sections | EXAM_CASE_ONLY | X120, V41 |
| E7 | examhole-declared-section-field-never-scored | EXAM_CASE_ONLY | V42, V43, X121, X78g |
| E8 | examhole-dispatch-cut-by-name | EXAM_CASE_ONLY | V44 |
| E9 | examhole-walk-bound-2-hops | EXAM_CASE_ONLY | V11c (with the existing X30b) |
| E10 | examhole-class-step-exact-type | EXAM_CASE_ONLY | V45, X14b |
| E11 | examhole-module-step-exact-type | EXAM_CASE_ONLY | V10b, X16b |
| E12 | examhole-inherited-direct-base-only | EXAM_CASE_ONLY | X14c |
| E13 | examhole-cache-body-module-check | EXAM_CASE_ONLY | X25c, X25d |
| E14 | exam-hole-coverage-on-failing-bar | EXAM_CASE_ONLY | X122, X122b |
| E15 | exam-hole-score-step-order | EXAM_CASE_ONLY | X96c, X78e |
| E16 | exam-hole-diagnostic-texts | EXAM_CASE_ONLY | X72b |
| E17 | exam-mut-stop-cleared-by-inner-exit | EXAM_CASE_ONLY (clearing no longer exists) | X65b |
| E18 | exam-mut-nested-by-section-name | EXAM_CASE_ONLY | V15b |
| E19 | exam-mut-restore-over-swapped-code | EXAM_CASE_ONLY | X59d |
| E20 | exam-mut-close-removes-foreign-profiler | RULE_RETIRED (adapted) | V58 |
| E21 | exam-mut-exit-removes-foreign-profiler | RULE_RETIRED (adapted) | V57 |
| E22 | exam-mut-double-exit-state-leak | EXAM_CASE_ONLY | V52 |
| E23 | exam-mut-hop-close-drops-closer-hook | RULE_RETIRED (adapted) | V28b |
| E24 | exam-mut-foreign-profiler-first-open-only | RULE_RETIRED (adapted) | V59 |
| E25 | exam-mut-target-set-before-stale | EXAM_CASE_ONLY | X109b |
| E26 | exam-mut-profiler-lost-only-if-none | RULE_RETIRED (adapted; successor MONITOR_LOST) | V60, X137 |
| E27 | exam-mut-bad-trace-end-type | EXAM_CASE_ONLY | X103c |
| E28 | exam-mut-problems-before-bad-count | EXAM_CASE_ONLY | X112b |
| E29 | exam-mut-uncredited-last-thread-wins | EXAM_CASE_ONLY | X123 |

### Round-4 items outside the 58
| key | status in audit | v5f |
|---|---|---|
| py313-signal-at-backedge-leaves-lock-held | found after round 4, BLOCKER-class, 3.13 | Closed structurally: there is no lock, and G_HYG's lint forbids a loop in any machinery `try` body, except `_run_async`'s one `await`, whose skippable `finally` nothing depends on (M7, p19). The same CPython bug in a harness's own `with` body gives L-ZOMBIE. Pinned by X140. |
| yappi-silently-replaced | surfaced, unverified | Moot: styxx never calls `sys.setprofile`. yappi is expected to coexist but is untested. |
| profile-module-refuses-on-312 | not confirmed (wording) | Moot: FOREIGN_PROFILER is retired. The `profile` module is a pure-Python `setprofile` profiler, V48's shape, and is expected to coexist; it was not executed. |
| recursion-walk-quadratic | not confirmed (NOTE) | Disclosed in Cost and over-blocking #17. No code change. |

---

## Finding closure, rounds 1–3 (rows that change; every other v5e row stands)

No row moves from CLOSED to open. G_CLOSURE re-runs the 41-case round 1–3 battery against v5f on 3.12 and 3.13.

| id | v5f status | how |
|---|---|---|
| R1-B1 shared code object | CLOSED_S | Unchanged (X40–X48). Generator objects created before the trace are under-credited, never over-credited (R14). |
| R1-B3 / R2-B2 / R3-B2 attribution | CLOSED_S | Unchanged anchor rule, plus the loop boundary: a loop started inside a section never credits it, uvloop included. The cut holds every `Handle._run` and `BaseEventLoop._run_once` code seen (revision 2). It is monotone and by identity, refuses shareable codes, and cannot be minted. CUT_MOVED is checked on both bindings at every hit. The one route left is the deliberate-only residual R18: re-entrant same-loop dispatch through code that is neither cut code (X34, X65b–X65g, X141b, X141c, V44, V63, V64). |
| R1-B4 C profiler crash or destroyed | CLOSED_S (structural, was: refusal) | styxx never calls `setprofile`, so no profiler is ever called, chained, replaced or removed (V33, V48, V57–V60). Among sys.monitoring tools, styxx adopts only an id that carries its own per-copy name, and never registers callbacks or changes events on an id that lost that name (X137, X142). |
| R1-D1 non-LIFO/reentry leaks | CLOSED_S | Atomic claims, idempotent detach, reconciliation (V15–V17, X32, X32d, V52). |
| R1-D2 resolution crashes and user code | CLOSED_P | Real-type branching with `is` comparisons (no tuple membership: V40b) and C-descriptor reads. User code runs only in the import and PEP 562, and any Exception there becomes a chained UNRESOLVED (V40, X17b, X131, X10–X13b). |
| R1-D3 / R2-D6 non-string trace keys, unhashable end | CLOSED_P | The exact type is tested before every hash or compare (X96–X108, X103b, X103c, X96d). |
| R2-B3 hook persists on a thread | CLOSED_S (structural), with one disclosed leak | There is no hook. The leftover check requires `sys.getprofile()` and `sys.gettrace()` unchanged on every case thread. A zombie's instrumentation also persists (L-ZOMBIE), but that is not this class. R2-B3 was a silent leak after a *completed* exit. A zombie exists only after a fault has propagated out of the harness's own `with`; `record()` refuses it, and it ends at `__exit__()` or at the next transaction once the facade is dropped. **Revision 2 (M3).** A party that frees styxx's id mid-trace could leave the global PY_UNWIND callback firing after a completed exit. Exit's reconciliation now re-takes an unowned freed id and clears its events (X137 free variant). **Disclosed leak:** if *another tool* takes the freed id before styxx's next transaction, styxx never touches it, and styxx's PY_UNWIND callback keeps firing on that id until the new owner changes its events or callbacks. MONITOR_LOST is noted on the trace in which it happened (`rev2/p3_free_reclaim.py`; L-MONITOR). |
| R2-D4 RecursionError in hook | CLOSED_S | Callbacks are not dropped when they raise. A frame killed at its entry never publishes (V27, X135). |
| R3-B3 hook swallows signal exceptions | CLOSED_S | Callbacks have no handler (H2 with its mutant). |
| R3-D3 finalizer deadlock | CLOSED_S (structural, was: RLock) | No locks exist. The robust mutex refuses REENTRANT instead of waiting, and callbacks take nothing (H1 with its mutant, X139). |
| R3 nit: f_locals cost | CLOSED_S | No Python-level profile or trace function exists, so there is no trampoline. The only `f_locals` read is the mutex's liveness check of a machinery frame on contention. |
| R3 nit: Ctrl-C drops a chained profiler | CLOSED_S | Nothing is chained. |
| R3 nit: PEP 562 | CLOSED_P | Two calls and identical products. FOREIGN_DEFINITION names the defining `module:qualname` (V10, V10b, X13b, X29b). |
| J1-X1 stub bound before the trace | CLOSED_P | `__globals__` identity plus code/file coherence on every visited link (X26–X30, X26b–f). The residual is L-STUB: an in-module stub, a wraps-stamped stub, or `'<'`/forged code (R05, R06, R05b). |
| J2 PROFILER_LOST flaky | N/A | The note is retired. |

---

## P1 retro under this spec
- **Harness and declaration unchanged.** `papers/first-afference/run_p1.py` is used unmodified, with `styxx/power_QUARANTINED.py.txt` loaded as `styxx.power` through SourceFileLoader. G4 declares the five `styxx.power` functions.
- **Runner change.** The only change is the v5e `cov.run(...)` line, and the interpreter is now 3.12 or 3.13.
- **Provenance.** All five pass coherence. Each function's `co_filename` is the `.txt` path, which is also the module's `__file__`, and `__globals__ is sys.modules["styxx.power"].__dict__`.
- **Expected record, identical to v5e.** `[{'calls': {'styxx.power:reachable': 12}, 'ambiguous': {}, 'end': 'returned', 'notes': []}]`, with empty `uncredited` and `problems`. Every one of the 12 calls returns, so all 12 are confirmed.
- **Verdict.** score() refuses NOT_EXERCISED, naming exactly the four unexercised functions (X118, G2). Afterwards `reachable.__code__` is restored and `_v5_state()["mints"] == []`.

---

## Over-blocking, disclosed

Each item is a refusal, or a missing credit, that a legitimate harness can meet.

1. **Off-stack work never counts.** This covers threads and grandchildren, thread pools, executors, `run_in_executor`, `asyncio.to_thread`, ThreadPool, library worker threads, asyncio child tasks and loop callbacks. **Remedy:** each job opens its own section. With `eager_task_factory`, only a child's first synchronous step runs on the parent's stack (X82). A child that opens its *own* section in that step refuses NESTED_SECTION for the whole trace (X83). **Remedy:** `await asyncio.sleep(0)` first (V35).
2. **Event loops must run outside the section.** `cov.run(name, asyncio.run, main())` counts nothing (X73). Every task step and callback of a loop started inside the section fails the loop boundary; with the stdlib loop it is also beyond the cut. This holds for uvloop and for any other loop that registers itself through `asyncio.events._set_running_loop` (revision 2, N9; a hand-driven scheduler that does not falls under L-WHERE), and for an eager task factory set through `loop_factory`: `asyncio.run` creates the main task before the loop runs, so the task is not started eagerly, and a `Handle._run` frame lies between it and the section (`rev1/p7_eager_loop_factory.py`, 3.12.3 and 3.13.12). A section opened inside a task of a running loop is credited normally, uvloop included (p9).
3. **Sections must be calls.** A generator or coroutine returned by fn gets LAZY_RESULT, and whatever of it runs after the close does not count.
4. **No same-tracer nesting on one stack above the cut or a loop boundary** (NESTED_SECTION). That includes an eager child's first step.
5. **A swallowed refusal refuses the whole trace.** This applies to any recorded code: REENTRY, TRACE_INACTIVE, UNDECLARED_SECTION, NESTED_SECTION, CLONE_CALLED, CLONE_ALIVE, CODE_SWAPPED, CUT_MOVED, REENTRANT, MACHINERY_BUSY. Every declaring gate scored against that trace refuses, including unrelated gates.
6. **Interpreters.** Tracing refuses UNSUPPORTED_VERSION on:
   - CPython 3.9, 3.10 and 3.11, including the lab's default 3.11, which P1-style harnesses use;
   - 3.14 and later;
   - free-threaded builds;
   - non-CPython implementations.

   Scoring works on every version. **Remedy:** run the harness on CPython 3.12 or 3.13.
7. **sys.monitoring.**
   - Enter refuses MONITOR_BUSY when tool ids 4 and 3 are both held by other tools.
   - styxx holds its id from the first enter until the process exits, so another tool that later asks for that id gets CPython's ValueError.
   - A tool or harness that clears styxx's events or replaces its callbacks blinds the trace. The trace gets a MONITOR_LOST note, and possibly NOT_EXERCISED.
   - A tool that frees styxx's id does not blind the trace's local events: CPython 3.12.3 and 3.13.12 leave the events and callbacks in place (`rev1/p3_free.py`). The trace gets a MONITOR_LOST note. While the id has no owner, styxx's next transaction re-takes it and clears its events (revision 2). If another tool has taken it, styxx never touches it, and any events styxx had set there stay until the new owner changes them (L-MONITOR). A section opened after the free, before the re-take, gets no PY_UNWIND, so its calls that raise are not counted.
   - A second loaded copy of `styxx.protocol` needs the other id; a third refuses MONITOR_BUSY.
8. **Declarable objects.** Declarable: a FunctionType; a staticmethod or classmethod of one; a C `lru_cache`/`cache` wrapper whose real callee is its own-dict `__wrapped__`, with that callee not bound by name in the module or holder and no sibling wrapper of it there. Refused:
   - class-based wrappers, `partial`, `property`/`cached_property`, bound methods, `singledispatchmethod`, builtins, C/Cython/numba callables, MagicMock;
   - attributes that come from a class through an instance; modules mid-path; inherited methods (declare the defining class);
   - a `sys.modules` entry that is not a ModuleType instance (UNRESOLVED);
   - a path step through an object whose `__dict__` is a Python-level descriptor (INSTANCE_PATH);
   - a cache wrapper whose `__wrapped__` was restamped (declare the function the wrapper calls);
   - a cache wrapper whose body is bound by name (declare that name);
   - two cache wrappers of one body in the same namespace, or two different declared objects reaching one body. **Remedy:** declare `'<module>:<name>.__wrapped__'`, which counts every execution of the body;
   - a PEP 562 attribute that returns a new object on each access, such as a deprecation shim (UNRESOLVED; declare the function it forwards to);
   - `asyncio.events:Handle._run`, and any function whose code is a recorded cut code (RESERVED_TARGET).
9. **FOREIGN_DEFINITION.**
   - Refused as in v5e: re-exports (declare the defining module); products of a no-`wraps` decorator or factory from another module; attrs- and namedtuple-generated methods whose globals are private; functions exec'd into private namespaces; autospec mocks and spies installed before the trace; PEP 562 lazy re-exports.
   - **New:** a declared module without an exact-str `__file__` (in-memory modules), or with a sourceless `.pyc`/`.pyo` `__file__`.
   - **New:** any function link the walk visits whose `co_filename`, after realpath and normcase, differs from its own module's `__file__`, unless it starts with `'<'`. That refuses, intentionally, a `__code__` swapped before the trace. It also refuses legitimate shapes:
     - modules whose code objects keep a stale filename, from loaders that do not fix `co_filename` (not measured);
     - a zip archive holding both `zmod.py` and a `zmod.pyc` compiled under a build path. On 3.13.12 zipimport loads the `.pyc`: `__file__` is `z2.zip/zmod2.pyc` and `co_filename` is the build path, so it refuses under (a) with the compiled-code message. On 3.12.3 the same archive loaded the source, whose names are coherent (`rev2/out_n2.txt`, from the second critic's `relp/z2.zip`). A zip holding only source is coherent on both versions (`relp/t_zip.py`). Revision 2 (N2) removes the rev-1 item "a relative `__file__` read after the working directory changed": the 3.12/3.13 path finder gives absolute paths, and the critic's `relp/t_rel.py` stays coherent after `chdir`;
     - a `__file__` rewritten by tooling;
     - a wrapper defined in an IPython/Jupyter cell, where `__main__` has no `__file__`, bound around a declared function.
10. **A wrapped target is the wrapper.** Calling the inner function directly does not exercise it.
11. **Cache hits do not count.** A body cached before the section opened reads as unexercised.
12. **`T.__code__` is a different, equal object during the trace.**
    - Code-identity tools see the change. Hot reload refuses CODE_SWAPPED, and `importlib.reload` during the trace under-counts.
    - Generator, coroutine and async-generator objects of T created before the trace, or in an earlier trace, keep T's original code, so their frames are never credited, even when resumed inside a section (R14). Create them inside the trace.
13. **A section open at trace exit** counts only calls confirmed before the exit's credit stop.
14. **Code run directly inside a trace, profile or sys.monitoring callback is never credited.** That includes code run by finalizers that CPython triggers inside such a callback.
15. **Child processes are invisible.** In a forked child, `run()` passes through: no section, no credit, no refusal. A tracer inherited across fork cannot exit in the child (a no-op), and its `record()` refuses TRACE_INCOMPLETE there.
16. **Valid cases of v5c/v5d that v5e refused** are still refused: `thread_started_in_section`, `thread_pool_inside_section`, `x2_grandchild_thread_in_section`, `asyncio_task_in_one_section`. The shape of `preexisting_python_profiler_chained` now passes (V48).
17. **Cost.** See Mechanism. The walk is linear in stack depth per hit, so deep recursion of a declared target is quadratic. A global PY_UNWIND callback runs for every frame that unwinds by exception, anywhere in the process, while any section is open (revision 2; revision 1: while any mint was registered). Each section open and close costs about 3 µs more for toggling it. The first `coverage_trace()` imports asyncio and scans gc once per new cut code.
18. **Confirmation.** A call counts only if its frame returns, yields, or unwinds from inside its body while the tracer is active. Never counted:
    - calls still running at the credit stop;
    - frames that never return, yield or unwind, such as `os._exit()`, or a thread still running at interpreter shutdown;
    - `throw()` and `close()` resumptions, even when a handler in the body then runs;
    - a frame killed at its entry instruction.
19. **CLONE_ALIVE after a `gc.freeze()` during a mint's life.** At a holder's exit the gc freeze count may be above its value when the mint was made. For a mint this tracer joined, the mint can be older than this trace. In that case any reference to M_T that gc cannot see at exit refuses:
    - a frame of T executing on any thread at that moment, since an executing frame's code reference is invisible to gc (`rev1/p5_execref.py`);
    - a frozen generator, coroutine, traceback or frame of T.

    Frozen objects dying and `gc.unfreeze()` only lower the count, so they never trigger it (p4).
20. **Lifecycle refusals.**
    - REENTRY for a retry after a failed `__enter__`, and for the losing thread of a concurrent double entry. Create a new tracer.
    - REENTRANT when a finalizer, audit hook or signal handler enters or exits a tracer inside another enter or exit on the same thread.
    - MACHINERY_BUSY when another thread holds the machinery for more than 10 s.
    - A section opened concurrently with the tracer's exit refuses TRACE_INACTIVE or records zero calls.
21. **The dispatch cut.**
    - CUT_MOVED: a harness or library that rebinds `Handle._run` or `BaseEventLoop._run_once`, or reassigns either's `__code__`, during a trace refuses every declaring gate. This happens if any hit of a declared target occurs while a binding is moved, or if one is still moved at exit (X141, X141b, X141c). A rebind and restore with no hit in between is accepted (V62). So is a rebind made before `__enter__` and kept through exit, because E2 adds its code to the cut (V61). nest_asyncio patches `_run_once` on the loop's own class, not on `BaseEventLoop`, so it is not a moved binding.
    - CUT_UNAVAILABLE: either binding that is not a plain Python function (mocked or C-replaced) at construction or entry refuses. Revision 2 (M2): so does either binding whose code is new to the cut and shareable, such as `Handle._run = logged(Handle._run)` with a generic decorator, or a module-level wrapper while another live function shares its code (X35b, X35c). Remedy: bind a dedicated module-level function.
    - **Cut poisoning that remains (revision 2, disclosed).** A function created *after* E2 that reuses a cut code, e.g. `FunctionType(W.__code__, g)` for a wrapper W bound earlier, stops attribution wherever it runs, for the rest of the process. The cut is monotone. The effect is an under-credit (NOT_EXERCISED with the call under `dispatched`), never an over-credit.
    - A signal handler or finalizer that runs directly in a re-entered `_run_once` frame, outside any `Handle._run`, is not credited to a section that re-entered it (revision 2; L-RUNTIME).
22. **Section types.** A non-str section refuses UNDECLARED_SECTION. A str subclass (StrEnum, `(str, Enum)`, numpy.str_) is normalized to its exact str value.

**Removed from v5e's list.**
- #6 foreign profilers: styxx calls neither `sys.setprofile` nor `sys.settrace`, so every such tool is expected to coexist. Coexistence was executed with D3's sys.monitoring adapter, not on the v5f machine, for cProfile, pdb, coverage.py's ctrace and sysmon cores, and a pure `setprofile` profiler (D3 t_coexist, p2_callback). The `profile` module, yappi, pyinstrument and debugpy were not executed. V33, V48, V50 and V51 pin coexistence on the implementation.
- #7 hook loss through `setprofile(None)`, RecursionError or signals: no hook exists.
- The per-event cost on non-target code.
- Over-block #16's `preexisting_python_profiler_chained`.

---

## Stated limits

- **Carried forward.** Exercised is not tested: one call satisfies a declaration. Transitive calls count. Only declared gates are checked. The trace is written by the runner, so forgery is an accepted residual under an honest-but-careless threat model. Hardcoded values (P1's G3) are out of scope.
- **L-WHERE (narrowed; revision 2 narrows it again).** Attribution certifies where code ran, not who asked for it. Work another gate supplies as data is credited to the section whose stack runs it:
  - queues drained inline or by a sectioned consumer;
  - `concurrent.futures` done-callbacks;
  - generators and coroutines *created during the trace* elsewhere and resumed there;
  - non-asyncio schedulers (trio, Twisted, a thread's own work queue, and any loop that does not register itself through `_set_running_loop`), which set no running asyncio loop;
  - eager tasks' first steps.

  Pinned by R01, R02, R09 and R10. Any asyncio loop, uvloop included, is no longer here. Work dispatched by a loop started inside a section fails the loop boundary and is never credited. v5e disclosed uvloop's Cython handles as a hole in this limit; revision 1 closes it (p9, X65d). Revision 2 closes revision 1's R17: its dispatch passes `BaseEventLoop._run_once`, now a cut code (X65g). The one asyncio route left is R18, deliberate only. A section opened in a task of a running loop re-enters that loop's dispatch through code that is neither cut code: a loop class whose own `_run_once` runs callbacks without `Handle._run`, or a self-restoring replacement of `BaseEventLoop._run_once` that does the same (`rev2/p1_runonce_cut.py`: credited on both versions).
- **L-RUNTIME (widened).** CPython-injected code counts for the section whose stack it lands on: signal handlers, `__del__` and weakref finalizers, gc callbacks, audit hooks, import-time module code (R08). Two exceptions follow from attribution (revision 2, N3). Such code landing while a loop started inside the section is running fails the loop boundary; v5e credited it. Such code landing in a re-entered `_run_once` frame, outside any `Handle._run`, meets a cut frame first (`rev2/p1_runonce_cut.py`: a SIGALRM handler in a re-entered `_run_once` is `dispatched` in revision 2, and was credited in revision 1). So does code a trace callback runs through `sys.call_tracing`, such as pdb's `debug` command; this is identical on 3.12 and 3.13 (R12). Code run directly inside any trace, profile or sys.monitoring callback is never credited.
- **L-CLONE.** During the trace, code reads M_T and then does one of these; each is credited as T:
  - builds a function with T's own globals and drops it before exit (R03);
  - runs `exec(M_T, T.__globals__)` (R04);
  - does `U.__code__ = M_T` and swaps it back before exit;
  - freezes a live clone while the gc freeze count ends exactly where it stood when the mint was made.

  Otherwise a live clone is caught by CLONE_ALIVE, foreign globals by CLONE_CALLED, and a swap left in place by CODE_SWAPPED.
- **L-STUB (widened and made true).** Provenance proves which globals the function was created with. It checks that every visited function's `co_filename` names its own module's file, or is a generated `'<…>'` filename. `co_filename` can be forged with `code.replace`, so this catches careless swaps; it does not prove where the code came from. Provenance does not prove that the function is the original binding. Credited:
  - a stub defined in the declared module (R05);
  - a `functools.wraps`-stamped stub (R06);
  - a stub whose code has a `'<…>'` filename, or whose `co_filename` was forged to the module's file, bound or swapped in before the trace (R05b; deliberate only).
- **L-CACHE (widened).** A cache wrapper's target is its real callee, the body. Every execution of the body counts, whatever route reaches it: a direct call, `__wrapped__`, a reference captured before decoration (R07), or a miss in a sibling cache wrapper of the same body held outside the module and holder namespaces (R13).
- **L-ASYNC-EXC (rewritten as the envelope I6).** A fault anywhere in the machinery can only do these:
  - lose counts;
  - make an opening read `"open"` or `"raised"` with OPEN_AT_EXIT;
  - add REENTRANT or MACHINERY_BUSY when the fault itself enters or exits a tracer;
  - make `record()` refuse TRACE_INCOMPLETE or TRACE_ACTIVE;
  - inside the PY_UNWIND callback, replace the exception being unwound (L-DELIVERY).

  An asynchronous Exception subclass landing in the declared module's import, or in its PEP 562 `__getattr__`, becomes a chained UNRESOLVED. An asynchronous exception during that import can also leave importlib's per-module lock inconsistent. That is CPython's behaviour: D1 observed it on 3.10 and 3.11. It was not measured on 3.12 or 3.13, where the lock's own wait loop is also exposed to #130279 on 3.13. **Remedy:** import declared modules before the trace. For a module already in `sys.modules` and not initializing, `import_module` takes no module lock.
- **L-DELIVERY (new; scope reduced in revision 2).** styxx's callbacks are Python code at these events:
  - while a mint is registered: every entry (PY_START/PY_RESUME), return and yield of a declared target;
  - while *some section is open* anywhere in the process (revision 2; revision 1: while any mint existed): every exception unwind of any Python frame, on every thread.

  An asynchronous exception can therefore surface *inside a callback*, and it takes effect at that event:
  - **At a target's entry:** the body does not run, and the call is not counted.
  - **At a target's return or yield:** the completed call raises that exception in its caller instead of returning (synth/p_deliver.py), and the call is still counted, confirmed by the unwind at the return offset (synth/p_r16.py).
  - **At any frame's unwind:** it replaces the exception being unwound, and on 3.12.3 and 3.13.12 its `__context__` is None, so the original exception is lost (synth/p_deliver.py). An `except` clause for the original exception then does not run.

  Near the recursion limit, a callback's own frame can raise RecursionError at those same points. No C call is ever skipped, because styxx enables no C-call event and installs no profile or trace function. So the lock-release hazard of hook-exception-leaves-lock-held cannot arise from styxx on 3.12/3.13. D1 measured 0 user-lock leaks in 51,075 and 52,456 SIGALRM timeouts with its PY_START/PY_RESUME-only adapter. G_SIG re-measures this with v5f's full event set.

  **What changes in the traced program (revision 2, M4).** This is a change of behaviour, and it is disclosed as one:
  - Untraced CPython has no eval-breaker check between a `raise` and the matching `except` clause. A pending asynchronous exception therefore takes effect only after the handler has started, and the handler's first instructions, up to its first eval-breaker check, always run. The measured consequence is below: 0 lost handlers untraced. With the unwind callback, it can take effect before the handler starts.
  - `finally` blocks and with-exits still run, for the replacing exception. A `with lock:` still releases.
  - An `except E:` handler for the exception in flight does not start, so its side effects are skipped.
  - Exception chaining is lost: the new exception's `__context__` is None.
  - CPython documents no guarantee that a handler starts before a pending asynchronous exception takes effect, but untraced programs can depend on it, and the second critic's probe does.

  Measured with that probe's method in `rev2/p4_unwind_scope.py`: a loop raising and catching ValueError in undeclared code, 1M iterations, under a 20 µs SIGALRM flood whose handler raises. It counts the handlers lost:

  | | 3.12.3 | 3.13.12 |
  |---|---|---|
  | untraced | 0 | 0 |
  | trace active, no section open: revision 1 | 171,683 | 121,297 |
  | trace active, no section open: revision 2 | **0** | **0** |
  | inside an open section: revision 2 | 168,512 | 120,255 |

  **Why this is accepted when 3.11's hook was not.** The 3.11 hook skipped C calls, including the `lock.release()` inside a `with` block's exit. That breaks code that the language's own `with`/`finally` rules make correct under asynchronous exceptions, and it reached every thread with a section. L-DELIVERY keeps every `with`/`finally` guarantee. It moves the point where an already-pending asynchronous exception takes effect to the start of a handler's matching. From revision 2 it does so only while a section is open.

  **G_SIG (frozen decision).** L-DELIVERY does not count as a "wrong result" under G_SIG. G_SIG's frozen harness nevertheless contains three L-DELIVERY cells, each with a fixed rule:
  - (a) an `except ValueError` flow in undeclared code, run while a trace is active and no section is open: gated at **0** lost handlers, the untraced value;
  - (b) the same flow inside an open section: measured and reported, not gated;
  - (c) `with lock:` and `try/finally` flows inside an open section: gated at 0 skipped cleanups and 0 leaks.

  Every other G_SIG harness flow uses only `with`/`finally` for cleanup and checks results only on iterations in which no asynchronous exception was delivered.

  **The alternative, not taken.** First-LINE confirmation would need no global event at all, at the cost of a LINE callback per line executed in declared functions. Revision 2 keeps PY_UNWIND and narrows it to open sections instead. That meets the measured case, unrelated code outside sections, at a cost of about 3 µs per section.
- **L-ZOMBIE (new).** A tracer whose exit never began stays active, and `record()` refuses TRACE_ACTIVE. The causes:
  - an exception at `__exit__`'s entry;
  - a foreign tool raising at `__enter__`'s return;
  - a harness `with` body ending in a loop on 3.13 hit by a signal at its back-edge (CPython #130279).

  Its equal-code mints stay installed. The process-wide PY_UNWIND callback stays only while one of its sections is still open (revision 2). That lasts until one of two things happens: `__exit__()` is called, or the facade becomes unreachable and some later enter or exit in the process reconciles. With neither, it lasts until the process exits. A double fault that leaves a stale anchor can keep the facade reachable through the anchor frame's callers.
- **L-MONITOR (new).** Any party can call `sys.monitoring.set_local_events`, `set_events` or `register_callback` on styxx's tool id. Doing so blinds the trace. Exit detects it and adds the MONITOR_LOST note, but calls lost before exit are not counted.
  - **`free_tool_id` does not blind.** On 3.12.3 and 3.13.12 it only removes the name and leaves events and callbacks in place (`rev1/p3_free.py`), so counting continues. Exit notes MONITOR_LOST because the name is gone.
  - **An unowned freed id is re-taken (revision 2).** At the next transaction, normally the trace's own exit, styxx takes the id back under `_TOOL_NAME` and clears its events. Nobody owns it, so nobody is clobbered. Afterwards no styxx callback outlives the completed exit (`rev2/p3_free_reclaim.py`).
  - **An id another tool took is never touched.** styxx registers no callback and changes no event there, so it cannot clobber the new owner. The cost falls the other way: events styxx had set on the freed id, including the global PY_UNWIND if a section was open at the free, keep calling styxx's callbacks there until the new owner changes them (p3: 1,000 callbacks for 1,000 unrelated raises after the exit). This is the one leak after a completed exit, and it is disclosed in the R2-B3 row.
  - **Races.** A `free_tool_id` or `use_tool_id` by another thread landing between two of styxx's sys.monitoring calls can make `run()` or a transaction raise ValueError (the Tool acquisition prefix).
  - **Pending entries.** A pending entry whose confirmation never arrives keeps its frame (and that frame's callers) alive until the mint is retired.
- **Counts are confirmed entries.** One per start or resumption whose frame then returned, yielded or unwound from inside its body. A two-yield generator consumed fully records 3; a one-await coroutine run by asyncio records 2. Counts are lower bounds.
- **Interrupted enter and exit** are reconciled at the next enter or exit (see the exception-safety model). The only exception is L-ZOMBIE.
- **Diagnostic buckets are partial.** `uncredited` counts confirmed, uncredited hits on every thread while the tracer is crediting and some section is open somewhere in the process (revision 2: a hit while no section is open stores nothing). It never sees code inside callbacks or unconfirmed calls, and it is never evidence.
- **Scope of testing.** CPython 3.12.3 and 3.13.12, GIL builds. Not covered: other patch levels, 3.14, free-threading, greenlet and gevent (a greenlet switch made from inside a transition defeats the mutex's liveness test), subinterpreters, and interpreter shutdown.

---

## Exam cases required

### Exam harness rules (frozen with the prereg before implementation)
- **Interpreters.** The full exam runs on CPython 3.12 and 3.13, with identical expected outcomes (G_XVER). On 3.10 and 3.11 the runner executes X37 and every scoring-only case, and those outcomes must equal the 3.12/3.13 ones. The scoring-only cases read prebuilt `/3` traces. `ref_v5f.py` generates them on 3.12 at freeze time, and they are committed in the freeze commit as `traces_v5f/*.json`, each hashed in the prereg.
- **How cases run.** There are three placements.
  - **Inside the self-trace.** Each case runs in its own thread inside the outer self-trace as `cov.run(<gate section>, case)`, with a 30 s join watchdog.
  - **On the main thread before the self-trace.**
    - Signal cases, hazard sweeps, H6–H10, X71c, X138–X140 and V65.
    - Every case that rebinds `Handle._run` or `BaseEventLoop._run_once`: X35, X35b, X35c, X65e–X65g, X141, X141b, X141c, V61, V62, V64, R18. Such a rebinding would otherwise be seen at the self-trace's own hits and refuse it CUT_MOVED.
    - Revision 2 (M6): every case that uses the id-5 injector on a machinery function, which is X92b, X131 and X132. Before the self-trace nothing is minted, so `_v5_faultpoints()` returns the code that runs, and the self-trace's own calls cannot be faulted.
  - **In a fresh subprocess** of the same interpreter, running the exam's fixture path. These are the cases that need tool ids in a state the process-long self-trace cannot give: X36, X137's `free_tool_id` variant and X142. The subprocess reports its outcome as JSON.
- **Case hygiene.** A case that calls `gc.freeze()` calls `gc.unfreeze()` before it returns. The leftover check then requires `gc.get_freeze_count()` to be no higher than before the case. A case that rebinds `Handle._run` restores it.
- **How cases pass.** A violation passes only if the refusal message *starts with* its expected `[V5:CODE]`. A valid case passes only with exactly the listed union counts, notes and ends. A residual case passes only with its documented outcome.
- **What the exam may read.** The public API, fixture modules, `_v5_state()` and `_v5_faultpoints()`, and no other private name of `styxx.protocol`. Machinery functions are named only by the frozen `_v5_faultpoints()` keys (M10). Private names of the standard library (`asyncio.events.Handle`, `loop._run_once`) may be used.
- **Leftover checks after every case:**
  - `_v5_state()` equals the snapshot taken before the case, except the monotone fields `cut` and `tool`;
  - `cut_current` is True;
  - `guard` is `"free"`;
  - every fixture function's `__code__` is its original;
  - `sys.getprofile()` and `sys.gettrace()` are unchanged on the case thread;
  - `threading.getprofile()`/`gettrace()` are unchanged;
  - sys.monitoring tool ids other than styxx's are in their pre-case state.
- **Fault tools.** The exam's own monitoring fault tool uses id 3, below styxx's 4. It takes id 3 only for the duration of each case that uses it and frees it afterwards. The frozen injector uses id 5 (INSTRUCTION events on `_v5_faultpoints()` code). On 3.12.3, INSTRUCTION events themselves create the #130279 skip at the instrumented code's back-edges (p12). That is harmless here: the machinery has no `finally` or `with` across a loop other than M7's `await`, and nothing depends on that.
- **Injector rules (revision 2).** Each rule answers a measured failure mode:
  - *Code identity.* The injector instruments the code objects `_v5_faultpoints()` returns at the moment of arming (M10). They are read at call time.
  - *Thread filter.* It faults only events on the case's own thread. That thread is identified by `Thread.ident`, read after `start()` and while the thread is alive, and the injector is disarmed before `join()`. Idents are reused once a thread ends: in `rev2/p6_faultpoint_identity.py`, a filter keyed on a finished thread's ident matched a later thread.
  - *No settrace.* A settrace function active over a code object silences other tools' INSTRUCTION events on that code, and they stay silent after `settrace(None)` until `sys.monitoring.restart_events()` (`rev2/p5b_settrace_blinds_injector.py`, 3.12.3 and 3.13.12). So the injector never runs while a settrace or setprofile function is set, it calls `restart_events()` before each trial, and G_COVER's settrace-based pass runs in a separate process.
  - *Self-check.* Each injector run first faults a frozen probe function at a known offset. If that trial does not fire, the run is void and counts as a failure of the instrument, not as clean.
- **Environment.** coverage.py 7.16 is pinned in the exam environment for V50.

### v5e cases whose outcome changes (the freeze-time delta against `ref_v5f.py` must equal this table)
| v5e id | v5e outcome | v5f outcome | reason |
|---|---|---|---|
| X75 | NOT_EXERCISED, message contains PROFILER_LOST | retired; replaced by V49: PASS `{f:1}`, no note | no hook to lose |
| X80 | FOREIGN_PROFILER | retired; replaced by V48: PASS `{f:1}`, profiler still installed and it saw the call | profilers coexist |
| X81 (≤3.11) | FOREIGN_PROFILER | retired (3.11 refused); V33 is unkeyed | — |
| V26 | `{f:1}` + PROFILER_LOST | `{f:1}`, no note | — |
| V28 | `{f:1}` + THREAD_HOP | `{f:1}`, no note | — |
| V30 | A `{f:1}`+PROFILER_LOST, B `{g:1}` | retired (no epochs); V28b covers hops | — |
| V31 | `getprofile()` None after one event | retired; the leftover check requires `getprofile()`/`gettrace()` to be unchanged | — |
| X82, V33 | version-keyed | unkeyed | 3.12+ only |
| X95 | `/1` → WRONG_TRACER | same; X95b adds `/2` → WRONG_TRACER | — |
| H1 mutant | non-reentrant Lock in the hook | the robust mutex replaced by `threading.Lock` | no hook exists |
| H2 mutant | `except Exception` in the hook | `except Exception` in the callbacks | — |
| V34 | self-coverage of v5e machinery | G0 declares `styxx.protocol:Experiment._check_coverage`, `styxx.protocol:_resolve_target`, `styxx.protocol:_open`, `styxx.protocol:_exit` and `styxx.protocol:_run` (all frozen names, M10). PASS: each has a union count ≥ 1 | renamed machinery. No exact `_run` count: a case's own loops make some `_run` calls fail the self-trace's loop boundary |
| X91 | `record()` before enter: TRACE_ACTIVE | same code; text "the tracer was never entered" | text per case (M8) |

**v5e cases and harness parts that read a private name of `styxx.protocol`.** Each keeps its outcome and is ported to the frozen surface as follows. G_V5E_DELTA runs the ported form.

| v5e part | private names read | v5f port |
|---|---|---|
| X71c | `P._hook`, and a rebinding of `P._ANCHORS` to a tapping dict | Same outcome, NOT_EXERCISED, with the witness tracer's union `{f:1}`. Runs on the main thread before the self-trace. An interval SIGALRM (0.2 ms) is armed before `cov.__exit__()`. Its handler calls f once, the first time `_v5_state()["anchors"]` is below its value when exit began and above 2 (the witness's and G's anchors). By spec order that is inside X3, after X1 and X2, and G's on-stack opening, appended last, is still registered. A handler tripped from inside a monitoring callback cannot be used: code it runs raises no monitoring events (`rev1/p16_handler_events.py`). **Revision 2 (M7): a landing rule instead of hoping for one.** 100,000 suspended `run_async('G', …)` openings make X3 long, not 1,000. A trial *lands* iff the witness tracer's union has f, an observable. A trial that does not land is void and is repeated, up to 20 trials. X71c passes iff some trial lands and no landed trial credits f to G. It fails if no trial lands in 20, or if any landed trial credits G. SM1 applies the same rule to ref+W: a weakening is KILLED iff some landed trial credits G. In `rev2/p7_x71c_landing.py`, 1,000 openings landed in only 6 of 10 trials on 3.12.3, which is the critic's point. 10,000 and 100,000 landed in 10 of 10 on both versions, and the M10 mutant (credit stop after detach) credited G in every landed trial |
| leftover snapshot | `_MINTED`, `_BY_FN`, `_ANCHORS`, `_THREADS`, `_ACTIVE` | `_v5_state()` (the harness rules above) |
| self-trace code list | `_CoverageTracer._open`, `_close`, `__enter__`, `__exit__`, `run`, `record`, `_resolve_target` | the frozen `_v5_faultpoints()` keys |
| H1 and H2 mutants | `P._hook`, `P._CoverageTracer` methods, `P._MINTED` | SM1 rows against `ref_v5f.py` (Hazard sweeps) |
| H5 (gc cost) | `P._hook` | the `prev is not P._hook` restore is deleted; no hook exists |

Every other v5e case keeps its id and its expected outcome.

### New violation cases (expected code)
| id | shape | code | source |
|---|---|---|---|
| X07b / X07c | `section: ""` / `section: "sеction"` (Cyrillic е) | SECTION_DECL | E1 |
| X13b | a PEP 562 `__getattr__` returning a fresh function on each access (deprecation shim) | UNRESOLVED; the message names the remedy | D13 |
| X14b | an inherited method of an `abc.ABC` subclass | INHERITED | E10 |
| X14c | `Leaf(Mid(Base)).fit` and `Model(LoggingMixin, Base).fit` | INHERITED (not UNRESOLVED); the message names the defining class | E12 |
| X16b | a submodule whose `__class__` is a ModuleType subclass, reached after the colon | INSTANCE_PATH | E11 |
| X17b | a step through an object whose class defines a Python `__dict__` property with a side-effect counter; the counter stays 0 | INSTANCE_PATH | D15 |
| X24b | round-4 repro: `power = functools.wraps(power_ref)(lru_cache(None)(fast))`, with `power_ref` reachable only as `Ref.power`, so `power.__wrapped__` is not the function the wrapper calls | NOT_A_FUNCTION; the message names `fast` | B3 |
| X24c | X24b with `power_ref` also bound at module level (v5e's message said "declare power_ref", which the wrapper never calls) | NOT_A_FUNCTION; the message names `fast`, never `power_ref` | B3 |
| X24d | both of two cache wrappers of one body declared | NOT_A_FUNCTION | S6 |
| X24e | the declared wrapper's body also wrapped by a sibling cache wrapper in the same module | NOT_A_FUNCTION; the message contains `.__wrapped__` | S6 |
| X25c | `Scorer.fast = lru_cache(None)(_impl)`, bare and as a staticmethod, with `_impl` bound at module level | NOT_A_FUNCTION | E13 |
| X25d | a cache wrapper served only through PEP 562 (holder None) whose body is bound at module level | NOT_A_FUNCTION | E13 |
| X26b | `real.__code__ = stub.__code__` before the trace; stub from a test module; called through a pre-bound alias | FOREIGN_DEFINITION | B1 (shape B) |
| X26c | `FunctionType(stub.__code__, vars(mod))` bound at the name | FOREIGN_DEFINITION | B1 (shape C) |
| X26d | a foreign `functools.wraps` wrapper bound at the name whose own `__code__` was swapped to a test stub before the trace (judge_sound/j_d1_wrapper_swap.py) | FOREIGN_DEFINITION | B1 (graft) |
| X26e | declared module built with `types.ModuleType`, with no `__file__`, registered in `sys.modules`, whose function has a `'<m>'` filename | FOREIGN_DEFINITION | D2 graft 2 |
| X26f | a sourceless module (`__file__` ends `.pyc`, SourcelessFileLoader) | FOREIGN_DEFINITION | D2 graft 2 |
| X29b | a re-export through a decorated PEP 562 lazy attribute; the message contains the defining `module:qualname` | FOREIGN_DEFINITION | S3 |
| X30d | a `__wrapped__` chain link whose class defines a Python `__dict__` property (never called), with no accepting link before it | FOREIGN_DEFINITION; the property counter stays 0 | D5 |
| X32d | two barrier-synchronised threads enter one tracer; 50 repetitions | REENTRY at score. Exactly one entry each time, with counts exact in the record | D14 |
| X34 | declare `asyncio.events:Handle._run` and f; `cov.run('A', asyncio.run, main())` | RESERVED_TARGET at entry | B5, E5 |
| X34b | a fixture function built as `FunctionType(Handle._run.__code__, vars(fx))` and declared | RESERVED_TARGET | B5 |
| X34c | declare `asyncio.base_events:BaseEventLoop._run_once` and f (revision 2) | RESERVED_TARGET at entry | B5, M1 (rev. 2) |
| X35 | `Handle._run` replaced by a MagicMock around `__enter__`; nothing minted afterwards | CUT_UNAVAILABLE | D12, B5 |
| X35b | before `__enter__`, `Handle._run = logged(orig)`, where `logged` is a closure decorator from a fixture module (`logged.<locals>.inner`); restored after | CUT_UNAVAILABLE; the message names `logged.<locals>.inner`; a later trace of a `logged`-decorated helper that calls f PASS `{f:1}` (`rev2/p2_shared_cut.py`) | M2 (rev. 2), `<locals>` clause |
| X35c | a module-level wrapper W (V61's shape) bound as `Handle._run` while the fixture also holds `FunctionType(W.__code__, g)` alive | CUT_UNAVAILABLE (p2) | M2 (rev. 2), gc-referrer clause |
| X36 | in a fresh subprocess: tool ids 3 and 4 taken by two other tools before any tracer is entered | MONITOR_BUSY; nothing minted | new |
| X37 (3.10/3.11 only) | `coverage_trace(exp)` | UNSUPPORTED_VERSION; scoring cases still pass on that interpreter | B6 |
| X55d | nested tracers on f; `FunctionType(f.__code__, {})()` while both hold the mint | CLONE_CALLED for **both** traces | E3 |
| X57b | a same-globals clone of M_T made in the trace, then `gc.freeze()`, kept alive through exit | CLONE_ALIVE | S2 |
| X57c | nested tracers on f; the inner section calls only a same-globals clone, kept alive past the inner exit and dropped before the outer exit | inner: CLONE_ALIVE | E2 |
| X58b | `U.__code__ = T.__code__`, U kept, then `gc.freeze()` | CLONE_ALIVE | S2 |
| X59c | nested tracers; the inner section calls f, then swaps `f.__code__` and leaves it through the inner exit, restoring before the outer exit | inner: CODE_SWAPPED | E4 |
| X59d | X59 plus a check after exit and before the case's own restore that `f59.__code__ is u59.__code__` and `f59() == -59` | CODE_SWAPPED; swap left in place | E19 |
| X65b | V15's inner tracer entered and exited inside the outer; then section A of the outer runs a loop serving another thread's `run_coroutine_threadsafe` and `call_soon_threadsafe` jobs that call f | A: NOT_EXERCISED with `dispatched {f:2}` | E17, B5 |
| X65c | inside a task of a running loop L, `cov.run('A', section)` where `section` calls `L._run_once()`, which runs a callback another task scheduled; the callback calls f (same loop at open and at the hit; only the cut separates them; p17) | A: NOT_EXERCISED with `dispatched {f:1}` | B5 (cut witness) |
| X65d | a `SelectorEventLoop` subclass whose `_run_once` runs ready callbacks through `map(operator.call, …)`, with no `Handle._run` frame (p8), run inside section A and serving another thread's `call_soon_threadsafe` job that calls f | A: NOT_EXERCISED with `dispatched {f:1}` | B5 (loop-boundary witness; the uvloop shape) |
| X65e | X65c's shape, with `asyncio.TimerHandle._run` set to a reimplementation after `__enter__` and before the section, and the job scheduled with `call_later(0, f)`; the override is deleted after exit (the second critic's A1) | A: NOT_EXERCISED with `dispatched {f:1}`; no CUT_MOVED | M1 (rev. 2): `_run_once` in the cut |
| X65f | X65c's shape, with `asyncio.events.Handle` rebound to a subclass with its own `_run` after `__enter__` and before `call_soon(f)`; restored before exit (A2) | A: NOT_EXERCISED with `dispatched {f:1}` | M1 (rev. 2) |
| X65g | revision 1's R17, pinned (M10). **After `__enter__`**, with no hit of a declared target before the section, the harness rebinds `Handle._run` to a module-level W that first restores the original binding and then runs the job. Section A, in a task of L, calls `L._run_once()`, which runs a job another task scheduled that calls f | A: NOT_EXERCISED with `dispatched {f:1}`; no CUT_MOVED. The same holds with W bound before `__enter__` (`rev2/p1_runonce_cut.py`), but that variant also passes through E2 and is not this case | M1, M10 (rev. 2) |
| X72b | X72's trace: the message contains exactly `dispatched {'<fx>:f': 2}, unattributed {}`; `check_metrics` gives `G:exercises` usable False with a note starting `[V5:NOT_EXERCISED]` | NOT_EXERCISED | E16 |
| X74d | `run(G, genfn)`: the LAZY_RESULT note text contains "whatever of its body runs after the section closed does not count (its body had not started)" | NOT_EXERCISED | N1 |
| X76b | X76 on the same section, and a variant on two sections: the two NESTED_SECTION texts | NESTED_SECTION | N1 |
| X78e | the harness swallows `cov.run('G_typo', f)` and never opens G's section | UNDECLARED_SECTION (not SECTION_ABSENT) | E15 |
| X78f | `cov.run(5, f)`, swallowed | UNDECLARED_SECTION | D6 |
| X78g | a gate whose declared section is `'harness'`, opened by its gate *name* | UNDECLARED_SECTION | E7 |
| X83 | eager child task created inside `run_async('A')` calls `cov.run_async('B', …)` in its first step | NESTED_SECTION | S1 |
| X92b | during exit, the id-5 injector, with INSTRUCTION events on `_v5_faultpoints()['_retire']`, raises `Injected` at the first instruction it sees at which the fixture's `f.__code__` is again the original. That is after the restore and before the unregister, a prefix defined by observable state, not by offsets | that trace: TRACE_INCOMPLETE; a later trace of the same target PASS `{f:1}`; leftovers clean | D8 |
| X92c | the id-3 fault tool raises at PY_START of the facade's `__exit__` code | TRACE_ACTIVE from `record()`; a second tracer on f PASS meanwhile; then `cov.__exit__()` again → PASS `{f:1}`; leftovers clean | S7 |
| X93d | a result whose trace was loaded with `object_pairs_hook=OrderedDict` | NO_TRACE, third wording ("'coverage_trace' is a `OrderedDict`, not an exact dict"): the outer OrderedDict passes step 1 and has the key | D3 |
| X95b | a committed v5e `/2` trace | WRONG_TRACER | — |
| X96c | a genuine trace with `gates_sha256` popped | BAD_TRACE (never KeyError or STALE_TRACE) | E15 |
| X96d | `gates_sha256: 5`; `tracer` given as a str subclass whose `__eq__` raises (the raiser never runs) | BAD_TRACE / WRONG_TRACER | graft 4 |
| X103b | `end` as a list and as a dict | BAD_TRACE; `check_metrics` REPORTED without raising | D7 |
| X103c | `end = S('returned')` with `class S(str)` | BAD_TRACE | E27 |
| X105d | a `/3` trace carrying a retired note (PROFILER_LOST) or problem (FOREIGN_PROFILER) | BAD_TRACE | — |
| X109b | an old trace scored against a gates block that also adds a declared target | STALE_TRACE | E25 |
| X112b | a trace with a genuine recorded UNDECLARED_SECTION problem and one `calls` count set to 0 | BAD_COUNT | E28 |
| X117b | a 400-digit int metric | `check_metrics` REPORTED ("int too large for a float"); `score` raises GateSpecError, not OverflowError | S5 |
| X117c | `smoke` is an object whose `__bool__` raises | REPORTED; `__bool__` never called | S5 |
| X117d | a smoke result carrying a trace that refuses NOT_EXERCISED | the `check_metrics` note starts with `[V5:NOT_EXERCISED]` | D9 |
| X119 | declared generator and coroutine functions: object dropped unstarted; `close()` unstarted; `throw()` into unstarted; primed outside the section and closed at a bare yield inside it | NOT_EXERCISED on 3.12 and 3.13 | B4 |
| X120 | gate A declares f, gate B declares g; `cov.run('A', g)` then `cov.run('B', f)` | A: NOT_EXERCISED | E6 |
| X121 | X[f] with section `'Y'`, Y[g] with section `'X'`; the harness opens each gate *by gate name* | X: NOT_EXERCISED | E7 |
| X122 | a declaring gate whose bar fails (m=0.0), and a harness that never calls one declared target | NOT_EXERCISED (never the table's FAIL row) | E14 |
| X122b | X122 plus a swallowed NESTED_SECTION | NESTED_SECTION | E14 |
| X123 | two live threads each open a section and dispatch g once through their own loop's `call_soon` | NOT_EXERCISED for a gate declaring g; `record()['uncredited']['dispatched'] == {g: 2}`; the message prints 2 | E29 |
| X131 | the id-5 injector raises `Injected(Exception)` at the first instruction of `_v5_faultpoints()['_provenance']` after its entry (RESUME) | `Injected` propagates from `__enter__` (not a GateSpecError); nothing minted | D10 |
| X132 | the injector faults every line of `_open` and `_detach` in turn, on a worker thread | each faulted trace refuses or scores within I6; after exit `anchors == 0`; a later trace PASS | D11 |
| X133 | an audit hook refuses the second `__code__` write mid-mint | enter raises the hook's error; retry → REENTRY; `record()` → TRACE_INCOMPLETE; a later trace PASS; leftovers clean; all code restored | D12 |
| X135 | the id-3 tool calls `PyThreadState_SetAsyncExc` at the target's PY_START (t_confirm_det3 / cr_det3) | NOT_EXERCISED; the body never ran | B4, graft 2 |
| X137 | inside G: call f, then clear styxx's local events on g's minted code (tool id from `_v5_state()`), then call g | NOT_EXERCISED for g; the message and notes contain MONITOR_LOST | E26 successor |
| X137 (free variant, subprocess) | inside G: call f, `free_tool_id(tool)`, call g; after exit, 1,000 raises in undeclared code that each unwind one frame; then a second tracer on f | first trace: PASS `{f:1, g:1}` with MONITOR_LOST on every opening, because CPython 3.12.3 and 3.13.12 keep the freed id's events and callbacks (p3). **Revision 2 (M3):** after that exit, `_v5_state()` shows `tool_ours` True and `global_events` 0, and no styxx callback runs for the 1,000 raises. Second trace: PASS `{f:1}` | E26 successor, R1-B4, M3 (rev. 2) |
| X137b (taken variant, subprocess) | as X137's free variant, but another tool takes the freed id with `use_tool_id` before g is called | first trace: PASS `{f:1, g:1}` with MONITOR_LOST; after exit the other tool still owns the id and styxx has changed none of its events or callbacks (the disclosed leak); a second tracer takes id 3 and PASS `{f:1}` | R1-B4, M3 (rev. 2) |
| X137c | inside G: call f, then `set_events(tool, 0)` on styxx's id, then call g, whose body raises and is caught inside G | NOT_EXERCISED for g (its unwind is not seen); MONITOR_LOST (a close found PY_UNWIND cleared while G was open) | M4 (rev. 2): the `UNWIND_LOST` flag |
| X138 | the id-3 tool's PY_START callback on `_v5_faultpoints()['_exit_txn']` sets Event `blocking`, then waits for Event `waiter_started`, then blocks **11 s from that moment**. The waiter thread waits on `blocking`, sets `waiter_started` immediately before entering its tracer, and records the time (revision 2, M12 and N6: the block is measured from the waiter's start, so no timing is left open) | MACHINERY_BUSY, raised in the waiter thread after it has waited at least 9.5 s (its tracer is then dead); the first trace completes; a new tracer on the waiter thread then PASS | graft, I5; upper boundary row |
| X139 | the id-3 tool, at PY_START of `_v5_faultpoints()['_enter_txn']`, runs `with coverage_trace(exp2): pass` on the same thread and records the code | the nested enter: REENTRANT; the outer trace PASS | R3-D3 |
| X140 | the round-4 py313 back-edge, made deterministic. For every JUMP_BACKWARD, and every JUMP_BACKWARD_NO_INTERRUPT, instruction in every `_v5_faultpoints()` code object (found with `dis`), one trial. The id-5 injector raises KeyboardInterrupt the first time that offset executes, in a scenario with 3 openings (one `run_async`, driven through a thrown-then-handled cancellation). Raising at the offset is the #130279 shape, since the exception-table lookup happens at the back-edge (p10 reproduces the skip this way on 3.12.3 and 3.13.12). **Revision 2 (M8).** The five callback-only functions (G_COVER's frozen list) raise no events while they run as callbacks. Their back-edge trials therefore run under the frozen direct-call driver `cover_driver_v5f.py` instead of the main scenario; `rev2/p5_cover_driver.py` shows the injector firing there. A trial whose offset never executes in its scenario is recorded UNREACHED and counts as clean. The scenario runs to completion and never waits for the offset, so no trial can hang. UNREACHED trials are listed and counted in the report | every trial is clean by G_FI's outcome rules. A back-edge in `_exit` gives TRACE_INCOMPLETE, since M5 has no loop before X1. A back-edge in `_run_async` gives that opening end `open` with OPEN_AT_EXIT. Another thread completes a trace within the watchdog; leftovers clean after the next enter | found after round 4 |
| X140f | SIGALRM floods raising KeyboardInterrupt during `cov.__exit__` with 100k suspended openings, 50 trials (timing-dependent, so an outcome set) | each trial is one of: PASS; TRACE_ACTIVE, then `__exit__()` → PASS; TRACE_INCOMPLETE. No hang; leftovers clean after the next enter | found after round 4 |
| X141 | the harness rebinds `Handle._run` to a wrapper function during the trace, and restores it after exit | CUT_MOVED | B5 |
| X141b | the harness rebinds `Handle._run` to a reimplementation inside section G, calls f, and restores it before exit (p18) | CUT_MOVED (the per-hit check) | B5 (a) |
| X141c | after `__enter__`, `BaseEventLoop._run_once` is rebound to a module-level W that runs ready callbacks without `Handle._run` and does not restore itself; section A, in a task of L, calls `L._run_once()`, whose job calls f; restored after exit | CUT_MOVED. Without the `_run_once` binding in `_cut_ok()`, f is credited to A with no refusal (`rev2/p1b_runonce_binding.py`, both versions) | M1 (rev. 2) |
| X142 | in a fresh subprocess: a second copy of `styxx.protocol` is loaded under another module name through SourceFileLoader. Copy A enters a tracer on f and keeps it open; copy B enters and exits a tracer on g; then A calls f and exits | both PASS; `_v5_state()["tool"]` is 4 for A and 3 for B; no MONITOR_LOST in A | R1-B4 (c) |
| X143 | revision 2, M4. Thread T2 opens section B and waits inside it. Thread T1 calls `cov.run('A', body)`, where body calls t and t raises inside its body; body catches it. The id-3 tool, with a local PY_RETURN event on `_v5_faultpoints()['_unwind_on']` and filtered to T1, blocks at T1's *first* return from `_unwind_on`, which is before A's anchor commit. The case then lets T2 close B, which is the last registered anchor: B's `_unwind_off()` clears PY_UNWIND and re-checks an empty `_ANCHORS`. Then it releases T1 | A PASS `{t:1}`: the opener's second `_unwind_on()` re-sets the event after its commit. Without that call, t's unwind is never seen and A refuses NOT_EXERCISED (`rev2/p14_recheck_witness.py`, both versions) | M4 (rev. 2) |

### New valid cases (expected union counts)
| id | shape | counts / property | source |
|---|---|---|---|
| V10b | a module whose `__class__` is a ModuleType subclass serves the target only through PEP 562 | `{target:1}` | E11 |
| V11c | the target sits exactly 16 hops down a foreign `functools.wraps` chain | `{target:1}` | E9 |
| V15b | outer and inner preregs both name their gate and section `'G'`, nested on one stack; variant: a case section named like the self-trace section | both `{f:1}` | E18 |
| V19b | inside a task of a running loop L, section A calls `L._run_once()`, which runs a callback that opens section B of the same tracer and calls g | B opens (no NESTED_SECTION: the cut lies between); B `{g:1}` | cut in the NESTED walk |
| V28b | coroutine section B, of the same tracer as A, is opened and driven with `send()` on a worker until it suspends, after calling g once. It is then resumed with `send()` to completion inside section A on the main thread, calling g once more. Then A calls f. No event loop is involved | A `calls {f:1}`, A `ambiguous {g:1}`; B `calls {g:1}`, B `ambiguous {g:1}`: after the hop both openings are on g's chain, which the attribution rule makes ambiguous (v5e's X70); B's end is `returned`; no notes | E23 (adapted) |
| V35 | an eager child does `await asyncio.sleep(0)`, then `cov.run_async('B', …)` | exact counts, PASS | S1 |
| V36 | a benign `gc.freeze()` inside a section, with no clone | `{f:1}` | S2 |
| V36b | before the trace: a list of 1,000 objects, then `gc.freeze()` (the count is > 0 on both versions). Inside the section: f is called once, then the list is deleted, so the count falls below its value at mint. A worker thread **enters f after `__enter__`** (revision 2, M9) and is inside f, blocked on an Event, while the tracer exits. It is released afterwards (p4, p5) | PASS `{f:1}`, no CLONE_ALIVE. A "count > 0" or "count ≠ baseline" freeze clause refuses here. A worker that entered f before the trace runs the original code, adds no reference to M_T (excess 0), and would witness neither weakening (critic2/t_v36b.py, re-run in `rev2/out_m9_v36b.txt`: excess 0 before, 1 after) | S2 (rev. 1, rev. 2) |
| V37 | a pure-Python profiler that forwards events, started inside a section | `{f:1}`; still installed after close and exit; it saw the later call | D4 |
| V38 | `@logged @Memo def fit`: `wraps` over a class-based wrapper. `Memo.__init__` calls `functools.update_wrapper(self, fn)`, so the Memo instance's own `__dict__` has `__wrapped__`; without that stamp v5f refuses FOREIGN_DEFINITION | `{fit:1}` | D5 |
| V39 | sections given as StrEnum, a `(str, Enum)` member and a numpy.str_-like subclass | PASS; record keys are exact str | D6 |
| V40 | a registry whose `__getattribute__` raises KeyError; a class whose metaclass `__getattribute__` raises | `{target:1}` each; no user side effects | D15 |
| V40b | a path step through an instance `registry` whose class has a metaclass defining a raising, counting `__eq__`; the target is `mod:registry.fit` in its own `__dict__`. Variant: fn of a section returns such an instance | `{fit:1}`; the `__eq__` counter stays 0 in both (p1) | D15 (rev. 1) |
| V41 | gates A and B both declare f, and each section calls f once | A `{f:1}`, B `{f:1}` | E6 |
| V42 | `G_fast[f]` and `G_slow[g]` share section `'run'`; one `cov.run('run', …)` calls both | both PASS | E7 |
| V43 | a gate whose section is `'harness'`, not its name | PASS | E7 |
| V44 | `cov.run('G', _run, 1)` with `def _run(cfg): return f() + cfg` | `{f:1}` | E8 |
| V45 | a method of an `abc.ABC` subclass; a method of an Enum | `{target:1}` each | E10 |
| V47 | a fork ProcessPoolExecutor inside a section, whose jobs call `COV.run('B', g)` | parent: A PASS; child jobs return their values; B SECTION_ABSENT in the parent's trace; `_v5_state()` clean | D1 |
| V48 | a pure-Python setprofile profiler installed before open (replaces X80) | `{f:1}`; profiler still installed; it saw the call | R1-B4 |
| V49 | the harness calls `sys.setprofile(None)` and `sys.settrace(None)` before the target (replaces X75) | `{f:1}`, no note | — |
| V50 | coverage.py 7.16, sysmon core and ctrace core, running across the section | `{f:1}`; coverage records the minted function's lines | graft 4 |
| V51 | a pdb/bdb settrace tracer active over the section (no `debug` command) | exact counts | graft 4 |
| V52 | (1) an explicit `cov.__exit__()` plus a second in `finally`; (2) `__exit__` in `finally` after `__enter__` raised UNRESOLVED | (1) PASS `{f:1}`. (2) `record()` refuses TRACE_INCOMPLETE (M8: `'entering'` without `'active'`), and `_v5_state()` is clean after that `__exit__`. In both, a later tracer on f PASS `{f:1}` and leftovers are clean | E22 |
| V53 | a `defaultdict` result carrying the exact-dict record | PASS | D3 |
| V54 | a target whose every call raises inside its body, caught by the harness | `{f:3}` for 3 calls (confirmed by PY_UNWIND) | graft 2 |
| V55 | `asyncio.run(cov.run_async('G', main))`, where the declared coroutine awaits once | `{coro:2}` | graft 2 |
| V57 | the case thread, which runs the `with coverage_trace` statement, installs a pure-Python profiler on itself before entering; the section runs on a worker thread the case starts | after exit, `sys.getprofile()` on the case thread is that profiler; `{f:1}`. The case removes it before returning | E21 (adapted) |
| V58 | on a case-owned thread: `cov.run('G', body)`, where body calls f then `sys.setprofile(prof)` | after run, `sys.getprofile()` is prof; `{f:1}`; no note | E20 (adapted) |
| V59 | a pure-Python profiler installed while another opening is open on the same thread (another task on the same loop), then a section opens | the open succeeds; exact counts | E24 (adapted) |
| V60 | inside G: call f, install a foreign pure-Python profiler, call g; remove it after close | `{f:1, g:1}`, no note; the profiler saw g | E26 (adapted) |
| V61 | after `coverage_trace()` and before `__enter__`, the harness rebinds `Handle._run` to a plain wrapper function **defined at a fixture module's top level** (revision 2: a function defined inside the case has `<locals>` in its qualname and refuses CUT_UNAVAILABLE, X35b) that calls the original; the trace runs a section calling f; the harness restores it after exit | PASS `{f:1}`, no CUT_MOVED: E2 adds the wrapper's code to the cut. Without E2's refresh, the per-hit check refuses CUT_MOVED | E5 (the E2 witness) |
| V62 | inside the trace, the harness rebinds `Handle._run` and restores it with no call of a declared target in between; then section G calls f | PASS `{f:1}`: CUT_MOVED needs a hit, or the exit, to see the moved binding | B5 (boundary row of the per-hit rule) |
| V63 | `cov.run('A', loop.run_until_complete, main())` with X65d's loop, where main opens `cov.run_async('B', …)` calling g | B opens without NESTED_SECTION: A's loop is None, not the running loop, so A is not visible at B's open. B `{g:1}`; A counts nothing from the loop | loop boundary in the NESTED walk |
| V64 | revision 2, N4: an outer tracer is entered; `Handle._run` is rebound to V61's module-level wrapper; an inner tracer is entered and exited (its E2 sees the wrapper); the binding is restored; then the outer's section calls f | outer PASS `{f:1}`, no CUT_MOVED. With the cut *replaced* at each E2 rather than kept monotone, the outer's hit sees the original binding outside the cut and refuses CUT_MOVED (`rev2/p1_runonce_cut.py`, both versions) | monotone cut (replaced) |
| V65 | X138 with the block set to **7 s** from the waiter's start (the lower boundary row of the busy bound; revision 2, M12) | the waiter's enter succeeds after waiting at least 6 s; both traces PASS. A bound of 0.5 s, or ×0.5 (5 s), fails here, and ×2 (20 s) fails X138 (`rev2/p12_busy_bound.py`, a model of M2's wait, both versions). 7 s rather than 5 s, so that ×0.5 is not a tie | busy bound, lower boundary row |

### New documented residuals (pinned outcome)
- **R05b.** A stub compiled with a `'<stub>'` filename is exec'd into the declared module's globals and bound before the trace. A variant installs stub code with `co_filename` forged to `mod.__file__` via `code.replace`. Outcome: PASS (deliberate only).
- **R12.** A settrace callback runs T on a section's stack through `sys.call_tracing` (pdb `debug`). Outcome: PASS, credited. The same callback calling T directly: not credited (NOT_EXERCISED).
- **R13.** A sibling cache wrapper of the declared wrapper's body, held in another module, is called. The declared wrapper is never called. Outcome: PASS.
- **R14.** A generator object of the declared generator function is created before the trace and resumed inside a section. Outcome: NOT_EXERCISED.
- **R16.** The id-3 tool raises at the target's PY_RETURN. Outcome: the caller sees that exception, and the call is counted `{f:1}` because its body ran (the L-DELIVERY shape).
- **R17 (retired in revision 2).** The shape is now violation case X65g: its dispatch passes a `BaseEventLoop._run_once` frame. That is a residual outcome changing before any prereg, so no prereg is affected.
- **R18 (revision 2).** Two variants. (a) A `SelectorEventLoop` subclass whose own `_run_once` runs ready callbacks through `map(operator.call, …)` (X65d's loop) runs `main`. In a task of it, section A calls `loop._run_once()`, which runs a job another task scheduled with `call_soon(f)`. (b) The stdlib loop, where the harness, after `__enter__`, rebinds `BaseEventLoop._run_once` to a module-level W that first restores the original binding and then runs the ready callbacks without `Handle._run`. Outcome of both: PASS, credited to A. No cut frame lies between f and A's anchor; the running loop is `A.loop`; and no hit or exit sees a moved binding (`rev2/p1_runonce_cut.py`, both versions; deliberate only; L-WHERE).

A residual whose outcome changes is a spec change and needs a new prereg.

### The exam-hole kill cases, from each verifier's `exam_case_that_would_kill_it`
Each row quotes the verifier's shape. The v5f case implements it, adapted where the rule is retired.

| key | verifier's kill shape (abridged verbatim) | v5f case |
|---|---|---|
| exam-mut-section-decl-clauses | "two frozen violation cases, both expecting SECTION_DECL: `section: ""`, and a confusable `section: "sеction"`" | X07b, X07c |
| examhole-clone-alive-single-tracer | "Nested tracers on f whose inner section calls only a same-globals clone … kept alive past the inner exit and dropped before the outer exit, … inner trace expected to refuse CLONE_ALIVE" | X57c |
| examhole-clone-called-first-tracer | "FunctionType(f.__code__, {})() runs while both tracers hold the mint … the inner tracer expected to refuse CLONE_CALLED as well as the outer" | X55d |
| examhole-code-swapped-single-tracer | "inner section calls f and then sets f.__code__ to other code, left in place through the inner exit … inner trace expected to refuse CODE_SWAPPED" | X59c |
| examhole-stop-read-before-mint | "A gate that declares asyncio.events:Handle._run and f … or simply assert P._STOP is asyncio.events.Handle._run.__code__ during the trace" | X34 (declaring it is now RESERVED_TARGET) and `cut_current` asserted in every case |
| examhole-union-over-all-sections | "gate A declares f and gate B declares g, section A runs only g and section B runs f … expecting A to refuse NOT_EXERCISED; … two gates both declare f … union {f:1} per gate" | X120, V41 |
| examhole-declared-section-field-never-scored | "two gates sharing a declared section … or one gate whose section differs from its name … cross-named violation case" | V42, V43, X121, X78g |
| examhole-dispatch-cut-by-name | "cov.run("G", _run, 1) with `def _run(cfg): return f() + cfg`, expecting PASS {f:1}" | V44 |
| examhole-walk-bound-2-hops | "a target that sits exactly 16 hops down a foreign functools.wraps chain (paired with X30b's 17), expecting PASS" | V11c + X30b |
| examhole-class-step-exact-type | "a method of an abc.ABC subclass (and one of an Enum) … PASS …, plus … an inherited method of an ABC subclass … INHERITED" | V45, X14b |
| examhole-module-step-exact-type | "sets `sys.modules[__name__].__class__` to a types.ModuleType subclass and serves the target only through PEP 562 … PASS …; an X16 variant … INSTANCE_PATH" | V10b, X16b |
| examhole-inherited-direct-base-only | "Leaf(Mid(Base)).fit … or Model(LoggingMixin, Base).fit … INHERITED rather than UNRESOLVED" | X14c |
| examhole-cache-body-module-check | "Scorer.fast = lru_cache(None)(_impl), bare or as a staticmethod … _impl bound at module level, or a wrapper served only through PEP 562 … NOT_A_FUNCTION" | X25c, X25d |
| exam-hole-coverage-on-failing-bar | "a declaring gate whose bar fails (m=0.0) … never calls one declared target (and a second run with a swallowed NESTED_SECTION)" | X122, X122b |
| exam-hole-score-step-order | "a valid trace with 'gates_sha256' popped must refuse BAD_TRACE, not raise KeyError … swallows cov.run('G_typo', f) … UNDECLARED_SECTION, not SECTION_ABSENT" | X96c, X78e |
| exam-hole-diagnostic-texts | "On X72's trace … "dispatched {'<fx>:f': 2}, unattributed {}" … check_metrics … usable False and a note starting with [V5:NOT_EXERCISED]" | X72b |
| exam-mut-stop-cleared-by-inner-exit | "V15's shape … then X65's shape in the outer tracer … A must refuse NOT_EXERCISED with dispatched {f:n}" | X65b |
| exam-mut-nested-by-section-name | "outer and inner prereg both name their gate/section 'G', nested on one stack, requiring both to PASS with {f:1}" | V15b |
| exam-mut-restore-over-swapped-code | "after the trace exits and before its own finally restores the code, … mod.f59.__code__ is still mod.u59.__code__ (f59() returns -59)" | X59d |
| exam-mut-close-removes-foreign-profiler | "cov.run('G', body), where body calls f and then sys.setprofile(prof); … require sys.getprofile() is prof (and the PROFILER_LOST note)" | V58 (adapted: prof kept, and no note because PROFILER_LOST is retired) |
| exam-mut-exit-removes-foreign-profiler | "a pure-Python profiler is installed on the main thread before `with coverage_trace(exp)`, the section runs on a worker thread, and after the exit … sys.getprofile() is that profiler" | V57 (adapted: the case thread plays the main thread's part, because `sys.setprofile` is per-thread and cases run on their own threads; no `_ACTIVE==0` branch exists) |
| exam-mut-double-exit-state-leak | "exits one tracer twice … or calls __exit__ in a finally after __enter__ raised UNRESOLVED, expecting PASS {f:1} … a later trace still passes" | V52 |
| exam-mut-hop-close-drops-closer-hook | "resume section B (opened and suspended on a worker thread) to completion inside section A on the main thread, then call A's target, expecting A {f:1} with no PROFILER_LOST and B's THREAD_HOP note" | V28b (adapted: THREAD_HOP is retired, so no notes. B's post-hop calls are ambiguous, not counted, because both openings are on the chain) |
| exam-mut-foreign-profiler-first-open-only | "installs a pure-Python profiler while another opening is open on the same thread … then opens a section, expecting [V5:FOREIGN_PROFILER]" | V59 (adapted: FOREIGN_PROFILER is retired; the open succeeds with exact counts) |
| exam-mut-target-set-before-stale | "An X109 variant whose second gates block also adds a declared target … expecting [V5:STALE_TRACE]" | X109b |
| exam-mut-profiler-lost-only-if-none | "Inside section G, call f, then install a pure-Python foreign profiler …, then call g … Expect … PROFILER_LOST and the NOT_EXERCISED message for g to name it" | V60 (adapted) + X137 (the MONITOR_LOST successor) |
| exam-mut-bad-trace-end-type | "replace that opening's end with a str subclass equal to 'returned' … Expect BAD_TRACE" | X103c |
| exam-mut-problems-before-bad-count | "a trace that carries a genuine recorded problem … set one calls count to 0. Expect BAD_COUNT" | X112b |
| exam-mut-uncredited-last-thread-wins | "Two threads … each dispatch g once through their own event loop's call_soon. Expect … {g: 2}, and the NOT_EXERCISED message … to print 2" | X123 |

### Hazard sweeps (main thread, before the self-trace), each paired with a detection mutant
Every detection mutant below is an SM1 row. It is a frozen text patch against `ref_v5f.py`, run at freeze time, so the sweep's power is shown before the implementation exists. On the implementation the sweeps run unmutated (G_FI, G_SIG); mutants of the implementation come from SM2.

- **H1 (finalizers).** Cyclic garbage whose `__del__` either calls a target or enters and exits a tracer. Gen-0 thresholds 1–40 are swept at `_open`, `_detach`, `record`, the callbacks, `_enter` and `_exit`, with a 10 s watchdog. Expected: no hang, and no problem other than REENTRANT from the tracer-entering finalizer. **Mutant:** the robust mutex replaced by `threading.Lock`. The sweep must detect a hang.
- **H2 (SIGALRM).** `Timeout(Exception)` in a tight traced loop after a target call, 20 trials. Expected: 20/20 propagated and 20/20 PASS. **Mutant:** the callbacks wrapped in `except Exception`. Propagation must drop below 20/20.
- **H3 (KeyboardInterrupt).** Raised from a signal, 5/5. Expected: it propagates, and `_v5_state()` is clean after exit.
- **H4 (performance).** Reported, not gated: the Cost table re-measured.
- **H5 (gc cost).** No gc at resolution or close. The exit scan is refcount-gated.
- **H6 (no-hang fault sweep, the deterministic core of G_FI).** For every code object in `_v5_faultpoints()`, the id-5 injector raises at each executed instruction, one point per run. Expected: another thread completes a trace within 5 s, and invariants C1–C8 hold. **Mutants** (SM1 rows, witnesses as listed there): M1 (`with RLock`) must hang; M2–M7 must be detected. M8 (per-thread counters) is retired with `_TH`.
- **H7 (user locks).** A `with lock:` loop inside a section under SIGALRM for 30 s per version. Expected: 0 harness locks left held and 0 hangs. **Mutant:** a setprofile-based event source (v5e's hook). It must leak more than 0.
- **H8 (body-less credit).** A SIGALRM flood with one section per call, each call counting its body runs. Expected: credited ≤ body runs, on both versions. **Mutant:** publish at entry. Detected on 3.12 (D3 p3: 181 in 8 s). On 3.13 the same mutant is killed by X135.
- **H9.** The back-edge cases X140 (deterministic) and X140f (flood), run on the main thread. **Mutant** (an SM1 row): `ref_v5f.py`'s X3 detach loop placed inside `with _M:`, where `_M` is a `threading.Lock` that `_exit_txn` also takes (v5e's shape). X140 must detect it on both versions: the exception raised at the back-edge offset skips the with-exit (p10), and another thread's exit then hangs.
- **H10 (L-DELIVERY; revision 2, M4).** G_SIG's three frozen L-DELIVERY cells (Stated limits): (a) outside every section with a trace active, 0 lost handlers; (b) inside a section, reported; (c) `with`/`finally` inside a section, 0 skipped. **Mutant** (an SM1 row): PY_UNWIND set at mint time and cleared at retire (revision 1's scope). Cell (a) must detect it: `rev2/p4_unwind_scope.py` measured 171,683 (3.12.3) and 121,297 (3.13.12) lost handlers under that scope, against 0.

### Mutation audit (every rule has a mutant; each is killed by the named case)
| rule deleted or weakened | cases that fail |
|---|---|
| minting / `is` vs `==` / `f_globals` check | X40–X44 / X45, X46 / X55, X56 |
| CLONE_ALIVE; its freeze clause; "count > 0" or "count ≠ baseline" instead of "count > baseline" | X57, X58 / X57b, X58b / V36b |
| per-holder CLONE_CALLED / CLONE_ALIVE / CODE_SWAPPED | X55d / X57c / X59c |
| CODE_SWAPPED at exit / at entry / restore over a swap | X59 / X31 / X59d |
| entry CODE_SWAPPED against a holderless mint (reconciliation dropped) | X92b |
| coherence on F_T / on intermediate links / module `__file__` rule / sourceless rule | X26b, X26c / X26d / X26e / X26f |
| FOREIGN_DEFINITION by `__module__` / without the chain / walk only through functions / hop bound 3, 16 or 18 | X30 / V11, V06 / V38 / V11c, X30b |
| cache callee identity / bound-body check / sibling check / alias-by-object rule | X24b, X24c / X25, X25c, X25d / X24e / X24d |
| PEP 562 twice / exact type for module step / class step / full-MRO INHERITED | X13b / V10b / V45, X14b / X14c |
| descriptor-only reads (isinstance or getattr reintroduced) / an `is` chain replaced by tuple membership | V40, X17b / V40b |
| RESERVED_TARGET / cut by identity (by name) / monotone cut cleared / monotone cut replaced at each E2 / CUT_MOVED at exit / CUT_MOVED at a hit / E2's refresh / CUT_UNAVAILABLE | X34, X34b, X34c / V44 / X65b (through CUT_MOVED, the second critic's A4) / V64 (revision 2, N4) / X141 / X141b / V61 / X35 |
| `_run_once` code in the cut (revision 2) / `_run_once` binding in `_cut_ok()` / shareable-code refusal: `<locals>` clause / gc-referrer clause | X65e, X65f, X65g / X141c / X35b / X35c |
| unwind scope: PY_UNWIND per section rather than per mint / the re-check after the anchor commit / `UNWIND_LOST` at close / reclaim of a freed, unowned id / at-fork order (restores last) / pass-through by `os.getpid()` | H10 (a) / X143 / X137c / X137 free variant / G_FI fork scenario (C9) / G_FI fork scenario (C9) |
| the busy bound 10 s: raised, lowered | X138 / V65 |
| dispatch cut in attribution / in the NESTED walk | X65c / V19b |
| loop boundary in attribution / in the NESTED walk | X65d / V63 |
| tool adopted by the bare name `styxx.protocol` / events changed on an id that lost its name | X142 / X137 (free variant) |
| confirmation deleted (publish at entry) / unwind-offset check deleted / PY_THROW credited | X135, H8 / X135 / X119 |
| credit re-check at publication deleted | X71 |
| exactly-one-opening-per-tracer / NESTED by name or across tracers | X70 / V15b |
| union over the declared section only / declared section, not gate name | X120, V41 / V42, V43, X121, X78g |
| emptying `by_code` at exit / recording open-time refusals / score reads problems | X71c / X76, X78–X79, X32 / X55–X59 |
| atomic enter claim replaced by check-then-set / exit claim replaced by an unconditional store | X32d / V52 |
| reconciliation deleted / holder-after-install / register-after-events | X92b, X133 / G_FI (M2, M6) |
| at-fork handler / pid pass-through | V47 |
| section normalization / non-str refusal | V39 / X78f |
| exact type before hash in BAD_TRACE (`end`, `gates_sha256`, tracer) | X103b, X103c, X96c, X96d |
| score step order (each adjacent pair) | X109b, X112b, X96c, X78e, X122 |
| NO_TRACE dict-subclass rule / split text | V53 / X93d |
| check_metrics overflow / smoke exact type / smoke note | X117b / X117c / X117d |
| NOT_EXERCISED bucket labels | X72b |
| TRACE_ACTIVE / TRACE_INCOMPLETE | X90, X91, X92c / X92, X133, V52 |
| MONITOR_BUSY / MONITOR_LOST / REENTRANT / MACHINERY_BUSY | X36 / X137 / X139, H1 / X138 |
| no handler in the callbacks / no lock anywhere | H2 / H1, H6 |
| each BAD_TRACE and BAD_COUNT clause | X96–X115, X103b, X103c, X105d |
| LAZY_RESULT exact type and text / NESTED_SECTION text | X74–X74d / X76b |
| SECTION_DECL non-empty / ASCII clauses | X07b / X07c |

---

## The semantic-mutation gate (G_SEM), frozen before implementation, decided by execution

**Goal.** Show that the v5f exam detects *weakened* rules, not only deleted refusals. Round 4 found this was not so for v5e: 57/57 deletions were detected, but only 27/63 hand-aimed weakenings, and 29 of the survivors were witnessed exam holes. Equivalence is decided mechanically or by a written argument signed before the freeze, and never by a reviewer after it.

**Objectivity rule (revision 1).** Every quantity the gate reads is computed by a frozen script from frozen inputs: the catalog, the corpus, the seeds, N and the list of spec-fixed substrings. No step after the freeze asks a person to judge anything: not whether a mutant is equivalent, whether a line is reachable, which window a fault fell in, or which observables count.

### Frozen artifacts
The v5f prereg lists `FROZEN_*_SHA256` for each artifact below. All are written by the exam author, who is independent of the implementer (G_INDEP).
- **The exam runner.**
- **`ref_v5f.py`.** The reference model: an executable spec written **from this document's text alone**. The author attests they did not read `crashcons/v5f_core.py`, `monitor/v5f_region.py` or `narrow/proto`.
- **`rules_v5f.json`.** Every normative sentence of this spec as a rule atom with an id, including each crash-consistency ordering and claim (M1–M9, I1–I6).
- **`weakenings_v5f.py`** (the SM1 catalog). Each entry is an exact-once text patch against `ref_v5f.py` and carries: rule id, operator family, the NAMED witness case id, the witness's spec outcome, its weakened outcome, and the versions it applies to.
- **`opmut_v5f.py`.** The SM2 operator generator for the real implementation.
- **`diffprobe_v5f.py`.** The differential probe, its normalizer and its noise-mask procedure.
- **`corpus_v5f/`.** The differential-probe corpus, written by the exam author before the freeze. It holds:
  - every exam case program;
  - the fuzzer's programs for its frozen seeds;
  - the crash sweep's points;
  - the round 1–4 repros, rewritten by the exam author against the public API from `protocol_v5_redteam/round1_module/` through `round4/` and `round4/closure-audit/r1/held_battery.py`.

  Each file is hashed in the prereg. Nothing is added after the freeze.
- **`corpus_v5f/manifest.json`** (revision 2, M5). It marks every corpus entry with exactly one comparison class, assigned by a frozen rule from the entry's source and never by judgement:
  - **`envelope`**: every entry that injects a fault or depends on timing. That is every crash-sweep point; every exam case that uses the id-3 fault tool, the id-5 injector, a signal, `PyThreadState_SetAsyncExc`, a finalizer threshold or a thread race (X71c, X92b, X92c, X131–X133, X135, X138, X139, X140, X140f, X143, V65, R16, the H sweeps and every G_SIG cell); and every fuzzer program whose grammar path includes a fault tool.
  - **`equality`**: every other entry.

  At freeze time the manifest is validated on `ref_v5f.py`. Each `equality` entry is run N = 5 times per version and must give identical spec-fixed observables. An entry that fails this is an exam-author error, fixed before the freeze by reclassifying it under the rule's own terms: it names a timing dependency the rule missed, and the rule is amended.
- **`cover_driver_v5f.py`** (revision 2, BF1). The direct-call coverage driver for the callback-only functions (G_COVER).
- **`traces_v5f/`.** The prebuilt `/3` traces for the scoring-only cases, generated by `ref_v5f.py` on 3.12 at freeze time.
- **`crash_sweep_v5f.py`.** The lab's `fault_injection_v5.py` and D1's `t_crash_sweep.py` merged and ported to the v5f interfaces. It holds the fault injector (sys.monitoring INSTRUCTION events, tool id 5, targets from `_v5_faultpoints()`), invariants C1–C8, the background-tracer variant, and the two-thread, `run_async`, generator-target and hopped-coroutine scenarios.
- **`fuzz_v5f.py`.** The oracle fuzzer. Its grammar covers nested tracers, shared and cross-named sections, clones, swaps, generator `throw()`/`close()`, cross-thread coroutine sections, `gc.freeze`, raising targets and lower-id fault tools.
- **`sigflood_v5f.py`.** G_SIG: user-lock leaks, hangs, poison, wrong results, and credited ≤ body runs.
- **`refcensus_v5f.py`.** G_REF (refusal deletion by coded literal) and G_HYG (hygiene and back-edge lint).
- **`controls_v5f.py`.** The positive controls.
- **`sm1_result.json`.** Computed at freeze time on `ref_v5f.py`. It is included in the freeze commit.

### SM1: catalog power, computed at freeze time on the reference only
**Admission (mechanical).** A weakening W is *admitted* on a version iff all three hold:
1. its patch applies exactly once;
2. its named witness scores the spec outcome on unpatched `ref_v5f.py`;
3. under `ref_v5f.py` + W, the witness's observable outcome differs from the spec outcome on that version.

**Isolation (D2).** An admitted W counts as **KILLED** only if its **named** witness fails on ref+W in the exam's mutation mode, whether by a wrong outcome, a crash or a timeout. If only some other case fails, the row is **WITNESS_MISMATCH** and counts as not killed. The fix is a better-isolating witness, before the freeze.

**Unwitnessed rows.** A row failing condition 3 is **UNWITNESSED**. Before the freeze, the exam author must do one of two things for every UNWITNESSED row:
- write a witness that satisfies condition 3, then re-run admission; or
- file it as **EQUIVALENT_BY_SPEC**, with a written argument that no harness can observe the difference under this spec. The argument is signed by a reviewer who is neither the exam author nor the implementer.

After the freeze, nothing is reclassified. A surviving admitted row fails G_SEM, and the only remedy is a new prereg with a new exam.

**Worked example.** D1's M9, "claim after cleanup", is envelope-equivalent. Its faulted outputs stay inside I6. It is filed as EQUIVALENT_BY_SPEC with the I6 argument, and it is also the control that SM2's envelope comparison must *not* flag.

**Gate.** Both must hold:
- `ref_v5f.py` passes the exam on 3.12 and 3.13;
- 100% of admitted rows are KILLED by their named witness on every version they are admitted for.

**Required catalog content:**
- every row of the Mutation-audit table above;
- all 63 round-4 census mutants (`protocol_v5_redteam/round4_exam_mutation/mutants.py`). Their classification is fixed here, by id, so nothing is decided by reading code:
  - **RETIRED (15).** Their site belongs to a v5e mechanism that "What is removed from v5e" deletes:
    - C01, C02, C04, C05, C06 and C08: the profile hook's close and hop handling, PROFILER_LOST, and `_THREADS` counts;
    - E04: the `_STOP` reset, replaced by the monotone cut;
    - E07: exit removing a foreign profiler;
    - H01, H02 and H03: the hook's self-removal and its `call`-event filter;
    - O03: install epochs;
    - O05 and O08: FOREIGN_PROFILER;
    - O06: the `_THREADS` count at open.

    Their successor behaviour is pinned by V37, V57–V60 and X65b instead.
  - **ADOPTED (1).** P03 "walk any type" is v5f's rule (Provenance (b)), so its patch has no site. The successor weakening, "walk only through functions", is a row (V38).
  - **RE-TARGETED (47).** Every other id. The exam author writes each as a patch against `ref_v5f.py` that weakens the same rule, with a named witness. P04 "no cycle detection" is expected UNWITNESSED: the walk is bounded at 16 hops and a revisited link repeats its own verdict, so the outcome cannot change. The exam author either finds a witness or files it EQUIVALENT_BY_SPEC with that argument, before the freeze. Cycle detection stays in the spec as a cost bound;
- the 29 round-4 exam-hole kill shapes, each as a row whose named witness is its v5f case;
- D1's crash-consistency weakenings, re-targeted to `ref_v5f.py`. A crash-sweep row's named witness is one invariant check of `crash_sweep_v5f.py`. The row is KILLED only if that invariant is among the sweep's failures; if only other invariants fail, it is WITNESS_MISMATCH:
  - M1 plain RLock → C3 (hang);
  - M2 no reconciliation → C7;
  - M3 register before append → C5 (anchors left);
  - M4 entering token always live → C7;
  - M5 exit claim not idempotent → C5 (openings left);
  - M6 install before register → C5 (code not restored);
  - M7 exiting token always live → C7;
  - M10 credit stop after detach → X71c;
  - M8 (per-thread counters) is RETIRED with `_TH`; M9 is filed as above;
- the confirmation weakenings, each with its named witness: publish at entry (X135); unwind-offset check deleted (X135); PY_THROW credited (X119); publication re-check deleted (X71); pending entry keyed without frame identity (UNWITNESSED unless a witness is found; filed with an argument if not);
- coherence weakenings: F_T exempt (X26b); intermediate links exempt (X26d); `'<'` skip widened to "no `__file__`" (X26e); sourceless accepted (X26f);
- freeze: "count > 0" or "count ≠ baseline" instead of "count > baseline" (V36b); visible accounting deleted (X58b);
- cut and loop: CUT_MOVED only at exit (X141b); E2's refresh deleted (V61); loop boundary deleted in attribution (X65d) or in the NESTED walk (V63); `is` chain replaced by tuple membership (V40b);
- revision 2: `_run_once` dropped from the cut (X65g); its binding dropped from `_cut_ok()` (X141c); cut replaced at each E2 (V64); either shareable-code clause deleted (X35b, X35c); PY_UNWIND back to mint scope (H10); `UNWIND_LOST` deleted (X137c); reclaim deleted (X137 free variant); at-fork restores moved first, or pass-through by a cached pid (G_FI fork scenario, C9);
- the hazard-sweep detection mutants H1, H2, H6 (M1–M7), H7, H8 and H9, with the sweep as the named witness;
- one weakening per operator family below, inside each rule-tagged region of `ref_v5f.py`;
- boundary rows on both sides of every quantitative rule: 16 hops accepted (V11c) and 17 refused (X30b); the 10 s busy bound, 11 s refused MACHINERY_BUSY (X138) and 7 s accepted (V65), both measured from the waiter's start (revision 2, M12). `_BUSY_SECONDS` is a float, which O7 (int ±1) never touches. So SM1 carries explicit rows for 0.5 s, ×0.5 and ×2, and SM2 gains operator O7b.

### SM2: operator mutants on the real implementation (the procedure is frozen; the mutants depend on the code)
**Region.** Defined by name, not by a marker the implementer places. It is the code objects of the frozen `_v5_faultpoints()` functions (M10), plus `Experiment._check_coverage`, `check_metrics`, `score` and `_check_trace_shape`, plus the module-level statements that bind the M1 names. G_HYG checks that `styxx/protocol.py` defines no function or class outside this set and the v4-era set. The v4-era set is listed by name in the prereg at freeze time, from the base commit.

**Operators,** applied mechanically at every applicable site. These are D1's O1–O14 plus D3's generic families:

| family | operators |
|---|---|
| deletion | O1 delete a statement; O13 refusal deletion by coded literal (any string constant or f-string part containing `[V5:` → its innermost enclosing statement becomes `pass`) |
| conditions | O2 negate a test; O3 drop one operand of and/or; IF: a test replaced by True / False; QUANT any↔all |
| comparisons | O4 `is`↔`==`, `is not`↔`!=`; CMP `==`↔`!=`, `<`↔`<=`, `>`↔`>=`; O6 `in`↔`not in` |
| types | O5 exact type ↔ `isinstance`/`issubclass`, both directions |
| constants | O7 every int constant ±1; O7b every float constant ×0.5 and ×2 (revision 2, M12: `_BUSY_SECONDS` and the 0.2 ms retry sleep are floats) |
| order | O8/SWAP: swap adjacent simple statements; O14 swap two sequential `if …: raise GateSpecError` blocks |
| claims | O9 `d.setdefault(k, v) is v` → unconditional store |
| scope | O10/ITER: `for x in seq` → `seq[:1]` / `seq[-1:]`; SLICE `[a:]` → `[a:a+1]`; O11 delete a `break` |
| immutability | O12 tuple rebuild → in-place mutation |

**TCE.** A mutant whose compiled module is byte-identical (bytecode, names, consts, recursively) to the original is equivalent by construction and is not run.

**Instruments,** in order, stopping at the first that detects the mutant:
- (a) the frozen exam in mutation mode;
- (b) the frozen crash sweep with a frozen stride;
- (c) the frozen fuzzer with frozen seeds and N;
- (d) the differential probe: the mutant against the unmutated implementation over the frozen `corpus_v5f/`.

**The normalizer compares only spec-fixed observables.** This list is closed:
- refusal codes, and exactly these message substrings:
  - the leading `[V5:CODE]`;
  - the NOT_EXERCISED fixed sentence (M11);
  - the `dispatched {…}, unattributed {…}` labels with their dict renderings;
  - the two NESTED_SECTION texts;
  - the LAZY_RESULT text and its "(its body had not started)" suffix;
  - the three NO_TRACE wordings;
  - "int too large for a float";
  - the TRACE_ACTIVE texts of M8;
  - for NOT_A_FUNCTION, FOREIGN_DEFINITION, INHERITED, INSTANCE_PATH and UNRESOLVED, the `module:qualname` (or `'<module>:<name>.__wrapped__'`) that this spec says the message names, as `ref_v5f.py` computes it for the same program;
- counts, ends, note codes and problem codes;
- `check_metrics` `present`/`usable` and each note's leading code;
- `_v5_state()` fields;
- fixture `__code__` identity;
- `sys.getprofile()`/`gettrace()` identity;
- styxx's tool ownership and the fixtures' local events.

Free-form message text, addresses, paths and timings are not compared. The **noise mask** is computed over the manifest's `equality` entries only. It masks a field iff the field differs between any two of exactly N = 5 unmutated runs on that version, run in the frozen corpus order with the frozen seeds. The mask is computed once, recorded and reported. If it masks any refusal code, count, end, note code or problem code, the baseline is unclean and G_SEM fails: the spec fixes those, so they must not vary.

**`envelope` entries** (revision 2, M5: "faulted" is now defined by the manifest) are never compared for equality. Each mutant output is checked against the entry's frozen acceptance predicate:
- for an injected fault, envelope I6 computed from the unmutated fault-free run of the same program;
- for a timing-dependent case, the outcome set or gate predicate the exam states for that case (X140f's three outcomes, X71c's landing rule, the G_SIG gates).

A mutant is flagged iff its output falls outside the predicate on some run. Nothing about an entry's class is decided after the freeze.

**Classification:**
- **KILLED:** (a), (b) or (c) detects it, or the mutant does not import;
- **EXAM_HOLE:** only (d) sees a spec-fixed difference;
- **UNDISTINGUISHED:** nothing does. It is counted and listed with its site and diff. No one judges whether it is equivalent, before or after the freeze, and it is not gated (judge 1). The shipping claim states the count and says that G_SEM certifies nothing about these mutants. Round 5 may attack them like any other code; a finding there is an ordinary red-team finding, not a reclassification. D3's "≤3%" cap is not adopted: both judges rejected it.

**Gate.** All of:
- EXAM_HOLE = 0 on 3.12 and 3.13;
- a clean baseline (every instrument passes the unmutated implementation);
- at least one applied mutant per family;
- G_REF: 100% of O13 mutants KILLED, and the literal census finds 0 coded literals outside a mutable site.

KILLED, UNDISTINGUISHED and TCE counts are reported per family.

### SM3 (aux, carried): the independent second implementation
- It comes from a different author **and** model family than the implementer. Round 4 showed correlated failure: the N-version implementation reproduced all 6 blockers (`round4/blockers_against_nversion.json`).
- It passes the frozen exam, matches the oracle fuzzer, and gives identical normalized traces on 3.12 and 3.13.
- Every round 1–4 blocker repro is replayed against both implementations, and none may reproduce.

### Positive controls (frozen; run before any v5f scoring; each must come out as stated, or G_SEM is void)
1. **SM1 on v5e.** SM1's admission and kill machinery is run on v5e's frozen exam with the 63 census mutants applied to v5e unchanged. For this control only, any failing case counts as a witness. There are no named witnesses, so SM1's admission conditions 2 and 3 are replaced by condition 1 alone, and the only classes are **KILLED** (some v5e exam case fails) and **SURVIVED** (none does). UNWITNESSED and WITNESS_MISMATCH do not arise (revision 2, N10). The control passes iff exactly the other 27 census mutants are KILLED and these 36 are SURVIVED, matching `semantic_mutation_census.json` (63 applied, 27 detected, 36 survived): B01, C01, C02, C06, D01, D02, E01, E04, E05, E07, E09, E11, H01, H12, H15, K01, O05, O07, O08, P01, P02, P03, P04, R01, R02, R03, S01, S02, S03, S07, S08, S10, S15, SC1, SC2, T01.
2. **SM2 on v5e.** SM2's generator, run on v5e, with instruments (a) and (d) only, must report EXAM_HOLE > 0 (revision 2, M11):
   - (a) is v5e's own frozen exam;
   - (d) is the differential probe over the corpus programs that use only the public API v5e shares with v5f.

   Instrument (b), the crash sweep, is excluded because control #3 requires it to find v5e unclean. Instrument (c), the fuzzer, is excluded because its oracle is `ref_v5f.py`, which v5e is not meant to match. SM2's clean-baseline condition applies to (a) and (d) only. v5e passes its own exam, and (d)'s mask is built from five unmutated v5e runs. On v5e the normalizer omits the `_v5_state()` fields and tool ownership, which v5e does not have, and compares every other listed observable. D3's 240-mutant sample let 83 survive, the witnessed holes among them.
3. **Crash sweep on v5e.** The frozen `crash_sweep_v5f.py` is run against v5e through `controls_v5f.py`'s v5e adapter. The adapter supplies the fault points (`_CoverageTracer.__enter__`, `__exit__`, `_open`, `_close`, `run`, `record`, `_hook` and `_resolve_target`) and v5e's registries for C5 and C7. It must report at least one non-clean point on 3.12 and on 3.13. The committed results of `fault_injection_v5.py`, which the sweep extends, are cited for reference only: on 3.12, 2393 of 9369 points not clean, 132 of them HANG; on 3.13, 2041 of 8604 not clean, 127 HANG. D1's M1–M7 are SM1 rows (above), not a control.
4. **G_SIG on v5e.** G_SIG must show v5e leaking on 3.12 and 3.13 (D3 sig_sweep: 2521 and 2265 leaks), and H8's publish-at-entry mutant must fail on 3.12.
5. **G_REF blind shapes.** A planted blind-shape emission must be caught by G_HYG, for each of the 8 shapes in `mutation_gate_blindspots.json`.

### Companion gates
- **G_FI (crash sweep, frozen).** Required on 3.12 and 3.13, on two threads: every fault point is **clean**. Clean is defined by outcome alone, so no window has to be mapped to implementation offsets. A point is clean iff all five hold:
  - (a) no hang: another thread completes a trace within 5 s;
  - (b) C1–C8 hold after the next reconciliation;
  - (c) the faulted trace's `record()` is within I6, or refuses TRACE_INCOMPLETE or TRACE_ACTIVE;
  - (d) if it refuses TRACE_ACTIVE, one more `__exit__()` yields a record within I6, and leftovers are clean;
  - (e) the injected exception reached the caller of the facade call it was injected under, unchanged, or `__enter__` raised UNRESOLVED with `__cause__` being the injected exception.

  **Scenarios added in revision 2:**
  - *Fork (N5).* A trace with a mint, an open section and a pending entry forks. In the child, the injector faults `_forget_in_child` at each of its instructions in turn, and an audit hook refusing `__code__` writes is a second variant. Invariant **C9** is checked in the child and reported to the parent through a pipe. In the child, `run()` passes through, whatever prefix of the handler ran. After the child's next transaction, `_v5_state()` shows no anchors, no registered mints and `global_events` 0. Every function's `__code__` is its original or an equal M_T with no local events. The parent's own trace is unaffected.
  - *Callback-only functions (BF1, M8).* The injector faults the five callback-only functions at each instruction while the direct-call driver runs them. Clean means (a)–(c), and the driver's own trace counts ≤ its fault-free counts.
  - *Injector rules.* The Exam harness rules apply: code read at arming, a thread filter on a live ident, no settrace, `restart_events()` before each trial, and a self-check. A trial that never fires is UNREACHED, counts as clean, and is reported.
- **G_SIG (signal floods, frozen, 60 s per cell per version).** Required: 0 user-lock leaks, 0 hangs, 0 poison, 0 wrong results, and credited ≤ body runs. Revision 2 (M4) freezes what "wrong result" means:
  - a skipped `with`/`finally` cleanup;
  - a result value that differs on an iteration in which no asynchronous exception was delivered;
  - a later trace whose record differs from its fault-free record.

  An `except E:` handler that did not start because an asynchronous exception replaced E inside the unwind callback is L-DELIVERY, not a wrong result. It is measured in the three L-DELIVERY cells (H10), and cell (a), outside every section, is gated at 0.
- **G_HYG (static).** These must hold:
  - 0 coded emissions in a blind shape;
  - no `with` statement, no `threading` lock and no `try … finally` in the v5 region, except `_run`/`_run_async`'s single `try/finally`;
  - no loop in any `try` body (CPython #130279). The one allowed `await` is `_run_async`'s, as the whole try body besides assignments;
  - no `except` in the region other than the two chained user-code sites and `_exit`'s two `except GateSpecError` clauses around `_locked`. In the scoring functions, the only ones allowed are check_metrics' existing `except GateSpecError` report loops and `except OverflowError` (`_finite` and score's metric guard);
  - no `import` statement and no `importlib`/`__import__` call in the region, except `_resolve_target`'s single `importlib.import_module(module)` and `coverage_trace`'s `import asyncio`;
  - no type test by tuple membership (`type(x) in (…)`, `in _LAZY_TYPES`) in the region;
  - no `sys.monitoring` event other than PY_START, PY_RESUME, PY_RETURN, PY_YIELD and PY_UNWIND is named in the region;
  - the region's function and class names are exactly the frozen set (SM2 Region);
  - (revision 2) `_forget_in_child` writes `__code__` only in its last loop, after every registry and event step; `_open` calls `_unwind_on()` both before and after its anchor store; `_detach` calls `_unwind_off()` after its anchor pop;
  - (revision 2) every M1 state name except the four constants is bound through `globals().get` (N8).
- **G_COVER.** Every executable line of the region runs in at least one of four instruments. No pragma exempts a line. A line that none of them reaches is dead code and must be deleted, or folded onto its guard's line.
  - **Instruments:** the exam's fast mode, the frozen crash sweep, the frozen fuzzer, and, for the named functions below only, the frozen direct-call driver `cover_driver_v5f.py`.
  - **The named list (revision 2, BF1), frozen here:** `_on_entry`, `_on_exit`, `_on_unwind`, `_outcome` and `_publish`, which run only inside sys.monitoring callbacks, and `_forget_in_child`, which runs only in a forked child's at-fork handler. The reason is measured: code inside a monitoring callback raises no events for any tool, and legacy settrace is suppressed there too. coverage.py 7.16.1 reports such lines as missing under both its sysmon and ctrace cores (critic2/`covt`; `rev2/p5_cover_driver.py`: 0 of 49 lines seen as real callbacks).
  - **The driver** is written by the exam author before the freeze, from M6's and M9's text, and hashed in the prereg. It builds `FunctionType(code, vars(styxx.protocol))` from the `_v5_faultpoints()` code object of each named function and calls it directly, outside any callback, inside real traces opened through the public API. Its frozen scenarios are one per branch of M6 and M9:
    - a non-minted code;
    - a CUT_MOVED binding;
    - foreign globals (CLONE_CALLED);
    - no registered anchor;
    - each outcome kind `c`, `a`, `d` and `u` (the `a` kind through V28b's manual hop);
    - two holders;
    - PY_RETURN;
    - PY_UNWIND at and past the entry offset;
    - a publication after the credit stop;
    - `_forget_in_child` in a spawned subprocess, as its last step.
  - **Scope of the driver.** Lines of other functions executed by the driver do not count toward G_COVER. The driver cannot be used to cover anything else. The coverage measurement uses a LINE-event tool and, in a separate process, settrace. `rev2/p5_cover_driver.py` shows both seeing the callback functions' lines under a direct call, and neither seeing them as real callbacks.
  - **After the freeze.** An implementation line in a named function that no frozen driver scenario reaches is dead code, like any other, and must be deleted or folded. No exemption is granted after the freeze, and none is needed.

---

## Process gates for the v5f prereg

Carried, and adapted to the version policy:
- **G_EXAM_FROZEN.** Every `FROZEN_*_SHA256` in the prereg matches, read from the prereg as first committed. The freeze commit contains the runner, `ref_v5f.py`, the SM1 catalog, `sm1_result.json` and every gate script. It must be an ancestor of the first commit that carries the `/3` tracer id.
- **G0.** Violations refused with their own code: 1.0. The self-trace declares `Experiment._check_coverage`, `_resolve_target`, `_open`, `_exit` and `_run` (frozen names, M10) and must PASS (V34).
- **G1.** Valid cases exact: 1.0.
- **G2.** P1 retro exact on 3.12 and 3.13 (X118).
- **G3.** No v4/v5 disagreement over the pairable committed results.
- **G4.** Population ≥ 33.
- **G5.** Residual outcomes as documented: 1.0.

New:
- **G_INDEP.** The exam author, the implementer and the second-implementation author are three different people or agents, and the second implementation is from a different model family. `ref_v5f.py` is written from this spec alone, with a signed attestation. EQUIVALENT_BY_SPEC arguments are signed by a fourth reviewer.
- **G_V5E_DELTA.** At freeze time, the v5e cases ported to the `_v5_state()` interface are run against `ref_v5f.py`. Their outcome delta must equal the "v5e cases whose outcome changes" table exactly.
- **G_XVER.** Every case's outcome is identical on 3.12 and 3.13. On 3.10 and 3.11, X37 refuses UNSUPPORTED_VERSION and every scoring-only case matches.
- **G_SEM:** SM1 = 1.0 at the freeze; SM2 EXAM_HOLE = 0 after implementation; the positive controls as stated.
- **G_REF = 1.0** and **G_HYG = 0**.
- **G_COVER = 1.0**, with no pragmas; the callback-only functions are measured by the frozen direct-call driver (revision 2, BF1).
- **G_FI** and **G_SIG** as stated.
- **G_N (aux).** SM3.
- **G_CLOSURE.** The round 1–3 closure battery (`round4/closure-audit/r1/held_battery.py`, 41 rows) is re-targeted to the public API and holds 41/41 on 3.12 and 3.13. Every round-4 blocker and defect repro no longer reproduces, or ends in its documented refusal.
- **G_RED.** A round-5 red team runs against the implementation before any shipping claim. The shipping claim names every UNDISTINGUISHED mutant (as uncertified, not as equivalent) and every residual.

---

## What round 5 should attack first

1. **The confirmation layer,** which is new to the winner.
   - Credit an entry whose body never ran: C-level resumption (`map(next, gens)`, itertools, the C Task step, `contextvars.Context.run`); `yield from` and `await` chains; a raising tool at PY_RESUME; PY_UNWIND offsets for frames that raise at the first instruction after RESUME.
   - Leak or strand pending entries: events cleared mid-frame; the tool freed; frames still running at retire.
   - Find 3.12 against 3.13 differences in PY_RESUME/PY_YIELD delivery.
2. **L-DELIVERY as possible program corruption.** A PY_UNWIND callback that raises replaces the in-flight exception, and on 3.12.3 and 3.13.12 its `__context__` is None. The second critic answered round-5 question 2 with a probe: yes, an `except ValueError` flow in undeclared code loses its handler under a signal flood, at hundreds of thousands per 2M iterations. Revision 2 confines this to open sections: 0 outside them (`rev2/p4_unwind_scope.py`). It also freezes that G_SIG does not count it as a wrong result. Round 5 should attack what remains:
   - legitimate harnesses whose sections contain `except`-driven control flow under asynchronous exceptions (timeouts, KeyboardInterrupt handling);
   - the thread race of the per-section toggle;
   - the cost of re-instrumenting after each toggle in harnesses with many short sections.

   The named alternative is still first-LINE confirmation with local events only, at a per-line cost inside declared functions.
3. **The robust mutex and reconciliation.**
   - The exactness of `_alive`: a frame id reused by a new frame of the same code, and `f_locals` reads of another thread's frame on 3.12.
   - The cost of `sys._current_frames()` under contention, and slow owners against the 10 s bound.
   - Greenlets.
   - Pruning a holder whose entering token is live but slow.
   - `'exiting'` holders racing another thread's join, which must not yield a false CODE_SWAPPED.
4. **The coherence false-refusal surface.** Symlinked checkouts, zipimport, editable installs, `.pth` trees, pytest assertion rewriting, `importlib.reload` after the source moved, a relative `__file__` after `chdir`, frozen modules, Jupyter. Measure how many committed harnesses now refuse FOREIGN_DEFINITION.
5. **sys.monitoring interplay.** Tools calling `free_tool_id`, `restart_events`, `set_events` or `register_callback` on id 4 or 3. Id squatting before styxx's first enter. The MONITOR_LOST re-registration check itself. Per-patch-release instrumentation bugs (D1 hit a 3.12.3 settrace opcode bug).
6. **The crash-sweep scope.** The callbacks' own bytecode is not reachable by the INSTRUCTION injector while it runs as a callback. Revision 2 reaches it through the direct-call driver, which faults the same bytecode but not in its real calling context: a fault there propagates to the driver, not into a target frame. Attack the real context with lower-id tools and floods, and on two threads with hopped coroutine sections. Also check that no settrace/setprofile activity in the sweep process silences the injector (`rev2/p5b_settrace_blinds_injector.py`).
7. **CLONE_ALIVE's freeze clause.** A frozen clone with the count not above its mint value, after frozen objects died or after `gc.unfreeze()` then `gc.freeze()`. Over-blocks from executing T frames at exit.
8. **The SM2 noise mask and envelope.** A nondeterministic baseline field could mask a real regression. The mask must be minimal, and its size is reported.
9. **Over-blocking breadth.** Refusing 3.11 moves every lab harness. Count the committed preregs and harnesses affected, and check that every refusal message gives a working remedy.
10. **The loop boundary and R18.** Asyncio-compatible loops that do not call `_set_running_loop`. Greenlet-based loop bridges. Any way to re-enter a running loop's dispatch without passing a `Handle._run` or `BaseEventLoop._run_once` frame, other than R18's two shapes. Libraries that ship a loop class with its own `_run_once` and re-enter it. Shared-code poisoning of the cut by functions created after E2 (#21).

---

## Decisions this synthesis is least sure of

1. **Refusing CPython 3.11.** Judge 1 required it. Judge 2 left it to the panel, and this spec decides it on the py310-class argument. Refusing is the fail-closed choice, but it moves the lab's default interpreter, the P1 retro and the exam to 3.12/3.13. If the panel ranks L-SIGNAL-311 below py310, the alternative is D1's 3.11 setprofile adapter with SIGNAL_TIMER and f_lasti pairing for every target (judge 2's graft 1). That brings back a second adapter and a list of version-keyed cases.
2. **Confirmation grafted into D1's machine.** The pending entries hold their frames, and a global PY_UNWIND is set while any section is open (revision 2; revision 1: while any mint existed). Single-thread semantics were probed on 3.12.3 and 3.13.12 (synth/p_confirm_frame.py). No prototype of the combined machine has passed D1's crash sweep, G_SIG or the fuzzer. L-DELIVERY is also a new disclosed behaviour: while a section is open, an exception raised inside the unwind callback replaces the one being unwound. Round 5 may judge that program corruption. Revision 2 made it measurable and frozen: 0 lost handlers outside sections, reported inside, and not a G_SIG wrong result. The named alternative, first-LINE confirmation, costs a callback per line executed in declared functions. LINE events did not create the back-edge skip on 3.12.3 (`rev1/p13_backedge_line_branch.py`: 0/100), unlike JUMP, BRANCH and INSTRUCTION.
3. **SM2's compromise.** SM2 compares only spec-fixed observables and does not gate UNDISTINGUISHED mutants. That makes EXAM_HOLE = 0 attainable by an exam frozen before the implementation. The cost is that a weakening whose only effect is on unfixed text, or that no frozen instrument observes, is reported rather than failed. The judges agreed on each half; they did not jointly test the combination.

---

## Revision 1: critique items and their resolution

This section answers `DESIGN_protocol_v5f_DRAFT_critique_2026_09_25.md`. There is one row per item, in the critique's order; the last row is the CPython #130279 check requested alongside the critique.

The "verified" column cites probes under `/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/rev1/`, abbreviated `rev1/`. They were run on CPython 3.12.3 and 3.13.12, and on 3.11.15 where marked. "Reading" means the resolution follows from the spec text and needed no execution.

No v5f implementation or `ref_v5f.py` exists yet. So no row claims a result *of the design as implemented*; exam cases and gates will measure those.

**Totals.** 42 rows:
- 40 resolved as the critique asked;
- 1 resolved with a rejected sub-claim: (b)4, the `loop_factory` part, which a probe shows is false;
- 1 partly rejected: (c)4, where the disclosure is fixed but the class claim is not accepted, with a note why.

| # | critique item | what changed (sections) | how it was verified |
|---|---|---|---|
| (a)1 | D15: `type(obj) in (staticmethod, classmethod)` runs a metaclass `__eq__`; so does `type(result) in _LAZY_TYPES` in `_run` | Resolution step 2 now uses `is` chains and forbids tuple-membership type tests. M7 `_run` uses an `is` chain. Also changed: delta table (Resolution), D15 and R1-D2 rows, a G_HYG lint clause, new case V40b, the mutation audit and SM1 | `rev1/p1_meta_eq.py` (3.11.15, 3.12.3, 3.13.12). The tuple test ran the metaclass `__eq__`, and its RuntimeError escaped; the lazy-types tuple did the same. The `is` chain and `issubclass(type(obj), ModuleType)` ran nothing |
| (a)2 | B5: CUT_MOVED only at exit; a transient `Handle._run` rebind loses the cut silently | CUT_MOVED is now checked by `_cut_ok()` at every entry event of minted code, flagged on holders, and recorded at exit. Changed: Tripwires, Attribution "At a hit", M1 (`_HANDLE_DICT`, `flags`), M5 X6 and M6 `_on_entry`. The class-B paragraph is rewritten, and over-blocking #21, the B5 row and the R1-B3 closure row are updated. New: X141b, V62, residual R17. The rebinding cases move to the main thread before the self-trace | `rev1/p18_transient_rebind.py`. Under both a rebind and a `__code__` swap, no cut frame lies between a re-entrantly dispatched call and the anchor, and `_cut_ok()` is false at the hit and true at exit |
| (a)3 | E5: no case exercises E2's refresh | New case V61: `Handle._run` is replaced between `coverage_trace()` and `__enter__`, and the expected result is PASS. It is the named witness for E2's refresh in the E5 row, the mutation audit and SM1 | Reading. Without E2, the wrapper's code is not in the cut, so the per-hit check refuses CUT_MOVED. SM1 admission checks this on `ref_v5f.py` at freeze time |
| (a)4 | D1: the "bootstrap frame" sentence was still false for forked children | Class-B paragraph: a forked child's thread is a copy of the forking stack, and the at-fork handler plus the pid pass-through exclude it. D1 row updated | `rev1/p6_fork_chain.py`: the child's chain is `section_body → _run → <module>` |
| (a)5 | S2: the freeze count falls when frozen objects die, so clause (b) fires with no freeze call; the heading and message were false | Clause (b) now fires on a *rise* (`>`), with a new message. Also changed: L-CLONE, over-blocking #19, the CLONE_ALIVE row, the S2 row and graft 3. New witness V36b; the mutation audit and SM1 are updated | `rev1/p4_freeze.py`: the count fell by 11 after deleting frozen objects (3.11–3.13), and `gc.unfreeze()` set it to 0 (3.12.3 boots at 375). `rev1/p5_execref.py`: a frame of T executing on another thread adds a reference that no gc referrer explains |
| (a)6 | E26: X137's `free_tool_id` variant expected NOT_EXERCISED | X137 is split. The free variant runs in a subprocess and expects PASS `{f:1, g:1}` with MONITOR_LOST, then a second trace PASS. L-MONITOR, #7 and coexistence are rewritten | `rev1/p3_free.py`: after `free_tool_id`, local and global events and callbacks still fired; `get_tool` returned None |
| (a)7 | E23: V28b's "B counts its calls after the hop exactly" contradicts the rule | V28b now specifies the hop (manual `send()`, no loop) and expects B's post-hop call to be ambiguous in both openings, as in v5e's X70. The kill table is updated | Reading of the attribution rule: after the hop, two registered openings of one tracer lie on g's chain, with no cut and the same loop (None) |
| (a)8 | E21: V57 needs a main-thread profiler, but cases run on their own threads | V57: the case thread, which runs the `with`, plays the main thread's part; the kill table is updated | `rev1/p20_misc.py`: a profiler set on one thread is not seen on a new thread |
| (a)9 | D3: X93d expected the second wording | X93d expects the third wording | `rev1/p20_misc.py`: with `object_pairs_hook`, the outer object is a dict subclass that has the key, and the inner one is an OrderedDict |
| (a)10 | D10 marked FIXED while L-ASYNC-EXC still converts | D10 is now FIXED + DISCLOSED_LIMIT | Reading |
| (b)1 | I6: "never … a swallowed exception" contradicts L-DELIVERY | I6 names the one exception (the unwind callback replaces the exception in flight), and L-ASYNC-EXC gains the bullet | `synth/p_deliver.py`, re-run: at unwind, the caller sees the callback's exception with `__context__` None, on both versions |
| (b)2 | "no import runs inside enter or exit" contradicts E3 and G_HYG | The Decisions row now says no *machinery* import. E3 states it holds the only import. The G_HYG import clause allows exactly `_resolve_target`'s `import_module` and the constructor's `import asyncio` | Reading |
| (b)3 | L-MONITOR and #7: `free_tool_id` does not blind; the re-registration repair clobbers a new owner | L-MONITOR and #7 are rewritten. M5 X5 never tests or re-registers on an id that lost this copy's name. M3 `_retire` steps 2 and 6 are guarded by ownership. The coexistence text and the MONITOR_LOST row are updated | `rev1/p3_free.py`: free leaves everything in place. After another tool took the id, styxx's PY_UNWIND callback still fired there, and `register_callback` returned styxx's callback. That is why styxx must not touch the id |
| (b)4 | L-WHERE drops uvloop; #2 is false under uvloop and with an eager `loop_factory` | uvloop: **closed rather than disclosed** by the new loop boundary (Attribution rule, open step 5, M1 `_Opening.loop`, M6 walk). L-WHERE and #2 are rewritten; new cases X65d and V63. The eager-`loop_factory` sub-claim is **rejected**, and #2 says why | `rev1/p9_uvloop.py` (uvloop 0.22.1, 3.12.3): a cross-thread job ran with the anchor on its chain and no `Handle._run` frame, and the running loop differed from the one at open. `rev1/p8_cdispatch.py` shows the same on both versions. `rev1/p7_eager_loop_factory.py`: with the eager factory set through `loop_factory`, main's first step had `Handle._run` on its chain, because the task is created before the loop runs, so it is not eager (both versions) |
| (b)5 | #19: the trigger includes frozen objects dying and changes from before this trace | #19 is rewritten: a rise only, and the mint may predate this trace. Tripwires states the same | `rev1/p4_freeze.py` |
| (b)6 | L-STUB "proves … compiled from its own module's file" contradicts forged `co_filename` | L-STUB now says provenance *checks* `co_filename`, which can be forged, so it catches careless swaps and proves nothing about origin | Reading (R05b already forges it with `code.replace`) |
| (b)7 | Line 884 claims `profile` was executed, and on v5f | The Removed list now says what was executed and with which adapter (D3's, not v5f's). `profile`, yappi, pyinstrument and debugpy are listed as not executed, and the `profile-module` row is corrected | Reading of the cited evidence (D3 t_coexist, p2_callback) |
| (b)8 | M8: a never-entered tracer gets the wrong TRACE_ACTIVE text; "calling `__exit__` again" is false | M8 has per-case texts: never entered; inside the with-block or a zombie, with "one call of `__exit__()` completes it" only for the zombie. The code stays TRACE_ACTIVE, as v5e's X91 expects. The TRACE_ACTIVE row and a delta row for X91 are added | Reading of v5e (`run_protocol_v5e.py` X91; v5e spec line 587) |
| (b)9 | Line 555: "exit's `except GateSpecError`" is singular | Now "two `except GateSpecError` clauses, at X0 and X5", and G_HYG agrees | Reading |
| (b)10 | Lines 115/520: "runs no user `__eq__`/`__hash__`" is too strong | The delta row, M11 and the Resolution preamble now name the str-subclass key collision (contrived) | `rev1/p2_dict_collide.py`: `dict.get` ran the subclass `__eq__` (twice on 3.11, once on 3.12/3.13) |
| (c)1 | R1-D2 reopened by the metaclass `__eq__` | Closed by (a)1. The R1-D2 closure row now cites V40b | as (a)1 |
| (c)2 | R1-B3 / R2-B2 / R3-B2 / J1-X2 reopened by a transient rebind and by uvloop | Closed by (a)2 (CUT_MOVED at every hit) and (b)4 (loop boundary). What remains is R17: a replacement `Handle._run` that restores the binding from inside its own running frame during re-entrant same-loop dispatch. It is deliberate only, pinned, and listed for round 5 (item 10). The R1-B3 closure row is updated. New witnesses X65c (the cut) and X65d (the boundary) replace X65 as the named witnesses | `rev1/p17_reentrant_dispatch.py`: re-entrant same-loop dispatch has the same loop at open and at the hit, with `Handle._run` before the anchor, so the cut is still needed there. Also p18, p9 and p8 |
| (c)3 | R1-B4 reopened by re-registration on a freed id, and by a second module copy adopting "ours" | New per-copy `_TOOL_NAME`. `_ensure_tool` adopts only this copy's name, and nothing is ever touched on an id that lost it (M3, M4, M5). New Decisions row; new X142; the R1-B4 closure row is updated | `rev1/p3_free.py` (see (b)3). The second-copy behaviour follows from the name test (reading); X142 pins it |
| (c)4 | R2-B3: a zombie keeps the process-wide PY_UNWIND callback indefinitely | **Partly rejected; disclosure fixed.** L-ZOMBIE, in both places, now names the global PY_UNWIND callback, its cost and its lifetime, up to process exit. The design is kept, and the R2-B3 closure row carries a note: R2-B3 was a silent leak after a *completed* exit, while a zombie exists only after a fault has left the harness's own `with`, `record()` refuses it, and it ends at `__exit__()` or the next transaction | Reading |
| (d)1 | G_COVER pragmas are written and judged after the fact | Pragmas are removed. A line counts as covered if the exam, the crash sweep or the fuzzer runs it; otherwise it must be deleted. G_COVER, the process gates and G_RED are updated | Reading |
| (d)2 | SM2 UNDISTINGUISHED presumed equivalent and handed to humans | Never judged equivalent by anyone; counted, listed, and stated in the ship claim as uncertified. The Objectivity rule is added | Reading |
| (d)3 | Noise mask "N ≥ 5" | Exactly N = 5, in frozen order with frozen seeds. A mask that covers any code, count, end, note or problem makes the baseline unclean | Reading |
| (d)4 | Open-ended substring list; corpus without an author or freeze point | The normalizer's substring list is closed. `corpus_v5f/` is written by the exam author before the freeze and hashed in the prereg, with its sources named | Reading |
| (d)5 | SM1 retirement by "anchor text absent" decides nothing | The classification is fixed by census id: RETIRED (15, listed), ADOPTED (P03) and RE-TARGETED (the other 47) | `protocol_v5_redteam/round4_exam_mutation/semantic_mutation_census.json`: 63 ids, whose anchors were read in `mutants.py` to assign each to a removed mechanism |
| (d)6 | Positive controls: open list; normalizer fields v5e lacks; unfrozen crash results | #1 is a fixed list of the 36 census survivors. #2 drops the `_v5_state()` and tool fields on v5e. #3 runs the frozen `crash_sweep_v5f.py` on v5e through an adapter and cites the committed results only as reference | The census JSON lists exactly those 36 survivors |
| (d)7 | G_FI allowed windows need offset mapping | "Clean" is defined by outcome alone, as clauses (a)–(e) | Reading |
| (d)8 | SM1 rows M1–M8 have no case-level witness | Each row's witness is one named crash-sweep invariant, killed only if that invariant fails; M8 is retired with `_TH` and M10 is witnessed by X71c | `crashcons/mut_final_312mon.txt`: M2, M4 and M7 tripped C7; M3, M5 and M6 tripped C5 |
| (d)9 | The SM2 region is bounded by a marker the implementer places | The region is defined by the frozen function names (M10) plus the scoring functions, and G_HYG checks the name set against the v4-era set | Reading |
| (e)1 | X36 cannot hold ids 3 and 4 inside the self-trace | X36, the X137 free variant and X142 run in a fresh subprocess (harness rules) | Reading: the self-trace holds id 4 for the process |
| (e)2 | V34/G0: freezing cases would make the self-trace refuse CLONE_ALIVE; `_run` undeclared; `_resolve_target` unfixed | Clause (b) is now a rise ((a)5), and a hygiene rule requires `gc.unfreeze()` with a count no higher than before the case. G0/V34 declare `_run`, and the names are frozen in M10. V34 expects PASS with each count ≥ 1 | `rev1/p4_freeze.py`: `unfreeze` lowers the count, so the self-trace's own `_exit` frame cannot trigger (b) |
| (e)3 | X92b, X131, X138, X139 and the faultpoint keys depend on internals | `_v5_faultpoints()` keys are frozen (M10). X92b is placed by observable state (`f.__code__` is the original again), X131 at `_provenance`'s first instruction, and X138/X139 by key | Reading |
| (e)4 | The H1, H6, H7 and H8 mutants need internals | Every hazard-sweep detection mutant is an SM1 row against `ref_v5f.py`, run at freeze time. The implementation's mutants come from SM2 | Reading |
| (e)5 | X140's outcome is timing-dependent | X140 is now a deterministic sweep: KeyboardInterrupt at every back-edge offset of every faultpoint, with outcomes set by G_FI. The flood variant is X140f, with an explicit outcome set | `rev1/p10_backedge.py`: raising at the back-edge offset reproduces the finally skip deterministically on both versions (while: offset 38; for+if: 18/28) |
| (e)6 | V52's failed-enter variant cannot PASS | Variant (2) expects TRACE_INCOMPLETE, a clean state, and a later PASS | Reading of M8 |
| (e)7 | The delta table omits X71c (reads `P._hook`, rebinds `P._ANCHORS`) | A new table lists every v5e case or harness part that reads a styxx private name, with its port. X71c keeps its outcome through an interval SIGALRM handler that fires inside X3, located by `_v5_state()["anchors"]` | `rev1/p16_handler_events.py`: a handler tripped inside a monitoring callback runs with events suppressed, so that port is impossible. A handler landing in ordinary code does raise events (both versions). `rev1/p14_handler_at_entry.py` shows the same |
| (e)8 | No source for the prebuilt `/3` traces; V38 must say that Memo stamps `__wrapped__` | `traces_v5f/` is generated by `ref_v5f.py` at freeze time and committed. V38 states `update_wrapper(self, fn)` | Reading |
| H | CPython #130279: no machinery state may depend on a `finally` or with-exit across a `while`, or a `for` ending in `if` | Added: the rule in Threat; M6 (styxx enables no INSTRUCTION, LINE, JUMP or BRANCH event); M7 (`_run_async`'s `await` loop and why nothing depends on its `finally`); the CLOSE prefix; exception-safety bullets; G_HYG; X140 covering the `await` throw path; the H9 mutant; the fault-tool note; round-4 row. **Two findings the critique did not raise:** (1) on 3.12.3, INSTRUCTION, JUMP and BRANCH events create the skip; (2) `_run_async`'s `await` has a back-edge outside its try range | `rev1/p11_backedge_timer.py` (SIGALRM): 3.13.12 skipped 400/400 (while) and 188/400 (for+if); 3.11.15 and 3.12.3 skipped 0. `rev1/p12`, `p13` on 3.12.3: styxx's event set 0/300, LINE 0/100, INSTRUCTION 7–14/100, JUMP 74–75/100, BRANCH 73–77/100. `rev1/p10_backedge.py`: `_run`'s `finally` is never skipped at any offset. `rev1/p19_run_async_throw_path.py`: the throw-path back-edge (offset 94) skips `finally` on both versions; it is JUMP_BACKWARD on 3.12 and JUMP_BACKWARD_NO_INTERRUPT on 3.13 |

---

## Revision 2: critique items and their resolution

This section answers `DESIGN_protocol_v5f_DRAFT_critique_rev1_2026_09_25.md` (verdict NOT_READY: 1 BLOCKER-for-freeze, 12 MUST-FIX, 10 NOTE). There is one row per item, in the critique's order. Three findings made while resolving them follow the table.

The "verified" column cites probes under `/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/rev2/`, abbreviated `rev2/`, with outputs in `rev2/out_*.txt`. Each was run on CPython 3.12.3 (`rt3/venv3.12`) and 3.13.12 (`rt3/venv3.13`) with the same outcome unless the row says otherwise. Most run against `rev2/mech2.py`, the second critic's event-path model extended with revision 2's changes behind switches. "Reading" means the resolution follows from the spec text and needed no execution. As in revision 1, no v5f implementation or `ref_v5f.py` exists. Every result is of the model or of CPython itself, never of the design as implemented.

**Totals.** 23 rows:
- 19 resolved as the critique asked;
- 3 resolved with a changed fix:
  - M1: two sub-checks rejected; the critic's fix is adopted, with the reads unified instead;
  - M12: the lower boundary row is 7 s, not 5 s;
  - N2: the zip claim is version-dependent;
- 1 (N4) resolved with a new witness.

| # | critique item | what changed (sections) | how it was verified |
|---|---|---|---|
| BF1 | G_COVER = 1.0 is unattainable: code run only inside sys.monitoring callbacks raises no events, so no instrument can cover `_on_entry`, `_on_exit`, `_on_unwind`, `_outcome` and `_publish`; `_forget_in_child` runs only in a forked child | **Both of the critic's options, combined and frozen.** G_COVER gains a frozen named list, those five functions plus `_forget_in_child`, measured by a fourth instrument only for them: the frozen direct-call driver `cover_driver_v5f.py`. The driver builds `FunctionType(code, vars(styxx.protocol))` from `_v5_faultpoints()` code and calls each function outside any callback, inside real traces. Its scenarios are frozen, one per branch of M6 and M9. `_forget_in_child` runs as the last step of a spawned subprocess. Lines of other functions run by the driver do not count. An unreached line in a named function is dead code, as for any other function, so nothing is judged or exempted after the freeze. Changed: G_COVER, the process gates, the frozen artifacts, the Evidence paragraph | `rev2/p5_cover_driver.py`. Run as real callbacks, 0 of the 49 body lines were seen by a LINE-event tool or by settrace. Called directly by a five-call driver, 38 of 49 were seen by both. The unseen lines are branches that driver did not drive (CUT_MOVED, CLONE_CALLED, the `a`/`d`/`u` outcomes), each of which is in the frozen scenario list |
| M1 | Three over-credit routes beyond R17 (A1 `TimerHandle._run`, A2 `events.Handle` rebound, A3 a custom `_run_once`); "Handle" read at three moments | **Adopted:** `BaseEventLoop._run_once`'s code joins the monotone cut, and its binding joins `_cut_ok()`, E2's refresh, RESERVED_TARGET and CUT_UNAVAILABLE. All reads use the class dicts captured by the first `coverage_trace()` (`_HANDLE_DICT`, new `_LOOP_DICT`), which ends the three-moment inconsistency. A1, A2 and revision 1's R17 are closed, as new violation cases X65e, X65f and X65g. X141c witnesses the new binding check and X34c the reservation. **The residual is stated honestly as R18:** re-entrant same-loop dispatch through code that is neither cut code, as either a loop class whose own `_run_once` bypasses `Handle._run` (A3) or a self-restoring rebind of `_run_once` that bypasses it. **Rejected sub-checks:** the critic also asked `_cut_ok()` to require that `asyncio.events.Handle` is the captured class and that `TimerHandle` has no own `_run`. With `_run_once` in the cut, both are redundant: A1 and A2 become `dispatched` without them. They would only add CUT_MOVED over-blocks for harmless subclassing, so they are not adopted. Rewritten: the delta rows, Tripwires, the Attribution rule and "Why the cut holds two codes", the class-B paragraph, the B5 and R1-B3 rows, L-WHERE, over-blocking #21, the residuals, the mutation audit, SM1 and round-5 item 10 | `rev2/p1_runonce_cut.py` with `critic2/t_fix_runonce.py` re-run: revision 1 credits A1, A2 and R17; revision 2 gives `dispatched {f:1}` for each, R17 with W bound before or after `__enter__`. Unchanged in revision 2: plain `{A:{f:1}}`, section in a task `{A:{f:1}}`, X65c and X65d `dispatched`, V19b and V63 `{B:{g:1}}`, V61 `{A:{f:1}}`. A3 and A3' stay credited (R18). `rev2/p1b_runonce_binding.py` (X141c): spec CUT_MOVED; without the `_run_once` binding check, credited silently. `rev2/p2_shared_cut.py`: a nest_asyncio-shaped loop is `dispatched` through `Handle._run` |
| M2 | A generic decorator on `Handle._run` poisons the monotone cut for the rest of the process | **Fixed, with a disclosed remainder.** E2 (`_cut_refresh`) refuses CUT_UNAVAILABLE when a binding's code is new to the cut and shareable: `'<locals>'` in its `co_qualname`, or another live FunctionType among `gc.get_referrers`. The scan runs once per new code. V61's wrapper must be defined at a fixture's top level. New cases X35b (`<locals>`) and X35c (a live twin). Remainder, disclosed in #21: a function created *after* E2 that reuses a cut code still stops attribution, as an under-credit only. Changed: E2, the reason-code row, #21, V61, the mutation audit | `rev2/p2_shared_cut.py`. Revision 1: `logged(orig)` gives `dispatched {f:1}` in this trace *and* in a later trace (the critic's A5). Revision 2: CUT_UNAVAILABLE naming `logged.<locals>.inner`, and the later trace `{A:{f:1}}`. A module-level W is accepted, and W with a live twin is refused. Scan cost: 1.6–2.1 ms (100k extra objects), 13.6–17.1 ms (1M) |
| M3 | After `free_tool_id` and a *completed* exit, the global PY_UNWIND callback into styxx outlives the exit | **Fixed.** New reconciliation step 0, `_reclaim`: if styxx's id has no owner (`get_tool is None`), re-take it under `_TOOL_NAME`, re-register the callbacks and bump `_LOST`. The retire steps then clear its events. Exit's MONITOR_LOST test reads `_LOST[0] != core.lost0`. If another tool took the id, styxx never touches it, and the leak is disclosed in the R2-B3 row, L-MONITOR and coexistence (new X137b). Races with other tools' id calls are faults, stated in the Tool acquisition prefix. Changed: M1, M3, M4 E4, M5 X5, I3, coexistence, L-MONITOR, #7, R2-B3, X137, X137b | `rev2/p3_free_reclaim.py`. `set_events` on a freed id raises ValueError, so re-taking is the only way to clear it. Freed mid-section, then a normal exit: revision 1 leaves `tool=None, global_events=4096`, and 1,000 unwind callbacks fire for 1,000 unrelated raises. Revision 2 leaves the tool ours, `global_events=0`, and 0 callbacks; record `{f:1, g:1}` with MONITOR_LOST in both. Taken by another tool: 1,000 callbacks remain (disclosed) |
| M4 | L-DELIVERY is large and reaches unrelated code; G_SIG does not say whether it counts | **Scope reduced, measured, and a frozen G_SIG decision.** The global PY_UNWIND is set only while some section is open, not while any mint exists. The opener sets it before and after its anchor commit (`_unwind_on`). The closer clears it after the last anchor pops, then re-checks (`_unwind_off`). `_on_entry` stores nothing when no anchor is registered. A close that finds the event cleared while its section was open sets `UNWIND_LOST`, which exit notes as MONITOR_LOST (X137c). **G_SIG decision:** L-DELIVERY is not a "wrong result". The term is now defined. Three frozen cells measure L-DELIVERY: (a) outside sections, gated at 0; (b) inside, reported; (c) `with`/`finally`, gated at 0 (H10). L-DELIVERY now states exactly what changes in the program and why 3.11's refusal does not apply. New cases X137c and X143 (the opener's re-check). Changed: Minting, At open, At a hit, Close, M6, M7 ("The unwind scope"), I3, I6, prefixes, L-DELIVERY, L-ZOMBIE, Cost, #17, H10, G_SIG, round-5 item 2, least-sure #2 | `rev2/p4_unwind_scope.py`, 1M iterations under a 20 µs flood (critic's method). Lost handlers with a trace active and no section open: 171,683 / 121,297 (3.12 / 3.13) under revision 1, **0 / 0** under revision 2. Inside a section: 168,512 / 120,255. Untraced: 0 / 0. Cost: +3.2 / +2.5 µs per section, and +13.1 / +7.9 µs for a section running 100 distinct functions (re-instrumentation). `rev2/p4b_disable_kept.py`: another tool's DISABLE survives 1,000 toggles (at most 2 fires per location, from lines spanning two offsets). `rev2/p4c_toggle_race.py`: 100,000 (2 threads) and 40,000 (4 threads) raising calls in sections, all counted, no false MONITOR_LOST, at a 1 µs switch interval. `rev2/p13_x137c.py`: X137c gives `{f:1}` with MONITOR_LOST; the control gives `{f:1, g:1}` without. `rev2/p14_recheck_witness.py`: X143 gives `{A:{t:1}}` under the spec and `{}` without the re-check |
| M5 | SM2 never defines "faulted" | A frozen `corpus_v5f/manifest.json` gives every entry one class, `equality` or `envelope`, by a frozen rule on the entry's source (fault tools, injector, signals, async exceptions, finalizer thresholds, thread races, timing). `envelope` entries are compared by a frozen acceptance predicate: I6 against the fault-free run, or the exam's stated outcome set or gate. The noise mask covers `equality` entries only. The manifest is validated on `ref_v5f.py` at freeze time. Changed: frozen artifacts, SM2 normalizer paragraph | Reading. The classes are assigned mechanically and the predicates are the exam's own texts |
| M6 | `_v5_faultpoints()` does not say which code object it returns while the self-trace has minted a machinery function | It returns `fn.__code__` read at call time. X92b, X131 and X132 move to the main thread before the self-trace. The injector also filters to the case thread by a *live* thread ident, disarmed before `join()`. Changed: M10, harness placement, injector rules | `rev2/p6_faultpoint_identity.py`. With the function minted, import-time code gives 0 injector events, and the call-time code gives 400 on the case thread with 400 other-thread events filtered out. An earlier version of the probe matched a finished thread's reused ident, which is why the rule requires a live ident |
| M7 | X71c's port depends on a signal landing in X3 | A landing rule. 100,000 suspended openings (not 1,000). A trial lands iff the witness union has f. Void trials are repeated up to 20 times. The case fails if none lands or if a landed trial credits G, and SM1 uses the same rule. Changed: the port table | `rev2/p7_x71c_landing.py`. With 1,000 openings, 6 of 10 trials landed on 3.12.3, which confirms the critic's point. With 10,000 and 100,000, 10 of 10 landed on both versions. The M10 mutant credited G in every landed trial, and the spec in none |
| M8 | X140's back-edge trials include callback code that the injector cannot reach | Trials for the five callback-only functions run under the direct-call driver (BF1). A trial whose offset never executes is recorded UNREACHED, counts as clean, and is reported. The scenario runs to completion, so no trial waits on an offset. Changed: X140, G_FI | `rev2/p5_cover_driver.py`: as real callbacks, 0 back-edge hits; under the driver, 48 injector hits at `_outcome`'s back-edges and 2 at `_publish`'s (after `restart_events()`; see F1) |
| M9 | V36b as worded cannot witness the freeze-rule rows | V36b now says the worker "enters f after `__enter__`" | `critic2/t_v36b.py` re-run (`rev2/out_m9_v36b.txt`). A worker that entered before the trace: excess 0, and neither mutant fires. One that entered after `__enter__`: excess 1; both mutants fire, and the spec rule does not |
| M10 | R17's pinned outcome depends on when W is bound | R17 is closed (M1), and its shape is pinned as X65g: "after `__enter__`, with no hit before the section". Both bindings now give the same outcome, so the timing no longer changes it. The case still fixes the order, so that it witnesses the `_run_once` cut and not E2 | `rev2/p1_runonce_cut.py`: `dispatched {f:1}` with W bound before and after `__enter__`. Under revision 1 the two differed, as the critic's `t_r17_timing.py` showed |
| M11 | Control #2 needs a clean baseline that control #3 needs to be unclean | Control #2 uses instruments (a) and (d) only. (b) is excluded because control #3 requires it unclean on v5e; (c) because its oracle is `ref_v5f.py`. The clean-baseline condition applies to (a) and (d) | Reading |
| M12 | The busy bound has a boundary row on one side only; X138 must start the waiter during the block | X138 now measures its 11 s block from the waiter's start, synchronised by two Events (N6). New V65 is the lower row: a 7 s block, and the waiter succeeds after at least 6 s. 7 s rather than the critic's 5 s, because a ×0.5 mutant (5 s) would tie at 5 s. SM1 carries rows for 0.5 s, ×0.5 and ×2, and SM2 gains O7b (float constants ×0.5 and ×2) | `rev2/p12_busy_bound.py`, a model of M2's wait at the real durations. Spec: X138 MACHINERY_BUSY at 10.0 s, V65 acquired at 7.0 s. Bound 0.5: V65 fails. ×0.5: V65 fails (BUSY at 5.0 s). ×2: X138 fails (acquired at 11.0 s). Both versions |
| N1 | Revision-1 mechanisms are cheap, but the Cost row understates a hit on small targets; PY_UNWIND cost | The Cost table gives per-hit figures against an untraced trivial call (×116–×356), the cost of the second binding check, the scoped PY_UNWIND cost inside and outside sections, the toggle cost, `os.getpid()` and the one-off gc scan | `rev2/p11_cost.py`. A hit costs 4.2–4.3 µs at depth 5 and 12.1 µs at depth 60. The second binding adds 0.16–0.42 µs. An unwind through 1 frame is ×1.43–×1.57 inside a section, and through 6 frames ×2.01–×2.23. Outside every section: ×0.99–×1.04 |
| N2 | #9's "relative `__file__` after chdir" does not occur; the zip `.pyc` case gives a misleading message | The chdir item is removed. The zip item is rewritten with the measured behaviour. FOREIGN_DEFINITION (a) gets a second message naming the `.pyc` `__file__` and the remedy. **Changed from the critique:** the zip result depends on the version | Critic's `relp/t_rel.py` and `t_zip.py` re-run: coherent after chdir; a source-only zip is coherent. `rev2/out_n2.txt`: on 3.13.12, `z2.zip` loads `zmod2.pyc`, with `co_filename` `/build/ci/checkout/zmod2.py`; on 3.12.3 the same archive loads `zmod2.py`, coherent |
| N3 | L-RUNTIME is false while a loop started inside the section runs | L-RUNTIME states two exceptions: the loop boundary, and, new with M1, a re-entered `_run_once` frame. #21 carries the second | `rev2/p1_runonce_cut.py`, "N3 signal handler in re-entered `_run_once`": credited in revision 1, `dispatched` in revision 2, with the handler run in both |
| N4 | "monotone cut (cleared or replaced) → X65b" is half right | The row is split. "Cleared" is killed by X65b through CUT_MOVED (the critic's A4). "Replaced" gets a new witness, V64: a nested tracer with a V61-style rebind between the two enters, restored before the outer's hit | `rev2/p1_runonce_cut.py`: V64 PASS `{A:{f:1}}` under the spec; under the "replaced" mutant, CUT_MOVED |
| N5 | The at-fork handler can abort partway; G_FI has no fork scenario | M9 is reordered so that every step running no user code precedes the `__code__` restores. The pass-through, exit, `record()` and reconciliation read `os.getpid()` rather than a pid cached by the handler, so an aborted handler cannot un-fork the child. G_FI gains a fork scenario with invariant C9 | `rev2/p8_atfork_abort.py`, with an audit hook refusing `__code__` writes in the child. Revision 1 order: the child keeps 1 anchor, 1 registered mint and `global_events=4096`. Revision 2 order: 0 anchors, 0 mints, `global_events=0`; only the inert M_T stays installed. `os.getpid()` costs about 0.14 µs more than a cached read |
| N6 | X138's waiter must be synchronised with the block | As M12: two Events, and the block is timed from the waiter's start | as M12 |
| N7 | The FOREIGN_DEFINITION message can raise TypeError | The name is used only when `type(name) is str`; otherwise `co_filename` | `rev2/p9_foreign_msg.py`. With no `__name__`, and with `__name__ = 42`, revision 1 raises TypeError and revision 2 gives `<string>:fit`. A str subclass takes the fallback too, so no user `__add__` runs |
| N8 | `importlib.reload(styxx.protocol)` loses held mints and uses up tool ids | M1's state is bound with `globals().get` semantics, so a reload keeps the registries, the tool id and the name. The first exit after a reload re-registers the reloaded callbacks and notes MONITOR_LOST once. The Decisions row is corrected, and G_HYG lints the binding form | `rev2/p10_reload.py`, a module shaped like M1. Revision 1: reload 1 takes id 3 and loses the held mint; reloads 2 and 3 get MONITOR_BUSY. Revision 2: id 4 is kept and the mint kept, through three reloads. The single MONITOR_LOST after a reload follows by reading from M5's re-registration test |
| N9 | #2 and L-WHERE overstate the boundary | The boundary is stated for loops that register through `_set_running_loop`. Others are L-WHERE's non-asyncio schedulers | Reading (the round-5 list already names such loops) |
| N10 | Control #1's wording does not match SM1's classes | Control #1 has two classes, KILLED and SURVIVED. It passes iff the 36 listed are SURVIVED and the other 27 KILLED | `semantic_mutation_census.json`: `n_applied` 63, `n_detected` 27, `n_survived` 36, with the survivor list equal to control #1's |

**Found while resolving (not raised by the critique):**
- **F1. A settrace function silences other tools' INSTRUCTION events, and they stay off.** On 3.12.3 and 3.13.12, once a settrace function has run over a code object, tool 5's INSTRUCTION events on that code stop. They stay off after `sys.settrace(None)`, until `sys.monitoring.restart_events()` (`rev2/p5b_settrace_blinds_injector.py`). An injector sharing a process with ctrace or pdb could therefore run every trial without firing, and report clean. Fixed by the injector rules: no settrace or setprofile, `restart_events()` before each trial, a self-check trial, UNREACHED reporting, and G_COVER's settrace pass in its own process.
- **F2. Thread idents are reused.** A thread filter keyed on a finished thread's ident matched a later thread (the first version of `rev2/p6_faultpoint_identity.py`). The injector rule requires an ident read while the case thread is alive.
- **F3. Zip import differs by version** (N2 row). This affects FOREIGN_DEFINITION's outcome for the same archive, not any exam case.

**Kept from revision 1.** No machinery state depends on a `finally` or with-exit across a loop back-edge (CPython #130279). The new functions `_reclaim`, `_cut_refresh`, `_unwind_on`, `_unwind_off` and `_ours` contain no `try`, and neither does the reordered `_forget_in_child`. `_detach`, still called from `_run`/`_run_async`'s single `finally`, gains no loop. `_cut_refresh`'s loop over two bindings and `_reclaim`'s callback registrations sit in no `try` body. G_HYG's lint is unchanged. The one new handler-free failure mode, a ValueError from another tool's id calls racing styxx's, is a fault within the model (the Tool acquisition prefix), not a caught exception.
