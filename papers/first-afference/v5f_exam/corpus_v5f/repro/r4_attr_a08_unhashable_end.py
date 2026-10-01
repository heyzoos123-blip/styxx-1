"""round4/attribution/r1/a08_unhashable_end.py, rewritten: an opening whose end is a list (unhashable), fed to
score() and check_metrics(); also a dict end."""


def main(api):
    fx = api.fixture("rp_a08_fix", "def f(): return 1\n")
    e = api.exp({"G": ["rp_a08_fix:f"]})
    cov = api.coverage_trace(e)
    with cov:
        cov.run("G", fx.f)
    out = {}
    for label, end in (("list", ["returned"]), ("dict", {"returned": 1})):
        rec = cov.record()
        rec["sections"]["G"][0]["end"] = end
        out[f"{label}_score"] = api.score(e, rec)
        out[f"{label}_metrics"] = api.metrics(e, {"m": 1.0, "coverage_trace": rec})
    return out
