# Brief: the frozen v5e exam runner

Write `papers/first-afference/run_protocol_v5e.py` in /home/user/styxx-1, the exam that will be frozen by
sha256 in `PREREG_protocol_v5e_mint_anchor_2026_09_24.md` BEFORE the v5e implementation is written.

## Source of truth
The spec: /tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/design/SPEC_v5e.md
(read ALL of it, especially "Exam cases required"), plus the AMENDMENTS below, which override it.
Prior exams to learn the house style and plumbing from (do not copy their API — v5e's API differs):
papers/first-afference/run_protocol_v5d.py (latest), run_protocol_v5.py (its `differential()` is reused).

## The API the implementation will expose in styxx/protocol.py (write the exam against exactly this)
- `coverage_trace(experiment) -> _CoverageTracer`; context manager; `with coverage_trace(exp) as cov:`
- `cov.run(section, fn, /, *args, **kwargs)`, `await cov.run_async(section, afn, /, *args, **kwargs)`, `cov.record()`
- `_CoverageTracer._open`, `_CoverageTracer._close`, `_CoverageTracer.__enter__`, `_CoverageTracer.__exit__`
- `_resolve_target(target: str)` (module level), `Experiment._check_coverage(name, result)`, `Experiment.check_metrics(result)`
- module globals: `_hook` (THE profile function, referenced by global name everywhere, so a test may monkeypatch it),
  `_LOCK` (RLock), `_MINTED`, `_BY_FN`, `_ANCHORS`, `_THREADS` (dicts), `_ACTIVE` (int), `_STOP`, `_TRACER_ID == "styxx.protocol.coverage_trace/2"`
- trace schema, reason codes, notes, resolution, scoring order: exactly as in the spec.
- Every refusal / recorded problem / note message begins with its complete literal code, e.g. "[V5:NESTED_SECTION] ...".

## AMENDMENTS (override the spec)
A1. Leftover checks compare against a snapshot taken immediately before the case, not against "empty": each case
    runs inside the exam's outer self-trace, whose own entries are legitimately present. After the case: the
    registries equal the snapshot, `_ACTIVE` equals the snapshot, `sys.getprofile()` on the case thread equals
    what it was before the case, `threading.getprofile()` unchanged, every fixture function's `__code__` is its
    original. A leftover is a case failure (for violation, valid and residual cases alike).
A2. Corpus differential (G3/G4): reuse `run_protocol_v5.differential()` semantics (pinned v4 at 98a5c368 vs the
    current implementation, over every committed papers/*/*_result.json whose prereg exists, excluding the v5
    exams' own preregs incl. v5e), PLUS the frozen nested-dict rule: for exactly the results listed under
    "reproduced" in papers/first-afference/corpus_provenance_rescore.json, score `result["metrics"]` instead of the
    whole receipt, with both v4 and v5. Metrics: n_v4_v5_outcome_disagreements (gate <= 0) and
    n_results_v5_scored (gate >= 39).
A3. Frozen dependencies. The runner verifies at startup, and reports in the result, the sha256 of: itself,
    papers/first-afference/mutation_gate.py, run_protocol_v5.py, run_p1.py, PREREG_p1_power_refusal_2026_08_08.md,
    p1_result.json, styxx/power_QUARANTINED.py.txt, corpus_provenance_rescore.json. The expected values are read
    from lines `FROZEN_<NAME>_SHA256: <hex>` in the v5e prereg (the prereg is written after the runner, so the
    runner reads them at run time). `exam_frozen` = 1.0 iff every one matches.
A4. Modes. `--smoke` (plumbing only, INVALID verdict by type), `--full-battery` (with --smoke: run every case),
    `--mutation-mode` (with --smoke --full-battery: every case EXCEPT the hazard sweeps H1-H3 and the stress run
    V32; used by mutation_gate.py). Env: `STYXX_V5_IMPORT_ROOT` (if set, put it FIRST on sys.path so `styxx` is
    imported from there), `STYXX_V5_RESULT_OUT` (if set, write the result JSON there instead of
    papers/first-afference/protocol_v5e_result*.json). Never write anywhere else in the repo.
A5. Mutation gate as gates. In a scored (non-smoke) run, read papers/first-afference/run_protocol_v5e_mutation_gate.json
    (written beforehand by `python papers/first-afference/mutation_gate.py --runner run_protocol_v5e.py`);
    require its impl_sha256 == sha256(styxx/protocol.py), runner_sha256 == own sha256, generator_sha256 ==
    frozen; else metric values are 0 / refusal. Metrics: `mutation_frac_detected` (0.0 if baseline_clean is
    false), `mutation_hygiene_violations`.
A6. Hazard sweeps H1-H3 exactly as the spec, each with its detection mutant built by monkeypatching the module
    global `_hook` in a SUBPROCESS (H1 mutant: wrapper acquiring a non-reentrant threading.Lock around the
    original; H2 mutant: wrapper with `try: original(...) except Exception: pass`). Metrics:
    h1_hangs (0), h1_mutant_detected (1), h2_propagated (20 of 20), h2_mutant_detected (1), h3_ok (5 of 5).
    Signal cases run on the main thread, before the self-trace. Each subprocess has a hard timeout.
A7. Version keys: this environment is Python 3.11. Keep version-keyed cases (X81 <=3.11; V33, X82 >=3.12) keyed
    by sys.version_info so the same runner works on 3.10-3.13.
A8. Self-coverage (V34): the outer self-trace declares, in the prereg's gates, G0 exercises
    [styxx.protocol:Experiment._check_coverage, styxx.protocol:_resolve_target, styxx.protocol:_CoverageTracer._open,
    styxx.protocol:_CoverageTracer.__exit__]; G1 exercises [styxx.protocol:Experiment._check_coverage,
    styxx.protocol:_CoverageTracer._open, styxx.protocol:_CoverageTracer.record]; G2 exercises [run_p1:degenerate];
    G5 exercises [styxx.protocol:_CoverageTracer._open]. Sections are the gate names. Each case runs in its own
    thread whose target is `lambda: cov.run(<gate section>, case)` with a 30 s join watchdog (a watchdog
    expiry is a case failure, never a hang of the exam).
A9. Metric names (the prereg's gates will use exactly these): exam_frozen, frac_violation_cases_refused_with_expected_code,
    frac_valid_cases_exact, frac_residuals_as_documented, p1_retro_exact, n_v4_v5_outcome_disagreements,
    n_results_v5_scored, mutation_frac_detected, mutation_hygiene_violations, h1_hangs, h1_mutant_detected,
    h2_propagated, h2_mutant_detected, h3_ok, n_crashes. Per-case detail in violation_cases / valid_cases /
    residual_cases dicts, each entry {expected, outcome, ok, detail, leftover}. The scored run's own verdict
    comes from `Experiment(PREREG).score(res)` with the self-trace in res["coverage_trace"].
A10. Fixtures: write fixture modules into a temp dir created at run time (as v5d does), never into the repo.
     Cases must be ISOLATED: each violation case must fail for its own named reason only, so that deleting any
     other rule cannot make it pass or fail (round 2's lesson: a mutant that refuses for a later reason never
     tested the check it names). Where a case needs other rules to hold, construct it so those rules are
     trivially satisfied.

## Dry-running
The implementation does not exist yet. You MAY build a scratch shim (under
/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/exam_v5e/shim/) that exposes the
design panel's prototype (/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/design/synth/v5f.py)
under the API above, in a copy of the styxx package, and run your exam against it through STYXX_V5_IMPORT_ROOT
to find plumbing bugs. The shim is never committed. WHEN THE PROTOTYPE AND THE SPEC DISAGREE, THE EXAM FOLLOWS
THE SPEC (+ amendments): log every disagreement in your final report. Never weaken a case to make the prototype pass.

## Hard rules
- Only create/modify `papers/first-afference/run_protocol_v5e.py` in the repo. Do not touch styxx/, other papers, or git.
- Do not commit. Do not run anything that writes into the repo other than your runner's own output via STYXX_V5_RESULT_OUT to scratch.
