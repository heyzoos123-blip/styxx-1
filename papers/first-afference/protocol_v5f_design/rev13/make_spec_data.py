# rev13 (GAP-51, GAP-53, GAP-55; G_INDEP): the prior-work files revision 13 declares spec data, copied or pinned.
#  spec_data/                      copies of the files the text names directly (byte-identical; sha256 in the manifest)
#  spec_data/kill_shapes_r13.json  the 29 round-4 exam-hole kill shapes: key, the verifier's kill shape, the v5e
#                                  mutant's files in protocol_v5_redteam/, and the v5f case(s) the text names
#  spec_data/manifest_r13.json     every declared file with its sha256: the copies, every tracked file of the prior-work
#                                  set in place, and v5e's implementation as the blob of commit 8b805e26
# Run from anywhere: python3 make_spec_data.py   (reads git; writes only under rev13/spec_data/)
import hashlib, json, os, re, shutil, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=HERE, capture_output=True, text=True, check=True).stdout.strip()
PA = 'papers/first-afference'
OUT = os.path.join(HERE, 'spec_data')
def sha(b): return hashlib.sha256(b).hexdigest()
def rd(p): return open(os.path.join(REPO, p), 'rb').read()
COPIES = {
  'mutation_gate_blindspots.json': PA + '/mutation_gate_blindspots.json',
  'round4_exam_mutation/mutants.py': PA + '/protocol_v5_redteam/round4_exam_mutation/mutants.py',
  'round4_exam_mutation/semantic_mutation_census.json': PA + '/protocol_v5_redteam/round4_exam_mutation/semantic_mutation_census.json',
  'round4_exam_mutation/semantic_mutation_census.py': PA + '/protocol_v5_redteam/round4_exam_mutation/semantic_mutation_census.py',
  'round4_verdicts.json': PA + '/protocol_v5_redteam/round4/verdicts.json',
}
man = {'declared_by': 'v5f design, revision 13 (GAP-51, GAP-53, GAP-55, G_INDEP)', 'repo_head_at_declaration':
       subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip(),
       'copies': [], 'prior_work_in_place': [], 'v5e_implementation': None}
for dst, src in COPIES.items():
    b = rd(src); p = os.path.join(OUT, dst); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(b)
    man['copies'].append({'path': 'protocol_v5f_design/rev13/spec_data/' + dst, 'source': src, 'bytes': len(b), 'sha256': sha(b)})
# the prior-work set, in place: every tracked file under protocol_v5_redteam/, and the v5-v5e top-level files
tracked = subprocess.run(['git', 'ls-files', PA], cwd=REPO, capture_output=True, text=True, check=True).stdout.split('\n')
TOP = re.compile(r'^(DESIGN_protocol_v5e_.*\.md|PREREG_protocol_v5[a-e]?_.*\.md|run_protocol_v5[a-e]?\.py|run_protocol_v5e_mutation_gate\.json|'
                 r'protocol_v5[a-e]?_.*\.json|protocol_v5e_round4_summary\.py|fuzz_v5e\.py|aux_v5e\.py|fault_injection_v5.*|'
                 r'mutation_gate.*|FINDING_protocol_v5e_round4_.*|ERRATUM_v5_hand_scored_claim_.*)$')
for p in tracked:
    if not p: continue
    rel = p[len(PA) + 1:]
    if 'v5f' in rel.lower(): continue
    if rel.startswith('protocol_v5_redteam/') or rel.startswith('nversion_v5e/') or ('/' not in rel and TOP.match(rel)):
        b = rd(p); man['prior_work_in_place'].append({'path': p, 'bytes': len(b), 'sha256': sha(b)})
blob = subprocess.run(['git', 'show', '8b805e26:styxx/protocol.py'], cwd=REPO, capture_output=True, check=True).stdout
man['v5e_implementation'] = {'path': 'styxx/protocol.py', 'commit': '8b805e26', 'extract': 'git show 8b805e26:styxx/protocol.py',
                             'bytes': len(blob), 'sha256': sha(blob),
                             'note': 'v5e as frozen and scored; mutation_gate_blindspots.json and semantic_mutation_census.json '
                                     'carry the same impl_sha256. Read and run as this blob only, never as the working-tree file '
                                     'once the v5f implementation has been committed there.'}
# the 29 kill shapes
V = json.loads(rd(PA + '/protocol_v5_redteam/round4/verdicts.json'))
C = json.loads(rd(PA + '/protocol_v5_redteam/round4/candidates_and_dedup.json'))
cand = {}
for e in C.get('all', []) + C.get('fresh', []):
    if isinstance(e, dict) and 'key' in e: cand.setdefault(e['key'], e)
ver = {e['key']: e for e in V['exam_hole_verifiers']}
design = open(os.path.join(REPO, PA, 'DESIGN_protocol_v5f_DRAFT_2026_09_25.md'), encoding='utf-8').read()
sec = design[design.index('### The exam-hole kill cases'):design.index('### Hazard sweeps')]
# the v5e mutants and finders' files that carry no key in their path (round4/exam-mutation/r1/ and round4/scoring/r1/)
EXTRA = {'exam-mut-bad-trace-end-type': ['exam-mutation/r1/m_B01_end_type_clause_dropped.py'],
         'exam-mut-hop-close-drops-closer-hook': ['exam-mutation/r1/m_C01_hop_close_drops_closer_hook.py'],
         'exam-mut-profiler-lost-only-if-none': ['exam-mutation/r1/m_C02_lost_note_only_if_none.py'],
         'exam-mut-close-removes-foreign-profiler': ['exam-mutation/r1/m_C06_close_removes_foreign_profiler.py'],
         'exam-mut-section-decl-clauses': ['exam-mutation/r1/m_D01_section_non_ascii_accepted.py'],
         'exam-mut-restore-over-swapped-code': ['exam-mutation/r1/m_E01_restore_over_swapped_code.py'],
         'exam-mut-stop-cleared-by-inner-exit': ['exam-mutation/r1/m_E04_stop_cleared_by_inner_exit.py'],
         'exam-mut-double-exit-state-leak': ['exam-mutation/r1/m_E05_double_exit.py'],
         'exam-mut-exit-removes-foreign-profiler': ['exam-mutation/r1/m_E07_exit_removes_foreign_profiler.py'],
         'exam-mut-uncredited-last-thread-wins': ['exam-mutation/r1/m_K01_record_uncredited_last_thread_wins.py'],
         'exam-mut-foreign-profiler-first-open-only': ['exam-mutation/r1/m_O05_foreign_profiler_checked_first_open_only.py'],
         'exam-mut-nested-by-section-name': ['exam-mutation/r1/m_O07_nested_refused_across_tracers_by_name.py'],
         'exam-mut-target-set-before-stale': ['exam-mutation/r1/m_S01_target_set_before_stale.py'],
         'exam-mut-problems-before-bad-count': ['exam-mutation/r1/m_S02_problems_before_bad_count.py'],
         'exam-hole-coverage-on-failing-bar': ['scoring/r1/f5_exam_hole_failing_bar.py'],
         'exam-hole-score-step-order': ['scoring/r1/f6_exam_hole_step_order.py'],
         'exam-hole-diagnostic-texts': ['scoring/r1/f10_exam_hole_diagnostic_texts.py']}
for k, fs in EXTRA.items():
    for f in fs: assert PA + '/protocol_v5_redteam/round4/' + f in tracked, f
rows = []
for line in sec.splitlines():
    m = re.match(r'^\| (exam[-a-z0-9]+) \| (.*) \| (.*) \|$', line)
    if not m: continue
    key, shape, cases = m.groups()
    files = [p for p in tracked if p.startswith(PA + '/protocol_v5_redteam/') and key in p]
    files += [PA + '/protocol_v5_redteam/round4/' + f for f in EXTRA.get(key, ())]
    ce = cand.get(key, {}); ve = ver.get(key, {})
    rows.append({'key': key, 'title': ce.get('title'), 'claim': ce.get('claim'),
                 'exam_case_that_would_kill_it': ve.get('exam_case_that_would_kill_it') or ce.get('exam_case_that_would_kill_it'),
                 'design_text_shape_abridged': shape, 'v5f_cases': cases, 'files_in_protocol_v5_redteam': files})
assert len(rows) == 29, len(rows)
kb = json.dumps({'what': 'the 29 round-4 exam-hole kill shapes (SM1 required content), from protocol_v5_redteam/round4/',
                 'rows': rows}, indent=1, ensure_ascii=False).encode()
open(os.path.join(OUT, 'kill_shapes_r13.json'), 'wb').write(kb)
man['copies'].append({'path': 'protocol_v5f_design/rev13/spec_data/kill_shapes_r13.json', 'source': 'extract (this script)',
                      'bytes': len(kb), 'sha256': sha(kb)})
open(os.path.join(OUT, 'manifest_r13.json'), 'w').write(json.dumps(man, indent=1))
print(len(man['copies']), 'copies;', len(man['prior_work_in_place']), 'prior-work files in place; v5e blob', man['v5e_implementation']['sha256'][:16])
print('kill shapes with no verifier text:', [r['key'] for r in rows if not r['exam_case_that_would_kill_it']])
print('kill shapes with no files:', [r['key'] for r in rows if not r['files_in_protocol_v5_redteam']])
