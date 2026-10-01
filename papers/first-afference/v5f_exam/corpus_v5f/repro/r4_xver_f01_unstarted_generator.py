"""round4/crossversion-spec/r1/f01_unstarted_generator_credited.py, rewritten: declared generator and coroutine
functions whose bodies never run (the generator is dropped unconsumed; the coroutine is built and closed), each in
its own gate's section; whether either body ran, the record and the score."""
MOD = '''
BODY_RAN = []
def scan(rows):
    BODY_RAN.append("scan")
    for r in rows:
        yield r * 2
async def fetch(x):
    BODY_RAN.append("fetch")
    return x
'''


def main(api):
    mod = api.fixture("rp_xv_f01_mod", MOD)
    e = api.exp({"G_gen": ["rp_xv_f01_mod:scan"], "G_co": ["rp_xv_f01_mod:fetch"]},
                sections={"G_gen": "G_gen", "G_co": "G_co"})

    def gen_harness():
        mod.scan([1, 2, 3])
        return 1.0

    def co_harness():
        c = mod.fetch(1)
        ok = type(c).__name__ == "coroutine"
        c.close()
        return 1.0 if ok else 0.0
    out = {"trace": api.trace(e, lambda c: c.run("G_gen", gen_harness), lambda c: c.run("G_co", co_harness))}
    out["body_ran"] = list(mod.BODY_RAN)
    return out
