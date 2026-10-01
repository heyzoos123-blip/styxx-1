"""round4/identity/r1/a01_code_swap_stub.py, rewritten: (a) a stub from another module installed in place before
the trace by assigning its code to the declared function's __code__, a captured alias called in the section;
(b) a stub function built with the declared module's globals and bound at the declared name before the trace."""
import types


def main(api):
    pw = api.fixture("rp_id_power", "def reachable(n):\n    return sum(i * i for i in range(n)) > 10\n")
    st = api.fixture("rp_id_teststubs", "def fake_reachable(n):\n    return True\n")
    captured = pw.reachable
    original = pw.reachable.__code__
    pw.reachable.__code__ = st.fake_reachable.__code__
    try:
        out = {"a_code_assigned_stub": api.trace(api.exp({"G": ["rp_id_power:reachable"]}),
                                                 lambda c: c.run("G", lambda: [captured(n) for n in range(3)]))}
    finally:
        pw.reachable.__code__ = original
    pb = api.fixture("rp_id_power_b", "def reachable(n):\n    return sum(i * i for i in range(n)) > 10\n")
    pb.reachable = types.FunctionType(st.fake_reachable.__code__, vars(pb), "reachable")
    out["b_functiontype_stub"] = api.trace(api.exp({"G": ["rp_id_power_b:reachable"]}), lambda c: c.run("G", pb.reachable, 3))
    return out
