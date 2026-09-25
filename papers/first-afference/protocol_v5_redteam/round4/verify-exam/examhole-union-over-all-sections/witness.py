"""Witness: a call credited to ANOTHER gate's section must not satisfy a gate (spec: 'A gate is
judged on the union of `calls` over all openings of ITS section')."""
import json, sys
sys.path.insert(0, "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify-exam/examhole-union-over-all-sections")
import witlib
P = witlib.load(sys.argv[1])
m = witlib.fixture("wu_fx", """
    def f(): return 1
    def g(): return 2
""")
T = lambda n: f"wu_fx:{n}"
out = {}
# W1a: sections swapped: A (declares f) runs only g; B (declares g) runs only f.
e = witlib.exp(P, {"A": {"exercises": [T("f")]}, "B": {"exercises": [T("g")]}})
out["W1a_swapped"] = witlib.outcome(P, e, lambda cov: (cov.run("A", m.g), cov.run("B", m.f)))
# W1b: A forgot f entirely; only B's section ran f (B also exercises its own g).
e = witlib.exp(P, {"A": {"exercises": [T("f")]}, "B": {"exercises": [T("g")]}})
out["W1b_A_forgot_f"] = witlib.outcome(P, e, lambda cov: (cov.run("A", m.g),
                                                         cov.run("B", lambda: (m.f(), m.g()))))
# W1c: both gates declare f, each section calls f once: counts per gate must be 1, not 2.
e = witlib.exp(P, {"A": {"exercises": [T("f")]}, "B": {"exercises": [T("f")]}})
out["W1c_counts"] = witlib.outcome(P, e, lambda cov: (cov.run("A", m.f), cov.run("B", m.f)))
# W1d (check_metrics, the pre-run tool): same trace as W1a.
e = witlib.exp(P, {"A": {"exercises": [T("f")]}, "B": {"exercises": [T("g")]}})
with P.coverage_trace(e) as cov:
    cov.run("A", m.g); cov.run("B", m.f)
cm = e.check_metrics({"m": 1.0, "coverage_trace": cov.record()})
out["W1d_check_metrics_A_usable"] = cm["A:exercises"]["usable"]
print(json.dumps(out))
