# verify8 (wide self-audit, W3): the reload paragraph (M1, "Reload") says that after importlib.reload(styxx.protocol)
# "that exit's trace and every trace live at that exit note MONITOR_LOST, including traces entered after the reload
# that lost nothing; traces entered after that exit do not". Its only witness was the prototype probe RELOAD
# (rev7/w7_witnesses.py; rev8/w8_witnesses.py), which enters both traces before the reload; no exam case pins it.
# Shape: P and Q entered and run before the reload; reload; R entered and run after it; P exits (its X5 registration
# finds the pre-reload callbacks); S is entered after P's exit; then Q, R, S exit.
# Spec: P, Q, R MONITOR_LOST; S none; every trace PASS its one call. Mutant cbrep_nocount: only P noted.
import sys, os, json, subprocess, importlib
R8 = '/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/rev8'
sys.path.insert(0, R8)

def child(mut):
    import mech8 as mech
    def f(): return 1
    P = mech.Tracer(f); P.__enter__(); P.run('A', f)
    Q = mech.Tracer(f); Q.__enter__(); Q.run('B', f)
    importlib.reload(mech)
    if mut: mech.MUT.update(mut.split('+'))
    R = mech.Tracer(f); R.__enter__(); R.run('C', f)
    P.__exit__(None, None, None)
    S = mech.Tracer(f); S.__enter__(); S.run('D', f)
    Q.__exit__(None, None, None); R.__exit__(None, None, None); S.__exit__(None, None, None)
    return {k: (v.result()['calls'], v.result()['MONITOR_LOST']) for k, v in dict(P=P, Q=Q, R=R, S=S).items()}

if __name__ == '__main__':
    if len(sys.argv) == 2:
        print(json.dumps(child(None if sys.argv[1] == '-' else sys.argv[1]), default=repr)); sys.exit(0)
    for mut in ('-', 'cbrep_nocount'):
        p = subprocess.run([sys.executable, __file__, mut], capture_output=True, text=True, timeout=120)
        out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else 'ERROR ' + p.stderr[-800:]
        print(sys.version.split()[0], 'X158e', 'spec' if mut == '-' else mut, out, flush=True)
