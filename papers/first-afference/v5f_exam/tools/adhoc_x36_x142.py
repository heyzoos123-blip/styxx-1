"""Ad hoc checks of X36 (MONITOR_BUSY) and X142 (a second loaded copy), run by the exam author for
revision 8. Usage: MODE=X36|X142 python tools/adhoc_x36_x142.py (a fresh process per mode)."""
import sys, os, importlib.util
import os
EXAM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(EXAM, 'ref_v5f.py')
sys.argv = [sys.argv[0]]
# reuse the smoke harness's fixtures and preregs
spec = importlib.util.spec_from_file_location('smoke', os.path.join(EXAM, 'smoke_cases.py'))
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
P = S.P
mode = os.environ['MODE']
if mode == 'X36':
    sys.monitoring.use_tool_id(4, 'other4'); sys.monitoring.use_tool_id(3, 'other3')
    cov = P.coverage_trace(S.EXP('F'))
    try:
        cov.__enter__(); print('X36 FAIL no refusal')
    except P.GateSpecError as e:
        print('X36', 'PASS' if str(e).startswith('[V5:MONITOR_BUSY]') else 'FAIL', P._v5_state()['mints'] == [])
if mode == 'X142':
    s2 = importlib.util.spec_from_file_location('copyB', REF); B = importlib.util.module_from_spec(s2); sys.modules['copyB'] = B; s2.loader.exec_module(B)
    expA = S.EXP('F')
    covA = P.coverage_trace(expA); covA.__enter__()
    expB = B.Experiment(expA.prereg.parent / 'PREREG_F.md')
    # copy B declares g via FG prereg? use GH (G:f, H:g) and run only H
    expB = B.Experiment(expA.prereg.parent / 'PREREG_AB.md')
    with B.coverage_trace(expB) as covB:
        covB.run('B', S.fx_v5f.g); covB.run('A', S.fx_v5f.f)
    covA.run('G', S.fx_v5f.f); covA.__exit__(None, None, None)
    ra = covA.record(); rb = covB.record()
    print('X142 A', S.score(expA, ra)[:2], 'notes', ra['sections']['G'][0]['notes'], 'tools', P._v5_state()['tool'], B._v5_state()['tool'])
    print('X142 B', S.score(expB, rb)[:2])
