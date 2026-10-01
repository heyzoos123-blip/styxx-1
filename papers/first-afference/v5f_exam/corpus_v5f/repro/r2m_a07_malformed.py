"""round2_module/a7_malformed.py, rewritten against v5f's record shape: a good record, then malformed traces (the
repro's v4 keys mapped to v5f's: sections, each opening's calls/ambiguous/end/notes, uncredited, problems) and
malformed results, each fed to score() and check_metrics()."""
import copy


def main(api):
    fs = api.fixture("rp_fx_simple", "def f(): return 1\n")
    e = api.exp({"G": ["rp_fx_simple:f"]})
    cov = api.coverage_trace(e)
    with cov:
        cov.run("G", fs.f)
    good = cov.record()
    out = {"good": api.score(e, good)}

    def mut(fn):
        r = copy.deepcopy(good)
        fn(r)
        return r

    def op(r):
        return r["sections"]["G"][0]
    K = "rp_fx_simple:f"

    class Weird(dict):
        def get(self, *a):
            raise RuntimeError("weird get")
    cases = {
        "trace_None": None, "trace_list": [1, 2], "trace_str": "x", "trace_int_huge": 10 ** 400,
        "sections_None": mut(lambda r: r.update(sections=None)),
        "sections_list": mut(lambda r: r.update(sections=[["G", {}]])),
        "section_G_None": mut(lambda r: r["sections"].update(G=None)),
        "section_G_dict": mut(lambda r: r["sections"].update(G={K: 1})),
        "section_G_str": mut(lambda r: r["sections"].update(G=K)),
        "section_G_empty": mut(lambda r: r["sections"].update(G=[])),
        "opening_None": mut(lambda r: r["sections"].update(G=[None])),
        "calls_None": mut(lambda r: op(r).update(calls=None)),
        "count_huge": mut(lambda r: op(r)["calls"].update({K: 10 ** 4000})),
        "count_nan": mut(lambda r: op(r)["calls"].update({K: float("nan")})),
        "count_inf": mut(lambda r: op(r)["calls"].update({K: float("inf")})),
        "count_True": mut(lambda r: op(r)["calls"].update({K: True})),
        "count_0": mut(lambda r: op(r)["calls"].update({K: 0})),
        "count_neg": mut(lambda r: op(r)["calls"].update({K: -1})),
        "count_str": mut(lambda r: op(r)["calls"].update({K: "1"})),
        "count_dict": mut(lambda r: op(r)["calls"].update({K: {}})),
        "calls_extra_target": mut(lambda r: op(r)["calls"].update({"x:y": 1})),
        "calls_key_int": mut(lambda r: op(r)["calls"].update({1: 1})),
        "end_None": mut(lambda r: op(r).update(end=None)),
        "end_bogus": mut(lambda r: op(r).update(end="bogus")),
        "notes_str": mut(lambda r: op(r).update(notes="x")),
        "ambiguous_list": mut(lambda r: op(r).update(ambiguous=[])),
        "sections_key_None": mut(lambda r: r["sections"].update({None: []})),
        "uncredited_None": mut(lambda r: r.update(uncredited=None)),
        "unattributed_count_neg": mut(lambda r: r["uncredited"]["unattributed"].update({K: -1})),
        "problems_None": mut(lambda r: r.update(problems=None)),
        "problems_int": mut(lambda r: r.update(problems=[1])),
        "extra_key": mut(lambda r: r.update(tracer=1)),
        "dict_subclass_get_raises": Weird(good),
        "missing_sections": {k: v for k, v in good.items() if k != "sections"},
        "missing_uncredited": {k: v for k, v in good.items() if k != "uncredited"},
        "missing_problems": {k: v for k, v in good.items() if k != "problems"},
    }
    for name, tr in cases.items():
        out[f"score_{name}"] = api.score(e, tr)
        out[f"metrics_{name}"] = api.metrics(e, {"m": 1.0, "coverage_trace": tr})
    for i, res in enumerate((None, [], "s", 5, {"m": float("nan")}, {"m": 1.0, "coverage_trace": good, 1: 2})):
        out[f"result_{i}_score"] = api.attempt(lambda: e.score(res).verdict)
        out[f"result_{i}_metrics"] = api.metrics(e, res)
    return out
