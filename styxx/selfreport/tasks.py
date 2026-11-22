# -*- coding: utf-8 -*-
"""Sandbox tasks: the format, its validation, and turning a task into a directory an agent can work in.

A task is a directory::

    <task_id>/
      task.json     the machine-readable statement, with digests that pin the seed, the prompt and the contract
      PROMPT.md     the instructions exactly as an agent receives them; ends with the shared report contract
      seed/         the repository as given: plain files, ASCII paths, its own pytest.ini
      EXPECTED.json the verdicts each scripted known-answer agent must receive on this task

Every pin is over bytes. A task whose seed, prompt or contract no longer matches its pins does not load.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .collect import manifest, manifest_digest, sha256_hex
from .score import REQUIRED_KEYS

SPEC_TASK = "styxx.selfreport.task/v0"

#: A path matching one of these is never carried from the agent's tree into the judged copy: each can change
#: how tests are collected or run. The seed's own copies stay.
NEVER_CARRIED = ("conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini", "sitecustomize.py",
                 "usercustomize.py", "*.pth")

#: The closed set of rules by which a declared key is compared with a fact.
TRUTH_RULES = {
    "tests_pass": "given_tests_pass",
    "files_changed": "manifest_count",
    "tests_added": "ast_new_test_functions",
    "only_touches": "all_changed_under_prefix",
}

_REQUIRED_FIELDS = ("spec", "id", "condition", "test_command", "test_timeout_s", "repeat", "editable",
                    "addable", "never_carried", "required_keys", "truth", "design", "seed_manifest_sha256",
                    "prompt_sha256", "contract_sha256")


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
    try:
        task = json.loads(tj.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise TaskError("%s: task.json is not JSON: %s" % (task_dir.name, exc))
    name = task_dir.name
    for f in _REQUIRED_FIELDS:
        _need(f in task, "%s: task.json lacks %r" % (name, f))
    _need(task["spec"] == SPEC_TASK, "%s: spec is %r, expected %r" % (name, task["spec"], SPEC_TASK))
    _need(task["id"] == name, "%s: id %r does not match the directory name" % (name, task["id"]))
    cmd = task["test_command"]
    _need(isinstance(cmd, list) and cmd and all(isinstance(c, str) for c in cmd) and "{python}" in cmd,
          "%s: test_command must be a list of strings containing '{python}'" % name)
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
    seed = task_dir / "seed"
    _need(seed.is_dir(), "%s: no seed/ directory" % name)
    _need((seed / "pytest.ini").is_file(), "%s: the seed needs its own pytest.ini" % name)
    prompt = task_dir / "PROMPT.md"
    _need(prompt.is_file(), "%s: no PROMPT.md" % name)
    m0 = manifest(seed)
    for p, meta in m0.items():
        _need(meta["type"] == "f", "%s: seed entry %r is not a regular file" % (name, p))
        _need(p.isascii(), "%s: seed path %r is not ASCII" % (name, p))
    if check_pins:
        pb = prompt.read_bytes()
        _need(b"\r" not in pb, "%s: PROMPT.md holds a carriage return; pins are over bytes" % name)
        _need(sha256_hex(pb) == task["prompt_sha256"], "%s: PROMPT.md does not match prompt_sha256" % name)
        _need(manifest_digest(m0) == task["seed_manifest_sha256"],
              "%s: seed/ does not match seed_manifest_sha256" % name)
        cp = contract_path(task_dir.parent)
        _need(cp.is_file(), "%s: no report contract at %s" % (name, cp))
        cb = cp.read_bytes()
        _need(sha256_hex(cb) == task["contract_sha256"], "%s: the report contract does not match "
                                                         "contract_sha256" % name)
        _need(pb.endswith(cb), "%s: PROMPT.md does not end with the report contract, byte for byte" % name)
    task["_dir"] = str(task_dir)
    task["_seed_manifest"] = m0
    return task


def _inside_repository(path: Path) -> Optional[Path]:
    for parent in [path] + list(path.parents):
        if (parent / ".git").exists():
            return parent
    return None


def materialise(task: dict, dest) -> Path:
    """Create the sandbox for one session at ``dest`` (which must not exist): a copy of the seed with one
    commit. Refuses a destination inside a repository, where a parent's test configuration or history could
    leak in. The sandbox's git history is a convenience for the agent and is never read back."""
    dest = Path(dest).resolve()
    if dest.exists():
        raise TaskError("%s already exists" % dest)
    inside = _inside_repository(dest.parent)
    if inside is not None:
        raise TaskError("a sandbox must sit outside every repository; %s is inside %s" % (dest, inside))
    shutil.copytree(str(Path(task["_dir"]) / "seed"), str(dest))
    if manifest_digest(manifest(dest)) != task["seed_manifest_sha256"]:
        raise TaskError("the copied seed does not match the task's pin")
    env: Dict[str, str] = dict(os.environ)
    env.update({"GIT_AUTHOR_NAME": "seed", "GIT_AUTHOR_EMAIL": "seed@example.invalid",
                "GIT_COMMITTER_NAME": "seed", "GIT_COMMITTER_EMAIL": "seed@example.invalid",
                "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull})
    for args in (["-c", "init.defaultBranch=main", "init", "-q", "."], ["add", "-A"],
                 ["-c", "commit.gpgsign=false", "commit", "-q", "-m", "seed"]):
        r = subprocess.run(["git"] + args, cwd=str(dest), env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
        if r.returncode != 0:
            raise TaskError("git %s failed in the sandbox: %s"
                            % (" ".join(args), r.stderr.decode("utf-8", "replace")[:200]))
    return dest
