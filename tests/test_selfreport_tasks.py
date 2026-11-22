# -*- coding: utf-8 -*-
"""The five example tasks load, and a task that no longer matches its pins does not."""
import json
import shutil
import subprocess
import sys

import pytest

from styxx.selfreport import tasks as T
from styxx.selfreport.collect import manifest, manifest_digest
from styxx.selfreport.scripted import AGENTS

ROOT = T.default_tasks_root()
IDS = [p.name for p in T.list_tasks(ROOT)]


def test_there_are_five_example_tasks_and_one_condition_each():
    assert len(IDS) == 5
    assert len({T.load_task(ROOT / i)["condition"] for i in IDS}) == 5


@pytest.mark.parametrize("tid", IDS)
def test_task_loads_with_its_pins(tid):
    task = T.load_task(ROOT / tid)
    assert task["id"] == tid
    assert set(T.NEVER_CARRIED) <= set(task["never_carried"])
    assert manifest_digest(task["_seed_manifest"]) == task["seed_manifest_sha256"]
    prompt = (ROOT / tid / "PROMPT.md").read_bytes()
    assert prompt.endswith(T.contract_path(ROOT).read_bytes())
    # The prompt must not tell the agent that the block will be checked or that it is being measured.
    lowered = prompt.decode("utf-8").lower()
    for word in ("will be checked", "will be verified", "honest", "benchmark", "evaluat", "measured"):
        assert word not in lowered, word


@pytest.mark.parametrize("tid", IDS)
def test_every_scripted_subject_has_an_expected_answer(tid):
    expected = json.loads((ROOT / tid / "EXPECTED.json").read_text(encoding="utf-8"))
    assert sorted(expected) == sorted(AGENTS)
    for row in expected.values():
        assert sorted(row) == ["as_left", "block", "changed", "claims", "given", "tests_added_ast"]


def _copy_set(tmp_path):
    dest = tmp_path / "selfreport"
    shutil.copytree(str(ROOT.parent), str(dest))
    return dest / "tasks"


@pytest.mark.parametrize("damage", ["seed", "prompt", "contract", "truth", "id"])
def test_a_task_that_does_not_match_its_pins_does_not_load(tmp_path, damage):
    root = _copy_set(tmp_path)
    d = root / IDS[0]
    if damage == "seed":
        with open(str(d / "seed" / "README.md"), "ab") as fh:
            fh.write(b"x")
    elif damage == "prompt":
        with open(str(d / "PROMPT.md"), "ab") as fh:
            fh.write(b"\n")
    elif damage == "contract":
        with open(str(T.contract_path(root)), "ab") as fh:
            fh.write(b"\n")
    else:
        tj = json.loads((d / "task.json").read_text(encoding="utf-8"))
        if damage == "truth":
            tj["truth"]["tests_pass"] = "the_agent_said_so"
        else:
            tj["id"] = "something_else"
        (d / "task.json").write_text(json.dumps(tj), encoding="utf-8")
    with pytest.raises(T.TaskError):
        T.load_task(d)
    if damage != "contract":
        T.load_task(root / IDS[1])  # damage to one task leaves the others loadable


def test_a_seed_without_its_own_pytest_ini_does_not_load(tmp_path):
    root = _copy_set(tmp_path)
    (root / IDS[0] / "seed" / "pytest.ini").unlink()
    with pytest.raises(T.TaskError, match="pytest.ini"):
        T.load_task(root / IDS[0], check_pins=False)


def test_materialise_copies_the_seed_and_refuses_bad_destinations(tmp_path):
    task = T.load_task(ROOT / IDS[0])
    sandbox = T.materialise(task, tmp_path / "sb")
    assert manifest_digest(manifest(sandbox)) == task["seed_manifest_sha256"]
    assert (sandbox / ".git").exists()
    with pytest.raises(T.TaskError, match="already exists"):
        T.materialise(task, tmp_path / "sb")
    # tests/ sits in the repository: a sandbox there could inherit its configuration and its history.
    with pytest.raises(T.TaskError, match="outside every repository"):
        T.materialise(task, T.repo_root() / "tests" / "_selfreport_must_not_be_created")
    assert not (T.repo_root() / "tests" / "_selfreport_must_not_be_created").exists()


@pytest.mark.skipif(shutil.which("git") is None or not (T.repo_root() / ".git").exists(),
                    reason="needs git and a checkout: asks git whether any task file is ignored")
def test_no_task_or_contract_file_is_ignored_by_git():
    """An ignored seed file would be dropped from a commit without a word, and the pin would fail on every
    other machine. The repository ignores *.log, *.out, build/ and more."""
    files = [str(p.relative_to(T.repo_root())) for p in sorted(ROOT.parent.rglob("*")) if p.is_file()]
    r = subprocess.run(["git", "check-ignore", "--no-index"] + files, cwd=str(T.repo_root()),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert r.stdout.decode().strip() == "", "ignored: %s" % r.stdout.decode()


def test_the_task_set_is_not_shipped_inside_the_package():
    """Seeds hold deliberately broken code and an import of a package that does not exist. They live beside
    the package, where neither the linter's `ruff check styxx` nor an import of styxx reaches them."""
    assert T.repo_root() / "selfreport" / "tasks" == ROOT
    assert "styxx" not in ROOT.relative_to(T.repo_root()).parts
    assert sys.modules.get("tabulon9") is None
