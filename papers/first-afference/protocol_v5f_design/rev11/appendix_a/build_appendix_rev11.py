# rev11: Appendix A data changes (GAP-33 to GAP-36). Writes, beside this script:
#   rev9_new_sentences_classified_rev11.json  the rev10 copy of the verifier's list with row 766 given X84 (GAP-35)
#   atom_witness_overrides_rev11.json         per-atom rulings that override every earlier list and map (GAP-33, 34, 36)
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
R10 = os.path.join(HERE, '..', '..', 'rev10', 'appendix_a')
V = json.load(open(os.path.join(R10, 'rev9_new_sentences_classified_rev10.json')))
for r in V['sentences']:
    if r['id'] == 766:
        r['witness_rev10'] = 'X84'
V['revision11'] = "Row 766 (over-blocking #23's disclosure) carries witness_rev10 X84 (GAP-35). Otherwise identical to the rev10 file."
json.dump(V, open(os.path.join(HERE, 'rev9_new_sentences_classified_rev11.json'), 'w'), indent=1, ensure_ascii=False)
O = {
 "R-MECHANISM_AND_LIFECYCLE_M3-030": {"gap": "GAP-33", "class": "P", "witness": "V72b (record() still refuses TRACE_INCOMPLETE after a later trace pruned the core; mutant mut_prune_marks_exited returns a record); X92, X157"},
 "R-OVER_BLOCKING_DISCLOSED-075": {"gap": "GAP-34", "class": "D", "witness": "X35e (an aiodebug-shaped closure bound as Handle._run: two coverage_trace() calls refuse CUT_UNAVAILABLE, a third after the restore constructs; mutants mut_no_locals_clause, mut_cut_before_scan)"},
 "R-OVER_BLOCKING_DISCLOSED-076": {"gap": "GAP-34", "class": "D", "witness": "X35c's twin-free shape and X65c (dispatch still passes cut codes); probe critic3/c10_aiodebug_overblock.py for the no-soundness-gain remark (reading)"},
 "R-OVER_BLOCKING_DISCLOSED-090": {"gap": "GAP-35", "class": "D", "witness": "X84"},
 "R-TARGET_IDENTITY-111": {"gap": "GAP-36 (W066)", "class": "D", "witness": "X57d (over-blocking #19 pinned: CLONE_ALIVE in the joiner; mutant mut_freeze0_at_join refuses nothing)"},
 "R-TARGET_IDENTITY-130": {"gap": "GAP-36 (W072)", "class": "D", "witness": "R03 (kept v5e residual: an in-trace same-globals clone called and dropped, PASS; rev11/v5e_cases_kept.json)"},
 "R-TARGET_IDENTITY-131": {"gap": "GAP-36 (W073)", "class": "D", "witness": "R04 (kept v5e residual: exec(T.__code__, T.__globals__), PASS)"},
 "R-TARGET_IDENTITY-132": {"gap": "GAP-36 (W074)", "class": "D", "witness": "R23 (new residual: U.__code__ = M_T inside the section, restored before exit: PASS {f:2})"},
 "R-TARGET_IDENTITY-134": {"gap": "GAP-36 (W076)", "class": "D", "witness": "R24 (new residual: a clone frozen by an unfreeze-then-freeze with fewer objects: PASS, credited; mutant mut_freeze_ne refuses CLONE_ALIVE)"},
 "R-MECHANISM_AND_LIFECYCLE_M1-061": {"gap": "GAP-36 (W130)", "class": "D", "witness": "V70 (the pending entry holds its frame; a mutant keyed by bare id without the frame fails); the 'callers alive' part is CPython's f_back (C, critic4/a6_pending_left_fault_free.py); G_FI C4 (gone once the mint retires)"},
 "R-MECHANISM_AND_LIFECYCLE_M3-020": {"gap": "GAP-36 (W141)", "class": "D", "witness": "X137j (new: after a reclaim, a foreign tool's local events and its callback for an event styxx does not register stay; its global events are cleared, which revision 11 corrects in M3)"},
 "R-MECHANISM_AND_LIFECYCLE_M11-028": {"gap": "GAP-36 (W224)", "class": "D", "witness": "X117g (new: check_metrics calls an int-subclass metric's __float__ exactly once and its __bool__ never; mutant mut_cm_bool calls __bool__); rev1/p2_dict_collide.py for the collision half (reading: a contrived shape no JSON result can carry)"},
 "R-MECHANISM_AND_LIFECYCLE_M11-029": {"gap": "GAP-36 (W225)", "class": "C", "witness": "rev11/p_rev11.py J225 (json.loads gives exact-str keys, both versions)"},
 "R-EXCEPTION_SAFETY_MODEL-119": {"gap": "GAP-36 (W279)", "class": "D", "witness": "V70; G_FI C4 and C5's pending exclusion (critic4/a6_pending_left_fault_free.py)"},
}
json.dump(O, open(os.path.join(HERE, 'atom_witness_overrides_rev11.json'), 'w'), indent=1, ensure_ascii=False)
print(len(O), 'overrides')
