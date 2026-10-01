"""round4/attribution/r1/a01_strsub_section.py, rewritten: section names that are str subclasses (a str-mixin
Enum member, a plain str subclass, numpy.str_ when numpy imports, enum.StrEnum on 3.11+), each run and scored, the
same trace scored after a JSON round trip, and a plain 'G' control."""
import enum, json, sys


class Sec(str, enum.Enum):
    G = "G"


class S(str):
    pass


def main(api):
    fx = api.fixture("rp_a01_fix", "def f(): return 1\n")
    names = {"str_mixin_enum": Sec.G, "str_subclass": S("G")}
    try:
        import numpy as np
        names["numpy_str"] = np.array(["G"])[0]
    except Exception:                                  # noqa: BLE001
        pass
    if sys.version_info >= (3, 11):
        names["StrEnum"] = enum.StrEnum("SE", {"G": "G"}).G
    e = api.exp({"G": ["rp_a01_fix:f"]})
    out = {}
    for label, sec in names.items():
        keep = []
        r = api.trace(e, lambda c: c.run(sec, fx.f), keep=keep)
        try:
            rec = keep[0].record()
            r["key_type_is_str"] = all(type(k) is str for k in rec["sections"])
            r["json_round_trip"] = api.score(e, json.loads(json.dumps(rec)))
        except BaseException as ex:                    # noqa: BLE001
            r["json_round_trip"] = {"raised": type(ex).__name__}
        out[label] = r
    out["control"] = api.trace(e, lambda c: c.run("G", fx.f))
    return out
