"""round1_module/t09_v4_checkmetrics.py and t11_backcompat.py, rewritten: their v5 halves (check_metrics on a
list; a gate carrying 'section' or 'exercises' as free-text annotations, scored). Their v4 halves exec v4's
implementation from git (98a5c368), which is not v5f's API (NOT_APPLICABLE.json)."""


def main(api):
    out = {}
    s = api.spec({"G": []})
    s["gates"]["G"].pop("exercises")
    p = api.prereg(s)
    out["check_metrics_list"] = api.metrics(api.Experiment(p), [1])
    for i, extra in enumerate(({"section": "see prose section 3.2"}, {"exercises": "the reachable() path"},
                               {"exercises": ["reachable() on the null"]})):
        s = api.spec({"G": []})
        s["gates"]["G"].pop("exercises")
        s["gates"]["G"].update(extra)
        p = api.prereg(s)
        out[f"annotation_{i}"] = api.attempt(lambda: api.Experiment(p).score({"m": 1.0}).verdict)
    return out
