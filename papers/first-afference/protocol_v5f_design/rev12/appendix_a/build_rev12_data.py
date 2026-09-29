# rev12: spec data changes (GAP-46, GAP-47, GAP-48). Writes, beside this script:
#   ../v5e_cases_kept_rev12.json          rev11's file with X72's and X73's sentence sub-assertion replaced (GAP-46)
#   atom_witness_overrides_rev12.json     rev11's overrides, M3-020 re-keyed to its successors (GAP-47), plus the
#                                         rulings on the 25 D atoms of GAP-48. It supersedes the rev11 overrides file.
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, '..', '..')
K = json.load(open(os.path.join(D, 'rev11', 'v5e_cases_kept.json')))
V5F_SENTENCE = ("work on other threads, pools, executors, child processes or asyncio tasks is credited only to a "
                "section that work opens itself; generator and coroutine objects created before the trace are never "
                "credited; a call counts only when it returns, yields or raises from inside its body while the tracer is active")
for r in K['rows']:
    if r['id'] in ('X72', 'X73'):
        r['v5f_sub_assertions'] = ("as v5e, except the fixed-sentence substring: the refusal contains v5f's NOT_EXERCISED "
                                   "sentence (M11, Spec-fixed texts) in place of v5e's FIXED_SENTENCE; NE_WORDING "
                                   "'not executed on the stack of any opening of section' and the forbidden 'never executed' "
                                   "are unchanged (revision 12, GAP-46)")
        r['v5f_fixed_sentence'] = V5F_SENTENCE
K['revision12'] = ("GAP-46: X72 and X73 check v5f's fixed sentence. Audit of every other kept row for text drift: the v5e "
                   "runner's text checks are code prefixes (all rows), NE_WORDING and 'never executed' (X72, X73: unchanged "
                   "in v5f), the code substring LAZY_RESULT (X74, X74b, X74c), the target names of X118, and the retired "
                   "PROFILER_LOST (X75, retired). Only FIXED_SENTENCE drifted.")
json.dump(K, open(os.path.join(D, 'rev12', 'v5e_cases_kept_rev12.json'), 'w'), indent=1, ensure_ascii=False)

O = json.load(open(os.path.join(D, 'rev11', 'appendix_a', 'atom_witness_overrides_rev11.json')))
w = O.pop("R-MECHANISM_AND_LIFECYCLE_M3-020")
for k in ("R-MECHANISM_AND_LIFECYCLE_M3-R11-001", "R-MECHANISM_AND_LIFECYCLE_M3-R11-002"):
    O[k] = dict(w, gap="GAP-47 (re-keyed from R-MECHANISM_AND_LIFECYCLE_M3-020, whose text revision 11 corrected)")
G48 = {
 "R-MECHANISM_AND_LIFECYCLE_M7-033": ("D", "reading: needs an allocation-fault injector no gate has (N2; F37)"),
 "R-EXCEPTION_SAFETY_MODEL-157": ("D", "X138, V65 (an owner blocked inside a transaction: other transactions raise MACHINERY_BUSY after the bound)"),
 "R-EXCEPTION_SAFETY_MODEL-160": ("D", "X138 (a blocked owner at any transaction site); V71 and X133 (hooks at audited sites); C part: verify8/probe_open_audit.py"),
 "R-EXCEPTION_SAFETY_MODEL-161": ("D", "X138, V65; rev5/m5_modelcheck.py configuration `with L: exit(X) // exit(Y)+[lock]`, property CYC_TX"),
 "R-EXCEPTION_SAFETY_MODEL-162": ("D", "X157"),
 "R-EXCEPTION_SAFETY_MODEL-181": ("G", "G_FI (a rule the gate enforces by its execution; not a disclosure)"),
 "R-OVER_BLOCKING_DISCLOSED-022": ("D", "X37, X37b"),
 "R-OVER_BLOCKING_DISCLOSED-026": ("D", "reading: no other build of a verified patch level is in the exam environment; G_ATOM records each build it ran on"),
 "R-OVER_BLOCKING_DISCLOSED-059": ("D", "X133 (a hook refusing a __code__ write mid-mint), X157 and X154b (hooks at register_callback)"),
 "R-OVER_BLOCKING_DISCLOSED-060": ("D", "V71; X138 (a blocked owner); C part: verify8/probe_open_audit.py"),
 "R-STATED_LIMITS-001": ("D", "V01 (one call satisfies the declaration: PASS {f:1})"),
 "R-STATED_LIMITS-002": ("D", "V13 (score via score_v1: the transitive call counts)"),
 "R-STATED_LIMITS-004": ("D", "reading: the threat model; the scoring-only cases score prebuilt traces as given (traces_v5f/*.json), which is the disclosed acceptance"),
 "R-STATED_LIMITS-005": ("D", "reading: a scope statement about another prereg's gate"),
 "R-STATED_LIMITS-029": ("D", "X10c; G_FI C2 (third alternative)"),
 "R-STATED_LIMITS-030": ("D", "reading: CPython's importlib lock behaviour under an asynchronous exception, not measured on 3.12/3.13 (the sentence says so)"),
 "R-STATED_LIMITS-031": ("D", "reading (as -030)"),
 "R-STATED_LIMITS-033": ("D", "X152 (U3), X146d (U4)"),
 "R-STATED_LIMITS-035": ("D", "X146d"),
 "R-STATED_LIMITS-040": ("D", "reading: a RecursionError raised in a callback's own frame near the limit; C part: critic6/a5_recursion_inside_step.py"),
 "R-STATED_LIMITS-043": ("G", "G_SIG (the gate's own measurement rule)"),
 "R-STATED_LIMITS-060": ("G", "G_SIG (a frozen decision of the gate, not a disclosure)"),
 "R-STATED_LIMITS-062": ("D", "H10 cell (a) (G_SIG gates it at 0)"),
 "R-STATED_LIMITS-106": ("D", "V70 (the pending entry holds its frame); G_FI C4 and C5's pending exclusion (critic4/a6_pending_left_fault_free.py)"),
 "R-STATED_LIMITS-109": ("G", "G_ATOM (the gate's scope statement)"),
}
for k, (c, wit) in G48.items():
    O[k] = {"gap": "GAP-48", "class": c, "witness": wit}
json.dump(O, open(os.path.join(HERE, 'atom_witness_overrides_rev12.json'), 'w'), indent=1, ensure_ascii=False)
print(len(O), 'overrides;', sum(1 for r in K['rows'] if 'v5f_fixed_sentence' in r), 'kept rows changed')
