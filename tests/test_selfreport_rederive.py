# -*- coding: utf-8 -*-
"""Every stored verdict re-derives from the record's files, and an edited record does not."""
import json
import shutil
import sys

import pytest

from styxx.selfreport import known_answers as K
from styxx.selfreport import records as R
from styxx.selfreport import tasks as T

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("git") is None,
    reason="the collector has been run on Linux only; it needs git and starts pytest in subprocesses")

ROOT = T.default_tasks_root()
AGENTS = ["honest", "test_editor", "plain_twin", "forger_in_src"]


@pytest.fixture(scope="module")
def pristine(tmp_path_factory):
    run_dir = tmp_path_factory.mktemp("selfreport-run") / "run"
    K.run_battery(ROOT, out_dir=run_dir, agents=AGENTS, only=["t01_control_pager"], repeat=1)
    return run_dir


@pytest.fixture()
def run(pristine, tmp_path):
    dest = tmp_path / "run"
    shutil.copytree(str(pristine), str(dest))
    return dest


def mismatches(run_dir):
    return [r for r in R.rederive(run_dir, ROOT) if r["result"] != "MATCH"]


def test_an_untouched_run_re_derives(pristine):
    rows = R.rederive(pristine, ROOT)
    assert len(rows) == 7 * len(AGENTS) + 1  # seven checks a session, one for the ledger
    assert [r for r in rows if r["result"] != "MATCH"] == []


def test_a_record_holds_what_a_stranger_needs_and_keeps_authored_bytes_apart(pristine):
    d = pristine / "sessions" / "t01_control_pager__honest"
    names = sorted(p.name for p in d.iterdir())
    assert names == ["blobs", "collector.manifest.json", "diff.patch", "facts.json", "junit_as_left_0.xml",
                     "junit_given_0.xml", "manifest_after.json", "report.md", "score.json", "session.json"]
    session = json.loads((d / "session.json").read_text(encoding="utf-8"))
    assert session["rung"] == "L1" and session["status"] == "COMPLETED"
    assert session["not_established"]
    manifest = json.loads((d / "collector.manifest.json").read_text(encoding="utf-8"))
    assert manifest["rung"] == "L1"
    receipts = {r["sha256"] for r in manifest["receipts"].values()} if isinstance(manifest["receipts"], dict) \
        else {r["sha256"] for r in manifest["receipts"]}
    authored = set(manifest["authored_sha256"])
    report_digest = R.C.sha256_hex((d / "report.md").read_bytes())
    assert report_digest in authored and report_digest not in receipts
    # no directory of the collecting machine is written into the receipt notes
    assert str(pristine) not in (d / "collector.manifest.json").read_text(encoding="utf-8")
    score = json.loads((d / "score.json").read_text(encoding="utf-8"))
    assert score["gate"]["note"].startswith("styxx.diffgate's reading")


def test_run_json_says_it_is_not_a_result(pristine):
    run = json.loads((pristine / "run.json").read_text(encoding="utf-8"))
    assert run["kind"] == "known_answer" and run["prereg"] is None
    assert "not a result" in run["statement"]
    assert set(run["modules"]) >= {"styxx/declare.py", "styxx/diffgate.py", "styxx/evidence.py",
                                   "styxx/selfreport/collect.py", "styxx/selfreport/score.py"}


def test_editing_the_report_is_seen(run):
    report = run / "sessions" / "t01_control_pager__test_editor" / "report.md"
    report.write_text(report.read_text(encoding="utf-8").replace("tests_pass: true", "tests_pass: false"),
                      encoding="utf-8")
    checks = {r["check"] for r in mismatches(run)}
    assert "report re-scored against the facts" in checks


def test_editing_a_stored_file_of_the_tree_is_seen(run):
    d = run / "sessions" / "t01_control_pager__honest"
    blob = next((d / "blobs").iterdir())
    blob.write_bytes(blob.read_bytes() + b"# edited\n")
    checks = {r["check"] for r in mismatches(run)}
    assert "facts recomputed from seed and stored blobs" in checks


def test_editing_a_test_report_is_seen(run):
    junit = run / "sessions" / "t01_control_pager__test_editor" / "junit_given_0.xml"
    text = junit.read_text(encoding="utf-8")
    assert "<failure" in text
    start = text.index("<failure")
    end = text.index("</failure>", start) + len("</failure>")
    junit.write_text(text[:start] + text[end:], encoding="utf-8")
    checks = {r["check"] for r in mismatches(run)}
    assert "stored files match their recorded sha256" in checks
    assert "test outcome (given) re-read from stored reports" in checks


def test_editing_the_stored_verdict_is_seen(run):
    path = run / "sessions" / "t01_control_pager__test_editor" / "score.json"
    score = json.loads(path.read_text(encoding="utf-8"))
    assert score["claims"]["tests_pass"]["verdict"] == "FALSE"
    score["claims"]["tests_pass"] = {"declared": "true", "verdict": "TRUE", "critical": True, "fact": "PASS"}
    path.write_text(json.dumps(score), encoding="utf-8")
    checks = {r["check"] for r in mismatches(run)}
    assert "report re-scored against the facts" in checks


def test_editing_the_stored_facts_is_seen(run):
    path = run / "sessions" / "t01_control_pager__plain_twin" / "facts.json"
    facts = json.loads(path.read_text(encoding="utf-8"))
    assert facts["changed"]["count"] == 3
    facts["changed"]["count"] = 1
    facts["changed"]["paths"] = facts["changed"]["paths"][:1]
    path.write_text(json.dumps(facts), encoding="utf-8")
    checks = {r["check"] for r in mismatches(run)}
    assert "facts recomputed from seed and stored blobs" in checks


def test_editing_the_ledger_is_seen(run):
    ledger = run / "ledger.jsonl"
    ledger.write_text(ledger.read_text(encoding="utf-8").replace('"verdict":"FALSE"', '"verdict":"TRUE"', 1),
                      encoding="utf-8")
    assert [r["check"] for r in mismatches(run)] == ["ledger equals the sessions' verdicts"]


def test_a_scored_run_cannot_be_written_without_a_preregistration(run, tmp_path):
    sessions = [json.loads((p / "session.json").read_text(encoding="utf-8"))
                for p in sorted((run / "sessions").iterdir())]
    with pytest.raises(ValueError, match="preregistration"):
        R.write_run(run, run_id="x", kind="scored", sessions=sessions, tasks_root=ROOT)
    with pytest.raises(ValueError, match="preregistration"):
        R.write_run(run, run_id="x", kind="scored", sessions=sessions, tasks_root=ROOT,
                    prereg={"path": str(tmp_path / "PREREG_missing.md")})
    with pytest.raises(ValueError):
        R.write_run(run, run_id="x", kind="result", sessions=sessions, tasks_root=ROOT)
    prereg = tmp_path / "PREREG_example.md"
    prereg.write_text("frozen text\n", encoding="utf-8")
    written = R.write_run(run, run_id="x", kind="scored", sessions=sessions, tasks_root=ROOT,
                          prereg={"path": str(prereg)})
    assert written["prereg"]["sha256"] == R.C.sha256_hex(b"frozen text\n") and written["statement"] is None
