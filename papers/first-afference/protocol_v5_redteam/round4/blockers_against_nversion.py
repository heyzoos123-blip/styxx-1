"""EXPLORATORY: do round 4's six blocker repros also break the independent second implementation?

The primary implementation (styxx/protocol.py) and the N-version implementation
(nversion_v5e/protocol_nv.py) were written from one frozen spec. They agreed on every exam case and
fuzz program. If round 4's blockers come from the spec rather than from one implementation's bugs, the
same repros should reproduce against both. Each committed repro prints "FINDING-REPRODUCED" when it
reproduces. The script runs each repro against each implementation on each available interpreter and
records whether that line appears. Writes blockers_against_nversion.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FA = ROOT / "papers" / "first-afference"
SP = "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt3"
PYS = [sys.executable] + [f"{SP}/venv3.{v}/bin/python" for v in (10, 12, 13)]
BLOCKERS = {
    "pretrace-code-swap-stub-passes-provenance": "identity/r1/a01_code_swap_stub.py",
    "cache-wrapper-body-from-writable-wrapped": "identity/r1/a02_cache_wrapped_restamped.py",
    "unstarted-generator-credited-py310-311": "crossversion-spec/r1/f01_unstarted_generator_credited.py",
    "stale-stop-after-mint-of-handle-run": "identity/r1/a05_stale_stop_after_mint.py",
    "hook-exception-leaves-lock-held": "lifecycle/r1/f12_hook_exception_leaves_lock_held.py",
    "py310-hook-reverts-closure-writes": "crossversion-spec/r1/f09_py310_closure_writes_lost.py",
}


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="v5e_nvblk_"))
    roots = {"primary": str(ROOT)}
    nv = work / "nv"
    shutil.copytree(ROOT / "styxx", nv / "styxx", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(FA / "nversion_v5e" / "protocol_nv.py", nv / "styxx" / "protocol.py")
    roots["nversion"] = str(nv)
    rows = {}
    for key, rel in BLOCKERS.items():
        script = HERE / rel
        rows[key] = {}
        for impl, root in roots.items():
            for py in PYS:
                if not Path(py).exists():
                    continue
                v = subprocess.run([py, "-c", "import sys;print(sys.version.split()[0])"],
                                   capture_output=True, text=True).stdout.strip()
                env = dict(os.environ, PYTHONPATH=root, STYXX_ROOT=root, PYTHONDONTWRITEBYTECODE="1")
                try:
                    p = subprocess.run([py, str(script)], cwd=script.parent, env=env, capture_output=True,
                                       text=True, timeout=180)
                    out = p.stdout + p.stderr
                    rep = "FINDING-REPRODUCED" in out
                    how = "reproduced" if rep else ("no finding" if "no finding" in out.lower() else f"exit {p.returncode}")
                except subprocess.TimeoutExpired:
                    rep, how, out = None, "timeout", ""
                rows[key][f"{impl}@{v}"] = {"reproduced": rep, "how": how, "tail": out.strip()[-240:]}
    shutil.rmtree(work, ignore_errors=True)
    summ = {k: {impl: sorted(c.split("@")[1] for c, r in v.items() if c.startswith(impl + "@") and r["reproduced"])
                for impl in roots} for k, v in rows.items()}
    res = {"what": "EXPLORATORY: round 4's blocker repros run against the primary and the independent N-version "
                   "implementation on each available interpreter",
           "generator": "papers/first-afference/protocol_v5_redteam/round4/blockers_against_nversion.py",
           "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "nversion_sha256": hashlib.sha256((FA / "nversion_v5e" / "protocol_nv.py").read_bytes()).hexdigest(),
           "primary_sha256": hashlib.sha256((ROOT / "styxx" / "protocol.py").read_bytes()).hexdigest(),
           "reproduced_on": summ,
           "n_blockers": len(BLOCKERS),
           "n_blockers_reproduced_on_nversion": sum(1 for s in summ.values() if s["nversion"]),
           "n_blockers_reproduced_on_primary": sum(1 for s in summ.values() if s["primary"]),
           "rows": rows}
    (HERE / "blockers_against_nversion.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for k, s in summ.items():
        print(f"{k:45s} primary {s['primary']}  nversion {s['nversion']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
