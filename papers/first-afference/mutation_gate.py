"""The refusal-deletion mutation gate for protocol v5 (frozen with PREREG v5e, before v5e exists).

Rounds 2 and 3 of the red team both found exam holes the same way: delete one refusal from the
implementation, re-run the frozen exam, watch it still pass. Each time that was discovered after
scoring, by hand. This makes it mechanical and part of the frozen gates: for EVERY refusal site in
the implementation, a mutant with that one refusal deleted must be DETECTED by the frozen exam.

Definitions, fixed here before any v5e code is written:

* A coded emission site is (a) a ``raise GateSpecError(<msg>)`` statement, or (b) an expression
  statement that is a call whose first positional argument is <msg> -- a refusal helper, a recorded
  problem, or a note appended to a trace -- where <msg> is a string literal or an f-string whose
  LITERAL text begins with a complete code ``[V5:<CODE>]``. Anywhere in ``styxx/protocol.py``.
  Every coded emission must be observable by the exam, notes included.
* The mutant replaces that one statement with ``pass``. Nothing else changes.
* HYGIENE: a ``raise GateSpecError(...)`` inside the v5 region whose message is NOT such a literal
  (a name, a call, a concatenation) is a refusal the mutator cannot see. The v5 region is every
  top-level definition after the line ``# -- v5: the coverage tracer`` plus every ``Experiment``
  method whose name contains ``coverage``. Their count is reported and gated at zero.
* A mutant is DETECTED if the frozen exam, run as ``--smoke --full-battery --mutation-mode``
  (the runner's frozen fast mode: every case except the hazard sweeps and the stress run) against it, exits
  non-zero, times out, reports any violation case not refused with its own code, any valid case
  not scoring with its property, a P1 retro that is not exact, or any crash.
* The UNMUTATED implementation must pass the same run cleanly, or the gate is INVALID: a gate that
  detects everything because the baseline is broken measures nothing.

Isolation: each mutant runs against a private copy of the ``styxx`` package, selected through the
runner's ``STYXX_V5_IMPORT_ROOT`` environment variable; its result goes to ``STYXX_V5_RESULT_OUT``.
The committed tree is never modified. Writes ``<runner stem>_mutation_gate.json``.
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures as cf
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IMPL = ROOT / "styxx" / "protocol.py"
MARKER = "# -- v5: the coverage tracer"


_CODED = re.compile(r"\[V5:[A-Z_]+\]")


def _msg_is_coded(node) -> bool:
    """The message's LITERAL text begins with a complete code, e.g. ``[V5:NOT_EXERCISED]``.

    A message that builds its code at run time (``f"[V5:{code}] ..."``) is not coded: a helper
    that assembles every code in one place would make all refusals a single mutation site, so
    deleting any one of them could never be told apart from deleting all. Such a raise is a
    hygiene violation, not a site.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return bool(_CODED.match(node.value))
    if isinstance(node, ast.JoinedStr) and node.values:
        first = node.values[0]
        return isinstance(first, ast.Constant) and isinstance(first.value, str) \
            and bool(_CODED.match(first.value))
    return False


def _is_gse_raise(stmt) -> bool:
    return (isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Call)
            and isinstance(stmt.exc.func, ast.Name) and stmt.exc.func.id == "GateSpecError")


def refusal_sites(src: str) -> list:
    """(lineno, end_lineno, col, kind, snippet) for every refusal site."""
    tree = ast.parse(src)
    out = []
    for node in ast.walk(tree):
        if _is_gse_raise(node) and node.exc.args and _msg_is_coded(node.exc.args[0]):
            out.append((node.lineno, node.end_lineno, node.col_offset, "raise"))
        elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
              and node.value.args and _msg_is_coded(node.value.args[0])):
            out.append((node.lineno, node.end_lineno, node.col_offset, "refusal_call"))
    lines = src.split("\n")
    return sorted({(a, b, c, k, lines[a - 1].strip()[:100]) for a, b, c, k in out})


def hygiene_violations(src: str) -> list:
    tree = ast.parse(src)
    lines = src.split("\n")
    try:
        marker_line = next(i + 1 for i, ln in enumerate(lines) if ln.startswith(MARKER))
    except StopIteration:
        return [{"line": 0, "problem": f"marker {MARKER!r} absent: the v5 region is undefined"}]
    region = []
    for top in tree.body:
        if top.lineno > marker_line:
            region.append(top)
        elif isinstance(top, ast.ClassDef) and top.name == "Experiment":
            region += [m for m in top.body
                       if isinstance(m, ast.FunctionDef) and "coverage" in m.name]
    # A helper that raises its own message PARAMETER is allowed iff every call to it in the file
    # passes a coded literal first (such calls are refusal_call sites, each mutated on its own).
    calls: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = (node.func.attr if isinstance(node.func, ast.Attribute)
                    else node.func.id if isinstance(node.func, ast.Name) else None)
            if name:
                calls.setdefault(name, []).append(
                    bool(node.args) and _msg_is_coded(node.args[0]))
    bad = []
    for top in region:
        funcs = [n for n in ast.walk(top) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for fn in funcs:
            params = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
            for node in ast.walk(fn):
                if not _is_gse_raise(node) or (node.exc.args and _msg_is_coded(node.exc.args[0])):
                    continue
                arg = node.exc.args[0] if node.exc.args else None
                ok = (isinstance(arg, ast.Name) and arg.id in params
                      and calls.get(fn.name) and all(calls[fn.name]))
                if not ok:
                    bad.append({"line": node.lineno,
                                "problem": lines[node.lineno - 1].strip()[:120]})
    return sorted({(b["line"], b["problem"]) for b in bad})


def mutate(src: str, site) -> str:
    a, b, col, _, _ = site
    lines = src.split("\n")
    indent = lines[a - 1][:col]
    new = lines[:a - 1] + [indent + "pass"] + lines[b:]
    out = "\n".join(new)
    ast.parse(out)                          # a mutant that does not compile is a generator bug
    return out


def run_exam(runner: Path, impl_src: str | None, timeout: int) -> dict:
    """Run the frozen exam against *impl_src* (None = the committed implementation)."""
    with tempfile.TemporaryDirectory(prefix="v5mut_") as td:
        td = Path(td)
        env = dict(os.environ)
        if impl_src is not None:
            shutil.copytree(ROOT / "styxx", td / "styxx",
                            ignore=shutil.ignore_patterns("__pycache__"))
            (td / "styxx" / "protocol.py").write_text(impl_src, encoding="utf-8")
            env["STYXX_V5_IMPORT_ROOT"] = str(td)
        out = td / "result.json"
        env["STYXX_V5_RESULT_OUT"] = str(out)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            p = subprocess.run([sys.executable, str(runner), "--smoke", "--full-battery",
                                "--mutation-mode"],
                               cwd=ROOT, env=env, capture_output=True, text=True,
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"detected": True, "how": f"timeout after {timeout}s"}
        if p.returncode != 0 or not out.exists():
            return {"detected": True, "how": f"exit {p.returncode}: {p.stderr.strip()[-300:]}"}
        r = json.loads(out.read_text(encoding="utf-8"))
        failed_v = sorted(k for k, v in r.get("violation_cases", {}).items() if not v.get("ok"))
        failed_g = sorted(k for k, v in r.get("valid_cases", {}).items() if not v.get("ok"))
        retro_ok = r.get("p1_retro_exact") == 1.0
        crashes = r.get("n_crashes", 0)
        detected = bool(failed_v or failed_g or not retro_ok or crashes)
        how = []
        if failed_v:
            how.append(f"violation cases {failed_v[:6]}")
        if failed_g:
            how.append(f"valid cases {failed_g[:6]}")
        if not retro_ok:
            how.append("P1 retro not exact")
        if crashes:
            how.append(f"{crashes} crashes")
        return {"detected": detected, "how": "; ".join(how) or "exam passed: SURVIVED"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runner", required=True)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    args = ap.parse_args()
    runner = (HERE / args.runner).resolve()
    src = IMPL.read_text(encoding="utf-8")
    sites = refusal_sites(src)
    hyg = hygiene_violations(src)
    base = run_exam(runner, None, args.timeout)
    results = []
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(run_exam, runner, mutate(src, s), args.timeout): s for s in sites}
        for f in cf.as_completed(futs):
            s = futs[f]
            results.append({"line": s[0], "kind": s[3], "statement": s[4], **f.result()})
    results.sort(key=lambda r: r["line"])
    survived = [r for r in results if not r["detected"]]
    out = {
        "generator": "papers/first-afference/mutation_gate.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runner": args.runner,
        "runner_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
        "impl_sha256": hashlib.sha256(src.encode("utf-8")).hexdigest(),
        "baseline_clean": not base["detected"],
        "baseline": base,
        "n_refusal_sites": len(sites),
        "n_mutants_detected": len(results) - len(survived),
        "frac_refusal_mutants_detected": round((len(results) - len(survived)) / len(results), 4)
        if results else 0.0,
        "n_hygiene_violations": len(hyg),
        "hygiene_violations": hyg,
        "survivors": survived,
        "mutants": results,
    }
    dest = HERE / f"{Path(args.runner).stem}_mutation_gate.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"baseline clean: {out['baseline_clean']} | {out['n_mutants_detected']}/{len(results)} "
          f"refusal mutants detected | hygiene violations {len(hyg)} | -> {dest.name}")
    for r in survived:
        print(f"  SURVIVED line {r['line']}: {r['statement']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
