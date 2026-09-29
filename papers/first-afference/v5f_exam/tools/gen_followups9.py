"""Build the 'Revision 9 follow-ups' section of SPEC_GAPS.md from rules_v5f.json."""
import json, collections
import os, sys
# usage: python tools/gen_followups9.py RULES_JSON (the revision-9 rules) -> followups.md in the cwd
d = json.load(open(sys.argv[1]))
R = d['rules']; C = d['meta']['counts']
g = [b for b in R if b['needs_witness']]
ptr = [b for b in R if b.get('list_witness_names_id') is False and b['witness']]
old = [b for b in R if 'rev7_list_unread' in b['class_source']]
def esc(t, n=170):
    t = ' '.join(t.split()).replace('|', '\\|')
    return t if len(t) <= n else t[:n-1] + '…'
def cls(xs):
    return ', '.join(f'{k} {v}' for k, v in collections.Counter(b['class'] for b in xs).most_common())
L = []; A = L.append
A("")
A("## Revision 9 follow-ups (raised after the revision-9 text; for the spec owner)")
A("")
A("These come from two sources. The first is reconciling `rules_v5f.json` with Appendix A's classified lists (revision 9, GAP-27: \"The classified lists are spec data\"). The second is a read of the revision-9 text for contradictions. The atoms were re-extracted from the revision-9 text with the revision-8 algorithm, and each atom's `rev8_ids` field links it to its revision-8 atom. The reconciliation followed the three rules of Appendix A. Rule 1 was applied only to the wide list, `rev9/appendix_a/wide_claims_classified.json`: the revision-7 list is outside what this author may read (see GAP-30). `rules_v5f.json`'s `meta.reconciliation` states the rule-2 reading used. The verifier's commit 2e8cc8a0 added `rev9/appendix_a/rev9_new_sentences_classified.json` and `.txt` to the branch while this reconciliation ran. The revision-9 text does not name them as spec data (Appendix A names the revision-7 list and the wide list only), so they were neither read nor used here, and the atoms that hold a revision-9 sentence are classed by rule 2. Once the text adopts that list, the reconciliation is re-run with it under rule 1.")
A("")
A("**Counts.** " + f"{C['atoms']:,} atoms: " + ", ".join(f"{k} {v}" for k, v in C['by_class'].items()) + f". {C['class_from_wide_list']} take their class from the wide list (rule 1). {C['class_by_rule2']:,} are classed by rule 2: {C['rule2_rev7_list_unread']} of these match a wide-list row that defers to the revision-7 list, and {C['rule2_rev9_new_sentence']} contain a sentence of `rev9_new_sentences.json`. Of the {C['PDC']:,} P, D and C atoms, {C['PDC_with_witness']} have a witness. The other **{C['PDC_without_witness']}** have none ({', '.join(f'{k} {v}' for k, v in C['PDC_without_witness_by_class'].items())}, C 0), and each is a gap below (GAP-W001 to GAP-W{len(g):03d}). The wide list's {C['wide_list_sentences_total']:,} sentences: {C['wide_list_sentences_matched']:,} fall inside an atom. The rest were changed by revision 9, or split differently by the two extractions, and rule 2 classes the atoms that now hold them.")
A("")
A("| gap | section | blocks the freeze? |")
A("|---|---|---|")
A(f"| GAP-W001 to GAP-W{len(g):03d} | {len(g)} P and D atoms with no witness (Appendix A rule 3) | **yes** (rule 3: \"the freeze waits for it\") |")
A(f"| GAP-30 | Rule 1 needs the revision-7 list, which the exam author may not read | **yes** (process: rule 1 is incomplete for {len(old)} atoms) |")
A(f"| GAP-31 | {len(ptr)} atoms take a wide-list witness that names no case, property, gate clause or probe | no, unless the owner rules that pointers are not witnesses |")
A("| GAP-28 | Reason codes: the UNSUPPORTED_VERSION row omits revision 9's `_get_running_loop` check | no |")
A("| GAP-29 | X156g says \"X65d's shape\" but describes another shape | no |")
A("")
A("**GAP-28. Reason codes, UNSUPPORTED_VERSION, vs M0 (revision 9, GAP-02).**")
A("- *The contradiction.* The row's \"when it fires\" cell lists these causes: the interpreter; a `sys.monitoring` function to be bound or already bound in `_MON`; a one-call name that is not the C object it names. It does not list the cause revision 9 added in M0 step 6: `asyncio.events._get_running_loop` is not the builtin of `_asyncio` (case X156g). That refusal fires under M0, and the exam judges it by its code prefix, so the row is incomplete, not wrong about any outcome.")
A("- *Reading taken.* M0 is normative. `ref_v5f.py` raises UNSUPPORTED_VERSION at step 6, with the M0 refusal template.")
A("- *Fix needed.* Add the `_get_running_loop` check to the row. The row's \"a `sys.monitoring` function to be bound, or already bound in `_MON`\" already covers the seventh function.")
A("")
A("**GAP-29. X156g (revision 9) vs X65d.**")
A("- *The contradiction.* X156g \"runs X65d's shape\", and then describes it as a loop whose `_run_once` runs ready handles' callbacks directly, running *a coroutine that calls f*. X65d's own row describes something else: another thread's `call_soon_threadsafe` job that calls f, through `map(operator.call, …)`. The two differ in who schedules f. Both give NOT_EXERCISED `dispatched {f:1}` unpatched.")
A("- *Reading taken.* `smoke_cases.py` X156g follows X156g's own sentence (a coroutine run by `run_until_complete` on the direct-dispatch loop). It passes on both interpreters: UNSUPPORTED_VERSION under the spec; the control, unpatched, gives NOT_EXERCISED `dispatched {f:1}`. My weakening `mut_grl_nocheck` gives PASS `{f:1}`.")
A("- *Fix needed.* Say which of the two shapes the frozen runner uses, or drop \"X65d's shape\".")
A("")
A("**GAP-30. Appendix A's rule 1 needs the revision-7 list, which the exam author may not read.**")
A("- *What is missing.* Rule 1 says an atom whose sentence is in *either* list takes that list's class and witnesses. The revision-7 list is `protocol_v5f_design/rev7/audit_claims_classified.txt`. The exam author's brief allows only `protocol_v5f_design/rev9/appendix_a/` under that directory, so the revision-7 list was not read. In the wide list, 84 rows have class `old`: they are covered by the revision-7 audit, and their witness field reads only \"revision 7 audit\". " + f"{len(old)} atoms contain such a sentence and no classified one ({cls(old)} after rule 2).")
A("- *Reading taken.* Those atoms are classed by rule 2, and `class_source` marks them `rule2_table_rev7_list_unread`. " + f"{sum(1 for b in old if b['needs_witness'])} of them still have no witness and are among the W gaps.")
A("- *Fix needed.* Either commit the revision-7 list into `rev9/appendix_a/` (it holds no code), or give the per-sentence class and witness of the 84 `old` rows in the wide list itself. Then this author re-runs the reconciliation.")
A("")
A("**GAP-31. Wide-list witnesses that name nothing checkable.**")
A("- *What is missing.* 53 P, D or C rows of the wide list give a pointer as the witness, not a named case, model property, gate clause or probe. Examples: \"the code's cases (Mutation audit code->case rows; Exam cases)\", \"model (holders read lock-free)\", \"CPython: a frame runs on one thread; X123\" (a C row with a case but no probe), and \"the Verified probe named with it\". " + f"{len(ptr)} atoms take such a witness under rule 1 ({cls(ptr)}). They carry `list_witness_names_id: false`.")
A("- *Reading taken.* Rule 1 is applied as written: these atoms count as witnessed, and they are not W gaps.")
A(f"- *Fix needed.* Rule whether a pointer is a witness. If it is not, name the case, property or probe in the list, or these {len(ptr)} become W gaps.")
A("")
A("**GAP-W001 to GAP-W%03d. P and D atoms with no witness (Appendix A, rule 3).**" % len(g))
A("Each row is one atom of `rules_v5f.json`, and each atom has `needs_witness: true` there. None of them is in either list with a witness. Each names no case, gate clause, invariant, model property or control. Where it cites a revision-9 gap, that gap's row in the Revision 9 table names none either. Its enclosing paragraph, list item or table row names none. Many are steps of a procedure whose case sits in another paragraph; others are definitions that rule 2 read as properties. Either way the text does not tie a witness to the sentence, and rule 3 hands each to the spec owner. \"Line\" is the line in the revision-9 text.")
A("")
A("| gap | atom | line | class | section | sentence |")
A("|---|---|---|---|---|---|")
for i, b in enumerate(g, 1):
    sec = b['section'].split(' > ')
    sec = esc(sec[-1] if len(sec) == 1 else sec[0].split(',')[0][:22] + ' > ' + sec[-1], 60)
    A(f"| GAP-W{i:03d} | {b['id']} | {b['line'] or '?'} | {b['class']} | {sec} | {esc(b['text'])} |")
open('followups.md', 'w').write('\n'.join(L) + '\n')
print(len(g), len(ptr), len(old))
