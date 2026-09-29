# rev10: Appendix A's data for the exam author's rule 1 (GAP-30, GAP-31, the verifier's list, GAP-W).
# Writes, beside this script:
#   rev7_audit_claims_classified.txt/.json   the revision-7 list, copied from protocol_v5f_design/rev7/ (GAP-30)
#   wide_old_rows_resolved.json              the wide list's 84 'old' rows, each with its class and witness (GAP-30)
#   pointer_witness_map.json                 the 40 atoms whose wide-list witness was a pointer, with named ids (GAP-31)
#   rev9_new_sentences_classified_rev10.json the verifier's list with its finding rows' witnesses (R9-1..R9-9) filled
# atom_witness_map.json is written by atom_witness_map_src.py (GAP-W001..W344).
import json, os, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
D5 = os.path.join(HERE, '..', '..')
for ext in ('txt', 'json'):
    src = os.path.join(D5, 'rev7', 'audit_claims_classified.%s' % ext)
    if os.path.exists(src):
        shutil.copyfile(src, os.path.join(HERE, 'rev7_audit_claims_classified.%s' % ext))
    elif ext == 'json':   # the committed rev7 dir holds audit_claims.json; add the classes from the .txt
        claims = json.load(open(os.path.join(D5, 'rev7', 'audit_claims.json')))
        cls = {int(l.split('\t')[0]): l.split('\t')[1] for l in open(os.path.join(D5, 'rev7', 'audit_claims_classified.txt'))}
        for c in claims: c['class'] = cls[c['id']]
        json.dump(claims, open(os.path.join(HERE, 'rev7_audit_claims_classified.json'), 'w'), indent=0, ensure_ascii=False)

# GAP-30: the wide list's 'old' rows, by wide id: (class, witness)
OLD = {
 48: ('P', 'V40, X17b, X30d (descriptor-only reads); V12, X25c (unwrap at every step)'),
 50: ('P', 'X26b, X26c, X26d (coherence on F_T and on intermediate links)'),
 79: ('P', 'X17, V40'),
 110: ('P', 'R22 (pinned residual, revision 7)'),
 111: ('P', 'X26b, X26c, X26d'),
 142: ('H', 'revision-3 history; its fix is witnessed by X146'),
 147: ('P', 'V67'),
 150: ('P', 'X119'),
 157: ('C', 'rev5/out_freed_id_calls.txt; X137f, X157c'),
 164: ('P', 'V47; G_FI fork scenario C9'),
 169: ('P', 'X135, H8 (I1)'),
 171: ('P', 'X37 (3.10/3.11: scoring works); G_XVER'),
 174: ('H', 'rejected design'),
 176: ('P', 'X156, X156b, X156c, X156d, X156f, X156g, X156h'),
 181: ('D', 'X156 (only the prefix is compared)'),
 207: ('P', 'X158e'),
 224: ('P', 'G_HYG (no try in a loop; #130279 clause); X140'),
 228: ('P', 'X154d, X154c'),
 229: ('D', 'X157b'),
 240: ('P', 'X154 (_set_local sweep); G_ATOM _set_local cases'),
 241: ('P', 'X152; G_HYG (_retire has no step 6)'),
 243: ('P', 'X146d'),
 268: ('H', 'history'),
 300: ('P', 'G_HYG (event-set clause); rev1/p11-p13 (C)'),
 301: ('C', 'synth/p_syn1.py; G_COVER named list (callback lines seen only by the driver)'),
 311: ('P', 'X146; G_HYG (_detach never assigns o.frame)'),
 333: ('C', 'G_ATOM part R (critic8/c4, rev8/r8_recursion_sweep.py)'),
 343: ('C', 'G_ATOM part D2 (rev6/t1d2_discriminating.py)'),
 344: ('C', 'G_ATOM part D2'),
 358: ('P', 'X158d; G_ATOM finalizer case; K14'),
 391: ('P', 'model property U1 (rev5/m5_modelcheck.py .. rev8/m8_modelcheck.py); X143, X145 (sweeps)'),
 394: ('P', 'model property U1; G_FI C4 (no MONITOR_LOST allowance); X152'),
 395: ('P', 'G_HYG index clause; G_ATOM _register cases with S set; K13'),
 398: ('P', 'model property STALE; X152; G_FI C5 (global_events 0)'),
 407: ('C', 'rev5/spec_rev5_eventpath.py'),
 459: ('G', 'G_ATOM interface (the gate itself)'),
 468: ('P', 'X72, X72b; SM2 normalizer'),
 470: ('P', 'X117, X117b, X117c, X103b, X117e'),
 483: ('P', 'G_HYG (setprofile/settrace clause); leftover check'),
 521: ('P', 'G_HYG (no lock clause); G_SIG (0 user-lock leaks, 0 hangs)'),
 524: ('H', 'history'),
 527: ('P', 'model properties U1 and FALSEFLAG; G_FI C4'),
 533: ('P', 'X144; G_FI C5'),
 542: ('P', 'X135; G_FI callback-only scenario (C1)'),
 549: ('P', 'X154; rev5/out_freed_id_calls.txt (C)'),
 559: ('P', 'model greenlet configurations (rev5..rev8 m*_modelcheck.py, property U1); X137f'),
 586: ('G', 'G_REF'),
 611: ('S', 'Blockers row: X138, X139, X37'),
 642: ('S', 'V33, V48, V57-V60'),
 643: ('S', 'X137, X142, X154'),
 664: ('D', 'X73'),
 682: ('D', 'V47'),
 685: ('C', 'rev1/p4_freeze.py; V36b'),
 695: ('D', 'X34b (fixture rule), over-blocking #21'),
 716: ('C', 'H10 untraced cell'),
 737: ('P', 'X154, X155, X154b (the bounded exception)'),
 738: ('P', 'X154'),
 750: ('P', 'model greenlet configurations; X137f'),
 752: ('G', 'G_XVER'),
 756: ('G', 'placement rule (the harness itself)'),
 766: ('G', 'fresh-wrapper rule (the harness itself)'),
 784: ('G', 'instruction-sweep rule'),
 790: ('G', 'fault-tool rule'),
 794: ('G', 'injector rule'),
 806: ('C', 'rev1/p16_handler_events.py'),
 816: ('N', 'X30d'),
 836: ('N', 'X140'),
 905: ('N', 'X156'),
 987: ('G', 'Mutation audit (the table itself)'),
 1002: ('G', 'SM2 manifest rule'),
 1016: ('G', 'SM1 procedure'),
 1026: ('G', 'SM1 P04 (EQUIVALENT_BY_SPEC argument, signed before the freeze)'),
 1057: ('G', 'positive control'),
 1088: ('G', 'G_FI C1'),
 1093: ('H', 'history'),
 1132: ('P', 'G_HYG index clause; K13'),
 1157: ('G', 'G_COVER'),
 1161: ('G', 'G_COVER'),
 1164: ('G', 'G_COVER; rev2/p5b_settrace_blinds_injector.py (C)'),
 1179: ('G', 'G_COVER'),
 1205: ('G', 'G_ATOM'),
 1209: ('G', 'G_HYG step controls'),
 1215: ('G', 'G_ATOM part R control K7'),
 1229: ('G', 'G_ATOM'),
}
wide = json.load(open(os.path.join(D5, 'rev9', 'appendix_a', 'wide_claims_classified.json')))
old = {}
for r in wide:
    if r.get('class') == 'old' and r['id'] not in old:
        k, w = OLD[r['id']]
        old[r['id']] = {"text": r['text'], "line_rev8": r['line'], "class": k, "witness": w}
assert len(old) == len(OLD), (len(old), len(OLD), sorted(set(OLD) ^ set(old)))
json.dump(old, open(os.path.join(HERE, 'wide_old_rows_resolved.json'), 'w'), indent=1, ensure_ascii=False)

# GAP-31: pointer witnesses replaced by named ids (atom id -> witness)
PTR = {
 "R-TARGET_IDENTITY-003": "X01, X02, X03, X04, X05",
 "R-TARGET_IDENTITY-023": "X16, X16b",
 "R-TARGET_IDENTITY-028": "X12",
 "R-TARGET_IDENTITY-030": "X14, X14b, X14c",
 "R-TARGET_IDENTITY-035": "X15, X17",
 "R-TARGET_IDENTITY-068": "X30d, V38",
 "R-TARGET_IDENTITY-071": "X26, X27, X28, X29, X29b",
 "R-TARGET_IDENTITY-098": "X55, X56, X55d",
 "R-TARGET_IDENTITY-112": "V36b, X57",
 "R-ATTRIBUTION-120": "X74, X74b, X74c, X74d",
 "R-ATTRIBUTION-132": "X60, X61, X82, X83, V35, X123",
 "R-MECHANISM_AND_LIFECYCLE_M1-022": "X156, X156b, X156c, X156d, X156f, X156g, X156h",
 "R-MECHANISM_AND_LIFECYCLE_M1-038": "rev5/m5_modelcheck.py properties U1, END and P8 (holders read lock-free in every configuration); V17",
 "R-MECHANISM_AND_LIFECYCLE_M1-040": "X123, V28b",
 "R-MECHANISM_AND_LIFECYCLE_M3-053": "rev6/m6_modelcheck.py property STALE (F20); rev6/p_first_reconcile.py",
 "R-MECHANISM_AND_LIFECYCLE_M4-055": "X133, X139; rev5/m5_modelcheck.py property END",
 "R-MECHANISM_AND_LIFECYCLE_M6-007": "X123, V28b, V22",
 "R-MECHANISM_AND_LIFECYCLE_M7-033": "reading (N2; no allocation-fault injector exists)",
 "R-MECHANISM_AND_LIFECYCLE_M7-035": "reading (N2)",
 "R-MECHANISM_AND_LIFECYCLE_M7-164": "rev7/m7_modelcheck.py and rev8/m8_modelcheck.py cb2: configurations, property LOSTNOTE",
 "R-EXCEPTION_SAFETY_MODEL-073": "X10, X11, X13, X10c; G_FI C2 (third alternative)",
 "R-EXCEPTION_SAFETY_MODEL-166": "rev6/m6_modelcheck.py greenlet configurations, properties U1 and LOSTNOTE; X137f, X158d",
 "R-REASON_CODES-005": "X08",
 "R-REASON_CODES-006": "X37, X37b, X156, X156b-X156d, X156f-X156i",
 "R-REASON_CODES-008": "X35, X35b, X35c",
 "R-REASON_CODES-009": "X10, X11, X12, X13, X13b, X33, X10c",
 "R-REASON_CODES-010": "X14, X14b, X14c, X14d",
 "R-REASON_CODES-014": "X26-X30, X26b-X26f, X29b, X30d",
 "R-REASON_CODES-015": "X36",
 "R-REASON_CODES-018": "X31, X59, X59c, X59d, X59e",
 "R-REASON_CODES-020": "X78, X78f, X78g",
 "R-REASON_CODES-022": "X55, X56, X55d",
 "R-REASON_CODES-028": "X95, X95b, X96d",
 "R-REASON_CODES-031": "X55-X59, X76, X78, X79, X32, X59e",
 "R-REASON_CODES-032": "X116, X78e",
 "R-OVER_BLOCKING_DISCLOSED-075": "critic3/c10_aiodebug_overblock.py (a disclosure pinned by its probe; no exam case)",
 "R-OVER_BLOCKING_DISCLOSED-076": "critic3/c10_aiodebug_overblock.py",
 "R-STATED_LIMITS-024": "X26b, X26c, X26d",
 "R-STATED_LIMITS-044": "H10 untraced cell; rev2/p4_unwind_scope.py",
 "R-STATED_LIMITS-112": "rev6/m6_modelcheck.py greenlet configurations (the switch inside a transaction); X137f",
}
json.dump(PTR, open(os.path.join(HERE, 'pointer_witness_map.json'), 'w'), indent=1, ensure_ascii=False)

# the verifier's list, adopted as spec data with the finding rows' witnesses filled by revision 10
V = json.load(open(os.path.join(D5, 'rev9', 'appendix_a', 'rev9_new_sentences_classified.json')))
FILL = {90: 'X24f (callee None), X24b, X24c', 91: 'X24c, X24f (metaclass counter)', 128: 'X78h, X78f variant (rev10)',
        130: 'X78f variant (rev10: repr/str/format and metaclass counters)', 132: 'X84', 170: 'reading (F34; R9-10)',
        194: 'X156g, X156h', 199: 'X08; M0 order: X156i', 200: 'X156i', 203: 'X156i', 204: 'X156i; G_HYG order clause (rev10)',
        221: 'G_HYG reload clause; X156g, X156h', 227: 'X156h', 483: 'reading (R9-7)', 485: 'reading (R9-7); rev9/verify/p_cpython_rev9.py',
        494: 'V72; leftover check (free)', 498: 'leftover check as revision 10 states it (R9-6); M10-S0 smoke case',
        500: 'M10-S0 smoke case; G_FI S0; rev9/out_texts.txt', 519: 'X117e', 520: 'X117e', 524: 'X117f, X117d', 528: 'X93e, X78f variant, X24f'}
for r in V['sentences']:
    if r['id'] in FILL:
        r['witness_rev10'] = FILL[r['id']]
V['revision10'] = ("Adopted as spec data by revision 10 (Appendix A, rule 1). Rows with a finding carry 'witness_rev10', "
                   "the witness revision 10 added; 116 of the 164 sentences are new texts and 48 are revision-8 rows that "
                   "moved (R9-11).")
json.dump(V, open(os.path.join(HERE, 'rev9_new_sentences_classified_rev10.json'), 'w'), indent=1, ensure_ascii=False)
print('old rows', len(old), 'pointers', len(PTR), 'verifier rows filled', sum('witness_rev10' in r for r in V['sentences']))
