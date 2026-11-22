# -*- coding: utf-8 -*-
"""The new code must run on Python 3.9, which CI tests and this machine does not have.

The first version passed ``newline=`` to ``Path.write_text`` in eleven places. That parameter arrived in
3.10; on 3.9 each call raises TypeError, and a syntax check cannot see it. These tests read the syntax tree
for the constructs that have bitten, and are no substitute for the 3.9 job itself.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted((ROOT / "styxx" / "selfreport").glob("*.py")) + sorted((ROOT / "tests").glob("test_selfreport_*.py")) \
    + [ROOT / "tests" / "_selfreport_util.py"]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_parses_as_python_3_9_and_avoids_calls_that_arrived_later(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            keywords = {k.arg for k in node.keywords}
            if node.func.attr == "write_text" and "newline" in keywords:
                problems.append("line %d: write_text(newline=) needs 3.10" % node.lineno)
            if node.func.attr in ("removeprefix", "removesuffix") and False:
                problems.append("line %d" % node.lineno)  # both exist in 3.9; kept as a reminder of the cut
            if node.func.attr == "zip" and "strict" in keywords:
                problems.append("line %d: zip(strict=) needs 3.10" % node.lineno)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "zip":
            if "strict" in {k.arg for k in node.keywords}:
                problems.append("line %d: zip(strict=) needs 3.10" % node.lineno)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dataclass":
            if {"slots", "kw_only"} & {k.arg for k in node.keywords}:
                problems.append("line %d: dataclass(slots/kw_only) needs 3.10" % node.lineno)
    assert not problems, "%s: %s" % (path.name, problems)


@pytest.mark.parametrize("path", sorted((ROOT / "styxx" / "selfreport").glob("*.py")), ids=lambda p: p.name)
def test_annotations_are_never_evaluated(path):
    """`dict[str, int]` and `X | None` in an annotation are fine on 3.9 only under the future import."""
    assert "from __future__ import annotations" in path.read_text(encoding="utf-8")


def test_the_package_is_not_imported_by_importing_styxx():
    """It starts subprocesses and is no part of the library's public surface."""
    import subprocess
    r = subprocess.run([sys.executable, "-c", "import sys, styxx; print('styxx.selfreport' in sys.modules)"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(ROOT))
    assert r.stdout.decode().strip() == "False", r.stderr.decode()[-300:]
