"""Witness: the gate's declared `section` (not its name) is what score reads."""
import json, sys
sys.path.insert(0, "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify-exam/examhole-declared-section-field-never-scored")
import witlib
P = witlib.load(sys.argv[1])
m = witlib.fixture("ws_fx", """
    def f(): return 1
    def g(): return 2
""")
T = lambda n: f"ws_fx:{n}"
out = {}
# W2a: two gates share one declared section "run"; one opening runs both targets.
e = witlib.exp(P, {"G_fast": {"exercises": [T("f")], "section": "run"},
                   "G_slow": {"exercises": [T("g")], "section": "run"}})
out["W2a_shared_section"] = witlib.outcome(P, e, lambda cov: cov.run("run", lambda: (m.f(), m.g())))
# W2b: one gate with a section name different from its gate name (the simplest use of the key).
e = witlib.exp(P, {"G": {"exercises": [T("f")], "section": "harness"}})
out["W2b_renamed_section"] = witlib.outcome(P, e, lambda cov: cov.run("harness", m.f))
# W2c: cross-named sections: gate X reads section "Y", gate Y reads section "X".
e = witlib.exp(P, {"X": {"exercises": [T("f")], "section": "Y"},
                   "Y": {"exercises": [T("g")], "section": "X"}})
out["W2c_cross_named"] = witlib.outcome(P, e, lambda cov: (cov.run("X", m.f), cov.run("Y", m.g)))
print(json.dumps(out))
