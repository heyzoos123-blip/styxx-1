# Brief: the independent second implementation of protocol v5e (N-version)

You are writing an INDEPENDENT implementation of a frozen specification. Another engineer is
implementing the same spec at the same time, without seeing yours; you must not see theirs. After both
exist, a frozen harness compares them: both must pass the same frozen exam, match a fuzz oracle, and
produce identical normalized traces on thousands of random programs. A disagreement means the spec is
ambiguous or one implementation is wrong, and that is a finding, not a failure of yours.

## Independence rules (the value of this work depends on them)
- Work ONLY inside the git worktree you were started in. It is checked out at the freeze commit, where
  `styxx/protocol.py` is still the OLD v5d implementation and no v5e implementation exists in git.
- Do NOT read `/home/user/styxx-1` (the main working tree), anything under
  `/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/` (it contains a design
  prototype), or any file named `v5f.py`.
- You MAY read everything committed in your worktree: the spec, the frozen exam, the fuzzer, the old
  implementations in git history, the red-team audits.

## What to build
`papers/first-afference/nversion_v5e/protocol_nv.py`: a COMPLETE drop-in replacement for
`styxx/protocol.py`. Start from the committed v5d `styxx/protocol.py` in your worktree (keep everything
before the v5 region: v1-v4 gate parsing, composition, `Experiment.score`, etc. — the frozen corpus
differential requires v1-v4 behaviour to be unchanged), and rewrite the v5 parts (the coverage
declaration parsing may stay; `_check_coverage`, `check_metrics` handling, and everything from the
line `# -- v5: the coverage tracer` onward) to implement the spec.

## The contract
- Spec: `papers/first-afference/DESIGN_protocol_v5e_mint_anchor_2026_09_24.md` — implement ALL of it.
- API and amendments: `papers/first-afference/DESIGN_protocol_v5e_exam_brief_2026_09_24.md`, section
  "The API the implementation will expose" — module-level `coverage_trace`, class `_CoverageTracer` with
  `run`, `run_async`, `record`, `_open`, `_close`, `__enter__`, `__exit__`; module-level
  `_resolve_target`; `Experiment._check_coverage`; module globals `_hook` (THE profile function,
  referenced by global name), `_LOCK` (RLock), `_MINTED`, `_BY_FN`, `_ANCHORS`, `_THREADS` (dicts),
  `_ACTIVE` (an int), `_STOP` (a plain module global holding asyncio.events.Handle._run.__code__ while
  active, read by the hook on every call event — the fuzzer's positive control sets it to None),
  `_TRACER_ID == "styxx.protocol.coverage_trace/2"`.
- Every refusal, recorded problem and note message must begin with its COMPLETE literal code at the
  site that emits it, e.g. `raise GateSpecError(f"[V5:NESTED_SECTION] ...")` or
  `self._problems.append(f"[V5:CLONE_ALIVE] ...")`. Never build the code at run time
  (`f"[V5:{code}]"`): the frozen mutation gate cannot see such refusals and counts them as violations.
- The frozen exam `papers/first-afference/run_protocol_v5e.py` and the fuzzer `fuzz_v5e.py` are how you
  will be judged. Run them against your implementation without modifying them:
  `STYXX_V5_IMPORT_ROOT=<a temp dir containing a copy of styxx/ with your protocol_nv.py as protocol.py>`
  `STYXX_V5_RESULT_OUT=<temp json>` `python papers/first-afference/run_protocol_v5e.py --smoke --full-battery`
  and `python papers/first-afference/fuzz_v5e.py --n 3000` with the same environment.
- The frozen exam additionally assumes (stated in the frozen prereg): `Experiment._check_coverage`
  returns `{declared target: union count}` and `Verdict.coverage` carries it per gate; the registries
  are module globals reached by global name at call time (a case rebinds `_ANCHORS` for one
  `__exit__`); `__exit__` empties `_by_code` before its first access to `_ANCHORS`; `_STOP` is a plain
  module global read by the hook on every call event and `_ACTIVE` is an int.
- If you believe a frozen exam case contradicts the spec, do NOT bend your implementation to it:
  implement the spec, and report the case, the spec text, and the evidence.

## Deliver
The file, plus a report: what you implemented, every place the spec was ambiguous and which reading you
chose (and why), exam and fuzz results against your implementation, and any exam case you believe is
wrong. Commit the file on your worktree branch.
