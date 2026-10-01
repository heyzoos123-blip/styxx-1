"""round4/scoring/r1/f3, f5, f6, f7, f8, f9 and f10, rewritten (f5, f6 and f10: their paired harnesses; their
other half, v5e mutants run against v5e's frozen exam, is exam tooling for v5e, NOT_APPLICABLE.json).
f3: results that are dict subclasses (defaultdict, OrderedDict) carrying the tracer's own record, with an
undeclaring v3 gate beside the declaring one; check_metrics on the defaultdict. f5: a gate declaring f and g whose
harness calls only f, scored with a failing bar (m = 0.0) and a passing one, and a swallowed NESTED_SECTION with a
failing bar. f6: HD, gates G and H, the harness swallows the refusal of a typo'd section 'G_typo' then runs H;
HE, the tracer's own trace with a required key missing (v5e's 'gates_sha256'; v5f's record keys are sections,
uncredited and problems, so each is removed in turn). f7: check_metrics on a smoke result whose trace refuses
NOT_EXERCISED. f8: a JSON-loaded 401-digit int metric to check_metrics and score. f9: (a) a section re-entering
itself (NESTED_SECTION's text), (b) fn doing its work in the section and returning a generator over its results
(LAZY_RESULT's note beside credited calls). f10: run_async section whose two gathered children call f (the
NOT_EXERCISED buckets' labels; check_metrics usable and note)."""
import asyncio, collections, json


def main(api):
    out = {}
    m = api.fixture("rp_sc_fx", "def f():\n    return 1\n\ndef g():\n    return 2\n")
    s = api.spec({"G": ["rp_sc_fx:f"], "H": []})
    s["gates"]["H"].pop("exercises")
    e3 = api.Experiment(api.prereg(s))
    cov = api.coverage_trace(e3)
    with cov:
        cov.run("G", m.f)
    rec = cov.record()
    dd = collections.defaultdict(dict)
    dd["m"] = 1.0
    dd["coverage_trace"] = rec
    out["f3"] = {"plain": api.attempt(lambda: e3.score({"m": 1.0, "coverage_trace": rec}).verdict),
                 "defaultdict": api.attempt(lambda: e3.score(dd).verdict),
                 "ordereddict": api.attempt(lambda: e3.score(collections.OrderedDict(m=1.0, coverage_trace=rec)).verdict),
                 "metrics_defaultdict": api.metrics(e3, dd)}
    s5 = api.spec({"G": ["rp_sc_fx:f", "rp_sc_fx:g"]})
    s5["outcomes"] = [{"when": {"G": True}, "verdict": "PASS"}, {"when": {"G": False}, "verdict": "FAIL"}]
    e5 = api.Experiment(api.prereg(s5))

    def nested(c):
        def inner():
            try:
                c.run("G", m.g)
            except api.GateSpecError:
                pass
            m.f()
        c.run("G", inner)
    out["f5"] = {"not_exercised_bar_fails": api.trace(e5, lambda c: c.run("G", m.f), m=0.0),
                 "swallowed_nested_bar_fails": api.trace(e5, nested, m=0.0),
                 "not_exercised_bar_passes": api.trace(e5, lambda c: c.run("G", m.f), m=1.0)}
    e6 = api.exp({"G": ["rp_sc_fx:f"], "H": ["rp_sc_fx:g"]})

    def hd(c):
        for sec, fn in (("G_typo", m.f), ("H", m.g)):
            try:
                c.run(sec, fn)
            except api.GateSpecError:
                pass
    out["f6_HD"] = api.trace(e6, hd)
    cov = api.coverage_trace(e6)
    with cov:
        cov.run("G", m.f)
        cov.run("H", m.g)
    for k in ("sections", "uncredited", "problems"):
        r = cov.record()
        r.pop(k, None)
        out[f"f6_HE_missing_{k}"] = {"score": api.score(e6, r), "metrics": api.metrics(e6, {"m": 1.0, "coverage_trace": r})}
    e7 = api.exp({"G": ["rp_sc_fx:f", "rp_sc_fx:g"]})
    cov = api.coverage_trace(e7)
    with cov:
        cov.run("G", m.f)
    r7 = cov.record()
    out["f7"] = {"full": api.metrics(e7, {"m": 1.0, "coverage_trace": r7}),
                 "smoke": api.metrics(e7, {"m": 1.0, "smoke": True, "coverage_trace": r7})}
    e8 = api.exp({"G": ["rp_sc_fx:f"]})
    cov = api.coverage_trace(e8)
    with cov:
        cov.run("G", m.f)
    res8 = json.loads(json.dumps({"m": 0, "coverage_trace": cov.record()}).replace('"m": 0', '"m": 1' + "0" * 400))
    out["f8"] = {"metrics": api.metrics(e8, res8), "score": api.attempt(lambda: e8.score(res8).verdict)}
    e9 = api.exp({"G": ["rp_sc_fx:f", "rp_sc_fx:g"]})
    box = {}

    def battery(c):
        def b():
            m.f()
            try:
                c.run("G", m.g)
            except api.GateSpecError as ex:
                box["a"] = str(ex)
        c.run("G", b)
    out["f9_a"] = api.trace(e9, battery)
    out["f9_a_text"] = api.text(box.get("a", ""))

    def battery_b():
        results = [m.f() for _ in range(3)]
        return (r * 2 for r in results)
    out["f9_b"] = api.trace(e9, lambda c: len(list(c.run("G", battery_b))))
    e10 = api.exp({"G": ["rp_sc_fx:f"]})

    async def amain():
        async def child():
            m.f()
        await asyncio.gather(child(), child())
    keep = []
    out["f10"] = api.trace(e10, lambda c: asyncio.run(c.run_async("G", amain)), keep=keep)
    out["f10_metrics"] = api.metrics(e10, {"m": 1.0, "coverage_trace": keep[0].record()})
    return out
