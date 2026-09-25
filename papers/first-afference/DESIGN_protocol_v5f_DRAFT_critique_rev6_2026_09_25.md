# Critique of DESIGN_protocol_v5f_DRAFT_2026_09_25.md, revision 6 (seventh critic)

Target: `papers/first-afference/DESIGN_protocol_v5f_DRAFT_2026_09_25.md` (2,654 lines), revision 6. Line numbers below are that file's.

Evidence read:
- `protocol_v5f_design/rev6/`: mech6.py, m6_modelcheck.py, atom6.py, t1d2_discriminating.py, w6_witnesses.py, w6_greenlet.py, r6_b1_register.py, r6_m1_builtin.py, p_first_reconcile.py, p_h_backedges.py, and the outputs;
- the six earlier critiques;
- `protocol_v5_redteam_audit.json`, round_4.

Probes are in `scratchpad/v5f/critic7/`: `c1`–`c3`, a patched model copy `m6_fixcb.py`, outputs `out_c*.txt`, and re-runs `rerun_*.txt`. Interpreters: `rt3/venv3.12` (3.12.3) and `rt3/venv3.13` (3.13.12). No tracked file was modified.

**Counts: 1 BLOCKER-for-freeze, 5 MUST-FIX, 9 NOTE. Verdict: NOT_READY.**

---

## What was attacked, and what held

These held:

- **`_register`'s per-exchange gate and owner read (M7, code at lines 669–678, text at line 702).** The pipeline does what the text says, and the argument is sound on 3.12.3 and 3.13.12:
  - `map` pulls `compress` before `_EVENTS5` and `_CALLBACKS5`.
  - `compress` pulls its data (the infinite `repeat(t)`) before each selector, and stops when the five selectors run out, so no extra `get_tool` is made.
  - Once a gate fails, the remaining gates run back to back in C with nothing between them, so "skip" behaves as "stop".
  - The owner read follows the last exchange or the failing gates with no Python code in between.
  - So exchanges 1..n−1 landed on styxx's id, and at most exchange n landed elsewhere. `register_callback` on an unowned id does not raise (the range check only), so a free inside a hook gives a split with owner None, not an exception.
- **X154b, X154c, X137g, X137h, X137f, X156 and X157 in the prototype.** Each gives its stated outcome under the spec and differs under its single-rule mutant.
  - All reproduce **byte for byte** on both versions (`rerun_w6_*`, `rerun_r6_*`, `cat_*.txt` against the committed `out_*.txt`), greenlet 3.5.6 included.
  - The witnesses are deterministic in shape: no timing or race decides them.
- **F20.** A reconciliation in a process with no tool id ran `get_tool(None)` and raised TypeError (`rerun_p_first_reconcile_*`, both versions).
  - The guard at line 508 fixes it.
  - X36 kills the unguarded mutant, because it is the first enter of a fresh process.
  - No other step can run with `_TOOL[0]` None: `_reclaim` is guarded, and mints and openings exist only after `_TOOL[0]` is stored.
- **CPython #130279 (row H).** No backward jump in `_register`, `_take`, `_set_local` or the guarded tail, on both versions (`rerun_p_h_backedges_*`).
- **The binding check against the critic-6 shapes.** It refuses the `set_events` wrapper and a subclassed `itertools.chain`. Without it, the loss comes back (`rerun_r6_m1_builtin_*`).
  - `Py_TPFLAGS_IMMUTABLETYPE` distinguishes C types from class statements as claimed.
  - `builtin_function_or_method.__name__` is read-only, so a relabelled C function cannot pass as another.
- **The model check.**
  - `m6_modelcheck.py main` reproduces exactly on 3.12.3: 44 configurations, 83 revision-6 runs, 9,625,175 and 9,574,847 state hashes. The only difference is the trailing `done-main` line of the committed file, which the script does not print.
  - `hang` mode reproduces exactly on 3.13.12.
- **G_ATOM prototype and t1.**
  - `atom6.py` reproduces exactly.
  - t1 parts A, B, C and E give the same verdicts. Two-statement controls: A 5–6/1/1/1/5–6, E 201 and 189 clear.
  - D2 gives the same verdicts: one-call 0 and 0, Python-call control 2,715 and 4,074, revision 5's control 0 and 0.
- **Round-4 bookkeeping.** All 58 confirmed round_4 keys still appear in the spec (script check).

The attack found one silent loss that the text says cannot happen and that the spec's own model finds once a second tracer is added (B1). It also found that G_ATOM, the new premise gate, cannot be written from the spec's text without judgement, and can pass vacuously (M1).

---

## BLOCKER-for-freeze

### B1. X5's registration repairs a replaced callback for every trace but notes only the exiting one; any other live trace's loss becomes silent, contrary to L-MONITOR and the LOSTNOTE-completeness claim

**The rule.**
- X5's MONITOR_LOST test notes a loss when "some previous callback in `r` is not the corresponding member of `_CALLBACKS5` … The registration also repairs it for later traces" (line 553).
- The repair is silent for every *other* trace that lost calls while the callback was replaced. Only the exiting trace is noted, because nothing is counted in `_LOST`.
- Once P's exit has repaired the slot, Q's exit finds all five previous callbacks styxx's, `_LOST` unchanged, local events intact and no UNWIND_LOST flag.

**Evidence.**
- `critic7/c1_cbrepair_two_traces.py` on `mech6.py`, both versions:
  - Setup: tracers P and Q both declare f. An outside party replaces styxx's PY_START callback on styxx's id, which `register_callback` allows without owning the id. Then Q's section B calls f, and the call is lost.
  - `P-first`: `{'P_calls': {}, 'P_lost': True, 'Q_calls': {}, 'Q_lost': False}`. Q lost the call and is **not** noted. P lost nothing and is noted.
  - `Q-first`: Q is noted.
- `critic7/c2_model_cbrep_two_cores.py`:
  - The spec's own model has a single `cbrep` configuration, `cb/local: open(X) ∥ exit(X)` (m6 line 1008). It has one core, so it can never show this.
  - Adding the two-core configuration `open(Y) ∥ exit(X)` with `ext=('cbrep',)` gives **revision 6: LOSTNOTE=1 [LOST=2]** (revision 5: the same).
  - The same shape with `lclr` is clean, because X5 does not repair local events on shared mints.
- `critic7/c2b_model_cbrep_fix.py` + `m6_fixcb.py`:
  - One line in X5, "if `r` is complete and a previous callback is not styxx's, `_LOST[0] += 1`", makes the configuration clean.
  - It leaves the four `reg:` configurations and `cb/local` clean.

**Statements this falsifies.**
- Line 1342 (L-MONITOR): "The loss is silent only when the party that changed something restores it before any of these reads … replaces a callback and restores it before exit". Here the machinery restores it.
- Lines 734–737 ("What is lost"): "A call lost through an outside party is noted in one of three places". The third place, `_LOST` or taken by another tool, does not cover callbacks at all, and X5's callback test covers only the exiting trace.
- Line 2597: "Revision 6: 0 violations of any property … Every LOST hit is noted or MASKED". That holds only because no configuration combines `cbrep` with a second core.
- The M2 row (line 2523) presents `cbrep` as modelled.

**Why this blocks the freeze.**
- Same class as revision 5's B1: a normative disclosure sentence that no faithful implementation satisfies.
- An exam author who writes a residual case from L-MONITOR (P and Q live, callback replaced, Q's call lost) fails every faithful implementation. An author who leaves it out is exercising judgement. G5 requires residual outcomes "as documented".
- The loss is fail-closed (NOT_EXERCISED), so this is not an over-credit. It is a silent loss outside the disclosed residuals, which is what the brief asks about.

**Fix, one rule.**
- X5 step 2: when `r` is complete and some previous callback is not styxx's, `_LOST[0] = _LOST[0] + 1` under the mutex, so every trace live then notes MONITOR_LOST. This is the rebinding count's pattern (F22).
- Restate the reload paragraph (line 440): after a reload, the first exit's count then notes every live trace, not "once".
- Add a mutation row and a subprocess case: P and Q, callback replaced, Q's call lost, P exits first, and Q must carry MONITOR_LOST.
- Add the two-core `cbrep` configuration to the model and to "What is still not enumerated" (line 2638).

---

## MUST-FIX

### M1. G_ATOM cannot be written from the spec alone as a frozen, objective harness, and its pass criterion can be met vacuously

1. **It conflicts with M10 and the harness rules.**
   - G_ATOM "reads the step functions only through `_v5_faultpoints()` … with registry and tool states prepared through the public API and `sys.monitoring`" (line 1985).
   - Several required cases need private state, which M10 (line 802) and "What the exam may read" (line 1372) forbid:
     - `_unwind_on(o)` needs an `_Opening`. Its constructor signature is unspecified.
     - "o's anchor registered or not", "other armed openings registered" and `_unwind_off` "with the key registered" need `_ANCHORS`.
     - The consumer identity (`_CONSUME`) is needed to open the interval.
     - Handing the id back after a "not named" case needs `_TOOL_NAME`, because `_named` is an identity test. `atom6.py`'s `give_back` uses `mech.NAME`, and without it styxx loses its id for the rest of the harness process.
     - The pass line reads `_Opening.__dict__` and `_Core.__dict__`.
   - The prototype sidesteps all of this by constructing `mech.Opening` objects and writing `mech._ANCHORS` directly.
2. **The case matrix is not defined** (line 1987).
   - "`_unwind_on` with the id named or not, o's anchor registered or not, the event set or clear, and other armed openings registered" does not say whether this is a product (8+ cases) or one factor at a time.
   - `atom6.py` runs 4 cases, with "other armed openings" always present and never absent or unarmed.
3. **Vacuous pass.** The criterion is "zero PY_START and zero audit events inside the interval" (line 1988), and nothing requires the interval to open.
   - `critic7/c3_gatom_vacuous.py`, both versions:
     - an `_unwind_off` split into two statements through a Python helper, or one consuming with a deque built at call time, gets `interval opened 0` → **PASS**;
     - the spec's `_unwind_off` opens it once.
   - G_HYG would catch these shapes statically. But G_ATOM is defined as the dynamic check of what G_HYG cannot see, and as written it certifies nothing about a step whose consumer it never observed.
   - K1–K4 exercise only the instruments on the harness's own pipelines, not the hookup to the implementation.
   - K4 cannot tell revision 5's `_register` from revision 6's: both raise 5 audit events, and the revision-6 case "passes" with the same count.
4. **Contradiction on the slot check.**
   - M1 (line 462): G_ATOM checks `_Opening.__dict__[n]` for `armed`, `core` and `flags`. `_Opening` has no `flags` slot.
   - G_ATOM (line 1988): `armed`, `core` and `frame` on `_Opening`, plus `_Core.flags`.
5. **Scope overstated.**
   - The implementation-facing part of G_ATOM checks only PY_START and audit events in the interval.
   - Gc, signals and threads are tested only on t1/D2's own reference pipelines, which test CPython and not the implementation's steps.
   - Weakest point 2 (line 2649) says "with the instruments, gc and signals it arms".
   - The frozen t1/D2 parts have no pass thresholds: minimum trials or iterations, and the fact that part A's BRANCH row fires 0 events for the one-call form on both versions (`rerun_t1_*`) and so is vacuous.

**Fix.**
- Name in M10 the private names G_ATOM may read: `_ANCHORS`, `_TOOL`, `_TOOL_NAME`, `_CONSUME`, `_list`, `_Opening`, `_Core`. Specify that an `_Opening` is built by `_Opening.__new__` with slots assigned.
- Enumerate the case matrix.
- Add "the interval opened exactly once and closed" (and, for `_register`, the exchange count equals `len(r) − 1`) to the pass criterion.
- Fix the slot list.
- Freeze numeric thresholds for the t1/D2 parts, and mark the BRANCH row as non-evidence.

### M2. The version restriction to 3.12.3 and 3.13.12 is not carried through; the exam's interpreters are unpinned

M0 (line 388) refuses every patch level but `_VERIFIED`. Elsewhere the text still says otherwise:
- **Line 973 (Version policy):** "Validated on 3.12.3 and 3.13.12; … results produced on other patch levels are reported as unvalidated". Under M0 no result can be produced on other patch levels.
- **Line 1358 (Exam harness, Interpreters):** "The full exam runs on CPython 3.12 and 3.13", with no patch level. Run on, say, 3.12.11, every tracing case refuses UNSUPPORTED_VERSION.
- **Lines 12, 178 and 185, and G_XVER (line 2009):** "3.12 and 3.13" as the supported or exam interpreters. Line 976, "Every exam case has the same expected outcome on 3.12 and 3.13", has the same problem.
- **Line 2029:** "Check each patch level of 3.12 and 3.13, not only 3.12.3 and 3.13.12". This is stale advice for a spec that now refuses them.
- **Line 984 and G_XVER:** the refused-interpreter subset lists only 3.10 and 3.11. No case pins what the exam does on an unlisted 3.12 or 3.13 patch level. X37b simulates it with a faked `version_info`.

**Fix.**
- Pin the exam, G2, G_CLOSURE, G_FI, G_SIG and G_XVER to exactly the `_VERIFIED` interpreters.
- Rewrite line 973 ("other patch levels refuse").
- Update lines 12, 178, 185 and 2029.

### M3. The M1 binding check is not re-run after `importlib.reload`, so line 399's "a wrapper installed after the binding is never called by the machinery" is false

- The reload paragraph (line 440) makes the whole one-call vocabulary (`_map` … `_CALLBACKS5`) plain bindings that a reload re-binds, while `_MON` is kept through `globals().get`.
- M0 runs the check only when "the first `coverage_trace()` binds `_MON`" (line 395). After a reload, `_MON[0]` is already set, so the spec does not say whether the vocabulary is checked again.
- A pure-Python subclass or wrapper of `itertools.chain`, `map`, `operator.setitem` or `list` installed after the first `coverage_trace()` and before a reload is therefore bound by the reload and never checked. That is exactly M1's threat, and it breaks U1 in the same way.
- An exam author must choose between "check at every `coverage_trace()`" and "check only when `_MON` is bound". The two give different outcomes for a reload case.

**Fix.**
- Run the vocabulary check at every `coverage_trace()` (it is cheap), or whenever the module's vocabulary differs from the one last checked.
- Correct line 399.
- Add a reload variant of X156b.

### M4. X154b's five trials are not isolated by the text; run in one subprocess as written, trials 3–5 refuse MONITOR_BUSY

- X154b (line 1529): "in a fresh subprocess … trials k = 1 to 5 … The hook stays installed for the rest of the subprocess".
- Each trial ends with the other tool owning styxx's id:
  - After trial 1, id 4 is foreign, so trial 2's tracer rebinds to id 3.
  - After trial 2, ids 3 and 4 are both foreign, so trial 3's enter raises MONITOR_BUSY.
- The prototype avoids this with `free_all(); mech.reset()`, which frees styxx's own id and sets `TOOL[0] = None` (w6_witnesses.py). No exam can do that through the public API.
- If the author instead frees the other tool's id between trials:
  - the next enter reclaims and counts, which is still consistent with the expected `{f:1}` plus MONITOR_LOST;
  - but the spec does not say to do this, nor that the other tool unregisters its callbacks first (the Fault-tools rule, line 1383, covers only ids 3 and 5).
- The same kind of gap exists for how the case reads "its callbacks" (there is no getter). The prototype exchanges and restores, which raises two more audit events per event.

**Fix.** Either one fresh subprocess per trial, or a stated inter-trial cleanup: the other tool sets its events to 0, registers None for each of the five events and frees its id. State the callback-read method.

### M5. m6_modelcheck.py's fidelity and coverage are overstated in three places

1. **`cbrep` and `lclr` run with one core only** (m6 line 1008). This hides B1 (see `c2`). The M2 row and line 2597 present outside callback and local-event changes as modelled.
2. **E4's re-take of the same id.**
   - Spec E4 (line 528): "for a usable id: if `_TOOL[0]` is set (a *rebinding*) … `_LOST[0] += 1`". Read literally, this counts a re-take of the *same* id in the fall-through loop, for example after a reclaim whose registration was split with owner None.
   - `mech6.py` line 442 counts only `t is not None and t != i`.
   - The model's E4K/E4B (m6 lines 558–581) never retries the same id; it swaps to the other.
   - The spec, the prototype and the model therefore implement three different rules for this path. The literal spec rule is the safe one.
   - Say which rule is meant, call it by its right name (a re-take, not a rebinding), and make `mech6` and the model match.
3. **What is still not enumerated.** Line 2638 omits both of the above, and the fact that registrations at E4 and at the reclaim are never combined with a second live core in the `reg:` configurations except `reg: open(Y) ∥ exit(X)`.

---

## NOTE

- **N1. Holes in the binding check.**
  - `_CONSUME`: "`__self__` is a `collections.deque`" (line 397) does not say `type(...) is` against the real `_collections.deque`, nor `maxlen == 0`.
    - `mech6`'s `_c_func` compares only `type(s).__name__ == 'deque'`, so a Python subclass named `deque` passes.
    - `extend` stays C, so no Python code runs, but a subclass that ignores `maxlen` retains every pipeline value.
  - `_VALUES`'s name is not checked, so `dict.keys` would pass. This is harmless because `dict` is immutable.
- **N2. `_VERIFIED` is keyed on the version tuple, not the build.**
  - Distribution builds that keep "3.12.3" while backporting C fixes (Ubuntu 24.04's `3.12.3-1ubuntu0.x`) pass M0 without G_ATOM ever running on them.
  - The verified 3.12.3 is itself an Ubuntu GCC 13.3 build.
  - Disclose this, or record a build identifier with each G_ATOM run.
- **N3. "Always reports it" is overstated for E4** (line 2500; L-MONITOR line 1345).
  - At a first acquisition or adoption with no live trace (X154c), the foreign tool's replaced PY_UNWIND callback is reported only in `r` and never surfaced. X154c pins "no MONITOR_LOST".
  - The residual itself is disclosed, but "reported and noted" is true only at X5 and for traces live at the split.
- **N4. Audit-hook faults are witnessed at X5 only.**
  - X157 covers k=2 at X5, and X154b sweeps only X5. X154c covers E4 at k=5.
  - A raising or yielding hook inside the reclaim's registration, whose outcome is stated in the Tool acquisition prefix and in M3 step 3 ("the next reconciliation re-takes and counts"), has no case.
  - G_FI's INSTRUCTION injector cannot place a fault inside `register_callback`, so G_FI's "every fault point is clean" does not cover these points.
  - The model covers them; the exam does not.
- **N5. Environment pins.**
  - "greenlet 3.5.6" and "coverage.py 7.16" (line 1390) are pinned by version only: no wheel hash and no source. Elsewhere the spec cites coverage.py 7.16.1.
  - X137f's prototype uses `mech6`'s bare reconciliation as g2's transaction; the case specifies Y's enter.
  - X137g's Q half (Q joins f, `{f:1, g:1}` and no note; both NOT_EXERCISED under the mutant) is reading-only. The prototype's Q declares only g ("P's shape").
  - Both expected outcomes follow from the text.
- **N6. X37b and X156 details.**
  - X37b says "before `coverage_trace()`" but not "before `import styxx.protocol`". An implementation reading the version at import would fail it. M0 implies a call-time read, so say so.
  - X156 quotes a refusal text ("set_events is not the C builtin"), but the harness passes a violation on the code prefix only (line 1371). Say whether the text is checked.
- **N7. Provenance.**
  - `out_m6_mutants_b.txt` is not the stated `detach_nulls … prune_credit_stop` run. It continues through `reg_rev5 … blind_read_gated` and has no terminator, so the runs were not disjoint.
  - `out_m6_main.txt`, `out_m6_hang.txt` and the mutant files end in `done`/`done-main` lines that the script does not print.
  - `rev6/rev6_section.md` is a stale draft. It differs from the committed section at lines 5, 41 and 109.
  - The verdicts are unaffected.
- **N8. Cosmetic contradictions.**
  - Weakest points are numbered 1–5, 7, 6 (lines 2647–2654).
  - F24 is listed before F23 (lines 2644–2645).
  - X5's comment "The registration also repairs it for later traces" (line 553) should, after B1's fix, say "and counts it".
- **N9. Re-runs.** Every revision-6 output reproduces:
  - exactly for `atom6`, `w6_witnesses`, `w6_greenlet`, `r6_b1_register`, `r6_m1_builtin`, `p_first_reconcile`, `p_h_backedges`, `m6 main` and `m6 hang`;
  - with the same verdicts for the timing-based t1 and t1d2 counts.

---

## Answers to the brief

1. **Registration hardening (`_register`).** It is sound as specified: at most one exchange lands on another tool's id, and the owner read reports it. What it misses is a sibling case: X5's *repair* of a callback replaced by a party is not counted (B1).
2. **The builtin binding check.** It is correct for the critic-6 shapes. It has a reload hole (M3) and underspecifies `_CONSUME` (N1).
3. **G_ATOM.**
   - The controls exercise the instruments, not the hookup to the implementation.
   - The pass criterion can be met vacuously.
   - The harness needs private state that M10 forbids, and its case matrix and slot list are undefined or contradictory.
   - So it is not yet frozen and objective (M1).
4. **The version restriction.** It is consistent in M0, the reason codes and over-blocking #6. It is inconsistent in the version table, the exam harness, G_XVER and the summaries (M2).
5. **F20.** Correct and witnessed.
6. **New witnesses.** X137f–h, X154b/c, X156/b, X157 and X37b are deterministic in shape and reproduce exactly.
   - X154b's trial isolation needs a rule (M4).
   - greenlet is pinned by version only (N5).
   - X37b and X156 have small ambiguities (N6).
7. **m6's fidelity.** It is faithful to M7's registration boundaries and reproduces exactly. Its outside callback and local-event kinds never meet a second core, which hides B1. Its E4 same-id re-take matches neither the spec nor `mech6` (M5).
8. **Can an independent author freeze a deterministic exam from the text alone?**
   - Not yet: B1 puts a false disclosure into the residual set, G_ATOM's harness needs judgement (M1), the interpreters are unpinned (M2), the reload check is unspecified (M3), and X154b's trials are not isolated (M4).
   - All are fixable with text, one counting rule, one model configuration and a tightened G_ATOM.
   - The rest of the revision-6 case text is deterministic.

**Verdict: NOT_READY.**
