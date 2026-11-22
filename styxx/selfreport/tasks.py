# -*- coding: utf-8 -*-
"""Sandbox tasks: the format, its validation, and turning a task into a directory an agent can work in.

A task is a directory::

    <task_id>/
      task.json     the machine-readable statement, with digests that pin the seed, the prompt and the contract
      PROMPT.md     the instructions exactly as an agent receives them; ends with the shared report contract
      seed/         the repository as given: plain files, ASCII paths, its own pytest.ini and .gitignore
      EXPECTED.json the verdicts each scripted known-answer subject must receive on this task

Every pin is over bytes. A task whose seed, prompt or contract no longer matches its pins does not load.
``check_seed`` goes further and runs the untouched seed: a task whose own tests the collector cannot read
the way the task says (a test it does not see, a test that is skipped) would accuse every honest agent, so
it is refused before any session.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from . import collect as C
from .score import REQUIRED_KEYS

SPEC_TASK = "styxx.selfreport.task/v0"
SPEC_MATERIALISED = "styxx.selfreport.materialised/v0"

#: A file of one of these names, at the root or under the tests directory, steers how tests are collected
#: or run. The judged copy always holds the seed's and never the agent's.
NEVER_CARRIED = ("conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini", "sitecustomize.py",
                 "usercustomize.py", "*.pth")

#: The closed set of rules by which a declared key is compared with a fact.
TRUTH_RULES = {
    "tests_pass": "given_tests_pass",
    "files_changed": "manifest_count",
    "tests_added": "ast_new_test_functions",
    "only_touches": "all_changed_under_prefix",
}

_REQUIRED_FIELDS = ("spec", "id", "condition", "pytest_args", "test_timeout_s", "repeat", "editable",
                    "addable", "never_carried", "required_keys", "truth", "design", "seed_expect",
                    "seed_manifest_sha256", "prompt_sha256", "contract_sha256")


class TaskError(ValueError):
    """A task that does not meet the format or its own pins. A usage error, never a verdict."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_tasks_root() -> Path:
    """``selfreport/tasks`` at the root of a clone. The task set is not part of the installed package."""
    return repo_root() / "selfreport" / "tasks"


def contract_path(tasks_root) -> Path:
    return Path(tasks_root).resolve().parent / "contract" / "REPORT_CONTRACT.md"


def list_tasks(tasks_root=None) -> List[Path]:
    root = Path(tasks_root) if tasks_root is not None else default_tasks_root()
    if not root.is_dir():
        raise TaskError("no task directory at %s; the task set lives in a clone of the repository, pass "
                        "--tasks" % root)
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))
                  and (p / "task.json").is_file())


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise TaskError(msg)


def load_task(task_dir, check_pins: bool = True) -> dict:
    """Read and validate one task. With ``check_pins`` (the default) the seed, the prompt and the contract
    must match the digests in ``task.json``."""
    task_dir = Path(task_dir).resolve()
    tj = task_dir / "task.json"
    _need(tj.is_file(), "%s: no task.json" % task_dir)
    raw = tj.read_bytes()
    try:
        task = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise TaskError("%s: task.json is not JSON: %s" % (task_dir.name, exc))
    name = task_dir.name
    for f in _REQUIRED_FIELDS:
        _need(f in task, "%s: task.json lacks %r" % (name, f))
    _need(task["spec"] == SPEC_TASK, "%s: spec is %r, expected %r" % (name, task["spec"], SPEC_TASK))
    _need(task["id"] == name, "%s: id %r does not match the directory name" % (name, task["id"]))
    args = task["pytest_args"]
    _need(isinstance(args, list) and all(isinstance(a, str) for a in args),
          "%s: pytest_args must be a list of strings" % name)
    _need(isinstance(task["test_timeout_s"], int) and task["test_timeout_s"] > 0, "%s: test_timeout_s" % name)
    _need(isinstance(task["repeat"], int) and task["repeat"] >= 1, "%s: repeat must be 1 or more" % name)
    for f in ("editable", "addable", "never_carried"):
        _need(isinstance(task[f], list) and all(isinstance(g, str) for g in task[f]),
              "%s: %s must be a list of globs" % (name, f))
    missing = [g for g in NEVER_CARRIED if g not in task["never_carried"]]
    _need(not missing, "%s: never_carried must include %s" % (name, missing))
    keys = task["required_keys"]
    _need(isinstance(keys, list) and keys and set(keys) <= set(REQUIRED_KEYS),
          "%s: required_keys must be drawn from %s" % (name, list(REQUIRED_KEYS)))
    for k in keys:
        _need(task["truth"].get(k) == TRUTH_RULES[k],
              "%s: truth[%r] must be %r" % (name, k, TRUTH_RULES[k]))
    _need(isinstance(task["design"].get("honest_completion_possible"), bool),
          "%s: design.honest_completion_possible must be true or false" % name)
    expect = task["seed_expect"]
    _need(isinstance(expect, dict) and expect.get("outcome") in (C.PASS, C.FAIL)
          and isinstance(expect.get("absent"), list),
          "%s: seed_expect must give the untouched seed's outcome (PASS or FAIL) and its absent tests" % name)
    seed = task_dir / "seed"
    tests_dir = C.tests_dir_of(task)
    _need(seed.is_dir(), "%s: no seed/ directory" % name)
    _need((seed / "pytest.ini").is_file(), "%s: the seed needs its own pytest.ini" % name)
    _need((seed / ".gitignore").is_file(), "%s: the seed needs a .gitignore naming the cache files" % name)
    _need((seed / tests_dir / "__init__.py").is_file(),
          "%s: the seed's %s/ needs an __init__.py, so that pytest puts the root on the import path" %
          (name, tests_dir))
    prompt = task_dir / "PROMPT.md"
    _need(prompt.is_file(), "%s: no PROMPT.md" % name)
    m0 = C.manifest(seed)
    for p, meta in m0.items():
        _need(meta["type"] == "f", "%s: seed entry %r is not a regular file" % (name, p))
        _need(all(ord(ch) < 128 for ch in p), "%s: seed path %r is not ASCII" % (name, p))
    if check_pins:
        pb = prompt.read_bytes()
        _need(b"\r" not in pb, "%s: PROMPT.md holds a carriage return; pins are over bytes" % name)
        _need(C.sha256_hex(pb) == task["prompt_sha256"], "%s: PROMPT.md does not match prompt_sha256" % name)
        _need(C.manifest_digest(m0) == task["seed_manifest_sha256"],
              "%s: seed/ does not match seed_manifest_sha256" % name)
        cp = contract_path(task_dir.parent)
        _need(cp.is_file(), "%s: no report contract at %s" % (name, cp))
        cb = cp.read_bytes()
        _need(C.sha256_hex(cb) == task["contract_sha256"], "%s: the report contract does not match "
                                                           "contract_sha256" % name)
        _need(pb.endswith(cb), "%s: PROMPT.md does not end with the report contract, byte for byte" % name)
    task["_dir"] = str(task_dir)
    task["_seed_manifest"] = m0
    task["_task_json_sha256"] = C.sha256_hex(raw)
    return task


def pin(task_dir) -> dict:
    """Recompute a task's three digests from its files and write them into ``task.json``. For someone
    writing or changing a task; ``load_task`` then holds every later reader to them."""
    task_dir = Path(task_dir).resolve()
    task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    task["seed_manifest_sha256"] = C.manifest_digest(C.manifest(task_dir / "seed"))
    task["prompt_sha256"] = C.sha256_hex((task_dir / "PROMPT.md").read_bytes())
    task["contract_sha256"] = C.sha256_hex(contract_path(task_dir.parent).read_bytes())
    C.write_lf(task_dir / "task.json", json.dumps(task, indent=1) + "\n")
    return task


def sidecar_path(sandbox) -> Path:
    sandbox = Path(sandbox)
    return sandbox.parent / (sandbox.name + ".selfreport.json")


def read_materialised(sandbox) -> Optional[dict]:
    """What ``materialise`` wrote beside the sandbox before the session, or ``None``."""
    path = sidecar_path(sandbox)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return data if data.get("spec") == SPEC_MATERIALISED else None


def materialise(task: dict, dest, python: str = sys.executable, environment: Optional[dict] = None) -> Path:
    """Create the sandbox for one session at ``dest`` (which must not exist): a copy of the seed with one
    commit. Beside it, not inside it, goes a small file holding the judging environment's fingerprint as it
    is now, before the session, for ``collect`` to compare with afterwards.

    Refuses a destination inside a repository, where a parent's test configuration or history could leak
    in. The sandbox's git history is a convenience for the agent and is never read back. Every git call
    gets a scrubbed environment: a caller's ``GIT_DIR`` (a git hook exports one) must not aim them at
    another repository.
    """
    dest = Path(dest).resolve()
    if dest.exists():
        raise TaskError("%s already exists" % dest)
    inside = C.inside_repository(dest.parent)
    if inside is not None:
        raise TaskError("a sandbox must sit outside every repository; %s is inside %s" % (dest, inside))
    shutil.copytree(str(Path(task["_dir"]) / "seed"), str(dest))
    if C.manifest_digest(C.manifest(dest)) != task["seed_manifest_sha256"]:
        raise TaskError("the copied seed does not match the task's pin")
    env = C.git_env("seed")
    for args in (["-c", "init.defaultBranch=main", "init", "-q", "."], ["add", "-A"],
                 ["-c", "commit.gpgsign=false", "commit", "-q", "-m", "seed"]):
        r = subprocess.run(["git"] + args, cwd=str(dest), env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
        if r.returncode != 0:
            raise TaskError("git %s failed in the sandbox: %s"
                            % (" ".join(args), r.stderr.decode("utf-8", "replace")[:200]))
    record = {"spec": SPEC_MATERIALISED, "task": task["id"],
              "seed_manifest_sha256": task["seed_manifest_sha256"], "prompt_sha256": task["prompt_sha256"],
              "environment": environment if environment is not None else C.environment_fingerprint(python)}
    C.write_lf(sidecar_path(dest), json.dumps(record, indent=1, sort_keys=True) + "\n")
    return dest


def check_seed(task: dict, python: str = sys.executable) -> List[str]:
    """Run the untouched seed through the collector and say every way it differs from what the task states.

    An empty list means: the outcome is the one ``seed_expect`` names; the given tests absent from the
    report are exactly the ones it lists; no given test is skipped; and every test pytest ran in the tests
    directory is one the syntax-tree finder saw. A task that fails any of these would misjudge sessions.
    """
    problems: List[str] = []
    td = Path(tempfile.mkdtemp(prefix="selfreport-seed-"))
    try:
        sandbox = materialise(task, td / "sandbox", python=python, environment={"sha256": "unused"})
        got = C.collect(task, sandbox, td / "work", python=python, repeat=1)
    except (C.Void, TaskError) as exc:
        shutil.rmtree(str(td), ignore_errors=True)
        return ["the untouched seed could not be collected: %s" % exc]
    shutil.rmtree(str(td), ignore_errors=True)
    given = got["facts"]["test_outcome"]["given"]
    run = given["runs"][0]
    expect = task["seed_expect"]
    if not got["facts"]["given_tests"]:
        problems.append("the seed has no test the syntax-tree finder sees")
    if run["class"] != expect["outcome"]:
        problems.append("the untouched seed reads %s (%s); the task says %s"
                        % (run["class"], run["why"][:120], expect["outcome"]))
    states = run.get("given", {})
    absent = sorted(k for k, v in states.items() if v == "absent")
    if absent != sorted(expect["absent"]):
        problems.append("given tests absent from the report: %s; the task lists %s" % (absent, expect["absent"]))
    skipped = sorted(k for k, v in states.items() if v == "skipped")
    if skipped:
        problems.append("given tests skipped in the untouched seed: %s" % skipped)
    if run.get("other_rows"):
        problems.append("pytest ran tests the syntax-tree finder did not see: %s" % run["other_rows"][:5])
    return problems
