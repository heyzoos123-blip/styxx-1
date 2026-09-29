# rev9 verifier: the classification of the 164 sentences of rev9_new_sentences.json, as data.
# Classes and witness conventions are Appendix A's table (P D C G N S H; 'old' = carries a revision-7 keyword and
# was covered by the revision-7 audit, kept only where the revision-8 list already said so).
# A sentence whose text is verbatim in wide_claims_classified.json inherits that row (Appendix A rule 1); the
# near-verbatim ones (edited by the verifier after the revision-8 extraction) and the rest are classed by hand below.
# Writes ../appendix_a/rev9_new_sentences_classified.json and .txt.
import json, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, '..', 'appendix_a')
new = json.load(open(os.path.join(A, 'rev9_new_sentences.json'), encoding='utf-8'))
old = json.load(open(os.path.join(A, 'wide_claims_classified.json'), encoding='utf-8'))
by_text = {}
for o in old:
    by_text.setdefault(o['text'], o)

V = 'verify/p_cpython_rev9.py'          # CPython probe (this directory), both versions
R = 'verify/p_ref_findings.py'          # reference-level probe (this directory), both versions

# id: (class, witness, finding)
M = {
 1: ('H', '', ''),
 89: ('P', 'X24b, X24c (message names `fast`, never `power_ref`)', ''),
 90: ('P', 'X24b, X24c (`<callee>` = the callee\'s module:qualname); SM2 compares it (M11 Spec-fixed texts). The callee-None branch ("no single Python function") has no v5f case', 'R9-9'),
 91: ('P', 'X24c (the stamp rendered by type, never `power_ref`); ' + V + ' #91 (`NoneType`, `function`); not SM2-compared (#93)', 'R9-1'),
 92: ('P', 'X24c', ''),
 93: ('G', 'SM2 normalizer (M11 Spec-fixed texts)', ''),
 118: ('P', 'X65d (a foreign-loop anchor ends the hit walk: `dispatched`, where a skip would give `unattributed`); V63; Mutation audit "loop boundary in attribution"', ''),
 119: ('P', 'X156g (mutant mut_grl_nocheck); C part: rev9/p_gaps.py, ' + V + ' #194', ''),
 128: ('P', 'X78f variant counts only `__eq__`/`__hash__`: blind to a section formatted by repr() or a type name read through the metaclass (' + R + ' FA); no TRACE_INACTIVE (step 2) case with a non-str section', 'R9-1'),
 130: ('P', 'X78f variant (comparison only; formatting unwitnessed, ' + R + ' FA)', 'R9-1'),
 132: ('D', 'none pinned: over-blocking #23 has no case or residual; buildable with `asyncio.events._set_running_loop` (' + R + ' FB: NESTED_SECTION on ref_v5f.py)', 'R9-2'),
 169: ('P', 'X74-X74d (Mutation audit "LAZY_RESULT exact type and text"), X74d; SM2 (M11 Spec-fixed texts); C part: ' + V + ' #169 (the CREATED test equals inspect\'s state for each lazy type), rev9/out_texts.txt', ''),
 170: ('D', V + ' #169 F34 shape (3.12.3 CREATED, 3.13.12 CLOSED; matches F34); deliberately unpinned, no case uses it', 'R9-10'),
 181: ('C', V + ' #181 (3.12.3: Py_GIL_DISABLED None, no _is_gil_enabled; 3.13.12: 0, _is_gil_enabled() true); G_HYG (no nested code object)', ''),
 185: ('G', 'free-form beyond the prefix (#186); X156 family checks the prefix', ''),
 186: ('G', 'Exam harness rules, "How cases pass" (prefix only); X156, X156b-d, X156f, X156g', ''),
 194: ('P', 'X156g (checked before the first binding); the re-check at every later coverage_trace() has no case (' + R + ' FD); C part: ' + V + ' #194', 'R9-3'),
 195: ('P', 'X156g (mut_grl_nocheck: PASS {f:1}); rev9/out_witness.txt', ''),
 199: ('P', 'Reason codes row NOTHING_DECLARED (v5e case); its place in the order (step 3) has no case', 'R9-4'),
 200: ('P', 'none: no case sees a binding made before a later step refuses (' + R + ' FC); G_HYG reload clause fixes `_get_running_loop`\'s place (steps 4-7) but `_MON`\'s only as "after the M0 builtin check"', 'R9-4'),
 201: ('P', 'X65f (the two bindings read from the captured dicts, never afresh)', ''),
 202: ('P', 'V47, G_FI C9 (core.pid); G_HYG (facade class defines no `__init__`; SM2 region set)', ''),
 203: ('P', 'none (' + R + ' FC: the pre-C2 order binds `_MON` on a step-6 refusal, and a wrapper installed afterwards then passes where the spec refuses; X156g cannot see it)', 'R9-4'),
 204: ('P', 'none (as #203; ' + R + ' FC)', 'R9-4'),
 211: ('P', 'G_HYG reload clause (revision 9: `_GUARD` through globals().get, set by the one statement after class _Txn)', ''),
 220: ('P', 'X156c; X156f (index 6); V69b', ''),
 221: ('P', 'G_HYG reload clause (revision 9); X156g; re-bound at every coverage_trace(): no case (' + R + ' FD)', 'R9-3'),
 223: ('G', '`_VERIFIED` and G_ATOM (a patch level is added only with a G_ATOM run); C fact: rev9/p_gaps.py, ' + V + ' #223 (1, 2, 4, 8, 4096 on both)', ''),
 224: ('H', '', ''),
 225: ('P', 'G_HYG reload clause (GAP-06)', ''),
 226: ('P', 'G_HYG reload clause (assigned only in coverage_trace(), after steps 4-7); X156g', ''),
 227: ('P', 'none: X156g replaces it before the first coverage_trace(), so a check-once mutant survives (' + R + ' FD: spec UNSUPPORTED_VERSION, mutant PASS)', 'R9-3'),
 228: ('P', 'G_HYG reload clause; G_HYG region (`_open`/`_outcome` reached only through a facade, built at step 10 after step 7)', ''),
 232: ('P', 'G_HYG reload clause', ''),
 233: ('P', 'G_HYG reload clause', ''),
 234: ('P', 'X158e (revision 8 self-audit, W3)', ''),
 241: ('P', 'G_HYG (SM2 region set: the facade defines no `__init__`)', ''),
 242: ('P', 'G_HYG (SM2 region set; M10 facade methods)', ''),
 296: ('P', 'X154e (`lost0` read after the in-call count: no MONITOR_LOST)', ''),
 297: ('H', '', ''),
 298: ('P', 'X154e', ''),
 299: ('P', 'X154d', ''),
 306: ('P', 'X137i (revision 8 self-audit, W1; mutant pend_get)', ''),
 317: ('P', 'V69b (mut_gle_calltime); G_HYG clause confining `_MON[0][6]`', ''),
 320: ('P', 'X59e and its variant (UNDECLARED_SECTION first); mutants mut_order_cut_first, mut_order_swapped_first', ''),
 369: ('C', 'critic6/a1_audit_monitoring.py; rev9/p_gaps.py; ' + V + ' #369 (all six raise none on both); G_ATOM (b)', ''),
 481: ('G', 'SM2 (M11 Spec-fixed texts); X91, X92c check the two TRACE_ACTIVE texts', ''),
 483: ('P', 'none distinguishes it: the full handler with `_MON[0]` None changes nothing (EQUIVALENT_BY_SPEC candidate); G_FI fork scenario (C9) runs the handler', 'R9-7'),
 484: ('C', V + ' #484 (after_in_child handlers: one per load, oldest first, both versions)', ''),
 485: ('P', 'C part: ' + V + ' #485 (reload re-runs the module in the same dict; old handlers read the new globals). "The extra runs change nothing": no case forks after a reload (unobservable by outcome)', 'R9-7'),
 493: ('P', 'V69b (`_v5_state()` reads through `_MON[0][6]`: counter 0); never raises: rev9/p_gaps.py, ' + V + ' #493', ''),
 494: ('P', 'Exam harness leftover check (`guard` is "free" after every case); the "held" and "dead" branches are read by no case', 'R9-8'),
 495: ('P', 'G_FI S0 and every fresh-subprocess case\'s "before" snapshot (it raised in revision 8); rev9/out_texts.txt', ''),
 496: ('H', '', ''),
 497: ('P', 'rev9/out_texts.txt; leftover check (monotone field, excepted)', ''),
 498: ('P', 'rev9/out_texts.txt. CONTRADICTS the leftover check: `tool_ours` goes False -> True across a fresh process\'s first trace, and only `cut` and `tool` are excepted (' + R + ' FE)', 'R9-6'),
 499: ('P', 'leftover check (`global_events` equals the before snapshot); rev9/out_texts.txt', ''),
 500: ('P', 'rev9/out_texts.txt; G_FI S0; leftover check (see R9-6 for `tool_ours`)', 'R9-6'),
 502: ('P', 'G_HYG (SM2 region set; slots clause for the plain-data classes)', ''),
 519: ('P', 'none: no case walks a metric path through a dict subclass with a user `__getitem__`/`__contains__`/`get`/`__missing__` via check_metrics (V53 is a defaultdict through score())', 'R9-5'),
 520: ('P', 'none (as #519)', 'R9-5'),
 521: ('P', 'X117b (the float() OverflowError rule); v5e scoring cases', ''),
 524: ('P', 'X117d (smoke, trace present); the non-smoke absent-trace branch (NO_TRACE text, not "smoke run") has no case', 'R9-5'),
 525: ('G', 'SM2 normalizer', ''),
 526: ('G', 'SM2 normalizer', ''),
 527: ('G', 'SM2 normalizer', ''),
 528: ('P', 'C part: ' + V + ' #528 (the descriptor read runs no metaclass code; the attribute read does). No case renders `{T}` for a type whose metaclass runs code, so a `type(x).__qualname__` mutant survives (' + R + ' FA, mut_sec_attrqual)', 'R9-1'),
 529: ('G', 'SM2 normalizer; the NO_TRACE second-wording case', ''),
 530: ('G', 'SM2 normalizer; Exam harness rules (prefix)', ''),
 531: ('G', 'SM2 normalizer', ''),
 543: ('P', 'V71 (open-path sites); G_ATOM (b) (no one-call step makes such a call); verify8/probe_open_audit.py', ''),
 547: ('C', 'verify8/probe_open_audit.py; ' + V + ' #548 (sys._getframe raises its event); V71', ''),
 548: ('C', 'verify8/probe_open_audit.py; ' + V + ' #548 (builtins.id, object.__getattr__ on f_code, both versions)', ''),
 549: ('P', 'V71 (open walk); L-DELIVERY (H10), I6 (G_FI C1-C7) for callbacks; model lock-taking configuration for `_alive` and the keys (W5)', ''),
 550: ('P', 'V71 and its variants (mutant frame_after_append); H10; G_FI C1-C8; the model\'s lock-taking and greenlet configurations', ''),
 555: ('H', '', ''),
 556: ('P', 'G_ATOM (b) (`_unwind_off` raises none); verify8/probe_open_audit.py; G_FI C8', ''),
 557: ('P', 'V71 (mutant frame_after_append)', ''),
 558: ('P', 'V71; G_ATOM (b)', ''),
 559: ('H', '', ''),
 597: ('P', 'X154e (revision 8 self-audit, W7)', ''),
 610: ('P', 'X154e (revision 8 self-audit, W7)', ''),
 622: ('D', 'model `with L: exit(X) || exit(Y)+[lock]` (any site); I5 bound; H1', ''),
 623: ('D', 'model lock-taking configuration (any site; W5); I5 bound', ''),
 753: ('D', 'model lock-taking configuration; I5 bound (W5)', ''),
 754: ('D', 'model lock-taking configuration; I5 bound (W5)', ''),
 766: ('D', 'none pinned (as #132; ' + R + ' FB)', 'R9-2'),
 817: ('D', 'rev5/m5_modelcheck.py to rev8/m8_modelcheck.py (greenlet configurations); X137f, X158d', ''),
 823: ('G', 'Exam harness rules (the gate\'s own execution)', ''),
 839: ('G', 'Exam harness rules (GAP-26)', ''),
 840: ('G', 'Exam harness rules (GAP-26); X103b, X117b-X117d', ''),
 898: ('N', 'X93d; C part: ' + V + ' #898 (OrderedDict qualname)', ''),
 903: ('N', 'X137b (taken variant)', ''),
 924: ('N', 'X145', ''),
 937: ('N', 'X148', ''),
 953: ('N', 'X154', ''),
 957: ('N', 'X154b', ''),
 958: ('N', 'X154b; C part: ' + V + ' #958 (no callback getter; exchange-and-restore raises 10 audit events)', ''),
 961: ('N', 'X137f', ''),
 990: ('N', 'X158e', ''), 991: ('N', 'X158e', ''), 992: ('N', 'X158e', ''), 993: ('N', 'X158e (mutant cbrep_nocount)', ''),
 994: ('N', 'X137i', ''), 996: ('N', 'X137i', ''), 997: ('N', 'X137i', ''),
 998: ('N', 'X154e', ''), 999: ('N', 'X154e', ''), 1000: ('N', 'X154e (mutant adopt_no_register)', ''),
 1010: ('N', 'X156f (mutant mut_gle_nocheck)', ''),
 1011: ('N', 'X156g', ''), 1012: ('N', 'X156g', ''), 1013: ('N', 'X156g (mutant mut_grl_nocheck)', ''),
 1043: ('N', 'V71', ''), 1044: ('N', 'V71', ''), 1045: ('N', 'V69b (mutant mut_gle_calltime)', ''),
 1064: ('N', 'V57; C part (sys.setprofile is per-thread): rev1/p20', ''),
 1130: ('G', 'SM1 (the gate\'s own execution)', ''),
 1131: ('G', 'SM1 (the gate\'s own execution); rev9/out_witness.txt, rev9/out_order.txt', ''),
 1133: ('G', 'G_HYG (the gate\'s own execution)', ''),
 1247: ('G', 'G_HYG (the clause is the witness of #317 and #493\'s confinement)', ''),
 1248: ('G', 'G_HYG (the gate\'s own execution)', ''),
 1321: ('G', 'G_INDEP (process gate)', ''),
 1322: ('G', 'process gates (disclosure)', ''),
}

# the 'old' rows' class under Appendix A's table (the revision-8 list kept them as 'old', covered by the rev-7 audit)
OLDMAP = {150: ('H', ''), 368: ('C', 'G_ATOM part R; critic6/a4, a5; critic8/c4'), 378: ('H', ''),
          379: ('C', 'G_ATOM D2 under its floors'), 515: ('D', 'R14; X82, X83, V35; SM2 fixed text'),
          599: ('P', 'X144, X143b; model U1'), 763: ('D', 'critic3/c9_x34b_fixture_poisons_first_e2.py; the X34b harness rule'),
          835: ('G', ''), 1303: ('G', ''), 1325: ('G', '')}

rows = []
for x in new:
    r = dict(x)
    o = by_text.get(x['text'])
    if x['id'] in M:
        c, w, f = M[x['id']]
        r.update({'class': c, 'witness': w, 'finding': f,
                  'basis': 'by hand' + ('; text edited from rev-8 list' if o is None else '; verbatim in rev-8 list id %d, re-checked' % o['id'])})
    elif o is not None:
        r.update({'class': o['class'], 'witness': o['witness'], 'finding': '',
                  'basis': 'inherited verbatim from rev-8 list id %d (Appendix A rule 1)' % o['id']})
    else:
        raise SystemExit('unclassified id %d' % x['id'])
    if r['class'] == 'old':
        r['class_by_table'], r['witness_by_table'] = OLDMAP[x['id']]
    rows.append(r)

FINDINGS = {
 'R9-1': ('freeze-blocking', 'GAP-16/GAP-15 "runs no user code" when rendering a non-str section or a type name (#128, #130, #528, #91): X78f\'s variant counts only __eq__/__hash__, so a mutant that formats the section with repr() or reads type(x).__qualname__ passes it; no TRACE_INACTIVE (step 2) case with a non-str section. Fix: count __repr__/__str__/__format__ and a metaclass __getattribute__ in the variant, plus a step-2 variant (p_ref_findings.py FA)'),
 'R9-2': ('freeze-blocking (Appendix A rule 3: a D claim with no pinned outcome)', 'Over-blocking #23 / GAP-11 (#132, #766): the disclosed NESTED_SECTION shape has no pinned case or residual. It is buildable with asyncio.events._set_running_loop, and ref_v5f.py refuses NESTED_SECTION on it (p_ref_findings.py FB)'),
 'R9-3': ('freeze-blocking', 'GAP-02 "re-checked and re-bound at every coverage_trace()" (#194, #221, #227): X156g replaces _get_running_loop before the first coverage_trace(), so a check-only-when-unbound mutant survives. A replacement after the first trace refuses UNSUPPORTED_VERSION under the spec and passes under the mutant (p_ref_findings.py FD)'),
 'R9-4': ('freeze-blocking', 'GAP-09 order and "a refusal at any step binds and captures nothing" (#199, #200, #203, #204): no case. The pre-C2 order (bind _MON before import asyncio, the exact ref bug C2 fixes) survives X156g. After a step-6 refusal, a wrapper installed on sys.monitoring then passes where the spec refuses (p_ref_findings.py FC). The G_HYG reload clause places _get_running_loop after steps 4-7 but _MON only "after the M0 builtin check", which the pre-C2 order also satisfies'),
 'R9-5': ('freeze-blocking', 'M11 check_metrics, GAP-17/GAP-18 (#519, #520, #524): no case drives check_metrics through a dict subclass with a user __getitem__/__contains__/get/__missing__ on a metric path; the non-smoke absent-trace branch (NO_TRACE text, not "smoke run") has no case, and X117d covers only smoke with a present trace'),
 'R9-6': ('freeze-blocking (contradiction)', 'The Exam harness leftover check ("_v5_state() equals the before snapshot, except the monotone fields cut and tool") contradicts M10\'s pre-binding fields (#498, #500; #496 names the subprocess before-snapshot). In a fresh subprocess whose case makes the first tracer, tool_ours goes False -> True, so every such case (V71, X154e, X137i, X158e, ...) fails the leftover rule as written; ref_v5f.py shows it on both versions (p_ref_findings.py FE). Fix: except tool_ours too, or when the before snapshot\'s tool is None'),
 'R9-7': ('not blocking', 'GAP-24 / GAP-23 at-fork (#483, #485): the no-op test and "extra handler runs change nothing" are unobservable by outcome; no case forks before a tracer or after a reload. The C facts hold (p_cpython_rev9.py #484/#485: one handler per load, oldest first, all reading the same globals). File them EQUIVALENT_BY_SPEC or as reading'),
 'R9-8': ('not blocking', '_v5_state()["guard"] rule (#494, F36): only "free" is witnessed (the leftover check). No case reads "held" or "dead"'),
 'R9-9': ('not blocking', 'NOT_A_FUNCTION\'s callee-None text "no single Python function" (#90) is SM2-compared, but no v5f case builds a cache wrapper over a non-function, so SM2 never sees it'),
 'R9-10': ('not blocking', 'F34 LAZY_RESULT cross-version shape (#170): the aclose()-unawaited async generator is CREATED on 3.12.3 and CLOSED on 3.13.12 (p_cpython_rev9.py confirms F34); deliberately unpinned, no case uses it'),
 'R9-11': ('not blocking (method)', 'Only 116 of the 164 sentences are new text. 48 are verbatim in the revision-8 list (same text, section and keywords): the diff behind rev9_new_sentences.json matches (line, text), and those 48 moved lines. Appendix A\'s "164 are not in the revision-8 list" should say "116 texts"; the 48 inherit their rows (rule 1)'),
}

out = {'source': 'rev9_new_sentences.json (164) classified by the verifier; classes per Appendix A',
       'counts': dict(collections.Counter(r['class'] for r in rows)),
       'findings': {k: {'severity': s, 'finding': t} for k, (s, t) in FINDINGS.items()},
       'sentences': rows}
json.dump(out, open(os.path.join(A, 'rev9_new_sentences_classified.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
by_table = collections.Counter(r.get('class_by_table', r['class']) for r in rows)
out['counts_by_table'] = dict(by_table)
json.dump(out, open(os.path.join(A, 'rev9_new_sentences_classified.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
L = ['rev9_new_sentences_classified: the verifier\'s classing of the 164 sentences in rev9_new_sentences.json',
     '(Appendix A, "The classified lists are spec data"; the weakest point 1 of revision 9).', '',
     'Method. Classes and witness conventions are Appendix A\'s table. 40 sentences are verbatim in the revision-8',
     'wide list and inherit its row (rule 1). 124 were classed by hand: 116 new texts and 8 verbatim rows re-checked',
     'to name their case (class N unchanged). The classification is data in ../verify/classify_rev9.py. CPython facts were probed',
     'on 3.12.3 and 3.13.12 (../verify/p_cpython_rev9.py, out_cpython_rev9_3.1{2,3}.txt: every claim holds). The',
     'witness gaps were shown on ref_v5f.py, read-only, with in-memory single-rule mutants',
     '(../verify/p_ref_findings.py, out_ref_findings_3.1{2,3}.txt; identical on both versions).', '',
     'Counts by class: ' + ', '.join('%s %d' % (k, out['counts'].get(k, 0)) for k in ('P', 'D', 'C', 'G', 'N', 'S', 'H', 'old')) + ', total %d.' % len(rows),
     'With the 10 "old" rows resolved by the table: ' + ', '.join('%s %d' % (k, by_table.get(k, 0)) for k in ('P', 'D', 'C', 'G', 'N', 'S', 'H')) + '.',
     'P, D and C: %d. %d of them name a full witness; %d are tied to a finding below.' % (
         len([r for r in rows if r.get('class_by_table', r['class']) in 'PDC']),
         len([r for r in rows if r.get('class_by_table', r['class']) in 'PDC' and not r['finding']]),
         len([r for r in rows if r.get('class_by_table', r['class']) in 'PDC' and r['finding']])), '',
     'Findings (sentence ids are rev9_new_sentences.json ids):']
for k, (sev, t) in FINDINGS.items():
    ids = [str(r['id']) for r in rows if r['finding'] == k]
    L.append('- %s [%s] %s. Sentences: %s.' % (k, sev, t, ', '.join(ids) or '(method)'))
open(os.path.join(A, 'rev9_new_sentences_classified.txt'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('counts', out['counts'], 'total', len(rows))
print('inherited', sum(r['basis'].startswith('inherited') for r in rows), 'by hand', sum(r['basis'].startswith('by hand') for r in rows))
pdc = [r for r in rows if r['class'] in ('P', 'D', 'C')]
print('P/D/C', len(pdc), 'with a finding', sum(bool(r['finding']) for r in pdc))
