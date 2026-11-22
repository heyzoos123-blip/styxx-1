# -*- coding: utf-8 -*-
"""Session and run records, and re-deriving every stored verdict from the files alone.

A session record holds the agent's final report, the tree as left (by hash), the harness's diff, every test
report the harness wrote, the facts and the score. ``rederive`` rebuilds the facts that need no test run from
the seed and the stored blobs, re-reads the stored test reports, re-scores the report, and says MATCH or
MISMATCH per check. It never trusts ``facts.json`` or ``score.json`` for the thing it is checking.

Run kinds:

* ``known_answer``: scripted agents whose correct score is written down in advance.
* ``smoke``: anything run without a committed preregistration. Never a result.
* ``scored``: requires a preregistration file that exists and whose sha256 is recorded. This module refuses
  to write a ``scored`` run without one.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from . import collect as C
from .score import compact, score
from .tasks import contract_path, load_task

SPEC_SESSION = "styxx.selfreport.session/v0"
SPEC_RUN = "styxx.selfreport.run/v0"
RUN_KINDS = ("known_answer", "smoke", "scored")

NOT_A_RESULT = ("This run is kind %r. It is not a result and no rate from it may be quoted: nothing was "
                "preregistered for it.")


def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                    newline="\n")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def module_digests() -> Dict[str, str]:
    """sha256 of each module a verdict depends on, over bytes with CRLF read as LF so that a checkout with
    line-ending conversion reports the same build."""
    here = Path(__file__).resolve().parent
    files = sorted(here.glob("*.py")) + [here.parent / n for n in ("declare.py", "diffgate.py", "evidence.py")]
    out: Dict[str, str] = {}
    for f in files:
        rel = "styxx/" + f.relative_to(here.parent).as_posix()
        out[rel] = C.sha256_hex(f.read_bytes().replace(b"\r\n", b"\n"))
    return out


def _tool_version(cmd: List[str]) -> Optional[str]:
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
        return None
    return r.stdout.decode("utf-8", "replace").strip() or None


def _gate_record(gate) -> Optional[dict]:
    if gate is None:
        return None
    return {"verdict": gate.verdict, "measured": bool(getattr(gate, "measured", True)),
            "claims": [{"kind": c.kind, "verdict": c.verdict, "declared": bool(c.detail.get("declared"))}
                       for c in gate.claims],
            "note": "styxx.diffgate's reading of the same report against the harness's diff: stored "
                    "report-only, never part of a score"}


def write_session(session_dir, *, run_id: str, session_id: str, task: dict, collected: dict, report: str,
                  scored: dict, driver: str, model: Optional[dict] = None, gate=None) -> dict:
    """Write one completed session's record. Returns the ``session.json`` object."""
    d = Path(session_dir)
    d.mkdir(parents=True, exist_ok=False)
    facts, m1, tree = collected["facts"], collected["manifest_after"], Path(collected["tree_after"])
    (d / "report.md").write_bytes(report.encode("utf-8", "surrogateescape"))
    _dump(d / "manifest_after.json", m1)
    (d / "blobs").mkdir()
    ch = facts["changed"]
    authored = [report.encode("utf-8", "surrogateescape")]
    for p in ch["added"] + ch["modified"]:
        if m1[p]["type"] != "f":
            continue
        data = (tree / p).read_bytes()
        (d / "blobs" / m1[p]["sha256"]).write_bytes(data)
        authored.append(data)
    (d / "diff.patch").write_bytes(collected["diff_text"].encode("utf-8", "surrogateescape"))
    for mode in ("given", "as_left"):
        for run in facts["test_outcome"][mode]["runs"]:
            src = Path(collected["work"]) / run["junit"]
            if src.is_file():
                shutil.copyfile(src, d / run["junit"])
    _dump(d / "facts.json", facts)
    out_score = dict(scored)
    out_score["gate"] = _gate_record(gate)
    _dump(d / "score.json", out_score)
    _mint_manifest(d, session_id, authored)
    files = {p.relative_to(d).as_posix(): C.sha256_hex(p.read_bytes())
             for p in sorted(d.rglob("*")) if p.is_file()}
    flags = {
        "runner_compromised": any("runner_compromised" in r.get("why", "")
                                  for mode in ("given", "as_left") for r in facts["test_outcome"][mode]["runs"]),
        "environment_mutated": bool(facts["environment"]["mutated"]),
        "renames_detected": bool(facts["renames_detected"]),
        "odd_entries": bool(facts["odd_entries"]),
    }
    session = {
        "spec": SPEC_SESSION, "run_id": run_id, "session_id": session_id, "status": "COMPLETED",
        "task": {k: task[k] for k in ("id", "condition", "seed_manifest_sha256", "prompt_sha256",
                                      "contract_sha256")},
        "driver": driver, "model": model, "rung": "L1", "flags": flags, "files": files,
        "facts_digest": C.facts_digest(facts), "claims": compact(scored),
        "not_established": list(C.NOT_ESTABLISHED),
    }
    _dump(d / "session.json", session)
    return session


def _mint_manifest(d: Path, session_id: str, authored: List[bytes]) -> None:
    """A ``sworn/manifest/0.2`` over what the harness produced, in the project's existing receipt format:
    harness-made bytes as receipts, agent-written bytes only as authored digests."""
    from styxx.harness import junit as J

    if not (d / "junit_given_0.xml").is_file():
        return
    # The adapter writes the report's path into its notes, so it is given the path relative to the session
    # folder: a record must not carry the collecting machine's directories.
    here = os.getcwd()
    os.chdir(str(d))
    try:
        m = J.mint("junit_given_0.xml", rung="L1", turn=session_id, authored=authored)
    finally:
        os.chdir(here)
    m.add("r5", (d / "facts.json").read_bytes(), "harness_note", complete=True,
          note="facts.json: every fact the collector computed for this session")
    m.add("r6", (d / "diff.patch").read_bytes(), "harness_note", complete=True,
          note="diff.patch: the harness's own diff between the seed and the tree as left")
    m.write(d / "collector.manifest.json")


def write_run(run_dir, *, run_id: str, kind: str, sessions: List[dict], tasks_root, python: str = sys.executable,
              prereg: Optional[dict] = None, void: Optional[List[dict]] = None) -> dict:
    """Write ``run.json`` and ``ledger.jsonl`` beside the session folders already under ``run_dir``."""
    if kind not in RUN_KINDS:
        raise ValueError("kind must be one of %s" % (RUN_KINDS,))
    if kind == "scored":
        if not prereg or not prereg.get("path") or not Path(prereg["path"]).is_file():
            raise ValueError("a scored run needs a committed preregistration file; without one the run is "
                             "a smoke run")
        prereg = {"path": str(prereg["path"]), "sha256": C.sha256_hex(Path(prereg["path"]).read_bytes())}
    else:
        prereg = None
    d = Path(run_dir)
    d.mkdir(parents=True, exist_ok=True)
    cp = contract_path(tasks_root)
    run = {
        "spec": SPEC_RUN, "run_id": run_id, "kind": kind, "prereg": prereg,
        "statement": None if kind == "scored" else NOT_A_RESULT % kind,
        "modules": module_digests(),
        "versions": {"python": sys.version.split()[0],
                     "pytest": _tool_version([python, "-m", "pytest", "--version"]),
                     "git": _tool_version(["git", "--version"])},
        "contract_sha256": C.sha256_hex(cp.read_bytes()) if cp.is_file() else None,
        "sessions": sorted(s["session_id"] for s in sessions),
        "void": void or [],
        "n_sessions": len(sessions),
    }
    _dump(d / "run.json", run)
    lines = []
    for s in sorted(sessions, key=lambda x: x["session_id"]):
        sc = _load(d / "sessions" / s["session_id"] / "score.json")
        for key in sorted(sc["claims"]):
            c = sc["claims"][key]
            lines.append(C.jcs({"run_id": run_id, "session_id": s["session_id"], "task": s["task"]["id"],
                                "condition": s["task"]["condition"], "driver": s["driver"], "key": key,
                                "declared": c.get("declared"), "verdict": c["verdict"],
                                "direction": c.get("direction"), "subtype": c.get("subtype"),
                                "critical": bool(c.get("critical"))}))
    (d / "ledger.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8", newline="\n")
    return run


# ------------------------------------------------------------------------------------------------ rederive
def _row(session_id: str, check: str, ok: bool, detail: str = "") -> dict:
    return {"session": session_id, "check": check, "result": "MATCH" if ok else "MISMATCH", "detail": detail}


def rederive_session(session_dir, tasks_root) -> List[dict]:
    """Re-derive one session's stored facts and verdicts from its files. No test is executed."""
    d = Path(session_dir)
    session = _load(d / "session.json")
    sid = session["session_id"]
    rows: List[dict] = []
    bad = [name for name, digest in sorted(session["files"].items())
           if not (d / name).is_file() or C.sha256_hex((d / name).read_bytes()) != digest]
    rows.append(_row(sid, "stored files match their recorded sha256", not bad, ", ".join(bad[:5])))
    task = load_task(Path(tasks_root) / session["task"]["id"])
    rows.append(_row(sid, "task pins equal the session's",
                     all(task[k] == session["task"][k] for k in ("seed_manifest_sha256", "prompt_sha256",
                                                                "contract_sha256"))))
    seed = Path(task["_dir"]) / "seed"
    m0 = task["_seed_manifest"]
    m1 = _load(d / "manifest_after.json")
    facts = _load(d / "facts.json")

    def read0(p: str) -> bytes:
        return (seed / p).read_bytes()

    def read1(p: str) -> bytes:
        meta = m1[p]
        if p in m0 and m0[p]["sha256"] == meta["sha256"]:
            return (seed / p).read_bytes()
        return (d / "blobs" / meta["sha256"]).read_bytes()

    try:
        again, diff_text = C.facts_from_trees(task, read0, m0, read1, m1)
        rows.append(_row(sid, "facts recomputed from seed and stored blobs",
                         C.facts_digest(again) == C.facts_digest(facts) == session["facts_digest"]))
        rows.append(_row(sid, "diff recomputed",
                         C.sha256_hex(diff_text.encode("utf-8", "surrogateescape"))
                         == C.sha256_hex((d / "diff.patch").read_bytes()) == facts["diff_sha256"]))
    except (OSError, RuntimeError) as exc:
        rows.append(_row(sid, "facts recomputed from seed and stored blobs", False, str(exc)[:120]))
    tests_dir = task.get("tests_dir", "tests")
    for mode in ("given", "as_left"):
        stored = facts["test_outcome"][mode]
        classes = []
        ok = True
        for run in stored["runs"]:
            junit = d / run["junit"]
            got = C.classify_run(junit if junit.is_file() else None, run["nonce"], facts["given_tests"],
                                 tests_dir, timed_out=bool(run.get("timed_out")))
            classes.append(got["class"])
            ok = ok and got["class"] == run["class"]
        agg = classes[0] if len(set(classes)) == 1 else C.INDETERMINATE
        env_bad = facts["environment"]["mutated"] or facts["environment"]["before"].get("sha256") is None
        if env_bad:
            agg = C.INDETERMINATE
        rows.append(_row(sid, "test outcome (%s) re-read from stored reports" % mode,
                         ok and agg == stored["class"], "stored %s, re-read %s" % (stored["class"], agg)))
    stored_score = _load(d / "score.json")
    rescored = score((d / "report.md").read_bytes().decode("utf-8", "surrogateescape"), facts, task)
    same = all(C.jcs(rescored[k]) == C.jcs(stored_score[k]) for k in ("block", "claims", "session",
                                                                    "volunteered"))
    rows.append(_row(sid, "report re-scored against the facts", same and compact(rescored) == session["claims"]))
    return rows


def rederive(run_dir, tasks_root) -> List[dict]:
    """Re-derive every session of a run, and check the ledger against the re-scored sessions."""
    d = Path(run_dir)
    run = _load(d / "run.json")
    rows: List[dict] = []
    for sid in run["sessions"]:
        rows.extend(rederive_session(d / "sessions" / sid, tasks_root))
    ledger = [json.loads(ln) for ln in (d / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if ln]
    want = {}
    for sid in run["sessions"]:
        for key, verdict in _load(d / "sessions" / sid / "session.json")["claims"].items():
            want[(sid, key)] = verdict
    got = {(r["session_id"], r["key"]): "/".join([r["verdict"]] + [r[f] for f in ("direction", "subtype")
                                                                  if r.get(f)]) for r in ledger}
    rows.append(_row("(run)", "ledger equals the sessions' verdicts", got == want))
    return rows
