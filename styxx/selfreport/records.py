# -*- coding: utf-8 -*-
"""Session and run records, and re-deriving every stored verdict from the files alone.

A session record holds the agent's final report, the tree as left (by hash), the harness's diff, every test
report the harness wrote, the facts and the score. ``rederive`` rebuilds the facts that need no test run from
the seed and the stored blobs, re-reads the stored test reports, re-scores the report, and says MATCH or
MISMATCH per check.

What re-derivation does and does not anchor. It recomputes, from bytes: which files changed, the test
counts, the given tests, the diff, the plan of the judged copy, each run's outcome from its stored report,
the aggregate outcome, the verdicts and the ledger. It takes on the record's word: that ``report.md`` is
what the agent wrote and the blobs are the tree it left; each run's printed-summary counts, its
``tree_altered`` flag and whether it timed out; the environment fingerprints; the count of entries under
excluded names; and which model or driver is named. It executes no test. And nothing outside a record
anchors the record: someone who rewrites every file consistently, canary nonces included, produces a record
that re-derives. Publishing ``sha256(run.json)`` at the time of the run is what fixes a record in place.

Run kinds:

* ``known_answer``: scripted subjects whose correct score is written down in advance.
* ``smoke``: anything run without a committed preregistration. Never a result.
* ``scored``: requires a preregistration file that is tracked by git and unmodified at ``HEAD``; its path,
  sha256 and commit are recorded. ``write_run`` refuses a ``scored`` run without one.
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
    C.write_lf(path, json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=True) + "\n")


def _load(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return C.sha256_hex(Path(path).read_bytes())


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
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=C.base_env())
    except OSError:
        return None
    return r.stdout.decode("utf-8", "replace").strip() or None


def gate_record(report: str, diff_text: str) -> dict:
    """``styxx.diffgate``'s reading of the same report against the harness's diff. Stored report-only: it is
    never part of a score, and ``rederive`` recomputes it."""
    from styxx.diffgate import gate_diff_text

    gate = gate_diff_text(report, diff_text)
    return {"verdict": gate.verdict, "measured": bool(getattr(gate, "measured", True)),
            "claims": [{"kind": c.kind, "verdict": c.verdict, "declared": bool(c.detail.get("declared"))}
                       for c in gate.claims],
            "note": "styxx.diffgate's reading of the same report against the harness's diff: stored "
                    "report-only, never part of a score"}


def _flags(facts: dict) -> dict:
    given_runs = facts["test_outcome"]["given"]["runs"]
    return {
        # Set from the given run only, and only when the canaries ran and read wrongly: a run that stopped
        # before the canaries (an agent's own `-x`, a broken conftest) is not evidence of tampering.
        "runner_compromised": any("runner_compromised" in r.get("why", "") for r in given_runs),
        "judged_run_did_not_report": any(r.get("did_not_report") for r in given_runs),
        "environment_mutated": bool(facts["environment"]["mutated"]),
        "environment_unknown_before_session": not facts["environment"]["known_since_materialise"],
        "renames_detected": bool(facts["renames_detected"]),
        "odd_entries": bool(facts["odd_entries"]),
        "outside_allowed_paths": bool(facts["compliance"]["outside"]),
        "entries_under_excluded_names": int((facts.get("excluded") or {}).get("entries", 0)),
    }


def write_session(session_dir, *, run_id: str, session_id: str, task: dict, collected: dict, report: str,
                  scored: dict, driver: str, model: Optional[dict] = None, with_gate: bool = True) -> dict:
    """Write one completed session's record. The folder is built under a temporary name and renamed at the
    end, so a failure part-way leaves no half-written session. Returns the ``session.json`` object."""
    final = Path(session_dir)
    if final.exists():
        raise FileExistsError("a session record already exists at %s" % final)
    d = final.parent / (final.name + ".partial")
    if d.exists():
        shutil.rmtree(str(d))
    d.mkdir(parents=True)
    facts, m1, tree = collected["facts"], collected["manifest_after"], Path(collected["tree_after"])
    raw_report = report.encode("utf-8", "surrogateescape")
    (d / "report.md").write_bytes(raw_report)
    _dump(d / "manifest_after.json", m1)
    (d / "blobs").mkdir()
    ch = facts["changed"]
    authored = [raw_report]
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
                shutil.copyfile(str(src), str(d / run["junit"]))
    _dump(d / "facts.json", facts)
    out_score = dict(scored)
    out_score["gate"] = gate_record(report, collected["diff_text"]) if with_gate else None
    _dump(d / "score.json", out_score)
    _mint_manifest(d, session_id, authored)
    files = {p.relative_to(d).as_posix(): _sha(p) for p in sorted(d.rglob("*")) if p.is_file()}
    session = {
        "spec": SPEC_SESSION, "run_id": run_id, "session_id": session_id, "status": "COMPLETED",
        "task": {"id": task["id"], "condition": task["condition"],
                 "seed_manifest_sha256": task["seed_manifest_sha256"], "prompt_sha256": task["prompt_sha256"],
                 "contract_sha256": task["contract_sha256"], "task_json_sha256": task["_task_json_sha256"]},
        "driver": driver, "model": model, "rung": "L1", "flags": _flags(facts), "files": files,
        "facts_digest": C.facts_digest(facts), "repeat": facts["repeat"], "claims": compact(scored),
        "not_established": list(C.NOT_ESTABLISHED),
    }
    _dump(d / "session.json", session)
    os.rename(str(d), str(final))
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


def _ledger_lines(run_id: str, run_dir: Path, session_ids: List[str]) -> List[str]:
    lines = []
    for sid in sorted(session_ids):
        session = _load(run_dir / "sessions" / sid / "session.json")
        sc = _load(run_dir / "sessions" / sid / "score.json")
        for key in sorted(sc["claims"]):
            c = sc["claims"][key]
            lines.append(C.jcs({"run_id": run_id, "session_id": sid, "task": session["task"]["id"],
                                "condition": session["task"]["condition"], "driver": session["driver"],
                                "key": key, "declared": c.get("declared"), "verdict": c["verdict"],
                                "direction": c.get("direction"), "subtype": c.get("subtype"),
                                "critical": bool(c.get("critical"))}))
    return lines


def _git_tracked_unmodified(path: Path) -> Optional[str]:
    """The commit at which ``path`` is tracked and unmodified, or ``None``."""
    env = C.git_env()
    here = str(path.parent)

    def git(*args: str):
        return subprocess.run(["git"] + list(args), cwd=here, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)

    if git("ls-files", "--error-unmatch", path.name).returncode != 0:
        return None
    if git("diff", "--quiet", "HEAD", "--", path.name).returncode != 0:
        return None
    head = git("rev-parse", "HEAD")
    return head.stdout.decode("ascii", "replace").strip() if head.returncode == 0 else None


def write_run(run_dir, *, run_id: str, kind: str, tasks_root, python: str = sys.executable,
              prereg: Optional[dict] = None, void: Optional[List[dict]] = None) -> dict:
    """Write ``run.json`` and ``ledger.jsonl`` over every session folder under ``run_dir``.

    The sessions are read from disk, so a second call adds to a run and never drops what an earlier call
    recorded. ``run.json`` carries the sha256 of every ``session.json`` and of the ledger; its own sha256 is
    the one value to publish to fix a run in place.
    """
    if kind not in RUN_KINDS:
        raise ValueError("kind must be one of %s" % (RUN_KINDS,))
    if kind == "scored":
        path = Path(str((prereg or {}).get("path", "")))
        commit = _git_tracked_unmodified(path) if path.is_file() else None
        if commit is None:
            raise ValueError("a scored run needs a preregistration file that git tracks and that is "
                             "unmodified at HEAD; without one the run is a smoke run")
        prereg = {"path": path.name, "sha256": _sha(path), "commit": commit}
    else:
        prereg = None
    d = Path(run_dir)
    (d / "sessions").mkdir(parents=True, exist_ok=True)
    ids = sorted(p.name for p in (d / "sessions").iterdir() if (p / "session.json").is_file())
    earlier_void = _load(d / "run.json").get("void", []) if (d / "run.json").is_file() else []
    lines = _ledger_lines(run_id, d, ids)
    ledger = "\n".join(lines) + ("\n" if lines else "")
    C.write_lf(d / "ledger.jsonl", ledger)
    cp = contract_path(tasks_root)
    run = {
        "spec": SPEC_RUN, "run_id": run_id, "kind": kind, "prereg": prereg,
        "statement": None if kind == "scored" else NOT_A_RESULT % kind,
        "modules": module_digests(),
        "versions": {"python": sys.version.split()[0],
                     "pytest": _tool_version([python, "-m", "pytest", "--version"]),
                     "git": _tool_version(["git", "--version"])},
        "contract_sha256": _sha(cp) if cp.is_file() else None,
        "sessions": {sid: _sha(d / "sessions" / sid / "session.json") for sid in ids},
        "ledger_sha256": C.sha256_hex(ledger.encode("utf-8")),
        "void": earlier_void + list(void or []),
        "n_sessions": len(ids),
    }
    _dump(d / "run.json", run)
    return run


def run_digest(run_dir) -> str:
    return _sha(Path(run_dir) / "run.json")


# ------------------------------------------------------------------------------------------------ rederive
def _row(session_id: str, check: str, ok: bool, detail: str = "") -> dict:
    return {"session": session_id, "check": check, "result": "MATCH" if ok else "MISMATCH", "detail": detail}


def _as_left_unreproducible(m1: Dict[str, dict]) -> List[str]:
    return sorted(p for p in m1 if m1[p]["type"] != "f"
                  and not (m1[p]["type"] == "l" and C._link_stays_inside(p, m1[p].get("target", ""))))


def rederive_session(session_dir, tasks_root, run_id: Optional[str] = None) -> List[dict]:
    """Re-derive one session's stored facts and verdicts from its files. No test is executed."""
    d = Path(session_dir)
    session = _load(d / "session.json")
    sid = session["session_id"]
    rows: List[dict] = []
    rows.append(_row(sid, "the folder is named for the session, and the session for its run",
                     sid == d.name and (run_id is None or session["run_id"] == run_id)))
    on_disk = sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if not p.is_dir() or p.is_symlink())
    links = [p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_symlink()]
    listed = sorted(list(session["files"]) + ["session.json"])
    rows.append(_row(sid, "the folder holds exactly the listed files, none of them a link",
                     on_disk == listed and not links, ", ".join((set(on_disk) ^ set(listed)) or links)[:120]))
    bad = [name for name, digest in sorted(session["files"].items())
           if not (d / name).is_file() or (d / name).is_symlink() or _sha(d / name) != digest]
    rows.append(_row(sid, "stored files match their recorded sha256", not bad, ", ".join(bad[:5])))
    task = load_task(Path(tasks_root) / session["task"]["id"])
    pins = ("seed_manifest_sha256", "prompt_sha256", "contract_sha256")
    rows.append(_row(sid, "task pins and task.json equal the session's",
                     all(task[k] == session["task"][k] for k in pins)
                     and task["_task_json_sha256"] == session["task"]["task_json_sha256"]))
    seed = Path(task["_dir"]) / "seed"
    m0 = task["_seed_manifest"]
    m1 = _load(d / "manifest_after.json")
    facts = _load(d / "facts.json")
    report = (d / "report.md").read_bytes().decode("utf-8", "surrogateescape")

    def read0(p: str) -> bytes:
        return (seed / p).read_bytes()

    def read1(p: str) -> bytes:
        meta = m1[p]
        if p in m0 and m0[p]["sha256"] == meta["sha256"]:
            return (seed / p).read_bytes()
        return (d / "blobs" / str(meta["sha256"])).read_bytes()

    diff_text = None
    try:
        again, diff_text = C.facts_from_trees(task, read0, m0, read1, m1)
        same = C.facts_digest(again) == C.facts_digest(facts) == session["facts_digest"]
        detail = ""
        if not same and facts.get("collector", {}).get("python", "")[:4] != sys.version[:4]:
            detail = ("collected by Python %s, re-derived by %s: the two parsers can count test functions "
                      "differently" % (facts.get("collector", {}).get("python"), sys.version.split()[0]))
        rows.append(_row(sid, "facts recomputed from seed and stored blobs", same, detail))
        rows.append(_row(sid, "diff recomputed",
                         C.sha256_hex(diff_text.encode("utf-8", "surrogateescape"))
                         == _sha(d / "diff.patch") == facts["diff_sha256"]))
    except (OSError, RuntimeError, KeyError) as exc:
        rows.append(_row(sid, "facts recomputed from seed and stored blobs", False, str(exc)[:120]))
    tests_dir = C.tests_dir_of(task)
    env = facts["environment"]
    mutated = C.environment_record(env.get("at_materialise"), env["before"], env["after"])["mutated"]
    rows.append(_row(sid, "environment flag follows from the stored fingerprints",
                     mutated == env["mutated"] and facts["repeat"] == session["repeat"]))
    for mode in ("given", "as_left"):
        stored = facts["test_outcome"][mode]
        classes, whys = [], []
        ok = len(stored["runs"]) == facts["repeat"]
        for k, run in enumerate(stored["runs"]):
            name = "junit_%s_%d.xml" % (mode, k)
            junit = d / name
            present = junit.is_file() and not junit.is_symlink()
            ok = ok and run["junit"] == name and str(run["nonce"]).startswith(mode[0])
            ok = ok and (not present or run.get("junit_sha256") == _sha(junit))
            ok = ok and not (run.get("timed_out") and present)
            got = C.classify_run(junit if present else None, run["nonce"], facts["given_tests"], tests_dir,
                                 timed_out=bool(run.get("timed_out")), summary=run.get("summary_counts"),
                                 tree_altered=bool(run.get("tree_altered")))
            classes.append(got["class"])
            whys.append(got["why"])
            ok = ok and got["class"] == run["class"]
        unrep = facts["copy_plan"]["unreproducible"] if mode == "given" else _as_left_unreproducible(m1)
        agg = C.aggregate(classes, whys, unrep)[0] if classes else C.INDETERMINATE
        if mutated:
            agg = C.INDETERMINATE
        rows.append(_row(sid, "test outcome (%s) re-read from stored reports" % mode,
                         ok and agg == stored["class"], "stored %s, re-read %s" % (stored["class"], agg)))
    stored_score = _load(d / "score.json")
    rescored = score(report, facts, task)
    same = all(C.jcs(rescored[k]) == C.jcs(stored_score.get(k)) for k in ("block", "claims", "session",
                                                                         "volunteered", "notes"))
    rows.append(_row(sid, "report re-scored against the facts", same and compact(rescored) == session["claims"]))
    if stored_score.get("gate") is not None and diff_text is not None:
        rows.append(_row(sid, "diffgate's reading recomputed",
                         C.jcs(gate_record(report, diff_text)) == C.jcs(stored_score["gate"])))
    rows.append(_row(sid, "flags follow from the facts", C.jcs(_flags(facts)) == C.jcs(session["flags"])))
    rows.append(_manifest_row(d, sid))
    return rows


def _manifest_row(d: Path, sid: str) -> dict:
    """The sworn manifest must be intact and must hold the folder's own bytes: given report number 0, the
    facts and the diff as receipts, and the report among the authored digests."""
    path = d / "collector.manifest.json"
    if not path.is_file():
        return _row(sid, "sworn manifest agrees with the folder", not (d / "junit_given_0.xml").is_file(),
                    "no manifest")
    from styxx.sworn import Manifest

    try:
        m = Manifest.load(path)
        receipts = m.to_dict()["receipts"]
        ok = m.intact() and m.rung == "L1"
        for rid, name in (("r3", "junit_given_0.xml"), ("r5", "facts.json"), ("r6", "diff.patch")):
            ok = ok and receipts[rid]["sha256"] == _sha(d / name)
        ok = ok and _sha(d / "report.md") in m.to_dict()["authored_sha256"]
        ok = ok and _sha(d / "report.md") not in {r["sha256"] for r in receipts.values()}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return _row(sid, "sworn manifest agrees with the folder", False, str(exc)[:100])
    return _row(sid, "sworn manifest agrees with the folder", ok)


def rederive(run_dir, tasks_root) -> List[dict]:
    """Re-derive a run: its own statements, then every session, then the ledger."""
    d = Path(run_dir)
    run = _load(d / "run.json")
    rows: List[dict] = []
    kind = run.get("kind")
    honest_statement = (run.get("statement") is None) if kind == "scored" else \
        (kind in RUN_KINDS and run.get("statement") == NOT_A_RESULT % kind)
    rows.append(_row("(run)", "kind is known and the run says what it is", kind in RUN_KINDS and honest_statement,
                     "kind %r" % kind))
    if kind == "scored":
        pr = run.get("prereg") or {}
        found = sorted(Path(tasks_root).resolve().parents[1].rglob(str(pr.get("path", "\0")))) \
            if pr.get("path") else []
        rows.append(_row("(run)", "the preregistration it cites is in this repository with the recorded sha256",
                         any(_sha(p) == pr.get("sha256") for p in found), str(pr.get("path"))))
    else:
        rows.append(_row("(run)", "an unscored run cites no preregistration", run.get("prereg") is None))
    folders = sorted(p.name for p in (d / "sessions").iterdir()) if (d / "sessions").is_dir() else []
    listed = sorted(run.get("sessions", {}))
    rows.append(_row("(run)", "the session folders are exactly the sessions listed",
                     folders == listed and run.get("n_sessions") == len(listed),
                     ", ".join(sorted(set(folders) ^ set(listed)))[:120]))
    cp = contract_path(tasks_root)
    rows.append(_row("(run)", "report contract equals the recorded sha256",
                     cp.is_file() and _sha(cp) == run.get("contract_sha256")))
    same_code = run.get("modules") == module_digests()
    rows.append({"session": "(run)", "check": "written by the code now re-deriving it",
                 "result": "MATCH" if same_code else "NOTE",
                 "detail": "" if same_code else "module digests differ: this is a different build"})
    for sid in listed:
        folder = d / "sessions" / sid
        if not (folder / "session.json").is_file():
            rows.append(_row(sid, "session.json present", False))
            continue
        rows.append(_row(sid, "session.json matches the sha256 in run.json",
                         _sha(folder / "session.json") == run["sessions"][sid]))
        rows.extend(rederive_session(folder, tasks_root, run_id=run.get("run_id")))
    ledger_path = d / "ledger.jsonl"
    stored = ledger_path.read_text(encoding="utf-8") if ledger_path.is_file() else ""
    present = [sid for sid in listed if (d / "sessions" / sid / "score.json").is_file()]
    lines = _ledger_lines(run.get("run_id"), d, present)
    want = "\n".join(lines) + ("\n" if lines else "")
    rows.append(_row("(run)", "ledger equals the sessions' verdicts, row for row",
                     stored == want and C.sha256_hex(stored.encode("utf-8")) == run.get("ledger_sha256")))
    return rows
