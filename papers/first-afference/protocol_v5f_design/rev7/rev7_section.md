
---

## Revision 7: critique items and their resolution

This section answers `DESIGN_protocol_v5f_DRAFT_critique_rev6_2026_09_25.md`, the seventh critic. Its verdict was NOT_READY: 1 BLOCKER-for-freeze, 5 MUST-FIX and 9 NOTE. The critic confirmed revision 6's registration bound, its binding check, F20, the #130279 constraint and every revision-6 witness, all byte for byte. It found one silent loss that the text said could not happen (B1), and a premise gate that could not be written without judgement and could pass vacuously (M1).

The section has these parts:
- what changed and what was rejected;
- one row per item, in the critique's order, then the #130279 check and the findings made while resolving;
- the revision-7 model check;
- the weakest points left.

A self-audit of every normative claim follows as an appendix.

The "verified" column cites probes under `/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/rev7/`, abbreviated `rev7/`, with outputs in `rev7/out_*.txt`. Each was run on CPython 3.12.3 (`rt3/venv3.12`) and 3.13.12 (`rt3/venv3.13`) with the same outcome unless the row says otherwise. The model check `m7_modelcheck.py` is interpreter-independent and was run once, on 3.12.3.

`rev7/mech7.py` is `rev6/mech6.py` copied with revision 7's rules, each behind a single-rule mutant. It also adds mint joining, which `mech6.py` lacked (F27). Revision 5's and revision 6's witness files, re-run on it through module aliases (`rev7/run_prev_on_mech7.py`), give the same verdicts for every row on both versions. The only exceptions are four label or count differences explained where they occur:
- `out_w5_on_mech7_*`: the `_register` sweep has 67 trials instead of 49, because its pipeline grew, and still 0 failing;
- `out_b1_on_mech7_*`: `r6_b1_register.py` prints revision 7's `r`, which no longer lists previous callbacks;
- `out_w6_on_mech7_*`: X137h's revision-6 mutant row now also notes P (F28);
- the tool name, and the patched-sleep count of revision 5's `time_at_call` row, which is timing.

`critic7/` is the seventh critic's probe directory. "Reading" means the resolution follows from the text and needed no execution. As before, no v5f implementation or `ref_v5f.py` exists, so every result is of a model, of M7's step functions as written (`rev7/steps7.py`), or of CPython itself.

### What changed, and what was rejected

**B1: the repair is counted, inside the registration's own C call.** The critic's diagnosis holds: `critic7/c1` reproduces on `mech6.py`, and `critic7/c2` and `c2b` reproduce on the model, all three exactly (`rev7/out_c1_rerun.txt`, `out_c2_rerun.txt`, `out_c2b_rerun.txt`). The critic proposed one rule: X5 increments `_LOST` after its registration returns, when `r` is complete and a previous callback was not styxx's. Revision 7's model, with the critic's two-core configuration and one fault, finds that this still loses the note. An asynchronous exception between the registration's return and the increment leaves the slot repaired and uncounted, and the other trace's loss is silent again. The trace: `rev7/m7_modelcheck.py`, `cb2: open(Y) ∥ exit(X) [cbrep, F1]`, mutant `count_after_register`, LOSTNOTE 1; on CPython, X158b.

So revision 7 moves the count into `_register`'s one consuming call. `_LOST` becomes a list read as `len(_LOST)`. For each exchange whose previous callback `is not` the one styxx registers, `_LOST_APPEND(True)` runs in C before the pipeline pulls the next gate. No fault, audit hook, thread switch or greenlet switch can then separate a repair from its count.

`r` becomes `[None] * k + [owner]`. It is complete iff `owner is _TOOL_NAME`, which implies five exchanges, because a failed gate is followed by the owner read with nothing between them. X5 reads `len(_LOST)` after its own registration, so the third note source of revision 6 folds into the `_LOST` test.

The consequences, each stated in the text:
- the reload paragraph is restated: every trace live at the first exit after a reload notes MONITOR_LOST;
- "What is lost" gains the callback and local-event places and names every silent shape;
- a registration onto a fresh id counts five (its previous callbacks are None). That is harmless, but it makes X137h's revision-6 shape note P without the rebinding's count, so X137h is rewritten to a shape that isolates that count (F28).

Cases: X158 (the critic's shape) and X158b (the fault after the registration). Mutation rows: `cbrep_nocount` and `count_after_register`.

**M1: G_ATOM made objective.**
- **The G_ATOM interface.** A frozen set of private names that G_ATOM alone may read (M10): `_ANCHORS`, `_TOOL`, `_TOOL_NAME`, `_CONSUME`, `_list`, `_Opening`, `_Core`, `_EVENTS5`, `_CALLBACKS5`, `_LOCAL` and `_LOST`. Openings and cores are built with `__new__` and slot assignment.
- **The case matrix.** Enumerated as products: 64 cases.
- **Four pass criteria per case.** (a) The consumer is called exactly once. (b) Inside that call, no Python code runs and no audit event is raised, except `_register`'s one per exchange. (c) Outside it, no Python code runs and no C call is made except the consumer's and `chain.from_iterable`. (d) The state at the consumer's call equals the state before the step, and the state after equals the effect the spec's rule gives for that gate outcome.
- **The slot list.** Fixed to `armed`, `core`, `frame` on `_Opening` and `flags` on `_Core`.
- **Hookup controls K4–K10.** Frozen patches of `ref_v5f.py`, each of which must make the run fail. They include the critic's two vacuous shapes (K5, K6), revision 5's `_register` (K4, which now fails on what distinguishes it from revision 6's) and the critic's post-call count (K10).
- **t1 and D2 get numeric floors.** The BRANCH row is marked as non-evidence.
- **Scope.** What the gate does and does not show is stated, and weakest point 2 of revision 6 is corrected.

**M2: the verified interpreters, everywhere.** "3.12 and 3.13" is replaced by the verified interpreters (3.12.3 and 3.13.12) at every normative site. That covers the grafts, the Delta table, the version table (with a new row for the other patch levels), the exam's interpreters, G2, G_XVER, G_FI, G_SIG, G_SEM, SM2, SM3, G_CLOSURE, the P1 retro and round-5 item 2. The exam runs on exactly the `_VERIFIED` interpreters, with their builds recorded. X37b pins the patch-level refusal, so the exam needs no real unverified interpreter.

**M3: the binding check runs at every `coverage_trace()`.** It reads the vocabulary as the module binds it now and `_MON` as bound. Line 399's claim is corrected. X156c is the reload variant.

**M4: one subprocess per trial.** X154b's five trials each run in their own subprocess, and the callback-read method (exchange and restore, hook disarmed) is stated. The harness rules add the per-trial rule for any case whose trials change tool ownership.

**M5: the model is extended.**
- Two-core configurations for callback replacement (the unwind callback, and the entry callback as a new kind) and for a local-events clear.
- A greenlet switch and a re-entered exit with a replaced callback.
- Registrations at E4 and at the reclaim with a second live core, a raising hook and a repeated free.
- An initial state in which the other id still carries styxx's callbacks.
- The three E4 counting rules are reconciled into one, stated in E4 ("The one E4 counting rule"): while `_TOOL[0]` is set, every take that ends in a complete registration is counted once, whether it is a reclaim, a rebinding or a re-take of the same id. `mech7.py` and the model implement exactly that. The same-id re-take is modelled and witnessed (X154d).

**N1–N9.** Each is fixed as its row says. Found while resolving: F25–F29.

Considered and rejected:
- **The critic's B1 form, a count in X5 after the registration.** It leaves a fault window between the repair and the count (above; `count_after_register`; X158b). The in-call count closes it at no extra call.
- **Excluding None previous callbacks from the in-call count**, so that a fresh id counts nothing. A party that registers None over styxx's callback removes it, which is a loss, and must count. Excluding None without a second pass over the previous callbacks needs a Python-level or hashing test inside the pipeline, which the premise forbids. The cost is redundancy at a first acquisition, adoption or rebinding, which changes no record, plus X137h's rewrite.
- **Counting a reclaim's re-take before its registration**, which would note a loss-free free even when a raising hook cuts the registration short (F25). It would open a window between the take and the count, reachable by an asynchronous exception or a signal-driven greenlet switch. The close's ungated read already notes every call lost while the id was freed (X157c). F25 is disclosed and pinned (X157b) instead.
- **Keying `_VERIFIED` on the build** (N2). It would refuse every rebuild of a verified version. The build is recorded and disclosed instead.
- **M3's alternative, re-checking only when the vocabulary changed since the last check.** Checking every time costs about 5 µs and needs no state.
- **M4's alternative, an inter-trial cleanup inside one subprocess.** A per-trial subprocess needs no cleanup protocol, and it matches how X36 and X142 already isolate tool ownership.
- **Freezing an `_Opening` constructor signature** for G_ATOM. `__new__` and slot assignment need none.

**Totals.** 20 rows: B1, M1–M5, N1–N9, H and F25–F29.
- B1 is resolved by mechanism: one counting rule, placed inside the registration's call, stronger than the critic's proposal.
- M1–M5 are resolved as the critique asked, with the choices above.
- The nine NOTEs are fixed.
- Five findings are recorded.

Rejected: the critic's exact B1 form (superseded), and the alternatives listed above.

| # | critique item | what changed (sections) | how it was verified |
|---|---|---|---|
| B1 | X5 repairs a callback replaced by an outside party for every trace but notes only the exiting one, so another live trace's loss is silent; L-MONITOR, "What is lost" and the rev-6 "0 violations" false | `_register` counts each exchange whose previous callback is not styxx's, in C, inside its consuming call (`_LOST` is a list; `_is_not`, `_LOST_APPEND` join the vocabulary and the binding check; M1, M0, M7 "The registration", M3 step 3, M5 X5, G_HYG). The reload paragraph is restated: every trace live at the first exit after a reload notes it. "What is lost" and L-MONITOR name the callback and local-event places and every silent shape. The MONITOR_LOST reason row is updated. Cases X158 and X158b; mutation rows; "What is still not enumerated" | `critic7/c1` on `mech7.py` (`rev7/c1_on_mech7.py`): both orders note both traces; with `cbrep_nocount` the critic's result returns. `rev7/w7_witnesses.py` X158: spec, P `{f:1}` and Q `{}`, both MONITOR_LOST; revision 6's rule, Q silent in (a). X158b: a fault right after P's registration, and Q is still noted; with `count_after_register` or no count, Q is silent. RELOAD: two traces live across a reload both note it, and only the first does without the count. `rev7/m7_modelcheck.py`: the `cb2:` configurations; revision 6 violates LOSTNOTE in 7 runs and revision 7 in none. `count_after_register` gives LOSTNOTE with one fault |
| M1 | G_ATOM needs private state M10 forbids; its case matrix is undefined; it passes vacuously (c3); K4 cannot tell revision 5's `_register` from revision 6's; the slot list contradicts itself; its scope is overstated; t1 and D2 have no thresholds | M10 gains the frozen G_ATOM interface. G_ATOM is rewritten: a 64-case matrix, criteria (a)–(d), instrument controls K1–K3, hookup controls K4–K10, t1 and D2 floors, the BRANCH row as non-evidence, the scope stated, and the build recorded. M1's slot sentence is fixed. Weakest point 2 of revision 6 is corrected. The Process gate states what "passes" means | `rev7/atom7.py` on `rev7/steps7.py` (M7's steps as written), one process per variant: 64 of 64 cases pass on both versions; K1–K3 detected; K4 fails 9 cases, K5, K6 and K7 24 each, K8 3, K9 3, K10 9. The critic's c3 shapes (K5, K6) now fail criterion (a) (`critic7/out_c3.txt` showed them passing `atom6.py`) |
| M2 | The restriction to 3.12.3 and 3.13.12 is not carried through (version table, exam interpreters, G_XVER, summaries, round-5 advice); no case for an unlisted patch level | Every normative "3.12 and 3.13" becomes the verified interpreters (listed above). The version table gains a row that refuses every other 3.12.x and 3.13.x. The exam's interpreters are pinned. X37b is the pinned case for the patch-level refusal | Reading; `rev7/w7_witnesses.py` X37b |
| M3 | The binding check is not re-run after `importlib.reload`, so "a wrapper installed after the binding is never called" is false | M0: the check runs at every `coverage_trace()`, on the vocabulary as bound now and on `_MON` as bound. The sentence is corrected. Case X156c; over-blocking #6; the UNSUPPORTED_VERSION row | `rev7/w7_witnesses.py` X156c: the spec refuses after the reload; `check_once` binds the subclass. `rev7/out_bind_cost.txt`: 4.8–4.9 µs per check |
| M4 | X154b's trials are not isolated: run in one subprocess, trials 3–5 refuse MONITOR_BUSY | X154b runs one fresh subprocess per trial, and the callback-read method is stated. The harness rules add the per-trial rule | `rev7/w7_witnesses.py` X154b, one subprocess per trial: the spec replaces exactly the k-th callback; revision 5's form 6 − k; identical to `rev6/out_w6.txt` |
| M5 | `cbrep` and `lclr` run with one core only; E4's re-take of the same id has three rules; "What is still not enumerated" omits both | Model: CONFIGS7 (14 configurations: `cb2:`, `cb2+greenlet`, `cb2+re`, `reg2:`, `rebind2:`), a replaced entry callback, a same-id re-take at E4. E4 states one counting rule, and the prototype and the model match it. The not-enumerated list is updated below | `rev7/out_m7_main.txt`, `out_m7_main_rebind2.txt`, `out_m7_table.md`: 58 configurations, 99 runs per revision. Revision 7: 0 violations (10,465,412 state hashes). Revision 6: LOSTNOTE in the 7 callback-replacement runs, clean elsewhere. X154d: the re-take counted; `retake_nocount` silent |
| N1 | `_CONSUME`'s deque not checked by type or `maxlen`; `_VALUES`'s name not checked | M0: the deque's type passes the C-type test with `('collections', 'deque')` and `maxlen == 0`; `_VALUES.__name__ == 'values'`. Case X156d | `rev7/w7_witnesses.py` X156d: the spec refuses; `deque_by_name` binds a subclass with `maxlen` None |
| N2 | `_VERIFIED` keyed on the version, not the build | M0 "What `_VERIFIED` does not key on", G_ATOM's output, the exam's interpreters, over-blocking #6 and Scope of testing disclose it and record the build | Reading; `rev7/out_atom7_*.txt` records the builds (3.12.3 GCC 13.3.0 of Mar 3 2026; 3.13.12 GCC 13.3.0 of Feb 4 2026) |
| N3 | "Always reports it" overstated for E4 | "The registration" and L-MONITOR say that a split at a first acquisition or adoption surfaces nowhere (X154c) | Reading |
| N4 | Audit-hook faults witnessed at X5 only | New cases: X154d (a hook that frees the id inside the enter's reclaims, and one that has another tool take it) and X157c (a raising hook inside a reclaim, with a lost call). Residual X157b (the same, loss-free). F25 found | `rev7/w7_witnesses.py`: X154d, X157b, X157c as stated. `rev7/m7_modelcheck.py`: `reg2:` with F1 clean for revision 7 |
| N5 | greenlet and coverage.py pinned by version only; 7.16 against 7.16.1; X137f's prototype used a bare reconciliation; X137g's Q half unshown | The environment pins four wheels by sha256 (coverage.py 7.16.1 throughout). `rev7/w7_greenlet.py` runs X137f with Y's enter. `mech7.py` joins mints (F27), and `rev7/w7_witnesses.py` runs X137g in full | Wheel hashes computed on the downloaded wheels (`rev6/wheels31*`, `rev7/wheels`), equal to PyPI's. `rev7/out_w7_greenlet_*`: the same verdicts as `rev6/w6_greenlet.py`. X137g: spec P `{f:1}`+ML, Q `{f:1, g:1}`; mutant P `{}`, Q `{g:1}` |
| N6 | X37b "before `coverage_trace()`" but not before import; X156 quotes a text the harness never checks | M0 reads the version at call time. X37b replaces `sys.version_info` after import. X156 checks the code prefix only | `rev7/w7_witnesses.py` X37b on both versions |
| N7 | Provenance: `out_m6_mutants_b.txt` overlaps other runs and lacks a terminator; `done` lines not printed by the script; `rev6/rev6_section.md` is stale | Recorded here. `rev6/out_m6_mutants_b.txt` is the concatenation of the second and third revision-6 mutant runs, captured into one file; the verdicts in `out_m6_mutants.txt` are unaffected. The `done` and `done-main` lines were appended by the shell wrapper, not by the script. `rev6/rev6_section.md` was a working draft, superseded by the committed section. Revision 7's outputs carry no appended lines, and `rev7/rev7_section.md` is this section's draft | Reading (the critic's diffs) |
| N8 | Weakest points numbered 1–5, 7, 6; F24 listed before F23; X5's "also repairs it" | Renumbered; F23 before F24; X5's third note source rewritten (B1) | Reading |
| N9 | Every revision-6 output reproduces | Nothing to change | The critic's re-runs; `rev7/run_prev_on_mech7.py` |
| H | CPython #130279: no machinery state may depend on a `finally` or with-exit across a loop back-edge | **Kept.** `_register`'s revision-7 pipeline, and the four other steps as M7 writes them, have no backward jump. `_run`'s and `_run_async`'s try bodies and `finally`s are unchanged. The binding check at every `coverage_trace()` runs in no `try` body | `rev7/h7_backedges.py` on `steps7.py`, both versions: none in any of the five steps |
| F25 | (found while resolving N4) A raising hook inside a reclaim's registration leaves the free uncounted, so a loss-free live trace is not told of it; revision 6's L-MONITOR said every free is noted | M3 step 3, L-MONITOR, the MONITOR_LOST row and the per-transition prefixes state it. X157b pins the residual, and X157c shows that a lost call is still noted | `rev7/w7_witnesses.py` X157b, X157c |
| F26 | (found in the model) The critic's B1 fix leaves a fault window between the repair and its count | The count moves inside `_register`'s call (B1 above). G_ATOM's K10 and X158b guard it | `rev7/m7_modelcheck.py`: `count_after_register` gives LOSTNOTE with one fault; `rev7/w7_witnesses.py` X158b |
| F27 | (found while resolving N5) `mech6.py` re-minted a function a second tracer declared instead of joining its mint, so the second tracer took the function away from the first | `mech7.py` joins mints and drops holdership at exit, as M4 and M5 specify. Revision 6's verdicts are unchanged on it | `rev7/out_w6_on_mech7_*`: identical to `rev6/out_w6.txt` |
| F28 | (found while resolving B1) The in-call count also notes X137h's revision-6 shape, because the rebinding onto the fresh id 3 counts five None callbacks, so X137h no longer isolated the rebinding's count | X137h is rewritten: a rebinding onto an id that still carries styxx's callbacks, where only the rebinding's count notes the loss. The model gains `rebind2:` | `rev7/w7_witnesses.py` X137h7: spec R noted; `rebind_count_none` silent. `rev7/m7_modelcheck.py`: `rebind_count_none` gives LOSTNOTE 3 in `rebind2:` |
| F29 | (found by the self-audit) The Tool acquisition prefix said a tool left named ours with missing callbacks "is adopted and re-registered at the next enter"; that holds only when `_TOOL[0]` is None | The prefix is corrected: with `_TOOL[0]` set, the next exit's X5 repairs it | Reading; `rev7/w7_witnesses.py` X157b (R's exit repairs and passes) |

### The revision-7 model check (M5)

`rev7/m7_modelcheck.py` is `rev6/m6_modelcheck.py` with:
- `rev=7`: the in-call count (a registration exchange whose previous callback is not styxx's appends in the same step) and the same-id re-take at E4;
- mutants `cbrep_nocount` (revision 6), `count_after_register` (the critic's form) and `retake_nocount`;
- a new outside kind, `cbrep0`, which replaces the entry callback;
- an initial state in which the other id still carries styxx's callbacks;
- fourteen configurations, CONFIGS7.

`main` runs revisions 6 and 7 over all 58 configurations.

| configuration (CONFIGS7) | budgets (F / I / X / W) | rev 6 | rev 7 |
|---|---|---|---|
| cb2: open(Y) ∥ exit(X) [cbrep] | 0 / 0 / 1 / 0 | LOSTNOTE=1  [LOST=2] (1,277 states) | ok  [LOST=2] (1,277 states) |
| cb2: open(Y) ∥ exit(X) [cbrep0] | 0 / 0 / 1 / 0 | LOSTNOTE=1  [LOST=2] (1,308 states) | ok  [LOST=2] (1,308 states) |
| cb2: open(Y) ∥ exit(X) [lclr] | 0 / 0 / 1 / 0 | ok  [LOST=2] (1,246 states) | ok  [LOST=2] (1,246 states) |
| cb2: open(Y) ∥ exit(X) [all, X2] | 0 / 0 / 2 / 0 | LOSTNOTE=3  [LOST=16] (6,082 states) | ok  [LOST=16] (6,082 states) |
| cb2: open(X) ∥ open(Y) ∥ exit(Y) [cbrep] | 0 / 0 / 1 / 0 | LOSTNOTE=12  [LOST=28] (557,112 states) | ok  [LOST=28] (557,112 states) |
| cb2: open(Y) ∥ exit(X) [cbrep, F1] | 1 / 0 / 1 / 0 | LOSTNOTE=9  [LOST=37] (7,373 states) | ok  [LOST=37] (7,373 states) |
| cb2+greenlet: [exit(X), exit(Z)] ∥ open(Y) [cbrep] | 0 / 0 / 1 / 2 | LOSTNOTE=12  [LOST=18] (191,982 states) | ok  [LOST=22] (195,020 states) |
| cb2+re: exit(X)+[exit(Z)] ∥ open(Y) [cbrep] | 0 / 1 / 1 / 0 | LOSTNOTE=5  [LOST=9, REENT=776] (20,175 states) | ok  [LOST=10, REENT=776] (20,330 states) |
| reg2: rec ∥ open(Y) + free/take | 0,1 / 0 / 2 / 0 | ok  [LOST=28] / ok  [LOST=4] (1,628/5,518 states) | ok  [LOST=28] / ok  [LOST=4] (1,628/5,518 states) |
| reg2: rec ∥ open(Y) + free/free | 0,1 / 0 / 2 / 0 | ok  [LOST=29] / ok  [LOST=4] (2,617/8,925 states) | ok  [LOST=29] / ok  [LOST=4] (2,617/8,925 states) |
| reg2: enter(X) ∥ open(Y) + free x3 | 0 / 0 / 3 / 0 | ok  [LOST=53] (12,182 states) | ok  [LOST=14] (10,538 states) |
| reg2: enter(X) ∥ open(Y) + free/take, F1 | 1 / 0 / 2 / 0 | ok  [LOST=104] (12,547 states) | ok  [LOST=104] (12,547 states) |
| reg2: enter(X) ∥ exit(Y) + free/take/cbrep | 0 / 0 / 2 / 0 | ok  [REGCLOB=12, BUSY_TX=308] (5,144 states) | ok  [REGCLOB=12, BUSY_TX=308] (5,171 states) |
| rebind2: enter(X) ∥ open(Y) + take [other id has styxx leftovers] | 0 / 0 / 2 / 0 | ok  [LOST=9] (3,481 states) | ok  [LOST=9] (3,481 states) |

**What the enumeration shows.**
- **Revision 7: 0 violations of any property** in 58 configurations and 99 runs (10,465,412 state hashes). Every LOST hit is noted or MASKED.
- **Revision 6 in the same model** violates LOSTNOTE in exactly the seven runs that combine an outside callback replacement with a second core, whether by a second tracer, a greenlet switch, a re-entered exit or a fault. It violates nothing else, so the new dimensions find the critic's B1 and are not vacuous.
- The 44 configurations of revision 6's model give the same verdicts for both revisions. Their state counts are identical except in `reg: first enter(X)`, where a first acquisition's registration now counts.

Outputs: `rev7/out_m7_main.txt`, `out_m7_main_rebind2.txt` (the `rebind2:` configuration, added after the main run started) and `out_m7_table.md`.

**Hang mode** (`rev7/out_m7_hang.txt`, the robust mutex's bound removed). `with L: exit(X) ∥ exit(Y)+[lock]`: HANG 14 for both revisions, the mutex cycle the bound breaks (I5, #20). Every other configuration of the mode has no HANG for either revision, and the counts equal revision 6's.

**Mutants** (`m7_modelcheck.py mutants`, revision 7, every configuration; `rev7/out_m7_mutants_a.txt`, `_b.txt` and `_c.txt`, three runs over disjoint mutant lists, each file one run). Every revision-5 and revision-6 rule's mutant is detected as in revision 6, except `rebind_count_none`. Revision 7 affects that one: without `rebind2:` it is undetected, because a rebinding onto a fresh id is also counted in-call, and with `rebind2:` it gives LOSTNOTE 3 (`out_m7_main_rebind2.txt` notes). The new rows:

| mutant | first violations |
|---|---|
MUTANT_ROWS

**What is still not enumerated.** Two or more nested programs on one thread at once. Budgets above the tables': at most 3 outside events per run, and at most 1 when combined with re-entry, greenlets or `run_async`, except `cb2: … [all, X2]`. The five exchanges of a registration are two in the model. Free-threaded interleavings, which the spec refuses. A real greenlet or gevent library: the model's greenlets are abstract. Pending entries and credit counts: hits carry the attribution outcome, not counts. The `record()` and scoring layers. One mint: two tracers share it or neither holds it, so a local-events clear on a mint held by one trace only is the one-core case. And the premise itself, which the model assumes and G_ATOM tests. Revision 6's two omissions named by the critic (outside callback and local-event changes with one core only, and E4's same-id re-take) are now enumerated.

### Found while resolving (not raised by the critique)
- **F25. A raising hook inside a reclaim leaves the free uncounted.** A trace that lost nothing is not told of the free. A lost call is still noted by its section's ungated close read. This is disclosed and pinned (X157b, X157c).
- **F26. The critic's B1 fix had a fault window.** The model found it with one fault, and X158b shows it on CPython. The count moved inside `_register`'s call.
- **F27. `mech6.py` did not join mints.** A second tracer declaring the same function re-minted it. X137g's Q half was not shown until `mech7.py` joined.
- **F28. The in-call count made X137h's revision-6 shape non-isolating.** X137h was rewritten, and `rebind2:` added.
- **F29. The Tool acquisition prefix overstated the next enter's repair.** Found by the self-audit (Appendix A).

### Weakest points of revision 7, for round 8
1. **The premise gate's reach.** G_ATOM now checks the implementation's own steps for Python code, audit events and state access outside their one C call, in 64 gate outcomes, and its hookup controls show that its criteria catch the known ways of splitting a step. Gc, signals and threads are still tested only on reference pipelines of the same construction. A CPython path that runs Python code only under conditions neither part creates (a debugger that preempts C code, an allocator hook) would pass it. The model takes the premise as an axiom.
2. **Builds.** `_VERIFIED` is keyed on the version, and a vendor build of 3.12.3 or 3.13.12 with backported C changes is accepted but unverified. Its build is not refused, only disclosed.
3. **The registration residual.** One callback slot of another tool can be left as styxx's when an audit hook lets that tool take styxx's id mid-registration. It is bounded, counted, reported and noted, but not repaired. At a first acquisition it is surfaced nowhere (X154c).
4. **F25.** A raising audit hook inside a reclaim leaves a free unnoted on traces that lost nothing. No call is lost silently through it, but the MONITOR_LOST note is not a complete record of frees.
5. **The model's abstractions.** Two exchanges stand for five. There is one mint. Greenlets and `run_async` are abstract. At most one nested program and at most three outside events run per configuration. Counts are not modelled.
6. **Over-blocking by patch level.** Every 3.12 and 3.13 patch level but two refuses until G_ATOM is run on it.
7. **The remaining cycle.** The mutex cycle through user code is bounded, not removed, and every exit's registration triggers its audit hooks five times inside the mutex.
