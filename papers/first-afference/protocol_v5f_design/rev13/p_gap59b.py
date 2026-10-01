# rev13 (GAP-59): G_ATOM parts A and E as revision 13 restates them, run with the exam author's own reference
# pipelines (v5f_exam/atom_v5f.py, read only) on this interpreter.
#   A  the exam author's part_a() (its CALL+C_RETURN instrument is local to the clearing function, as the text's
#      instruments are): one-call rows against the revision-13 floors, and the two-statement control's rows
#   E  revision 13's part-E harness, stated in full in the text: 20 control runs (until the first clear sample, bound
#      50,000 samples) and 3 one-call runs (until 50,000 samples)
# Run: <venv3.12|venv3.13>/bin/python p_gap59b.py
import importlib.util, json, os, sys, threading, time
HERE = os.path.dirname(os.path.abspath(__file__))
EXAM = os.path.join(HERE, '..', '..', 'v5f_exam')
sys.argv = [os.path.join(EXAM, 'atom_v5f.py')]
spec = importlib.util.spec_from_file_location('atom_v5f', os.path.join(EXAM, 'atom_v5f.py'))
AT = importlib.util.module_from_spec(spec); spec.loader.exec_module(AT)
MON, EV = sys.monitoring, sys.monitoring.events
AT.load()
REF = AT.ref_pipelines()
FLOORS13 = {"INSTRUCTION": 40, "CALL+C_RETURN": 18, "setprofile": 3, "opcode": 40}
a = AT.part_a()["rows"]
partA = {"rows": a, "floors_r13": FLOORS13,
         "pass_r13": all(a["clear_one/" + i]["violations"] == 0 and a["clear_one/" + i]["trials"] >= f
                         and a["clear_two/" + i]["violations"] >= 1 for i, f in FLOORS13.items())}

def part_e13(close, floor=50000, until_first=False, T_MAX=60.0):
    """Revision 13's part E: 4 workers; each sets a profile function that calls time.sleep(0) at every c_call made
    from the close function's frame; per section: open_one(k, k), then 3 times {sample; time.sleep(0)}, then
    close(k), then time.sleep(0). sys.setswitchinterval(1e-6) for the run. Totals are added under a harness lock
    every 64 samples and at stop; the main thread polls every 5 ms."""
    ccode = close.__code__; opener = REF["open_one"]; ge = lambda: MON.get_events(AT.RTOOL) & EV.PY_UNWIND
    st = {"samples": 0, "clear": 0, "stop": False}; lock = threading.Lock()
    def prof(frame, event, arg):
        if event == "c_call" and frame.f_code is ccode:
            time.sleep(0)
    def worker():
        sys.setprofile(prof); s = c = 0
        while not st["stop"]:
            k = object(); opener(k, k)
            for _ in range(3):
                s += 1; c += not ge(); time.sleep(0)
            close(k); time.sleep(0)
            if s >= 64:
                with lock: st["samples"] += s; st["clear"] += c
                s = c = 0
        sys.setprofile(None)
        with lock: st["samples"] += s; st["clear"] += c
    AT.A.clear(); MON.set_events(AT.RTOOL, 0)
    old = sys.getswitchinterval(); sys.setswitchinterval(1e-6)
    ths = [threading.Thread(target=worker) for _ in range(4)]; t0 = time.monotonic()
    for t in ths: t.start()
    while not (st["samples"] >= floor or (until_first and st["clear"]) or time.monotonic() - t0 > T_MAX):
        time.sleep(0.005)
    st["stop"] = True
    for t in ths: t.join()
    sys.setswitchinterval(old)
    left = len(AT.A); AT.A.clear(); MON.set_events(AT.RTOOL, 0)
    return {"samples": st["samples"], "clear": st["clear"], "seconds": round(time.monotonic() - t0, 2), "anchors_left": left}

ctrl = [part_e13(REF["clear_two"], until_first=True) for _ in range(20)]
one = [part_e13(REF["clear_one"]) for _ in range(3)]
partE = {"control_runs": len(ctrl), "control_found_clear": sum(1 for r in ctrl if r["clear"] and r["samples"] < 50000),
         "control_samples_at_stop": sorted(r["samples"] for r in ctrl), "control_max_seconds": max(r["seconds"] for r in ctrl),
         "one_call": one, "pass_r13": all(r["clear"] == 0 and r["samples"] >= 50000 for r in one)
                     and all(r["clear"] and r["samples"] < 50000 for r in ctrl)}
print(json.dumps({"version": sys.version.split()[0], "part_A": partA, "part_E": partE}))
sys.stdout.flush(); os._exit(0)
