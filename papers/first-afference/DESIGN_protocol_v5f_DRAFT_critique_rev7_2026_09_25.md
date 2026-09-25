# Critique of DESIGN_protocol_v5f_DRAFT_2026_09_25.md, revision 7 (eighth critic)

Target: `papers/first-afference/DESIGN_protocol_v5f_DRAFT_2026_09_25.md` (3,066 lines), revision 7. Line numbers below are that file's.

Evidence read:
- `protocol_v5f_design/rev7/`: `mech7.py`, `m7_modelcheck.py`, `steps7.py`, `atom7.py`, `w7_witnesses.py`, `w7_audit.py`, `w7_greenlet.py`, `audit_classify.py`, and the outputs;
- the scratch copies of `audit_claims.json` and `audit_claims_classified.txt`, which the committed `rev7/` does not contain (N5);
- the seven earlier critiques;
- `protocol_v5_redteam_audit.json`, round_4.

Probes are in `scratchpad/v5f/critic8/`: `c1`–`c7` with outputs `out_c*.txt`, and re-runs `rerun_*.txt` and `order_*.txt`. Interpreters: `rt3/venv3.12` (3.12.3) and `rt3/venv3.13` (3.13.12). greenlet 3.5.6 comes from `rev6/site31*`. No tracked file was modified.

**Counts: 0 BLOCKER-for-freeze, 5 MUST-FIX, 9 NOTE. Verdict: READY_FOR_EXAM_BRIEF, conditional on the five MUST-FIX text edits landing before the freeze.**

---

## What was attacked, and what held

**Re-runs.** Every re-run reproduces:
- `w7_witnesses.py` and `atom7.py` byte for byte on 3.12.3 and 3.13.12, after the random tool name is masked;
- `w7_audit.py` with the same values on both versions;
- `m7_modelcheck.py main` on 3.12.3 line for line, except the `(Ns)` timings. The only other difference is that the `rebind2:` rows now appear inside the main run instead of in `out_m7_main_rebind2.txt`. The totals match: 99 revision-7 runs, 10,465,412 state hashes and 0 violations. Revision 6 has LOSTNOTE in exactly the 7 `cb2` rows.
- `mutants` for `cbrep_nocount`, `count_after_register`, `retake_nocount` and `rebind_count_none` give the stated first violations, with one run that did not reproduce (N9).

These held:
- **B1 as specified.** The spec's `_register` pipeline, read against CPython's `map_next`, `filter_next` and `compress_next`:
  - Each `_LOST_APPEND` runs after the exchange that found a previous callback other than styxx's, and before the next gate.
  - Completeness still implies five exchanges: after a failed gate, the remaining gates and the owner read run back to back in C with nothing between them.
  - X158, X158b and RELOAD behave as stated, and their single-rule mutants are silent (`rerun_w7_*`).
  - The model's `cb2:` rows find revision 6's B1 and nothing else.
- **The E4 counting rule, X154d, X157b and X157c.** Each is deterministic, gives its stated outcome, and differs under its mutant. X157b's F25 residual is fail-closed: a loss is still noted through the close's ungated read (X157c), or through the leftover callbacks at the next registration.
- **X156c, X156d and X37b.** The binding check runs at every `coverage_trace()` and refuses as stated.
- **V67, V68, V69 and R20–R22.** Each reproduces with the stated value.
- **The G_ATOM matrix and K4–K10.**
  - The 24/24/3/4/9 product is well defined.
  - K4 fails all 9 `_register` cases; K5, K6 and K7 fail 24 each; K8 fails 3, K9 3 and K10 9.
  - The critic-7 vacuous shapes now fail criterion (a).
  - The interval criterion does close the "0 and 0" vacuity.
- **M2 (versions).** Every normative "3.12 and 3.13" that matters now names 3.12.3 and 3.13.12. The only leftovers are historical or compiler facts (lines 3, 49, 567, 1996) and one positive control on v5e (line 1919).
- **A14.**
  - **Recursion:** a depth sweep across the C-recursion boundary (`c4`) finds no partial effect in `_unwind_off` or `_unwind_on` on either version. Every pipeline call runs at the same C depth, and the first call in each pipeline precedes its first write, so RecursionError lands before any effect or not at all. The claim holds, and the sweep is cheap enough to freeze (N3).
  - **Gc:** `c1` does not contradict the gc claim itself. What runs there is refcount deallocation, not gc.
- **The deallocation hazard in the other steps.** The one-call steps are clear of it. In `_unwind_off`, the popped key and value are always held by the caller: `_detach`'s `fr` and `o`, and the prune's `list(_ANCHORS.items())` snapshot. So no finalizer runs inside `_unwind_on`, `_unwind_off`, `_take` or `_set_local`.

The attack found one new silent loss that the text says cannot happen. It is fail-closed and needs a finalizer that switches greenlets (M1). It also found that two of the self-audit's cited witnesses do not witness their claims (M2, M3), that G_ATOM's timing floors have no rule for a void run (M4), and one contradictory case sentence (M5). None of these stops an exam author from freezing a deterministic exam once the text is fixed.

---

## BLOCKER-for-freeze

None.

---

## MUST-FIX

### M1. A replaced callback's finalizer runs between the exchange that repairs it and the in-call count; with a greenlet switch there, another live trace's loss is silent again (B1 through a new door)

**The claim.**
- Line 714 (the paragraph on the registration): "Nothing runs between exchange i, its comparison and count, and gate i+1 … since all are C."
- Line 718: "A fault, an audit hook, a thread switch or a greenlet switch can land between two exchanges, but never between an exchange and its count."
- Line 2782: "No fault, audit hook, thread switch or greenlet switch can then separate a repair from its count."
- Appendix id 99 (line 3027).

**Why it is false.**
- Revision 7 stopped keeping the previous callbacks. Revision 6 returned them in `r`, which held them alive until X5 dropped `r`.
- Now `map_next` of the `_is_not` map decrefs its arguments right after `is_not` returns. That is *before* `filter` yields the True and before `_LOST_APPEND` runs.
- If the outside party's replacement is referenced only by the monitoring slot, its deallocation runs Python code at exactly that point. The slot is already repaired and the count is not yet made. The code can be a `__del__`, a `weakref.finalize`, or a `__del__` of something the callable's closure holds.

**Evidence** (`critic8/c1_del_between_exchange_and_count.py` on `mech7.py`, X158's shape, both versions, `out_c1.txt`):
- *observe*: inside the finalizer `len(_REPL)` is 5, the pre-count value; after the exit it is 6.
- *greenlet*: the finalizer switches to a greenlet that runs Q's exit, which steals the robust mutex because P's frames are off the chain. Q finds all five callbacks styxx's and `_LOST` unchanged. Result: `Q_calls {}, Q_lost False` on 3.12.3 and 3.13.12. Q's call was lost and not noted.

**Scope.**
- It is fail-closed: Q is NOT_EXERCISED, not over-credited.
- It needs a hostile or odd outside party: a replacement callable whose finalizer switches greenlets.
- That is the same class the spec already takes into scope for audit hooks (X137f, `cb2+greenlet`).
- A thread switch in the finalizer is harmless, because P's frames stay on its thread's chain and the mutex holds.

**Also wrong.**
- G_ATOM's criterion (b) and its scope paragraph (line 2087) assume no Python code runs inside `_register`'s call except the audit hooks. Its matrix never uses a replacement callback with a finalizer.
- The model counts in the same step as the exchange (`m7_modelcheck.py` line 670). Neither the U1 axiom list (line 741) nor "What is still not enumerated" (line 2907) says the model takes this atomicity as an axiom.

**Fix (either).**
- *(a) Mechanism.* Keep every previous callback alive until the consuming call has made every count. One C-only form reads the exchanges through `itertools.tee`, compresses the previous callbacks that are not styxx's, and appends for each. `critic8/c7_tee_fix_sketch.py` shows each finalizer then sees `len(_LOST)` equal to 2 of 2 counts on both versions, against 0 and 1 for the spec's form, with the same `r`. This adds `_tee` to the vocabulary, the binding check and G_HYG.
- *(b) Disclosure.* Pin a residual, X158 with a greenlet-switching finalizer, whose outcome is "Q silent". Correct lines 714, 718 and 2782, and appendix id 99. Name the exchange-and-count atomicity as a model axiom.
- Either way, add a G_ATOM `_register` case whose replaced callback has a finalizer, and state what criterion (b) expects there.

### M2. G_ATOM's criterion (c) sees only PyCFunction calls; a count after the call, or a gate read by bytecode, passes all 64 cases, so "no read or write of shared state happens outside the one call" and appendix id 99's witness are overstated

**Evidence.** `critic8/c2_gatom_bytecode_split.py` runs `atom7.py`'s own harness unchanged on two more frozen-text patches of `steps7.py` (`out_c2.txt`, both versions):
- **K11:** `_register` counts after its consuming call, through `_LOST.__iadd__([...])` and an inlined list comprehension. This is exactly F26's fault window. Result: **0 of 64 cases fail**.
- **K12:** `_unwind_on` reads its own-anchor gate by `in` and a subscript in statement 1, then gates on the precomputed bool. This is a test-then-act split across eval-breaker checks. Result: **0 of 64 cases fail**.
- K10, which uses `list.extend`, a method descriptor, is still caught.

**Why.**
- `sys.setprofile` reports `c_call` only for `PyCFunction` objects and method descriptors. A method-wrapper call, a subscript and `CONTAINS_OP` are invisible to it.
- X158b does not catch K11 either: its injector arms at `_register`'s PY_RETURN, which comes after the count.
- Only G_HYG's two-statement clause (lines 2004–2006) rejects both shapes.

**Statements to correct.**
- Line 2054, criterion (c): "So no read or write of shared state happens outside the one call".
- Line 2087: it "checks the implementation's own five steps for … shared-state access outside their one C call".
- Line 3027: id 99's witness lists "G_ATOM K10 and criterion (c)". The real witness for a count placed inside `_register` after the call is G_HYG.

**Fix.**
- Say that criterion (c) sees C-function calls only, and that bytecode-level access is G_HYG's.
- Cite G_HYG for id 99.
- Cheaply, strengthen (c) with the local CALL events G_ATOM already arms on the step's code: from the step's code, no CALL of anything except the vocabulary constructors, `from_iterable` and the consumer. That catches K11 but not K12, which stays G_HYG's.

### M3. Appendix id 107, "`_register` never writes S", cites a G_HYG clause that does not exist; the mutant passes G_HYG's text and all of G_ATOM

**The claim.** Line 3032 gives the witness as "G_HYG (`set_events` only in the other steps); G_ATOM state criterion (d)".

**What the text actually says.**
- G_HYG allows `set_events` in "the step functions", and `_register` is one of them (line 2010).
- G_HYG allows statement 1 to bind any `_MON[0][i]` (line 2005).

**Evidence.** `critic8/c5_register_clears_S.py` builds **K13**: `_register` with a gated `set_events(t, 0)` chained in front, its None swallowed by `_filter(None, …)`, which G_HYG allows. Every name it uses is on G_HYG's list, and `r` is unchanged. G_ATOM: **0 of 64 cases fail** on both versions (`out_c5.txt`). All nine `_register` cases start with the global event clear, so a clear is unobservable.

**Harm.** At X5 this mutant clears PY_UNWIND under another trace's open section. The result is an UNWIND_LOST note and an under-credit, not a silent loss. The problem is that the self-audit's witness claim is false.

**Fix.**
- Add a G_HYG clause fixing each step's `_MON[0]` indices, as M7 already writes them ("under the names shown", line 701):
  - `_unwind_on`: {0, 1, 2};
  - `_unwind_off`: {0, 2};
  - `_take`: {0, 5};
  - `_register`: {0, 4};
  - `_set_local`: {0, 3}.
- Add `_register` cases with the global event set.
- Correct id 107's witness.

### M4. G_ATOM's t1 part E and D2 floors are time-bounded; below a floor "the run is void", and no rule says what follows

**The rule.**
- Line 2084: part E needs at least 50,000 body samples. The prototype measured about 67,000–70,000, in a fixed 3 s (`rev5/t1_onecall_atomic.py` `part_e(seconds=3.0)`).
- Line 2085: D2 needs at least 5,000 closes in "3 s per form".

**The problem.**
- A machine about 30% slower, or a loaded CI host, voids G_ATOM.
- Line 2110 requires G_ATOM to pass before any scoring and for every `_VERIFIED` entry.
- Nothing says whether a void run may be repeated, or how often. That is judgement after the freeze, in the gate that everything else rests on.

**Fix.** Make both parts count-bounded ("run until 50,000 samples, or fail at T_max = 60 s"), or freeze a retry rule (for example, at most 3 runs, each committed).

### M5. X158's expected outcome contradicts itself (line 1573)

**The contradiction.**
- The outcome column says "in both variants: P PASS `{f:1}` with MONITOR_LOST".
- It ends: "In (b), P lacks the note".
- That last sentence describes revision 6, where the Q-first order leaves P without a note: `rerun_w7_*`, `cbrep_nocount Q-first` gives P_lost False, and spec Q-first gives P_lost True.

**Why it matters.** Read literally, an exam author gets two expected outcomes for variant (b).

**Fix.** "Without the count, (a) leaves Q and (b) leaves P without the note."

---

## NOTE

**N1. F25 is avoidable at no cost, and its rejection rationale is wrong (line 2820).**
- Line 2820 says "counting a reclaim's re-take before its registration … would open a window between the take and the count". That is true only for a separate statement.
- An append chained into `_take`'s own consuming call has no window: `_CONSUME(_map(_LOST_APPEND, _map(use_tool_id, …)))`. `use_tool_id` returns None, so each take appends once.
- That one rule would count every reclaim, re-take and rebinding at the take. It would close F25 (X157b would then note P). It would make the step-3 and E4 counts redundant, and would count harmlessly at a first acquisition.
- As the text stands, F25 is disclosed, pinned and fail-closed, so this is a design option, not a defect.

**N2. A13 can be witnessed deterministically, and EQUIVALENT_BY_SPEC would be false.**
- A13's mutant, a pending entry keyed by bare `id(frame)` without holding the frame, is observable whenever a dead frame's id is reused.
- `critic8/c3_a13_frame_id_reuse.py`: a frame materialised in a raising function and then dropped is reused by the next call of the same function **1000/1000** times on both verified builds, with gc on and off.
- So the SM1 "Unwitnessed rows" route should be the witness, not an equivalence argument. The spec can write the case itself, with the shape A13 already gives, instead of leaving the choice open.

**N3. A14 holds and is cheap to freeze.** `c4`'s depth sweep is deterministic and takes milliseconds: 61 depths around the boundary per step, and every trial either took full effect or raised before any effect. Adding it to G_ATOM would turn A14 from probe-only into gate-witnessed.

**N4. The "None previous callbacks count" rule has no named witness.**
- `c6`: X158 with the outside party registering **None** over styxx's PY_START callback. Under the spec, P and Q are both noted in both orders. Under a count-excluding-None mutant, both are silent in both orders, and Q's call is lost.
- No case in the list uses None, and G_ATOM's matrix has no None-previous case.
- G_HYG's name list makes the mutant hard to write in C: it needs the previous callback twice. So this is a coverage NOTE, not a hole. X158c costs one row.

**N5. The self-audit's method, classes and provenance.**
- The extraction keys on *must, never, always, cannot*. The false sentence behind M1, "Nothing runs between exchange i, its comparison and count" (line 714), is phrased with "Nothing" and was never a hit. The next audit should add *nothing, no, none, only, every*.
- Id 121 (line 905, "the machinery's correctness arguments never use the absence of an eval-breaker check between two bytecodes") is a property but is classed H. Id 56 (the N2 build disclosure) is classed H, not D.
- The committed `rev7/` has `audit_classify.py` but not the `audit_claims.json` it reads, nor `audit_claims_classified.txt`, both of which Appendix A cites as `rev7/…`. Only the scratch copy has them. Re-running the scratch copy gives the stated counts: P 104, G 81, N 32, H 27, D 25, C 18 and S 18, 305 in all.
- Sampled witnessed claims: of about 25 P, D and C rows checked, ids 99 and 107 do not hold as cited (M1–M3). The others checked (ids 8, 18, 45, 52, 57, 62, 70, 73, 76, 84, 87, 116, 125, 137, 143, 177 and 182) cite a case, a probe or a gate clause that does bear on the claim.
- V69's and X78f's mutant rows rest on reading (line 1837), although the appendix row for id 177 cites `rev7/w7_audit.py`, which runs V69's spec row only.

**N6. Bookkeeping.** "Totals. 20 rows: B1, M1–M5, N1–N9, H and F25–F29" (line 2826) lists and tables 21 rows.

**N7. Case-text details.**
- X137h (line 1568) calls both a tool and R's section "A" ("A closes. A unregisters its RAISE callback"). It also states only R's outcome and the tool id, not P's, Q's or S's, which follow from the text.
- V68's "within 1 s" is a timing criterion; mark it `envelope` in G_SEM's manifest.
- G_ATOM does not say what object an `_Opening`'s `frame` slot holds. The prototype uses `object()`; freeze that.

**N8. The refused interpreters used by the exam are unpinned.** "On 3.10 and 3.11 the runner executes X37 and every scoring-only case" (lines 1014, 1389) names no patch level or build. The builds should be recorded like the verified ones, since those outcomes "must equal the verified interpreters' ones".

**N9. One non-reproduced model output.**
- My first combined run, `m7_modelcheck.py mutants cbrep_nocount count_after_register retake_nocount rebind_count_none` (`rerun_m7_mutants_new.txt`), printed `rebind_count_none … NOT DETECTED`.
- Every later run detects it at `rebind2:` F0, LOSTNOTE=3, as `out_m7_mutants_rebind2.txt` says:
  - alone;
  - after each of the other three (`order_A`–`C`);
  - in-process after a full `retake_nocount` sweep;
  - under 30 hash seeds.
- The exact same four-mutant command, run again (`order_D.txt`), detects it. I could not reproduce the first result or find any shared state in the model that explains it; that run overlapped my other probes in time.
- Treat it as an unexplained, one-off output. The frozen mutant runs should each be executed twice and compared, and the text should not rest a mutant verdict on a single run.
- The verdicts the text states are reproduced.

---

## Answers to the brief

1. **The in-call `_LOST` count in `_register`.**
   - It is sound against faults, audit hooks, thread switches and greenlet switches from audit hooks, which is what the model enumerates and X158b shows.
   - It is not atomic with respect to the replaced callback's own deallocation. A finalizer can run, and switch greenlets, between the repair and the count (M1).
   - The rest of the count's consequences hold: fresh-id counts of five, RELOAD, X137h's rewrite, and E4's one rule.
2. **G_ATOM.**
   - The interface is sufficient and needs no judgement to build.
   - The 64-case matrix is well defined.
   - The interval criterion closes the "0 and 0" vacuity, and K4–K10 fail as stated.
   - It is not the witness the text makes it: bytecode-level splits (K11, K12) and a `_register` that clears S (K13) pass all 64 cases (M2, M3).
   - Its timing floors lack a void-run rule (M4).
3. **The self-audit.** Its counts reproduce. Two sampled "witnessed" claims are not witnessed as cited (ids 99, 107), one false sentence escaped its keywords, and its inputs are not committed (N5).
4. **A13 and A14.**
   - A13 is open by SM1's procedure, but a deterministic witness exists, and EQUIVALENT_BY_SPEC would be false (N2).
   - A14 holds, and can be frozen (N3).
5. **F25.** Correctly disclosed and pinned, and fail-closed. It is avoidable by a count inside `_take`'s call, and the stated reason for rejecting that option is wrong (N1).
6. **The new cases.**
   - X158 has a self-contradictory sentence (M5).
   - X158b, X154d, X156c/d, X157b/c, V67–V69 and R20–R22 are deterministic and reproduce on both versions.
   - V68 is timing-based (N7).
   - The None-previous rule has no named witness (N4).
7. **Model fidelity.**
   - It reproduces exactly and finds revision 6's B1.
   - It takes the exchange-and-count step as atomic, which CPython does not guarantee when a finalizer runs (M1), and the text does not list this as an axiom.
8. **Can an independent author freeze a deterministic exam from the text alone, with no judgement after the freeze?**
   - Yes, once M1–M5 are applied. All five are text edits: M1 alternatively takes a small mechanism change.
   - M4 is the only item that would otherwise force a post-freeze decision.
   - M1 is the only silent loss outside the disclosed residuals. It is fail-closed and hostile-shaped.
   - No over-credit, hang or corruption was found.

**Verdict: READY_FOR_EXAM_BRIEF** (conditional on M1–M5 being applied before the freeze; no item blocks writing the exam brief).
