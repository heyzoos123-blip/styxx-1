"""Append the 'Revision 10 follow-ups' section to SPEC_GAPS.md from rules_v5f.json (revision 10).
Usage: python tools/gen_followups10.py > section.md"""
import json, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, '..', 'rules_v5f.json')))
R, C = d['rules'], d['meta']['counts']
by = {b['id']: b for b in R}
gaps = [b for b in R if b['needs_witness']]
unl = [b for b in R if not b['listed']]
disp = [b for b in R if b.get('disputed_by_exam_author')]
def esc(t, n=150):
    t = ' '.join(t.split()).replace('|', '\\|')
    return t if len(t) <= n else t[:n - 1] + '…'
L = []; A = L.append
A("")
A("## Revision 10 follow-ups (raised on the revision-10 text; for the spec owner)")
A("")
A("`rules_v5f.json` was re-extracted from the revision-10 text (`tools/extract_rules.py`) and reconciled with Appendix A's revision-10 data (`tools/reconcile10.py`). Rule 1 was applied in the stated order of precedence: `rev9_new_sentences_classified_rev10.json`, `wide_old_rows_resolved.json`, the wide list, then the revision-7 list. For the revision-7 list, the witness is taken from Appendix A's own revision-7 tables by audit id, since the list has classes only. Then `pointer_witness_map.json` and `atom_witness_map.json` were applied by atom id. A witness counts only if it names a checkable object, under Appendix A's revision-10 definition. Appendix A's convention that \"model\" means the model-check file with the property named is applied, so \"model U1\" counts. \"Reading\" dispositions (R9-7, F37, F38, and revision 7's untestable D claim) are counted apart. Atoms whose text is unchanged keep their revision-9 ids, which the maps are keyed by. New atoms get `-R10-` ids.")
A("")
bc = ', '.join(f'{k} {v}' for k, v in C['by_class'].items())
A(f"**Counts.** {C['atoms']:,} atoms ({C['ids_kept_from_rev9']:,} keep their revision-9 id, {C['ids_new_in_rev10']} are new): {bc}.")
A(f"- P/D/C atoms: {C['PDC']:,}. {C['PDC_with_checkable_witness']:,} have a checkable witness, {C['PDC_resolved_by_reading']} are resolved by reading, and **{C['PDC_without_witness']}** have none (GAP-33 to GAP-35).")
A(f"- Map ids that no longer exist: {', '.join(C['map_ids_not_found_in_rev10_atoms'])}. Revision 10 edited both sentences, and the new atoms name their own witnesses (V72; X156g–X156i). No map text mismatched its atom.")
A(f"- In no list and no map: **{C['unlisted']:,}** atoms ({', '.join(f'{k} {v}' for k, v in C['unlisted_by_class'].items())}). {C['unlisted'] - C['unlisted_with_list_keyword']:,} of them contain none of the lists' keywords. {C['unlisted_with_list_keyword']} contain one; {C['unlisted_new_in_rev10']} of all unlisted atoms are new or edited text in revision 10. Every unlisted P, D or C atom has a witness by rule 2 (GAP-32).")
A(f"- Disputed `definition` rows: {len(disp)} (GAP-36).")
A("")
A("| gap | section | blocks the freeze? |")
A("|---|---|---|")
A("| GAP-32 | The revised rule 3 (\"in no list and no map\") vs rule 2: 1,119 atoms are unlisted by construction | **yes**, as the status line reads (\"with no atom left unlisted\"), until the owner rules |")
A("| GAP-33 | R-MECHANISM_AND_LIFECYCLE_M3-030: its witness names a model mutant and a pointer | **yes** (rule 3) |")
A("| GAP-34 | R-OVER_BLOCKING_DISCLOSED-075: a D claim pinned only by a probe | **yes** (rule 3) |")
A("| GAP-35 | R-OVER_BLOCKING_DISCLOSED-090: the verifier list's witness is stale (\"none pinned\"); X84 now pins it | no (data fix; the atom's paragraph names X84) |")
A(f"| GAP-36 | {len(disp)} `definition` rows the exam author disputes as D claims with no checkable witness | **yes** if the owner agrees they are D; no if the owner keeps them S |")
A("")
A("**GAP-32. Rule 3 as revision 10 words it vs rule 2.**")
A("- *The contradiction.* Revision 10's required change says: \"An atom that is P, D or C and still has no witness, or that appears in no list and no map, is a new gap\". The status line says the freeze waits for `rules_v5f.json` \"with no atom left unlisted\". But the lists hold only sentences with a list keyword (*must, never, always, cannot, nothing, no, none, only, every*), and the maps hold only the 344 GAP-W atoms and the 40 pointer atoms. Rule 2 (\"any other atom is classed by the table\") still exists for every other atom. " + f"{C['unlisted'] - C['unlisted_with_list_keyword']:,} unlisted atoms have no keyword, so no list could hold them. The other {C['unlisted_with_list_keyword']} contain a keyword: text new or edited in revision 10, which no list has seen yet, or table rows and list items split differently from the wide extraction.")
A("- *Reading taken.* Rule 2 classes every unlisted atom, and it takes a witness from the atom, from a revision-9 or revision-10 table row it cites, or from its enclosing paragraph. No unlisted P, D or C atom is left without a witness. Every unlisted atom is marked `listed: false`, so the owner can see each one.")
A("- *Fix needed.* Either say that rule 2 classes unlisted atoms and that only rule 3's witness test applies to them, or extend the lists or maps to every atom. If they are extended, the wide extraction must also be re-run on the revision-10 text, which Appendix A already requires of the frozen text.")
A("")
g = {b['id']: b for b in gaps}
def gblock(n, aid, what, fix):
    b = by[aid]
    A(f"**GAP-{n}. {aid}** (line {b['line']}, class {b['class']}, {b['class_source']}).")
    A(f"- *Atom.* {esc(b['text'], 400)}")
    A(f"- *Witness given.* {esc(b['witness'] or '(none)', 300)}")
    A(f"- *What is missing.* {what}")
    A(f"- *Fix needed.* {fix}")
    A("")
gblock(33, 'R-MECHANISM_AND_LIFECYCLE_M3-030', "Appendix A's revision-7 table gives \"model (`prune_credit_stop` restored changes nothing); M8's refusals\": a model mutant name and a pointer, with no case and no named property.", "Name the case that shows `record()` refusing TRACE_INCOMPLETE for a dead exiting token (an interrupted exit such as X92b), or the model property.")
gblock(34, 'R-OVER_BLOCKING_DISCLOSED-075', "The asyncio-debug over-block is pinned only by `critic3/c10_aiodebug_overblock.py`. Under revision 10's definition a probe witnesses only C claims, and this is a D claim with no exam case.", "Add a case: with asyncio debug mode on, `coverage_trace()` refuses. Or file it as reading.")
gblock(35, 'R-OVER_BLOCKING_DISCLOSED-090', "The verifier list row still says \"none pinned (as #132; verify/p_ref_findings.py FB)\". Revision 10 added X84, which pins over-blocking #23, in the next sentence of the same item.", "Give the row `witness_rev10: X84`.")
A(f"**GAP-36. `definition` rows disputed ({len(disp)}).** Revision 10's weakest point 2 invites this. Each row below is a disclosure (a door, a leak or a user-code site the design admits), so class D by Appendix A's table rather than S. Its map witnesses name no checkable object: a limit's name (L-CLONE, L-MONITOR, L-ZOMBIE), \"over-blocking #19\", a probe (which witnesses only C claims), or nothing. `rules_v5f.json` keeps the map's class and records the dispute in `disputed_by_exam_author`. If the owner agrees, each needs a pinned residual or case, or a reading disposition.")
A("")
A("| atom | map gap | map witnesses | the dispute | atom text |")
A("|---|---|---|---|---|")
for b in disp:
    A(f"| {b['id']} | {b.get('map_gap')} | {esc(b['witness'] or '', 60)} | {esc(b['disputed_by_exam_author'], 110)} | {esc(b['text'], 120)} |")
print('\n'.join(L))
