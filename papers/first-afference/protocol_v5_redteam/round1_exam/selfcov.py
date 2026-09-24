import sys, types, json, tempfile
from pathlib import Path
mode = sys.argv[1]
sys.argv = ['x', '--attempt-b']
sys.path.insert(0, 'papers/first-afference')
import run_protocol_v5 as R
src = open(R.__file__).read().replace('if __name__ == "__main__"', 'if False')
m = types.ModuleType("selfcov"); m.__file__ = R.__file__
exec(compile(src, R.__file__, "exec"), m.__dict__)
fake_v = {f"v{i}": (True, "refused: fake") for i in range(24)}
fake_ok = {f"k{i}": (False, "scored fake") for i in range(9)}
def one_real_call():
    # exactly one genuine pass through the machinery, then fabricate the rest
    r = m._run(m._spec(G={"exercises": [m.T]}), m._sec("G"))
    return r
if mode == "none":
    m.violations = lambda: dict(fake_v); m.valids = lambda: dict(fake_ok)
elif mode == "one":
    m.violations = lambda: (one_real_call(), dict(fake_v))[1]
    m.valids = lambda: (one_real_call(), dict(fake_ok))[1]
m.p1_retro = lambda: {"G4": {"refused": True, "calls": None}, "G1_ungated": {"refused": False, "calls": None}}
m.differential = lambda: {"n_v4_v5_outcome_disagreements": 0, "n_pairable_results": 0, "n_v5_raised_on": 0,
                          "ungated_n_v5_differs_from_committed_verdict": 0, "v4_v5_disagreements": [],
                          "ungated_v5_differs_from_committed_verdict": [], "v4_pin": {}}
m.corpus = lambda: (0, [])
m.main()
d = json.load(open("papers/first-afference/protocol_v5b_result.json"))
print(mode, "->", d["verdict"][:200], "| self coverage:", d.get("coverage"))
