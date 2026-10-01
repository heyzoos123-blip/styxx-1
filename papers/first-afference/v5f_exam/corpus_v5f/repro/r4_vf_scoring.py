"""round4/verify/ (the verifiers' repros of the scoring findings), rewritten:
check-metrics-smoke-masks-refusal/own_repro.py: a prereg with a declaring gate G [f, g], a v3 gate S and a
composite gate C (agg max over pop); check_metrics on traces A complete, B NOT_EXERCISED, C SECTION_ABSENT, D stale
(v5e set gates_sha256; v5f's record carries no gates hash, so D is a trace recorded under another prereg whose gates
differ), E no trace, each full and smoke; the smoke contrast with present-but-bad v3 and composite values; score
with smoke=True. unhashable-end-typeerror/verify_end.py: a JSON round-tripped trace whose opening end is untouched,
'finished', 1, None, b'returned', a list, a dict, a set; score and check_metrics. dict-subclass-result-no-trace/
own_repro.py: plain dict, bare dict subclass, defaultdict and OrderedDict results; check_metrics on the subclass; a
v3 prereg's score of a bare dict subclass. check-metrics-overflow-raises/repro.py is round 4's f8 again
(r4_sc_scoring). nested-and-lazy-texts-misstate/repro.py: (a) same-section self-nesting with one gate, (a') A
nesting B with two gates, (b1) a genexpr over precomputed results, (b1g) a genexpr whose body calls g after the
close, (b2) a generator advanced inside the section then returned. str-subclass-section-bad-trace/repro.py: a str
subclass, (str, Enum) members with name == value and name != value, and mixed orders of 'G' and a subclass, each
scored, JSON round-tripped and check_metrics'd; an undeclared (str, Enum) value at open."""
import collections, copy, enum, json


class S(str):
    pass


class E(str, enum.Enum):
    G = "G"
    OTHER = "G2"


class E2(str, enum.Enum):
    GATE = "G"


def main(api):
    out = {}
    m = api.fixture("rp_vf_sc", "def f():\n    return 1\n\ndef g():\n    return 2\n")
    spec = api.spec({"G": ["rp_vf_sc:f", "rp_vf_sc:g"], "S": [], "C": []})
    spec["gates"]["S"] = {"metric": "s", "op": ">=", "value": 0.5}
    spec["gates"]["C"] = {"metric": "c", "op": ">=", "value": 0.5, "agg": "max", "over": "pop"}
    exp = api.Experiment(api.prereg(spec))
    other = api.Experiment(api.prereg(api.spec({"G": ["rp_vf_sc:f"]})))

    def trace(e, body):
        cov = api.coverage_trace(e)
        with cov:
            body(cov)
        return cov.record()
    traces = {"A_complete": trace(exp, lambda c: c.run("G", lambda: (m.f(), m.g()) and None)),
              "B_not_exercised": trace(exp, lambda c: c.run("G", m.f)),
              "C_section_absent": trace(exp, lambda c: None),
              "D_other_prereg": trace(other, lambda c: c.run("G", lambda: (m.f(), m.g()) and None)), "E_no_trace": None}
    for label, tr in traces.items():
        for smoke in (False, True):
            res = {"m": 1.0, "s": 1.0, "c": 1.0, "pop": {"a": 1.0}}
            if tr is not None:
                res["coverage_trace"] = tr
            if smoke:
                res["smoke"] = True
            out[f"smoke_{label}_{smoke}"] = api.metrics(exp, res)
    out["smoke_contrast"] = api.metrics(exp, {"m": 1.0, "s": "oops", "c": 1.0, "pop": [1.0], "smoke": True,
                                              "coverage_trace": traces["B_not_exercised"]})
    out["score_smoke_true"] = api.attempt(lambda: exp.score({"m": 1.0, "s": 1.0, "c": 1.0, "pop": {"a": 1.0},
                                                             "coverage_trace": traces["B_not_exercised"]}, smoke=True).verdict)
    eg = api.exp({"G": ["rp_vf_sc:g"]})
    base = json.loads(json.dumps(trace(eg, lambda c: c.run("G", m.g))))
    for label, end in (("untouched", ...), ("finished", "finished"), ("int", 1), ("None", None), ("bytes", b"returned"),
                       ("list", ["returned"]), ("dict", {}), ("set", {"returned"})):
        rec = copy.deepcopy(base)
        if end is not ...:
            rec["sections"]["G"][0]["end"] = end
        out[f"end_{label}"] = {"score": api.score(eg, rec), "metrics": api.metrics(eg, {"m": 1.0, "coverage_trace": rec})}
    sA = api.spec({"A": ["rp_vf_sc:g"]}, metric="score")
    eA = api.Experiment(api.prereg(sA))
    recA = trace(eA, lambda c: c.run("A", m.g))

    class Result(dict):
        pass
    dd = collections.defaultdict(float)
    dd["score"] = 1.0
    dd["coverage_trace"] = recA
    for label, res in (("plain", {"score": 1.0, "coverage_trace": recA}), ("subclass", Result(score=1.0, coverage_trace=recA)),
                       ("defaultdict", dd), ("ordered", collections.OrderedDict(score=1.0, coverage_trace=recA))):
        out[f"dictsub_{label}"] = api.attempt(lambda: eA.score(res).verdict)
    out["dictsub_metrics"] = api.metrics(eA, Result(score=1.0, coverage_trace=recA))
    s3 = api.spec({"B": []}, metric="score")
    s3["gates"]["B"].pop("exercises")
    out["dictsub_v3"] = api.attempt(lambda: api.Experiment(api.prereg(s3)).score(Result(score=1.0)).verdict)
    e1 = api.exp({"G": ["rp_vf_sc:f", "rp_vf_sc:g"]})
    box = {}

    def inner(c, outer, sec):
        def body():
            try:
                c.run(sec, m.g)
            except api.GateSpecError as ex:
                box[outer + sec] = api.text(str(ex))
        return body
    out["a_self_nesting"] = api.trace(e1, lambda c: c.run("G", inner(c, "G", "G")))
    e2 = api.exp({"A": ["rp_vf_sc:f"], "B": ["rp_vf_sc:g"]})
    out["a_prime_A_over_B"] = api.trace(e2, lambda c: c.run("A", inner(c, "A", "B")))
    out["a_texts"] = box

    def b1():
        rs = [m.f() for _ in range(3)]
        return (r * 2 for r in rs)

    def b1g():
        m.f()
        return (m.g() for _ in range(2))

    def genfn():
        m.f()
        yield 1
        m.g()
        yield 2

    def b2():
        gen = genfn()
        next(gen)
        next(gen)
        return gen
    for label, fn in (("b1", b1), ("b1g", b1g), ("b2", b2)):
        out[label] = api.trace(e1, lambda c: len(list(c.run("G", fn))))
    es = api.exp({"G": ["rp_vf_sc:f"]})
    for label, secs in (("control", ("G",)), ("S", (S("G"),)), ("E_G", (E.G,)), ("E2_GATE", (E2.GATE,)),
                        ("G_then_S", ("G", S("G"))), ("S_then_G", (S("G"), "G")), ("G_then_E2", ("G", E2.GATE))):
        keep = []
        r = api.trace(es, *[(lambda s: (lambda c: c.run(s, m.f)))(s) for s in secs], keep=keep)
        try:
            rec = keep[0].record()
            r["keys"] = sorted(type(k).__name__ + ":" + str.__str__(k) for k in rec["sections"])
            r["json_round_trip"] = api.score(es, json.loads(json.dumps(rec)))
            r["metrics"] = api.metrics(es, {"m": 1.0, "coverage_trace": rec})
        except BaseException as ex:                    # noqa: BLE001
            r["extra"] = type(ex).__name__
        out[f"strsub_{label}"] = r
    out["strsub_undeclared_enum"] = api.trace(es, lambda c: c.run(E.OTHER, m.f))
    return out
