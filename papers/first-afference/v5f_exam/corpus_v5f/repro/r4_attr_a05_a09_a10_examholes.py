"""round4/attribution/r1/a05_examhole_cut_by_name.py, a09_examhole_union_all_sections.py and
a10_examhole_section_field.py, rewritten: their harness programs (the half that runs against the public API).
a05: an ordinary harness helper named _run called as the section function; a09: section A runs only g and section
B only f, where A declares f and B declares g; a10: (1) two gates sharing one declared section, (2) gates X and Y
whose declared sections are swapped ("Y" and "X"), each gate's work opened under the gate's name. Their other
half (patching v5e's implementation and running v5e's frozen exam on the mutant) is exam tooling for v5e, not a
program against v5f's API (NOT_APPLICABLE.json)."""


def main(api):
    fx = api.fixture("rp_a05_fix", "def f(): return 1\ndef g(): return 2\n")

    def _run(cfg):
        return fx.f() + cfg
    out = {"a05_helper_named_run": api.trace(api.exp({"G": ["rp_a05_fix:f"]}), lambda c: c.run("G", _run, 1))}
    e = api.exp({"A": ["rp_a05_fix:f"], "B": ["rp_a05_fix:g"]})
    out["a09_cross_sections"] = api.trace(e, lambda c: c.run("A", fx.g), lambda c: c.run("B", fx.f))
    e1 = api.exp({"G_fast": ["rp_a05_fix:f"], "G_slow": ["rp_a05_fix:g"]}, sections={"G_fast": "run", "G_slow": "run"})
    out["a10_shared_section"] = api.trace(e1, lambda c: c.run("run", lambda: (fx.f(), fx.g())))
    e2 = api.exp({"X": ["rp_a05_fix:f"], "Y": ["rp_a05_fix:g"]}, sections={"X": "Y", "Y": "X"})
    out["a10_swapped_sections"] = api.trace(e2, lambda c: c.run("X", fx.f), lambda c: c.run("Y", fx.g))
    return out
