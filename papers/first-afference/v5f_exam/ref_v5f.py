# -*- coding: utf-8 -*-
# ref_v5f.py -- the v5f REFERENCE MODEL (exam author's executable spec).
#
# Written from the text of papers/first-afference/DESIGN_protocol_v5f_DRAFT_2026_09_25.md alone
# (plus the v5e spec and v5e's styxx/protocol.py as the delta base), under gate G_INDEP. It is a
# drop-in replacement for styxx/protocol.py: the v4-era head below is v5e's, with M11's scoring
# changes; everything from "-- v5f: the coverage tracer" on is the v5 region, rewritten. Where the
# text was ambiguous the reading taken is recorded in SPEC_GAPS.md (cited here as "GAP-nn").
# Revision 9 of the text ("Revision 9: spec gaps from the exam author") resolves every GAP-nn in
# the text; each GAP-nn comment below now cites that resolution. This file applies its "Required
# changes to ref_v5f.py", C1-C4 (C1-C3 in coverage_trace(), _exit_txn and _v5_state()).
"""styxx.protocol — the research loop as enforceable machinery.

The witness harnesses the program's *instruments*; this harnesses its *process*. The
prereg → frozen-gates → scored-run → verdict discipline that styxx cycles perform by
convention becomes machinery an agent cannot quietly bend:

  1. **Prereg-before-data.** ``Experiment(prereg=...)`` refuses to score unless the prereg
     file is committed in git history (not merely on disk) — the freeze is checked against
     the repository, not the agent's word.
  2. **Gates parse from the frozen document.** The prereg embeds a fenced ```gates json
     block; the scorer reads bars from the committed text. There is no API to pass a bar at
     scoring time — a bar that isn't in the frozen document does not exist.
  3. **Verdicts are mechanical.** The outcome table is part of the gates block; ``score()``
     evaluates gate expressions against the result dict and walks the table. The agent
     reports the verdict; it does not choose it.
  4. **Smoke is INVALID-only.** ``score(smoke=True)`` always returns the INVALID smoke
     verdict regardless of numbers — a smoke that looks good licenses nothing, by type.
  5. **Tamper check.** The gates block's sha256 is returned with every verdict; re-scoring
     against an edited prereg produces a hash mismatch against the recorded one.

Format — a prereg embeds one fenced block::

    ```gates
    {"gates": {"G0": {"metric": "llama_top1", "op": ">=", "value": 0.29},
               "G1": {"metric": "gemma_top1", "op": ">=", "value": 0.143}},
     "outcomes": [{"when": {"G0": false}, "verdict": "INVALID__pipeline_broken"},
                  {"when": {"G0": true, "G1": true}, "verdict": "DOOR_OPENS"},
                  {"when": {"G0": true, "G1": false}, "verdict": "CLOSED_NEGATIVE"}],
     "smoke_verdict": "INVALID__smoke_plumbing_only"}
    ```

Metrics are keys of the result dict (dots traverse nesting). Ops: >=, <=, >, <, ==.
Outcomes are evaluated in order; the first row whose ``when`` matches wins; no row matching
is itself an error (the frozen table must be total — a partial table is a design bug the
harness surfaces instead of guessing).
"""

from __future__ import annotations

import collections
import functools
import gc
import hashlib
import importlib
import itertools
import math
import json
import numbers
import operator
import os
import re
import subprocess
import sys
import sysconfig
import threading
import time
import types
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from types import (AsyncGeneratorType, BuiltinFunctionType, CoroutineType, FunctionType,
                   GeneratorType, GetSetDescriptorType, MemberDescriptorType,
                   MethodDescriptorType, ModuleType)

__all__ = ["Experiment", "Verdict", "PrologueError", "GateSpecError",
           "undeclared_power_gates", "coverage_trace"]

# -- v5f M1: module state (every piece of shared state is a registry changed only by single
# GIL-atomic C operations, an immutable value replaced by one store, or a monotone map changed only
# by setdefault). Placed before every function (M1). `import styxx.protocol` never touches
# sys.monitoring or asyncio (M0), so the event masks are literals (revision 9, GAP-01: the first line of M1).
PY_START, PY_RESUME, PY_RETURN, PY_YIELD, PY_UNWIND = 1, 2, 4, 8, 4096

_TRACER_ID = "styxx.protocol.coverage_trace/3"
_CACHE_WRAPPER = type(functools.lru_cache(None)(lambda: 0))
# Reload (N8): exactly these are bound through globals().get, so importlib.reload keeps them.
_BY_FN = globals().get("_BY_FN", {})              # F_T -> _Mint
_MINTED = globals().get("_MINTED", {})            # id(M_T) -> _Mint (the mint holds M_T)
_ANCHORS = globals().get("_ANCHORS", {})          # anchor frame -> _Opening (the key holds the frame)
_CUT = globals().get("_CUT", {})                  # id(code) -> code; setdefault only
_GUARD = globals().get("_GUARD", None)            # head of the robust-mutex chain (set below, M1)
_TOOL = globals().get("_TOOL", [None])            # sys.monitoring tool id
_TOOL_NAME = globals().get("_TOOL_NAME") or "styxx.protocol/" + os.urandom(6).hex()
_HANDLE_DICT = globals().get("_HANDLE_DICT", [None])   # asyncio.events.Handle's class dict
_LOOP_DICT = globals().get("_LOOP_DICT", [None])       # asyncio.base_events.BaseEventLoop's class dict
_LOST = globals().get("_LOST", [])                # a counter read as len(_LOST); grows by append only
_MON = globals().get("_MON", [None])              # the seven sys.monitoring functions, bound once:
# (get_tool, get_events, set_events, set_local_events, register_callback, use_tool_id,
#  get_local_events); index 6 from revision 9 (GAP-03), read only by _exit_txn and _v5_state (M0)
_get_running_loop = globals().get("_get_running_loop")   # asyncio.events._get_running_loop, checked
# and re-bound by every coverage_trace() after its import asyncio (revision 9, GAP-02; M0 steps 5-7)
_BUSY_SECONDS = 10.0
_LOCAL = PY_START | PY_RESUME | PY_RETURN | PY_YIELD        # local, on minted code only
# The M1 one-call vocabulary (M7): `_map` through `_CALLBACKS5`; plain bindings, re-bound by a reload.
_map, _chain, _compress, _filter = map, itertools.chain, itertools.compress, filter
_is, _not, _and, _setitem = operator.is_, operator.not_, operator.and_, operator.setitem
_ARMED = operator.attrgetter('armed');  _FLAGS = operator.attrgetter('core.flags');  _VALUES = dict.values
_CONSUME = collections.deque(maxlen=0).extend
_LOST_KEY, _TRUE = itertools.repeat('UNWIND_LOST'), itertools.repeat(True)
_PYU1, _ZERO1, _NONE1, _NAME1 = (PY_UNWIND,), (0,), (None,), (_TOOL_NAME,)
_repeat, _list = itertools.repeat, list
_is_not, _LOST_APPEND = operator.is_not, _LOST.append
_tee = itertools.tee
_EVENTS5 = (PY_START, PY_RESUME, PY_RETURN, PY_YIELD, PY_UNWIND)
# _CALLBACKS5 is bound after the three callbacks are defined (M1), in the v5 region below.
_VERIFIED = ((3, 12, 3), (3, 13, 12))
_monotonic, _sleep = time.monotonic, time.sleep


def undeclared_power_gates(prereg) -> list:
    """Gate names in *prereg* carrying no usable ``power_basis`` — corpus-auditable.

    Frozen as a deliverable in ``PREREG_protocol_power_basis_2026_08_07.md`` item 4 and silently
    dropped from the implementation; the red team caught the omission, not the exam.
    """
    return Experiment(prereg).undeclared_power_gates

_FENCE_LINE_RE = re.compile(r"^([ \t]*)(`{3,}|~{3,})[ \t]*(\S*)[ \t]*$")
_CLOSER_RE = re.compile(r"^ {0,3}`{3,}[ \t]*$")


def _select_gates_block(text: str) -> str:
    """The ONE gates block, or a refusal. Single scanner, single definition.

    Three red-team rounds (2026-08-09) broke every version of this that used two notions of "a
    gates fence" — a human-view counter and a machine extractor — because each divergence between
    them is a shadowing channel: round 1 hid a fence in an HTML comment, round 2 swapped a tilde
    for a backtick, round 3 swapped one Latin letter for a Cyrillic one in the info string and
    tab-indented an opener the counter skipped but the unanchored extractor matched. This
    function is the round-3 recipe: tokenize every fence line ONCE, on the ORIGINAL text, and
    extract from the very match the multiplicity guard validated. There is no second regex to
    disagree with.

    Rules, each a refusal:
    * a fence info string containing any non-ASCII character refuses outright — a confusable
      info string ("gаtes") is indistinguishable from "gates" to a reader and distinct to
      the machine, and no normalization table is trusted to enumerate that class;
    * gates-like = a CommonMark-rendered fence (indent ≤ 3 columns, tab = 4) whose casefolded
      info is "gates", counted comments-included so hidden fences count;
    * exactly one gates-like block must exist, it must be the plain unindented lowercase
      backtick form, it must not sit inside an HTML comment (unterminated comments extend to
      EOF — a renderer hides everything after one), and its closing fence must exist.
    """
    lines = text.split("\n")
    # HTML comment spans, computed on character offsets; an unterminated opener hides to EOF.
    spans, pos = [], 0
    while True:
        s = text.find("<!--", pos)
        if s < 0:
            break
        e = text.find("-->", s + 4)
        spans.append((s, len(text) if e < 0 else e + 3))
        pos = s + 4 if e < 0 else e + 3
    offsets, off = [], 0
    for ln in lines:
        offsets.append(off)
        off += len(ln) + 1

    gates_like = []          # (line_index, indent, marker, info)
    for i, ln in enumerate(lines):
        m = _FENCE_LINE_RE.match(ln)
        if not m:
            continue
        indent, marker, info = m.groups()
        if not info.isascii():
            raise GateSpecError(
                f"fence info string {info!r} (line {i + 1}) contains non-ASCII characters — a "
                f"confusable info string is a shadowing channel, and this parser refuses the "
                f"class rather than trusting a normalization table to enumerate it")
        cols = 0
        for ch in indent:
            cols = cols + 4 - cols % 4 if ch == "\t" else cols + 1
        rendered = cols <= 3
        if rendered and info.casefold() == "gates":
            gates_like.append((i, indent, marker, info))

    if not gates_like:
        raise GateSpecError("prereg has no ```gates block — nothing frozen to score against")
    if len(gates_like) > 1:
        where = [f"line {i + 1} ({marker}{info})" for i, _, marker, info in gates_like]
        raise GateSpecError(
            f"prereg contains {len(gates_like)} gates-like fenced blocks ({', '.join(where)}) "
            f"— the frozen block must be unambiguous. A document that can show a reader one "
            f"block and score against another is not frozen; remove or rename all but one.")

    i, indent, marker, info = gates_like[0]
    if indent or marker != "```" or info != "gates":
        raise GateSpecError(
            f"the single gates-like block (line {i + 1}, {indent!r}{marker}{info}) is not a "
            f"plain unindented ```gates fence — the one form a renderer and this parser read "
            f"identically. A block only one of them recognises is a shadowing channel, not a "
            f"style choice.")
    if any(s <= offsets[i] < e for s, e in spans):
        raise GateSpecError(
            f"the ```gates fence at line {i + 1} sits inside an HTML comment (possibly "
            f"unterminated) — a renderer hides it, so scoring it would divorce the machine's "
            f"authority from the reader's. De-comment it.")
    for j in range(i + 1, len(lines)):
        if _CLOSER_RE.match(lines[j]):
            return "\n".join(lines[i + 1:j])
    raise GateSpecError(
        f"the ```gates fence at line {i + 1} is never closed — an unterminated block renders "
        f"as everything-is-code and freezes nothing")
# fullmatch, not ^...$: "$" also matches before a trailing newline (red team round 1, N2).
_TARGET_RE = re.compile(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*:[A-Za-z_]\w*(\.[A-Za-z_]\w*)*",
                        re.ASCII)
_TRACE_KEY = "coverage_trace"

_OPS = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b, "<": lambda a, b: a < b,
        "==": lambda a, b: a == b}


class PrologueError(RuntimeError):
    """The prereg is not committed / not found — scoring is refused."""


class GateSpecError(ValueError):
    """The frozen gates block is missing, malformed, or not total."""


@dataclass
class Verdict:
    verdict: str
    gates: dict                 # gate name -> bool
    gates_sha256: str           # hash of the frozen gates block text
    prereg_commit: str          # the earliest commit containing the prereg
    smoke: bool = False
    power_basis: dict = field(default_factory=dict)      # gate -> how its bar was derived
    undeclared_power_gates: list = field(default_factory=list)
    vacuous_gates: list = field(default_factory=list)    # gates no outcome row depends on
    metric_paths: dict = field(default_factory=dict)     # gate -> the dotted path it read
    coverage: dict = field(default_factory=dict)         # gate -> {declared target: calls}


def _resolve(result: dict, dotted: str):
    obj = result
    for k in dotted.split("."):
        if not isinstance(obj, dict) or k not in obj:
            raise GateSpecError(f"metric {dotted!r} not present in result")
        obj = obj[k]
    return obj


class Experiment:
    """One preregistered experiment, scored only on the frozen document's terms."""

    def __init__(self, prereg: str | Path, repo_root: str | Path | None = None,
                 require_power_basis: bool = False,
                 require_nonvacuous_gates: bool = False):
        self.require_power_basis = require_power_basis
        self.require_nonvacuous_gates = require_nonvacuous_gates
        self.prereg = Path(prereg)
        self.repo_root = Path(repo_root) if repo_root else self.prereg.resolve().parent
        if not self.prereg.exists():
            raise PrologueError(f"prereg not found: {self.prereg}")
        self.prereg_commit = self._committed_at()
        text = self.prereg.read_text(encoding="utf-8")
        self._gates_text = _select_gates_block(text)
        self.gates_sha256 = hashlib.sha256(self._gates_text.encode("utf-8")).hexdigest()

        def _no_dup_keys(pairs):
            # Red team 2026-08-09 (v4 audit, D2): json.loads silently keeps the LAST duplicate
            # key, so '"excluding": "real", "excluding": "decoy"' displayed both while the
            # machine honoured only the decoy. Corpus measured clean; refusal rewrites nothing.
            seen = {}
            for k, v in pairs:
                if not k.isascii():
                    # Verification pass F2 (2026-08-09): "exсluding" with a Cyrillic с is a
                    # DIFFERENT key to json and the same word to a human — two live
                    # declarations, machine honours one. Byte-equality dup detection cannot see
                    # it; an ASCII allowlist can. No committed gates block has non-ASCII keys.
                    raise GateSpecError(
                        f"non-ASCII key {k!r} in the gates block — a key a human cannot "
                        f"distinguish from an ASCII one is a shadowing channel. Keys must be "
                        f"ASCII.")
                if k in seen:
                    raise GateSpecError(
                        f"duplicate key {k!r} in the gates block — a block that declares the "
                        f"same key twice shows a reader both and honours only the last, which "
                        f"is a shadowing channel, not a typo to forgive")
                seen[k] = v
            return seen

        try:
            spec = json.loads(self._gates_text, object_pairs_hook=_no_dup_keys)
        except json.JSONDecodeError as e:
            raise GateSpecError(f"gates block is not valid JSON: {e}") from e
        for key in ("gates", "outcomes", "smoke_verdict"):
            if key not in spec:
                raise GateSpecError(f"gates block missing {key!r}")
        self.spec = spec
        self.power_basis = {n: g.get("power_basis") for n, g in spec["gates"].items()}
        self.metric_paths = {n: g.get("metric") for n, g in spec["gates"].items()}
        _bad = sorted(n for n, m in self.metric_paths.items() if not isinstance(m, str) or not m)
        if _bad:
            raise GateSpecError(
                f"gates with a missing or non-string 'metric' path: {_bad}. Left unchecked this "
                f"put None into metric_paths and made check_metrics() raise AttributeError — the "
                f"pre-run safety tool crashing on the most mis-specified gate there is.")
        self.metric_means = {n: g.get("metric_means") for n, g in spec["gates"].items()}

        # -- v4: declared gate composition ------------------------------------------------------
        # E1 (cycle 159): G1 judged the minimum over ALL candidates while G2 disqualified one of
        # them in the same run. Every component was individually correct; the composition was
        # wrong, and nothing here looked at relationships between gates. A gate whose metric is
        # an aggregate over a set may now declare that set:
        #   "agg": "min"|"max"  — which extremum the metric claims to be
        #   "over": path        — a dict of per-member values in the result
        #   "excluding": path   — optional; a list of member names to exclude first
        # score() recomputes the aggregate over the declared population minus the declared
        # exclusions and REFUSES if the quoted metric does not equal the recomputation. This
        # checks declared composition only — a ratchet, not a proof.
        self.composition = {}
        for n, g in spec["gates"].items():
            keys = {k: g.get(k) for k in ("agg", "over", "excluding") if k in g}
            if not keys:
                continue
            if "agg" not in keys or "over" not in keys:
                raise GateSpecError(
                    f"gate {n!r}: a composition declaration needs both 'agg' and 'over' "
                    f"(got {sorted(keys)}). Half a declaration checks nothing while looking "
                    f"like it checks something, which is worse than no declaration.")
            if keys["agg"] not in ("min", "max"):
                raise GateSpecError(
                    f"gate {n!r}: 'agg' must be \"min\" or \"max\", got {keys['agg']!r}")
            if not isinstance(keys["over"], str) or not keys["over"]:
                raise GateSpecError(f"gate {n!r}: 'over' must be a non-empty result path")
            if "excluding" in keys and (not isinstance(keys["excluding"], str)
                                        or not keys["excluding"]):
                raise GateSpecError(
                    f"gate {n!r}: 'excluding' must be a non-empty result path when present")
            self.composition[n] = keys

        # -- v5: declared harness coverage ------------------------------------------------------
        # P1 (cycle 158): three of five frozen gates were satisfiable without testing what they
        # named — G4 scored 1.0 while its harness called one of five public entry points. A gate
        # may now declare the functions the code producing its metric must have executed:
        #   "exercises": ["module:qualname", ...]  — non-empty, ASCII, no duplicates
        #   "section": name                        — optional; the trace section (default: gate)
        # coverage_trace() reads the targets from THIS frozen block, records calls to their code
        # objects per section, and score() refuses a declaring gate whose section shows a target
        # uncalled. Exercised is not tested: this catches a harness that never touched a
        # function, not one that touched it and checked nothing.
        self.coverage = {}
        for n, g in spec["gates"].items():
            if "exercises" not in g and "section" not in g:
                continue
            if "exercises" not in g:
                raise GateSpecError(
                    f"[V5:SECTION_DECL] gate {n!r}: 'section' without 'exercises' declares a place and nothing to "
                    f"find in it — half a declaration checks nothing while looking like a check")
            ex = g["exercises"]
            if not isinstance(ex, list) or not ex:
                raise GateSpecError(
                    f"[V5:DECL] gate {n!r}: 'exercises' must be a non-empty list of \"module:qualname\" "
                    f"strings, got {ex!r}. An empty declaration would pass every harness.")
            bad = [t for t in ex if not isinstance(t, str) or not _TARGET_RE.fullmatch(t)]
            if bad:
                raise GateSpecError(
                    f"[V5:DECL] gate {n!r}: 'exercises' entries must be ASCII \"module:qualname\" strings "
                    f"(e.g. \"styxx.power:reachable\"); refused {bad!r}")
            if len(set(ex)) != len(ex):
                raise GateSpecError(
                    f"[V5:DECL] gate {n!r}: 'exercises' names a target twice: {ex!r}")
            sec = g.get("section", n)
            if not isinstance(sec, str) or not sec or not sec.isascii():
                raise GateSpecError(
                    f"[V5:SECTION_DECL] gate {n!r}: 'section' must be a non-empty ASCII string, got {sec!r}")
            self.coverage[n] = {"exercises": list(ex), "section": sec}
        self.coverage_targets = sorted({t for c in self.coverage.values()
                                        for t in c["exercises"]})
        self.coverage_sections = sorted({c["section"] for c in self.coverage.values()})

        self.undeclared_power_gates = sorted(
            n for n, v in self.power_basis.items()
            if not (isinstance(v, str) and v.strip()))   # " " and true are NOT declarations
        if self.require_power_basis and self.undeclared_power_gates:
            raise GateSpecError(
                f"gates without a declared power basis: {self.undeclared_power_gates}. "
                f"Each gate must carry \"power_basis\": how its bar was derived, or the literal "
                f"\"none — exploratory\". Three bars in this program were set without checking "
                f"whether any instrument could clear them (b37 G2, b48 G2, C5 G1); each was "
                f"written up and each recurred. An undeclared bar is now a refusal, not a note.")

        # VACUITY. A gate no outcome row mentions is computed, hashed, displayed and scored —
        # and no verdict depends on it. It is decoration wearing a bar's clothes, and this
        # programme has shipped one: the v0.11 drafting record names a BLOCKER where "the
        # warrant gate as first drafted could not fail". Our own preregs say a leg that cannot
        # fail must not gate; nothing enforced it.
        #
        # Adopted from `honest-signal` (github.com/alexcard3/honest-signal), whose preregistration
        # firewall refuses a merge when the kill criterion is vacuous. The frozen prior-art survey
        # (RESULT_oath_prior_art_survey_2026_08_26.md) found that tool occupying the mechanism
        # this lab thought was its own, and this check is the half we did not have. Credit is the
        # useful response to being second, not priority.
        #
        # Deliberately NARROW: vacuous means "no outcome row's `when` clause names this gate".
        # Single-polarity mention is NOT flagged — a gate appearing once as true, with a wildcard
        # row catching false, genuinely decides the verdict, and the totality check already
        # refuses the case where nothing catches it. An unfailable BAR (`>= 0.0` on a
        # probability) needs domain knowledge this parser does not have and is not attempted;
        # that residual is disclosed rather than silently implied to be covered.
        _mentioned = {n for row in spec["outcomes"] for n in (row.get("when") or {})}
        self.vacuous_gates = sorted(n for n in spec["gates"] if n not in _mentioned)
        if self.require_nonvacuous_gates and self.vacuous_gates:
            raise GateSpecError(
                f"gates no outcome row depends on: {self.vacuous_gates}. Such a gate is scored "
                f"and reported while no verdict turns on it — a leg that cannot fail must not "
                f"gate. Either give it an outcome row, or stop calling it a gate and record it "
                f"as an asserted invariant, which is what it is.")

    def check_metrics(self, result: dict) -> dict:
        """Resolve every gate's metric path against a candidate result WITHOUT scoring.

        Call this before launching a run. It never raises for a JSON-shaped result (M11): dicts,
        lists, str, bool, None, floats and ints of any size. It runs no user ``__bool__``, ``get``
        or ``__missing__``: every dict read is ``dict.get`` behind an ``issubclass(type(x), dict)``
        test. **It cannot catch B49's actual error** (a path resolving to a real but wrong field).
        """
        out = {}
        isd = issubclass(type(result), dict)
        s = dict.get(result, "smoke") if isd else None
        ts = type(s)
        smoke = (ts is bool or ts is int or ts is float or ts is str) and bool(s)
        for name, path in self.metric_paths.items():
            val, found = result, True
            for k in path.split("."):
                if not issubclass(type(val), dict):
                    found = False
                    break
                val = dict.get(val, k, _MISSING)
                if val is _MISSING:
                    found = False
                    break
            if not found:
                out[name] = {"path": path, "present": False, "usable": False,
                             "note": ("result is a smoke run; smoke scores by type and never "
                                      "reads gate metrics" if smoke else "path not in result")}
                continue
            tv = type(val)
            usable = issubclass(tv, (int, float)) and tv is not bool and _finite(val)
            if usable:
                note = None
            elif issubclass(tv, int) and tv is not bool:
                note = "int too large for a float"
            else:
                note = (f"resolves to {_TYPE_QUAL.__get__(tv)}"
                        f"{' (NaN/inf)' if issubclass(tv, float) else ''} — score() cannot "
                        f"compare it")
            out[name] = {"path": path, "present": True, "usable": usable, "note": note}
        for name, c in self.composition.items():
            for kind in ("over", "excluding"):
                if kind not in c:
                    continue
                key = f"{name}:{kind}"
                val, found = result, True
                for k in c[kind].split("."):
                    if not issubclass(type(val), dict):
                        found = False
                        break
                    val = dict.get(val, k, _MISSING)
                    if val is _MISSING:
                        found = False
                        break
                if not found:
                    out[key] = {"path": c[kind], "present": False, "usable": False,
                                "note": ("smoke run" if smoke else
                                         f"composition path ({kind}) not in result")}
                    continue
                if kind == "over":
                    ok = issubclass(type(val), dict) and dict.__len__(val) > 0
                else:
                    ok = issubclass(type(val), list)
                out[key] = {"path": c[kind], "present": True, "usable": ok,
                            "note": None if ok else
                            f"composition path ({kind}) resolves to "
                            f"{_TYPE_QUAL.__get__(type(val))}; score() will refuse it"}
        # v5 coverage: `present` is the NO_TRACE test; "smoke run" only when the trace is absent,
        # otherwise the refusal text, so the note always starts with its [V5:CODE] (M11, D9).
        present = isd and type(dict.get(result, _TRACE_KEY)) is dict
        for name in self.coverage:
            key = f"{name}:exercises"
            try:
                self._check_coverage(name, result)
                out[key] = {"path": _TRACE_KEY, "present": True, "usable": True, "note": None}
            except GateSpecError as e:
                if smoke and not present:
                    note = "smoke run"
                elif smoke:
                    note = str(e) + " (smoke run: score(smoke=True) does not read coverage)"
                else:
                    note = str(e)
                out[key] = {"path": _TRACE_KEY, "present": present, "usable": False,
                            "note": note}
        return out

    # -- the freeze check --------------------------------------------------

    def _committed_at(self) -> str:
        """Earliest commit hash containing the prereg file; refuses if none."""
        try:
            r = subprocess.run(
                ["git", "log", "--diff-filter=A", "--format=%H", "--follow", "--",
                 str(self.prereg.name)],
                cwd=self.prereg.resolve().parent, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise PrologueError(f"cannot verify the freeze against git: {e}") from e
        hashes = [h for h in r.stdout.split() if h]
        if r.returncode != 0 or not hashes:
            raise PrologueError(
                f"{self.prereg.name} is not committed — a prereg on disk is a draft, "
                "not a freeze; scoring is refused")
        return hashes[-1]

    # -- scoring -----------------------------------------------------------

    def _check_composition(self, name: str, quoted: float, result: dict) -> None:
        """Recompute a declared aggregate and refuse if the quoted metric disagrees.

        The E1 defect made concrete: a metric quoting the unrestricted minimum cannot equal the
        eligible-restricted recomputation when the two differ, so declaring the population turns
        that mistake from a silent pass into a refusal. Everything ill-formed refuses — a
        composition check that guesses is a composition check that can be gamed.
        """
        c = self.composition[name]
        pop = _resolve(result, c["over"])
        if not isinstance(pop, dict) or not pop:
            raise GateSpecError(
                f"gate {name!r}: 'over' path {c['over']!r} must resolve to a non-empty dict of "
                f"per-member values, got {type(pop).__name__}")
        excluded: set = set()
        if "excluding" in c:
            exc = _resolve(result, c["excluding"])
            if not isinstance(exc, list):
                raise GateSpecError(
                    f"gate {name!r}: 'excluding' path {c['excluding']!r} must resolve to a "
                    f"list of member names, got {type(exc).__name__}")
            bad_names = [e for e in exc if not isinstance(e, str)]
            if bad_names:
                # A mixed-type list previously crashed the sorted(set-difference) below with a
                # raw TypeError, which a harness catching only GateSpecError records as a crash
                # rather than a refusal (red team D8).
                raise GateSpecError(
                    f"gate {name!r}: 'excluding' entries must be strings naming members of "
                    f"'over'; got {bad_names!r}")
            unknown = sorted(set(exc) - set(pop))
            if unknown:
                raise GateSpecError(
                    f"gate {name!r}: 'excluding' names members absent from 'over': {unknown}. "
                    f"An exclusion that excludes nothing hides a key mismatch between the two "
                    f"fields, and the check would silently pass on the full population.")
            excluded = set(exc)
        eligible = {k: v for k, v in pop.items() if k not in excluded}
        if not eligible:
            raise GateSpecError(
                f"gate {name!r}: every member of {c['over']!r} is excluded — an aggregate over "
                f"an empty population is not a measurement")
        vals = []
        for k, v in eligible.items():
            # numbers.Real admits numpy float32/int64 scalars in in-process receipts (red team
            # D9: they are finite numbers and were refused with a wrong diagnosis); bool is a
            # Real and stays banned.
            if isinstance(v, bool) or not isinstance(v, numbers.Real) \
                    or not math.isfinite(float(v)):
                raise GateSpecError(
                    f"gate {name!r}: member {k!r} of {c['over']!r} is {v!r}, which cannot be "
                    f"aggregated")
            vals.append(float(v))
        recomputed = min(vals) if c["agg"] == "min" else max(vals)
        if not math.isclose(float(quoted), recomputed, rel_tol=0.0, abs_tol=1e-12):
            # The comparison is exact (1e-12) by design: rounding forgiveness would readmit
            # near-miss shadowing. The convention this imposes (red team D5): store per-member
            # values at the same precision you quote the metric — round both or neither. A
            # runner quoting round(min, 4) over full-precision members refuses HERE, loudly,
            # before any verdict; that is the fail-safe direction and it is intentional.
            members = sorted(k for k, v in eligible.items()
                             if math.isclose(float(v), recomputed, rel_tol=0.0, abs_tol=1e-12))
            raise GateSpecError(
                f"gate {name!r}: COMPOSITION VIOLATION — metric quotes {quoted!r} but the "
                f"declared {c['agg']} over {c['over']!r}"
                + (f" excluding {sorted(excluded)}" if excluded else "")
                + f" recomputes to {recomputed!r} (attained by {members}). The quoted value "
                f"belongs to a population this prereg's own declarations rule out. This is the "
                f"E1 defect (cycle 159): a gate passing on a candidate another gate disqualified.")

    def _check_coverage(self, name: str, result: dict) -> dict:
        """v5f score-time check for one declaring gate. Returns {declared target: union count}.

        Order (M11): NO_TRACE, WRONG_TRACER, BAD_TRACE (exact types before any hash or compare),
        STALE_TRACE, TARGET_SET, BAD_COUNT, a recorded problem (the FIRST one's own code; one site
        per recorded code, G7), SECTION_ABSENT, NOT_EXERCISED. Every code is a literal at its site.
        """
        c = self.coverage[name]
        if not issubclass(type(result), dict):
            raise GateSpecError(
                f"[V5:NO_TRACE] gate {name!r} declares 'exercises' but the result is a "
                f"{_TYPE_QUAL.__get__(type(result))}, not a dict -- run the harness inside "
                f"styxx.protocol.coverage_trace() and store its record()")
        tr = dict.get(result, _TRACE_KEY, _MISSING)
        if tr is _MISSING:
            raise GateSpecError(
                f"[V5:NO_TRACE] gate {name!r} declares 'exercises' but the result has no "
                f"{_TRACE_KEY!r} key -- run the harness inside styxx.protocol.coverage_trace() and "
                f"store its record(). A declared coverage with no trace is unverified, not met.")
        if type(tr) is not dict:
            raise GateSpecError(
                f"[V5:NO_TRACE] gate {name!r}: {_TRACE_KEY!r} is a {_TYPE_QUAL.__get__(type(tr))}, "
                f"not an exact dict (e.g. loaded with object_pairs_hook)")
        tid = dict.get(tr, "tracer")
        if type(tid) is not str or tid != _TRACER_ID:
            shown = repr(tid) if type(tid) is str else "a " + _TYPE_QUAL.__get__(type(tid))
            raise GateSpecError(
                f"[V5:WRONG_TRACER] gate {name!r}: {_TRACE_KEY}.tracer is {shown}, not "
                f"{_TRACER_ID!r} -- this trace was not written by the machinery that can read it")
        _check_trace_shape(name, tr)
        if tr["gates_sha256"] != self.gates_sha256:
            raise GateSpecError(
                f"[V5:STALE_TRACE] gate {name!r}: the trace was taken against gates block "
                f"{tr['gates_sha256'][:12]}..., not this one ({self.gates_sha256[:12]}...). "
                f"A trace of a different declaration is not evidence about this one.")
        if sorted(tr["targets"]) != self.coverage_targets:
            raise GateSpecError(
                f"[V5:TARGET_SET] gate {name!r}: the trace's target set {sorted(tr['targets'])} "
                f"differs from the declared set {self.coverage_targets}")
        declared = set(self.coverage_targets)
        where_dicts = []
        for s, ops in tr["sections"].items():
            for i, o in enumerate(ops):
                where_dicts.append((f"sections[{s!r}][{i}].calls", o["calls"]))
                where_dicts.append((f"sections[{s!r}][{i}].ambiguous", o["ambiguous"]))
        where_dicts.append(("uncredited.dispatched", tr["uncredited"]["dispatched"]))
        where_dicts.append(("uncredited.unattributed", tr["uncredited"]["unattributed"]))
        for where, d in where_dicts:
            for t, n in d.items():
                if t not in declared or type(n) is not int or n < 1:
                    shown = repr(n) if type(n) is int else "a " + _TYPE_QUAL.__get__(type(n))
                    raise GateSpecError(
                        f"[V5:BAD_COUNT] gate {name!r}: {where} holds {t!r}: {shown}; counts are "
                        f"declared targets with integer values >= 1")
        problems = tr["problems"]
        if problems:
            first = _CODE_RE.match(problems[0]).group(1)
            listed = f"; every recorded problem: {problems}"
            if first == "REENTRY":
                raise GateSpecError(f"[V5:REENTRY] gate {name!r}: {problems[0]}{listed}")
            if first == "TRACE_INACTIVE":
                raise GateSpecError(f"[V5:TRACE_INACTIVE] gate {name!r}: {problems[0]}{listed}")
            if first == "UNDECLARED_SECTION":
                raise GateSpecError(f"[V5:UNDECLARED_SECTION] gate {name!r}: {problems[0]}{listed}")
            if first == "NESTED_SECTION":
                raise GateSpecError(f"[V5:NESTED_SECTION] gate {name!r}: {problems[0]}{listed}")
            if first == "CLONE_CALLED":
                raise GateSpecError(f"[V5:CLONE_CALLED] gate {name!r}: {problems[0]}{listed}")
            if first == "CLONE_ALIVE":
                raise GateSpecError(f"[V5:CLONE_ALIVE] gate {name!r}: {problems[0]}{listed}")
            if first == "CODE_SWAPPED":
                raise GateSpecError(f"[V5:CODE_SWAPPED] gate {name!r}: {problems[0]}{listed}")
            if first == "CUT_MOVED":
                raise GateSpecError(f"[V5:CUT_MOVED] gate {name!r}: {problems[0]}{listed}")
            if first == "REENTRANT":
                raise GateSpecError(f"[V5:REENTRANT] gate {name!r}: {problems[0]}{listed}")
            if first == "MACHINERY_BUSY":
                raise GateSpecError(f"[V5:MACHINERY_BUSY] gate {name!r}: {problems[0]}{listed}")
        openings = tr["sections"].get(c["section"])
        if openings is None:
            raise GateSpecError(
                f"[V5:SECTION_ABSENT] gate {name!r}: section {c['section']!r} was never opened -- "
                f"nothing the harness ran can be attributed to this gate")
        union: dict = {}
        for o in openings:
            for t, n in o["calls"].items():
                union[t] = union.get(t, 0) + n
        missing = [t for t in c["exercises"] if t not in union]
        if missing:
            notes = sorted({n for o in openings for n in o["notes"]})
            ends = sorted({o["end"] for o in openings if o["end"] != "returned"})
            disp = {t: tr["uncredited"]["dispatched"][t]
                    for t in missing if t in tr["uncredited"]["dispatched"]}
            unat = {t: tr["uncredited"]["unattributed"][t]
                    for t in missing if t in tr["uncredited"]["unattributed"]}
            raise GateSpecError(
                f"[V5:NOT_EXERCISED] gate {name!r}: COVERAGE VIOLATION -- not executed on the stack "
                f"of any opening of section {c['section']!r}: {missing} (did execute "
                f"{sorted(union) or 'none of them'}). Uncredited calls of those targets: "
                f"dispatched {disp}, unattributed {unat}; openings' non-returned ends {ends}; "
                f"notes {notes}. Note: {_FIXED_SENTENCE}. This is the P1 defect (cycle 158): a gate "
                f"satisfied without running what it names.")
        return {t: union[t] for t in c["exercises"]}

    def score(self, result: dict, smoke: bool = False) -> Verdict:
        """Evaluate the frozen gates against a result dict; walk the frozen outcome table."""
        if smoke:
            return Verdict(verdict=self.spec["smoke_verdict"], gates={},
                           gates_sha256=self.gates_sha256,
                           prereg_commit=self.prereg_commit, smoke=True,
                           power_basis=dict(self.power_basis),
                           undeclared_power_gates=list(self.undeclared_power_gates),
                           vacuous_gates=list(self.vacuous_gates),
                           metric_paths=dict(self.metric_paths))
        fired: dict[str, bool] = {}
        covered: dict[str, dict] = {}
        for name, g in self.spec["gates"].items():
            op = _OPS.get(g.get("op"))
            if op is None:
                raise GateSpecError(f"gate {name!r}: unknown op {g.get('op')!r}")
            _v = _resolve(result, g["metric"])
            if isinstance(_v, bool) or not isinstance(_v, numbers.Real):
                raise GateSpecError(
                    f"gate {name!r}: metric {g['metric']!r} resolves to {_v!r}, which cannot be "
                    f"compared. A NaN previously made every comparison False and returned the "
                    f"frozen table's false branch as a SEALED verdict, with no refusal anywhere.")
            try:
                _fv = float(_v)
            except OverflowError:
                # M11: an overflowing metric gives GateSpecError, not OverflowError (v3 path, no code)
                raise GateSpecError(
                    f"gate {name!r}: metric {g['metric']!r} is too large for a float") from None
            if not math.isfinite(_fv):
                raise GateSpecError(
                    f"gate {name!r}: metric {g['metric']!r} resolves to {_v!r}, which cannot be "
                    f"compared. A NaN previously made every comparison False and returned the "
                    f"frozen table's false branch as a SEALED verdict, with no refusal anywhere.")
            if name in self.composition:
                self._check_composition(name, _v, result)
            if name in self.coverage:
                covered[name] = self._check_coverage(name, result)
            fired[name] = bool(op(_v, g["value"]))
        for row in self.spec["outcomes"]:
            hit = True
            for k, v in row["when"].items():
                if fired.get(k) != v:
                    hit = False
                    break
            if hit:
                return Verdict(verdict=row["verdict"], gates=fired,
                               gates_sha256=self.gates_sha256,
                               prereg_commit=self.prereg_commit,
                               power_basis=dict(self.power_basis),
                               undeclared_power_gates=list(self.undeclared_power_gates),
                               vacuous_gates=list(self.vacuous_gates),
                               metric_paths=dict(self.metric_paths),
                               coverage=covered)
        raise GateSpecError(
            f"no outcome row matches gates {fired} — the frozen table is not total; "
            "this is a prereg design bug, surfaced instead of guessed around")


# -- v5f: the coverage tracer (the v5 region) ---------------------------------------------------
#
# protocol v5f, "claim-and-reconcile mint-and-anchor on sys.monitoring, with confirmed-entry
# credit". Section references (M0-M11, E0-E5, X-1..X8, I1-I6, U1-U4) are to the v5f spec.
#
#   IDENTITY. A frame is a hit of T iff frame.f_code IS M_T and frame.f_globals IS
#   F_T.__globals__; M_T is F_T.__code__.replace(), published only by __code__ assignment and given
#   sys.monitoring local events (PY_START|PY_RESUME|PY_RETURN|PY_YIELD).
#   ATTRIBUTION. At the entry event the hit is credited, pending, to opening O iff O's anchor is
#   registered and met on the f_back chain before a cut code or a loop boundary, the running loop is
#   O.loop, and no other opening of O's tracer is met; the credit is published only when the frame
#   returns, yields, or unwinds at an offset other than its entry offset, while O's tracer credits.
#
# No lock, no profile or trace function, no try/finally except _run/_run_async's one, no nested
# code object (G_HYG). Every coded emission carries its complete literal code at its own site.

_MISSING = object()          # scoring sentinel for dict.get (M11: read only with dict.get)
_CODE_RE = re.compile(r"\[V5:([A-Z_]+)\] ")
_NOTE_CODES = frozenset({"OPEN_AT_EXIT", "LAZY_RESULT", "MONITOR_LOST"})
_RECORDED_CODES = frozenset({"REENTRY", "TRACE_INACTIVE", "UNDECLARED_SECTION", "NESTED_SECTION",
                             "CLONE_CALLED", "CLONE_ALIVE", "CODE_SWAPPED", "CUT_MOVED",
                             "REENTRANT", "MACHINERY_BUSY"})
_TRACE_KEYS = frozenset({"tracer", "gates_sha256", "targets", "sections", "uncredited", "problems"})
_OPENING_KEYS = frozenset({"calls", "ambiguous", "end", "notes"})
_UNCREDITED_KEYS = frozenset({"dispatched", "unattributed"})
_ENDS = frozenset({"returned", "raised", "open"})
_FIXED_SENTENCE = ("work on other threads, pools, executors, child processes or asyncio tasks is "
                   "credited only to a section that work opens itself; generator and coroutine "
                   "objects created before the trace are never credited; a call counts only when "
                   "it returns, yields or raises from inside its body while the tracer is active")

# Resolution primitives (Target identity, Resolution): C descriptors only.
_MOD_DICT = types.ModuleType.__dict__['__dict__']
_TYPE_DICT = type.__dict__['__dict__']
_TYPE_MRO = type.__dict__['__mro__']
_TYPE_QUAL = type.__dict__['__qualname__']
_SM_FUNC = staticmethod.__dict__['__func__']
_CM_FUNC = classmethod.__dict__['__func__']


# -- plain-data classes (M1): __slots__ literal tuples of exactly their fields, and __init__ ------

class _Txn:
    __slots__ = ("tid", "fid", "code", "succ")

    def __init__(self, tid, fid, code):
        self.tid = tid
        self.fid = fid
        self.code = code
        self.succ = {}                       # a fresh dict per token (M1, revision 5 N6)


if _GUARD is None:                           # M1 (revision 9, GAP-06): the statement right after class _Txn; a reload keeps the dict
    _GUARD = {"hint": _Txn(None, 0, None)}


class _Mint:
    __slots__ = ("fn", "qualname", "original", "code", "globals", "freeze0", "holders", "pend")

    def __init__(self, fn):                  # pure (Minting step 1)
        self.fn = fn
        n = dict.get(fn.__globals__, "__name__")
        self.qualname = (n if type(n) is str else fn.__code__.co_filename) + ":" + fn.__qualname__
        self.original = fn.__code__
        self.code = self.original.replace()
        self.globals = fn.__globals__
        self.freeze0 = gc.get_freeze_count()
        self.holders = ()                    # a tuple, rebuilt only under the mutex
        self.pend = {}                       # id(frame) -> (frame, entry_offset, outcomes)


class _Core:
    __slots__ = ("exp", "marks", "by_code", "names", "sections", "openings", "problems",
                 "clone_called", "uncredited", "lost_note", "flags", "facade", "pid", "prov",
                 "lost0")

    def __init__(self, exp, facade):
        self.exp = exp
        self.marks = {}                      # monotone: entering, active, exiting, exited
        self.by_code = {}                    # id(code) -> names; emptied first at exit
        self.names = {}                      # id(code) -> names; kept for record()
        self.sections = tuple(exp.coverage_sections)
        self.openings = []
        self.problems = []
        self.clone_called = {}               # id(code) -> module:qualname
        self.uncredited = {}                 # tid -> ({dispatched}, {unattributed}), by id(code)
        self.lost_note = None
        self.flags = {}                      # CUT_MOVED, UNWIND_LOST: set lock-free
        self.facade = facade                 # weakref.ref with no callback
        self.pid = os.getpid()
        self.prov = {}
        self.lost0 = 0


class _Opening:
    __slots__ = ("core", "section", "frame", "tid", "loop", "calls", "ambiguous", "fin", "lazy",
                 "armed")

    def __init__(self, core, section, frame, tid, loop):
        self.core = core
        self.section = section
        self.frame = frame                   # assigned here and, to None, only by its own finally
        self.tid = tid
        self.loop = loop
        self.calls = {}
        self.ambiguous = {}
        self.fin = {}                        # one claim: fin.setdefault('fin', (end, notes))
        self.lazy = None
        self.armed = False                   # set last by _commit


# -- resolution (Target identity) -----------------------------------------------------------

def _own_dict(obj):
    """The exact dict served by the first '__dict__' entry of type(obj)'s MRO, read through a C
    descriptor, or None. A Python-level __dict__ descriptor is never called."""
    t = type(obj)
    for k in _TYPE_MRO.__get__(t):
        e = _TYPE_DICT.__get__(k).get('__dict__', _MISSING)
        if e is not _MISSING:
            if type(e) is GetSetDescriptorType or type(e) is MemberDescriptorType:
                d = e.__get__(obj, t)
                return d if type(d) is dict else None
            return None
    return None


def _cache_callee(w):
    """The unique FunctionType among gc.get_referents(w) (the C func slot), or None."""
    fs = [x for x in gc.get_referents(w) if type(x) is FunctionType]
    return fs[0] if len(fs) == 1 else None


def _provenance(target, D, md):
    """FOREIGN_DEFINITION (Resolution step 6)."""
    mf = dict.get(md, '__file__')
    if type(mf) is not str:
        raise GateSpecError(
            f"[V5:FOREIGN_DEFINITION] declared target {target!r}: the declared module has no source "
            f"file to tie its code to")
    if mf.endswith('.pyc') or mf.endswith('.pyo'):
        raise GateSpecError(
            f"[V5:FOREIGN_DEFINITION] declared target {target!r}: the declared module was loaded "
            f"from compiled code {mf}, not from source (a zip archive holding a .pyc does this); "
            f"import it from its .py source")
    seen = {}
    cur = D
    inner = None
    for _hop in range(17):
        if cur is None or id(cur) in seen:
            break
        seen[id(cur)] = cur
        if type(cur) is FunctionType:
            inner = cur
            cf = cur.__code__.co_filename
            gf = dict.get(cur.__globals__, '__file__')
            coherent = cf.startswith('<') or (
                type(gf) is str and not gf.endswith('.pyc') and not gf.endswith('.pyo')
                and os.path.normcase(os.path.realpath(cf)) == os.path.normcase(os.path.realpath(gf)))
            if not coherent:
                n = dict.get(cur.__globals__, '__name__')
                raise GateSpecError(
                    f"[V5:FOREIGN_DEFINITION] declared target {target!r}: the code of "
                    f"{(n if type(n) is str else cf) + ':' + cur.__qualname__} was compiled from "
                    f"{cf}, not from its module's file {gf if type(gf) is str else None}: its "
                    f"__code__ was replaced")
            if cur.__globals__ is md:
                return
            cur = dict.get(_own_dict(cur) or {}, '__wrapped__')
        elif type(cur) is _CACHE_WRAPPER:
            cur = _cache_callee(cur)
        else:
            d = _own_dict(cur)
            if d is None:
                break
            cur = dict.get(d, '__wrapped__')
    if inner is None:
        where = "no Python function"
    else:
        n = dict.get(inner.__globals__, '__name__')
        where = (n if type(n) is str else inner.__code__.co_filename) + ':' + inner.__qualname__
    raise GateSpecError(
        f"[V5:FOREIGN_DEFINITION] declared target {target!r}: neither it nor its __wrapped__ "
        f"chain was defined in the declared module; the innermost function reached is {where} "
        f"(declare this instead) -- a re-export, a stub or a mock bound at the name is not the "
        f"function the declaration names")


def _resolve_target(target):
    """``module:qualname`` -> (D, F_T), or a refusal. Runs no user code except the import and a
    module's PEP 562 __getattr__ (and the contrived str-subclass key collision, M11)."""
    mod_name, qual = target.split(":", 1)
    try:
        mod = importlib.import_module(mod_name)
    except Exception as e:                           # noqa: BLE001  user-code site 1 of 2
        raise GateSpecError(
            f"[V5:UNRESOLVED] declared target {target!r}: importing {mod_name!r} raised "
            f"{_TYPE_QUAL.__get__(type(e))}") from e
    if not issubclass(type(mod), ModuleType):
        raise GateSpecError(
            f"[V5:UNRESOLVED] declared target {target!r}: the sys.modules entry is not a module")
    md = _MOD_DICT.__get__(mod)
    obj, holder = mod, md
    i = 0
    for part in qual.split("."):
        if type(obj) is staticmethod:                # unwrap first, at every step (D2)
            obj = _SM_FUNC.__get__(obj)
        elif type(obj) is classmethod:
            obj = _CM_FUNC.__get__(obj)
        if issubclass(type(obj), ModuleType):
            if i > 0:
                raise GateSpecError(
                    f"[V5:INSTANCE_PATH] declared target {target!r}: {part!r} is reached through a "
                    f"module after the colon -- put the full module path before it")
            d = _MOD_DICT.__get__(obj)
            if part in d:
                holder, obj = d, d[part]
            elif '__getattr__' in d:
                ga = d['__getattr__']
                try:                                 # user-code site 2 of 2 (PEP 562, called twice)
                    a = ga(part)
                    b = ga(part)
                except Exception as e:               # noqa: BLE001
                    raise GateSpecError(
                        f"[V5:UNRESOLVED] declared target {target!r}: {mod_name}.__getattr__"
                        f"({part!r}) raised {_TYPE_QUAL.__get__(type(e))}") from e
                if a is not b:
                    raise GateSpecError(
                        f"[V5:UNRESOLVED] declared target {target!r}: module __getattr__ returns a "
                        f"new object on each access; declare the function it forwards to")
                holder, obj = None, a
            else:
                raise GateSpecError(
                    f"[V5:UNRESOLVED] declared target {target!r}: {mod_name!r} has no attribute "
                    f"{part!r} and no module __getattr__ (an unimported submodule is not an "
                    f"attribute)")
        elif issubclass(type(obj), type):
            own = _TYPE_DICT.__get__(obj)
            if part in own:
                holder, obj = own, own[part]
            else:
                definer = None
                for k in _TYPE_MRO.__get__(obj)[1:]:
                    if part in _TYPE_DICT.__get__(k):
                        definer = k
                        break
                if definer is not None:
                    dm = _TYPE_DICT.__get__(definer).get('__module__')
                    raise GateSpecError(
                        f"[V5:INHERITED] declared target {target!r}: {part!r} is inherited by "
                        f"{_TYPE_QUAL.__get__(obj)}, not defined on it -- declare the defining "
                        f"class {(dm if type(dm) is str else '?') + ':' + _TYPE_QUAL.__get__(definer)}")
                raise GateSpecError(
                    f"[V5:UNRESOLVED] declared target {target!r}: class {_TYPE_QUAL.__get__(obj)} "
                    f"has no attribute {part!r} in its own or any class of its MRO")
        else:
            d = _own_dict(obj)
            if d is None or part not in d:
                raise GateSpecError(
                    f"[V5:INSTANCE_PATH] declared target {target!r}: {part!r} is not in the own "
                    f"__dict__ of the {_TYPE_QUAL.__get__(type(obj))} it is reached through -- an "
                    f"attribute that comes from a class is declared on the class "
                    f"({_TYPE_QUAL.__get__(type(obj))})")
            holder, obj = d, d[part]
        i += 1
    if type(obj) is staticmethod:                    # final unwrap (step 3)
        obj = _SM_FUNC.__get__(obj)
    elif type(obj) is classmethod:
        obj = _CM_FUNC.__get__(obj)
    D = obj
    if type(D) is FunctionType:                      # step 4: choose F_T
        fn = D
    elif type(D) is _CACHE_WRAPPER:
        callee = _cache_callee(D)
        stamped = dict.get(_own_dict(D) or {}, '__wrapped__')
        if callee is None or callee is not stamped:
            if callee is None:
                cname = "no single Python function"
            else:
                n = dict.get(callee.__globals__, '__name__')
                cname = (n if type(n) is str else callee.__code__.co_filename) + ':' + callee.__qualname__
            # revision 9, GAP-07: the stamp is named by its type only (<T>), never by name (X24c).
            raise GateSpecError(
                f"[V5:NOT_A_FUNCTION] declared target {target!r}: the wrapper calls {cname}; its "
                f"__wrapped__ names a different object (a {_TYPE_QUAL.__get__(type(stamped))}); "
                f"declare the function the wrapper calls")
        for k, v in md.items():
            if v is callee:
                raise GateSpecError(
                    f"[V5:NOT_A_FUNCTION] declared target {target!r}: the body is also bound as "
                    f"{mod_name}:{k}; declare that name")
        if holder is not None and holder is not md:
            for k, v in holder.items():
                if v is callee:
                    raise GateSpecError(
                        f"[V5:NOT_A_FUNCTION] declared target {target!r}: the body is also bound as "
                        f"{k}; declare that name")
        for ns in (md, holder):
            if ns is None:
                continue
            for k, w in ns.items():
                if w is not D and type(w) is _CACHE_WRAPPER and _cache_callee(w) is callee:
                    raise GateSpecError(
                        f"[V5:NOT_A_FUNCTION] declared target {target!r}: two cache wrappers call one "
                        f"body; declare '{target}.__wrapped__' to count every execution of the body")
        fn = callee
    else:
        raise GateSpecError(
            f"[V5:NOT_A_FUNCTION] declared target {target!r} resolves to "
            f"{_TYPE_QUAL.__get__(type(D))}: only Python functions, staticmethod/classmethod of "
            f"one, and C cache wrappers (through the function they call) can be observed; "
            f"partial, property, bound methods, builtins, class-based wrappers and mocks cannot")
    fc = fn.__code__                                 # step 5: reserved
    if (fn is _HANDLE_DICT[0].get('_run') or fn is _LOOP_DICT[0].get('_run_once')
            or _CUT.get(id(fc)) is fc):
        raise GateSpecError(
            f"[V5:RESERVED_TARGET] declared target {target!r}: asyncio's dispatch functions "
            f"(Handle._run, BaseEventLoop._run_once) and any function sharing their code are the "
            f"attribution cut and cannot be traced")
    _provenance(target, D, md)                       # step 6
    return D, fn


# -- the dispatch cut --------------------------------------------------------------------------

def _cut_ok():
    h = _HANDLE_DICT[0].get('_run')
    r = _LOOP_DICT[0].get('_run_once')
    return (type(h) is FunctionType and _CUT.get(id(h.__code__)) is h.__code__
            and type(r) is FunctionType and _CUT.get(id(r.__code__)) is r.__code__)


def _cut_refresh():
    """E2: both watched bindings must be plain functions; a code new to the cut must not be
    shareable; then it joins the monotone cut."""
    for label, x in (("asyncio.events.Handle._run", _HANDLE_DICT[0].get('_run')),
                     ("asyncio.base_events.BaseEventLoop._run_once",
                      _LOOP_DICT[0].get('_run_once'))):
        if type(x) is not FunctionType:
            raise GateSpecError(
                f"[V5:CUT_UNAVAILABLE] {label} is not a plain function (a "
                f"{_TYPE_QUAL.__get__(type(x))}): attribution cannot be cut at asyncio dispatch")
        c = x.__code__
        if _CUT.get(id(c)) is c:
            continue
        twins = [r for r in gc.get_referrers(c) if type(r) is FunctionType and r is not x]
        if '<locals>' in c.co_qualname or twins:
            raise GateSpecError(
                f"[V5:CUT_UNAVAILABLE] {label} is bound to {c.co_qualname}, whose code other "
                f"functions share; every function with that code would stop attribution for the "
                f"rest of the process. Bind a dedicated module-level function")
        _CUT.setdefault(id(c), c)


# -- the robust mutex (M2) ---------------------------------------------------------------------

def _txn():
    f = sys._getframe(1)
    return _Txn(threading.get_ident(), id(f), f.f_code)


def _alive(tok):
    if tok is None or tok.tid is None:
        return False
    f = sys._current_frames().get(tok.tid)
    while f is not None:
        if id(f) == tok.fid and f.f_code is tok.code and f.f_locals.get('me') is tok:
            return True
        f = f.f_back
    return False


def _acquire(me):
    t0 = None
    while True:
        r = _GUARD["hint"]
        n = r.succ.get("next")
        while n is not None:
            r = n
            n = r.succ.get("next")
        if _alive(r):
            if r.tid == me.tid:
                raise GateSpecError(
                    "[V5:REENTRANT] a coverage_trace enter or exit was re-entered on the same "
                    "thread from inside another enter or exit (a finalizer, audit hook or signal "
                    "handler)")
            now = _monotonic()
            if t0 is None:
                t0 = now
            elif now - t0 > _BUSY_SECONDS:
                raise GateSpecError(
                    "[V5:MACHINERY_BUSY] another thread has held styxx's machinery (the robust "
                    "mutex) for more than 10 s")
            _sleep(0.0002)
        elif r.succ.setdefault("next", me) is me:
            _GUARD["hint"] = me
            return


def _release(me):
    me.succ.setdefault("next", _Txn(None, 0, None))


def _locked(fn, *args):
    me = _txn(); _acquire(me); out = fn(*args); _release(me); return out   # no try/finally, by design


# -- the one-call steps (M7) -------------------------------------------------------------------

def _unwind_on(o):
    # ONE CALL { if get_tool(t) is _TOOL_NAME and _ANCHORS.get(o.frame) is o:
    #                if not (get_events(t) & PY_UNWIND):
    #                    for p in _ANCHORS.values(): if p.armed: p.core.flags['UNWIND_LOST'] = True
    #                set_events(t, PY_UNWIND) }
    t, get_tool, get_events, set_events = _TOOL[0], _MON[0][0], _MON[0][1], _MON[0][2]
    _CONSUME(_chain(
        _map(_setitem, _map(_FLAGS, _filter(_ARMED, _chain.from_iterable(_map(_VALUES,
            _compress(_compress(_compress((_ANCHORS,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                                _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),
                      _map(_not, _map(_and, _map(get_events, (t,)), _PYU1))))))), _LOST_KEY, _TRUE),
        _map(set_events,
             _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                       _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),
             _PYU1)))


def _unwind_off(key):
    # ONE CALL { _ANCHORS.pop(key, None); if get_tool(t) is _TOOL_NAME and not _ANCHORS: set_events(t, 0) }
    t, get_tool, set_events = _TOOL[0], _MON[0][0], _MON[0][2]
    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),
                    _map(set_events, _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                                               _map(_not, (_ANCHORS,))), _ZERO1)))


def _take(t):
    # ONE CALL { if get_tool(t) is None: use_tool_id(t, _TOOL_NAME) }
    get_tool, use_tool_id = _MON[0][0], _MON[0][5]
    _CONSUME(_map(use_tool_id, _compress((t,), _map(_is, _map(get_tool, (t,)), _NONE1)), _NAME1))


def _register(t):
    # NOT a one-call step (register_callback raises an audit event before each exchange). Each
    # exchange is gated on the name; a previous callback that is not styxx's is counted in _LOST in
    # the same C call; the tee buffer keeps every previous callback alive until the call returns.
    # Returns [None] * (count) + [owner].
    get_tool, register_callback = _MON[0][0], _MON[0][4]
    a, b = _tee(_map(register_callback,
                     _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
                     _EVENTS5, _CALLBACKS5))
    return _list(_chain(
        _map(_LOST_APPEND, _map(_is_not, _compress(a, _map(_is_not, b, _CALLBACKS5)), _repeat(None))),
        _map(get_tool, (t,))))


def _set_local(t, code, events):
    # ONE CALL { if get_tool(t) is _TOOL_NAME: set_local_events(t, code, events) }
    get_tool, set_local_events = _MON[0][0], _MON[0][3]
    _CONSUME(_map(set_local_events, _compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)), (code,), (events,)))


def _named(i): return _MON[0][0](i) is _TOOL_NAME


def _ours(): return _TOOL[0] is not None and _named(_TOOL[0])


# -- reconciliation (M3) -----------------------------------------------------------------------

def _reclaim():
    """Step 0: an id styxx holds in _TOOL[0] that was freed and is unowned is re-taken and counted."""
    t = _TOOL[0]
    if t is None or _MON[0][0](t) is not None:
        return
    _take(t)
    if not _named(t):
        return
    r = _register(t)
    if r[-1] is _TOOL_NAME:
        _LOST.append(True)


def _retire(m):
    if m.fn.__code__ is m.code:
        m.fn.__code__ = m.original
    _set_local(_TOOL[0], m.code, 0)
    m.pend.clear()
    if _BY_FN.get(m.fn) is m:
        _BY_FN.pop(m.fn, None)
    if _MINTED.get(id(m.code)) is m:
        _MINTED.pop(id(m.code), None)


def _prune(h):
    for o in list(h.openings):
        _detach(o, ("open", ("[V5:OPEN_AT_EXIT] pruned: the trace's own exit did not run",)))


def _reconcile():
    _reclaim()
    pid = os.getpid()
    ms = {}
    for m in list(_BY_FN.values()) + list(_MINTED.values()):
        ms[id(m)] = m
    for m in list(ms.values()):
        keep = []
        for h in m.holders:
            mk = h.marks
            if (h.facade() is None or 'exited' in mk or h.pid != pid
                    or ('exiting' in mk and not _alive(mk['exiting']))
                    or ('active' not in mk and not _alive(mk.get('entering')))):
                _prune(h)
            else:
                keep.append(h)
        m.holders = tuple(keep)
        if not keep:
            _retire(m)
    for fr, o in list(_ANCHORS.items()):             # prune cores reached from anchors (rev. 4, B1)
        c = o.core
        mk = c.marks
        if (c.facade() is None or 'exited' in mk or c.pid != pid
                or ('exiting' in mk and not _alive(mk['exiting']))
                or ('active' not in mk and not _alive(mk.get('entering')))):
            _prune(c)
            _unwind_off(fr)
    if _TOOL[0] is not None:
        _unwind_off(None)


# -- tool acquisition, minting, enter (M4) -----------------------------------------------------

def _ensure_tool():
    t = _TOOL[0]
    if t is not None:
        _reclaim()
        if _named(t):
            return
    for i in (4, 3):
        if not _named(i):
            _take(i)
        if _named(i):
            r = _register(i)
            if r[-1] is _TOOL_NAME:
                if _TOOL[0] is not None:             # a rebinding or a re-take: counted (rev. 6, 7)
                    _LOST.append(True)
                    for m in list(_MINTED.values()):
                        _set_local(i, m.code, _LOCAL)
                _TOOL[0] = i
                return
    raise GateSpecError(
        "[V5:MONITOR_BUSY] sys.monitoring tool ids 4 and 3 are both held by other tools (or by "
        "another loaded copy of styxx.protocol): styxx cannot trace alongside them")


def _mint(core, fn):
    m = _BY_FN.get(fn)
    if m is not None:                                # join: reconciliation left only live holders
        if fn.__code__ is not m.code:
            raise GateSpecError(
                f"[V5:CODE_SWAPPED] declared target {m.qualname}: an enclosing trace minted it and "
                f"its __code__ has since been replaced -- the trace cannot tell its calls apart")
        m.holders = m.holders + (core,)
        return m
    m = _Mint(fn)                                    # 1. pure
    m.holders = (core,)                              # 2. holder
    _MINTED[id(m.code)] = m                          # 3. register
    _BY_FN[fn] = m
    _set_local(_TOOL[0], m.code, _LOCAL)             # 4. local events, one gated call
    fn.__code__ = m.code                             # 5. install, last
    return m


def _enter_txn(core, resolved):
    _reconcile()                                     # E4.1
    _ensure_tool()                                   # E4.2
    for t, D, fn in resolved:                        # E4.3: entry CODE_SWAPPED, before any join
        m = _BY_FN.get(fn)
        if m is not None and fn.__code__ is not m.code:
            raise GateSpecError(
                f"[V5:CODE_SWAPPED] declared target {t!r}: an enclosing trace minted it and its "
                f"__code__ has since been replaced -- the trace cannot tell its calls apart")
    names = {}
    prov = {}
    done = {}
    for t, D, fn in resolved:                        # E4.4: join or mint, in the Minting order
        m = done.get(id(fn))
        if m is None:
            m = _mint(core, fn)
            done[id(fn)] = m
        names[id(m.code)] = names.get(id(m.code), ()) + (t,)
        prov[t] = f"{m.original.co_filename}:{m.original.co_firstlineno}"
    core.names = names                               # E4.5
    core.prov = prov
    core.lost0 = len(_LOST)
    core.by_code = dict(names)


def _enter(core):
    me = _txn()                                      # E0: the claim
    if core.marks.setdefault('entering', me) is not me:
        txt = ("[V5:REENTRY] this coverage_trace was already entered; a tracer is entered exactly "
               "once -- a retry or a nested use needs a new tracer")
        core.problems.append(txt)
        raise GateSpecError(txt)
    gil = getattr(sys, '_is_gil_enabled', None)      # E1: the M0 gate, read at call time
    vi = tuple(sys.version_info[:3])
    if not (sys.implementation.name == 'cpython' and vi in _VERIFIED
            and not sysconfig.get_config_var('Py_GIL_DISABLED') and (gil is None or gil())):
        raise GateSpecError(
            f"[V5:UNSUPPORTED_VERSION] {sys.implementation.name} {vi} is not a verified "
            f"interpreter: tracing runs only on CPython 3.12.3 and 3.13.12 GIL builds, the patch "
            f"levels on which styxx's atomicity premise was verified (verified: 3.12.3, 3.13.12); "
            f"run the G_ATOM probe on it. Scoring works on every version")
    _cut_refresh()                                   # E2
    resolved = []
    for t in core.exp.coverage_targets:              # E3: resolve everything, outside the mutex
        D, fn = _resolve_target(t)
        resolved.append((t, D, fn))
    first = {}
    for t, D, fn in resolved:                        # Resolution step 7: aliases by declared object
        p = first.setdefault(id(fn), (t, D))
        if p[1] is not D:
            raise GateSpecError(
                f"[V5:NOT_A_FUNCTION] declared targets {p[0]!r} and {t!r} reach one body through "
                f"different declared objects; declare the body once")
    _locked(_enter_txn, core, resolved)              # E4
    core.marks['active'] = True                      # E5, after the mutex is released


# -- exit (M5) ---------------------------------------------------------------------------------

def _clone_alive(m):
    excess = sys.getrefcount(m.code) - 2 - (m.fn.__code__ is m.code)
    if excess <= 0:
        return None
    code = m.code
    here = sys._getframe()
    refs = gc.get_referrers(code)
    fns = [r for r in refs if type(r) is FunctionType and r is not m.fn]
    if fns:
        return (f"[V5:CLONE_ALIVE] {len(fns)} live function(s) other than {m.qualname} hold its "
                f"minted code -- a clone built during the trace would be credited as it")
    if gc.get_freeze_count() > m.freeze0:
        visible = 0
        for r in refs:
            if r is m or r is m.fn or r is here or r is refs:
                continue
            for x in gc.get_referents(r):
                if x is code:
                    visible += 1
        if excess - visible > 0:
            return (f"[V5:CLONE_ALIVE] gc.freeze() ran while the minted code existed: "
                    f"{excess - visible} references to it cannot be attributed")
    return None


def _exit_txn(core):
    _reconcile()                                     # X5.1: this core's exiting token is live
    # GAP-19 (revision 9): held = the mints holding the core, from a list(_MINTED.values())
    # snapshot taken after step 1, in that order.
    held = [m for m in list(_MINTED.values()) if [h for h in m.holders if h is core]]
    t = _TOOL[0]
    r = _register(t)                                 # X5.2: registration first (revision 6 order)
    lost = r[-1] is not _TOOL_NAME
    if not lost:
        if len(_LOST) != core.lost0:
            lost = True
        gle = _MON[0][6]                             # C3 (GAP-03): the bound get_local_events
        for m in held:
            if gle(t, m.code) != _LOCAL:
                lost = True
        if 'UNWIND_LOST' in core.flags:
            lost = True
    swapped = []
    for m in held:                                   # X5.3, in held order
        if m.fn.__code__ is not m.code:
            swapped.append(
                f"[V5:CODE_SWAPPED] {m.qualname}.__code__ was replaced during the trace -- calls "
                f"through the replacement were not observed")
        m.holders = tuple([h for h in m.holders if h is not core])
        if not m.holders:
            _retire(m)
    return held, (swapped, lost)                     # GAP-19: (held, (swapped, lost))


def _exit(core):
    if core.pid != os.getpid():                      # X-1: an inherited tracer is inert
        return
    if 'active' not in core.marks:                   # X0
        try:
            _locked(_reconcile)
        except GateSpecError:
            pass
        return
    me = _txn()                                      # X1: the claim
    if core.marks.setdefault('exiting', me) is not me:
        return
    core.by_code = {}                                # X2: credit stop, one store
    for o in list(core.openings):                    # X3
        _detach(o, ("open", (f"[V5:OPEN_AT_EXIT] section {o.section!r} was still open when the "
                             f"trace exited; only calls confirmed before the exit count",)))
    probs = []                                       # X4
    for cid, q in list(dict(core.clone_called).items()):
        probs.append(f"[V5:CLONE_CALLED] the minted code of {q} ran under globals that are not its "
                     f"function's: a function was built from its code object, or it was exec'd")
    # X5 (GAP-19): on a GateSpecError from _locked, held = [], swapped = [], lost = False. The
    # order of probs: X4's CLONE_CALLED texts; the _locked error or the swapped texts; X6.
    held, swapped, lost = [], [], False
    try:                                             # X5
        held, (swapped, lost) = _locked(_exit_txn, core)
    except GateSpecError as e:
        probs.append(str(e))
    else:
        probs.extend(swapped)
    for m in held:                                   # X6: tripwires, outside the mutex, held order
        txt = _clone_alive(m)
        if txt is not None:
            probs.append(txt)
    if 'CUT_MOVED' in core.flags or not _cut_ok():
        probs.append(
            "[V5:CUT_MOVED] asyncio.events.Handle._run or asyncio.base_events.BaseEventLoop."
            "_run_once was rebound, or its code replaced, while this trace saw it: dispatch through "
            "the moved binding is not cut")
    core.problems.extend(probs)                      # X7
    if lost:
        core.lost_note = ("[V5:MONITOR_LOST] styxx's sys.monitoring tool id lost events or callbacks "
                          "during this trace (freed, taken, cleared or replaced by another party); "
                          "counts are lower bounds")
    core.marks['exited'] = True                      # X8


# -- the event path (M6) -----------------------------------------------------------------------

def _outcome(f, code, holders, tid):
    loop = _get_running_loop()
    found = []
    cut = False
    g = f.f_back
    while g is not None:
        c = g.f_code
        if _CUT.get(id(c)) is c:
            cut = True
            break
        o = _ANCHORS.get(g)
        if o is not None:
            if o.loop is not loop:                   # the loop boundary ends the walk as a cut does
                cut = True
                break
            found.append(o)
        g = g.f_back
    out = []
    k = id(code)
    for h in holders:
        if k in h.by_code:
            mine = [o for o in found if o.core is h]
            if len(mine) == 1:
                out.append((h, 'c', mine[0]))
            elif mine:
                out.append((h, 'a', tuple(mine)))
            elif cut:
                out.append((h, 'd', tid))
            else:
                out.append((h, 'u', tid))
    return out


def _publish(code, out):
    k = id(code)
    for h, kind, x in out:
        if k in h.by_code:
            if kind == 'c':
                x.calls[k] = x.calls.get(k, 0) + 1
            elif kind == 'a':
                for o in x:
                    o.ambiguous[k] = o.ambiguous.get(k, 0) + 1
            else:
                u = h.uncredited.get(x)
                if u is None:
                    u = h.uncredited.setdefault(x, ({}, {}))
                d = u[0] if kind == 'd' else u[1]
                d[k] = d.get(k, 0) + 1


def _on_entry(code, offset):                        # PY_START, PY_RESUME (local, minted code only)
    m = _MINTED.get(id(code))
    if m is None or m.code is not code: return
    f = sys._getframe(1)
    holders = m.holders
    if not _cut_ok():                               # CUT_MOVED: a moved binding seen at a hit
        for h in holders: h.flags['CUT_MOVED'] = True
    if f.f_globals is not m.globals:                # CLONE_CALLED: credits nothing
        for h in holders: h.clone_called[id(code)] = m.qualname
        return
    if not _ANCHORS: return                         # no section open anywhere: store nothing
    out = _outcome(f, code, holders, threading.get_ident())
    if out: m.pend[id(f)] = (f, offset, out)        # pending: the only store


def _on_exit(code, offset, value):                  # PY_RETURN, PY_YIELD (local)
    m = _MINTED.get(id(code))
    if m is None or m.code is not code: return
    f = sys._getframe(1); p = m.pend.pop(id(f), None)
    if p is not None and p[0] is f: _publish(code, p[2])


def _on_unwind(code, offset, exc):                  # PY_UNWIND (global, only while a section is open)
    m = _MINTED.get(id(code))
    if m is None or m.code is not code: return
    f = sys._getframe(1); p = m.pend.pop(id(f), None)
    if p is not None and p[0] is f and offset != p[1]: _publish(code, p[2])


_CALLBACKS5 = (_on_entry, _on_entry, _on_exit, _on_exit, _on_unwind)   # data, never called in a step


# -- sections (M7) -----------------------------------------------------------------------------

def _lazy_text(result):
    t = type(result)
    if t is GeneratorType:
        fresh = result.gi_frame is not None and not result.gi_running and not result.gi_suspended
    elif t is CoroutineType:
        fresh = result.cr_frame is not None and not result.cr_running and not result.cr_suspended
    else:
        fresh = result.ag_frame is not None and not result.ag_running and not result.ag_suspended
    return (f"[V5:LAZY_RESULT] fn returned a {_TYPE_QUAL.__get__(t)}; whatever of its body runs "
            f"after the section closed does not count" + (" (its body had not started)" if fresh else ""))


def _open(core, section, fr):
    if core.pid != os.getpid():                      # 1. pass-through in a forked child
        return None
    mk = core.marks
    if 'active' not in mk or 'exiting' in mk:        # 2.
        shown = repr(section) if type(section) is str else "of type " + _TYPE_QUAL.__get__(type(section))
        txt = (f"[V5:TRACE_INACTIVE] section {shown}: the trace is not active (it was never "
               f"entered, or its exit has begun)")
        core.problems.append(txt)
        raise GateSpecError(txt)
    if type(section) is not str:                     # 3. section type
        if issubclass(type(section), str):
            section = str.__str__(section)
        else:
            txt = (f"[V5:UNDECLARED_SECTION] a section of type "
                   f"{_TYPE_QUAL.__get__(type(section))} is not a str; sections are declared as "
                   f"strings (declared: {list(core.sections)})")
            core.problems.append(txt)
            raise GateSpecError(txt)
    if section not in core.sections:                 # 4.
        txt = (f"[V5:UNDECLARED_SECTION] section {section!r} is not declared by any gate "
               f"(declared: {list(core.sections)})")
        core.problems.append(txt)
        raise GateSpecError(txt)
    loop = _get_running_loop()                       # 5. read once, after steps 1-4
    g = fr.f_back
    while g is not None:
        c = g.f_code
        if _CUT.get(id(c)) is c:
            break
        p = _ANCHORS.get(g)
        if p is not None and p.core is core and p.loop is loop:
            if p.section == section:
                txt = (f"[V5:NESTED_SECTION] section {section!r} opened on the stack of an open "
                       f"opening of the same section of the same trace -- a call there would be on "
                       f"the stack of two openings of section {section!r}")
            else:
                txt = (f"[V5:NESTED_SECTION] section {section!r} opened on the stack of an open "
                       f"opening of section {p.section!r} of the same trace -- one call would count "
                       f"for both sections {p.section!r} and {section!r}")
            core.problems.append(txt)
            raise GateSpecError(txt)
        g = g.f_back
    o = _Opening(core, section, fr, threading.get_ident(), loop)   # 6. append
    core.openings.append(o)
    return o


def _commit(o):                                     # At open, steps 7-8 (revision 5 order)
    _ANCHORS[o.frame] = o                           # the store
    if 'fin' in o.fin or 'exiting' in o.core.marks:  # step 8: a detacher claimed o, or exit began
        _detach(o, ("open", (f"[V5:OPEN_AT_EXIT] section {o.section!r} was still open when the "
                             f"trace exited; only calls confirmed before the exit count",)))
        txt = (f"[V5:TRACE_INACTIVE] section {o.section!r}: the trace's exit began while this "
               f"section was opening")
        o.core.problems.append(txt)
        raise GateSpecError(txt)
    _unwind_on(o)                                   # one call, after the store
    o.armed = True                                  # last: the body may run now


def _detach(o, fin):
    o.fin.setdefault("fin", fin)                    # one claim: first finaliser wins
    fr = o.frame                                    # never assigned here
    if fr is not None:
        if o.armed and not (_MON[0][1](_TOOL[0]) & PY_UNWIND) and _ANCHORS.get(fr) is o:
            o.core.flags['UNWIND_LOST'] = True      # the event first, the anchor last
        _unwind_off(fr)                             # one call: pop, then clear iff no anchor is left


def _run(core, section, fn, args, kwargs):          # module level: its frame is the anchor
    o = _open(core, section, sys._getframe())
    if o is None: return fn(*args, **kwargs)        # forked child: pass-through
    end = "raised"
    try:
        _commit(o)
        result = fn(*args, **kwargs); end = "returned"
    finally:
        _detach(o, (end, ()))
        o.frame = None
    t = type(result)                                # `is` chain, never `in`
    if t is GeneratorType or t is CoroutineType or t is AsyncGeneratorType: o.lazy = _lazy_text(result)
    return result


async def _run_async(core, section, afn, args, kwargs):   # the coroutine frame is the anchor
    o = _open(core, section, sys._getframe())
    if o is None: return await afn(*args, **kwargs)
    end = "raised"
    try:
        _commit(o)
        result = await afn(*args, **kwargs); end = "returned"
    finally:
        _detach(o, (end, ()))
        o.frame = None
    return result


# -- the facade --------------------------------------------------------------------------------

class _CoverageTracer:
    """One trace (a thin facade over its _Core). Built only by coverage_trace()."""

    def __enter__(self):
        _enter(self._core)
        return self

    def __exit__(self, exc_type, exc, tb):
        _exit(self._core)
        return False

    def run(self, section, fn, /, *args, **kwargs):
        """Open *section*, call fn(*args, **kwargs) from _run's frame, close it on return and raise."""
        return _run(self._core, section, fn, args, kwargs)

    def run_async(self, section, afn, /, *args, **kwargs):
        """The coroutine form: _run_async's coroutine frame is the anchor. A plain def (M1)."""
        return _run_async(self._core, section, afn, args, kwargs)

    def record(self):
        """The trace to store under ``coverage_trace``, taken after the trace exits (M8)."""
        core = self._core
        if core.pid != os.getpid():
            raise GateSpecError(
                "[V5:TRACE_INCOMPLETE] inherited across fork: the record belongs to the parent "
                "process")
        mk = core.marks
        if 'exited' not in mk:
            if 'exiting' in mk or ('entering' in mk and 'active' not in mk):
                raise GateSpecError(
                    "[V5:TRACE_INCOMPLETE] the trace's enter or exit began and did not complete, so "
                    "its checks and its restorations did not all run")
            if 'entering' not in mk:
                raise GateSpecError("[V5:TRACE_ACTIVE] the tracer was never entered")
            raise GateSpecError(
                "[V5:TRACE_ACTIVE] the tracer is active: record() was called inside its with-block, "
                "or its __exit__ never started, and then one call of __exit__() completes it")
        names = core.names
        sections = {}
        for o in list(core.openings):
            end, notes = o.fin.get("fin", ("open", ()))
            notes = list(notes)
            if o.lazy is not None:
                notes.append(o.lazy)
            if core.lost_note is not None:
                notes.append(core.lost_note)
            calls = {}
            for k, n in list(o.calls.items()):
                for nm in names.get(k, ()):
                    calls[nm] = calls.get(nm, 0) + n
            amb = {}
            for k, n in list(o.ambiguous.items()):
                for nm in names.get(k, ()):
                    amb[nm] = amb.get(nm, 0) + n
            sections.setdefault(o.section, []).append({
                "calls": dict(sorted(calls.items())), "ambiguous": dict(sorted(amb.items())),
                "end": end, "notes": notes})
        disp = {}
        unat = {}
        for a, b in list(core.uncredited.values()):
            for k, n in list(a.items()):
                for nm in names.get(k, ()):
                    disp[nm] = disp.get(nm, 0) + n
            for k, n in list(b.items()):
                for nm in names.get(k, ()):
                    unat[nm] = unat.get(nm, 0) + n
        return {"tracer": _TRACER_ID, "gates_sha256": core.exp.gates_sha256,
                "targets": dict(sorted(core.prov.items())),
                "sections": dict(sorted(sections.items())),
                "uncredited": {"dispatched": dict(sorted(disp.items())),
                               "unattributed": dict(sorted(unat.items()))},
                "problems": list(core.problems)}


def coverage_trace(experiment: "Experiment") -> _CoverageTracer:
    """Trace a harness against the targets its frozen prereg declares (protocol v5f).

    ::

        exp = Experiment("PREREG_x.md")
        with coverage_trace(exp) as cov:
            res["degenerate_refusal_rate"] = cov.run("G4_refuses_degenerate", battery)
        res["coverage_trace"] = cov.record()
        exp.score(res)

    Tracing runs on the verified interpreters only (CPython 3.12.3 and 3.13.12, GIL builds);
    scoring works on every version. Sections are calls (``cov.run`` / ``await cov.run_async``).
    """
    gil = getattr(sys, '_is_gil_enabled', None)      # M0, read at call time (revision 9, GAP-04: no lambda)
    vi = tuple(sys.version_info[:3])
    if not (sys.implementation.name == 'cpython' and vi in _VERIFIED
            and not sysconfig.get_config_var('Py_GIL_DISABLED') and (gil is None or gil())):
        raise GateSpecError(
            f"[V5:UNSUPPORTED_VERSION] {sys.implementation.name} {vi} is not a verified "
            f"interpreter: tracing runs only on CPython 3.12.3 and 3.13.12 GIL builds, the patch "
            f"levels on which styxx's atomicity premise was verified (verified: 3.12.3, 3.13.12); "
            f"run the G_ATOM probe on it. Scoring works on every version")
    if not isinstance(experiment, Experiment):
        raise TypeError("coverage_trace() takes the Experiment whose frozen gates block "
                        "declares the targets -- never a caller-supplied list")
    if not experiment.coverage_targets:
        raise GateSpecError(
            "[V5:NOTHING_DECLARED] no gate in this prereg declares 'exercises' -- a coverage "
            "trace with nothing declared would record nothing and could be mistaken for a check "
            "that passed")
    # M0 binding check, at every coverage_trace(): _MON as bound (or sys.monitoring's functions,
    # before the first binding), and the one-call vocabulary as the module binds it now.
    sm = sys.monitoring
    mon = _MON[0]
    if mon is None:                                  # C1 (GAP-03): seven functions
        mon = (sm.get_tool, sm.get_events, sm.set_events, sm.set_local_events,
               sm.register_callback, sm.use_tool_id, sm.get_local_events)
    bad = None
    i = 0
    for nm in ("get_tool", "get_events", "set_events", "set_local_events", "register_callback",
               "use_tool_id", "get_local_events"):
        f = mon[i]
        i += 1
        if not (type(f) is BuiltinFunctionType and f.__self__ is sm and f.__name__ == nm):
            bad = "sys.monitoring." + nm
            break
    g = globals()
    opmod = sys.modules.get("_operator")
    if bad is None:
        for nm, x, modn, qn in (("builtins.map", g.get("_map"), "builtins", "map"),
                                ("builtins.filter", g.get("_filter"), "builtins", "filter"),
                                ("builtins.list", g.get("_list"), "builtins", "list"),
                                ("itertools.chain", g.get("_chain"), "itertools", "chain"),
                                ("itertools.compress", g.get("_compress"), "itertools", "compress"),
                                ("itertools.repeat", g.get("_repeat"), "itertools", "repeat"),
                                ("operator.attrgetter", type(g.get("_ARMED")), "operator", "attrgetter"),
                                ("operator.attrgetter", type(g.get("_FLAGS")), "operator", "attrgetter")):
            if not (type(x) is type and x.__flags__ & (1 << 8) and x.__module__ == modn
                    and x.__qualname__ == qn):
                bad = nm
                break
    if bad is None:
        for nm, x, fname in (("operator.is_", g.get("_is"), "is_"),
                             ("operator.not_", g.get("_not"), "not_"),
                             ("operator.and_", g.get("_and"), "and_"),
                             ("operator.setitem", g.get("_setitem"), "setitem"),
                             ("operator.is_not", g.get("_is_not"), "is_not")):
            if not (type(x) is BuiltinFunctionType and x.__self__ is opmod and x.__name__ == fname):
                bad = nm
                break
    if bad is None:
        x = g.get("_tee")
        if not (type(x) is BuiltinFunctionType and x.__name__ == "tee"
                and x.__self__ is sys.modules.get("itertools")):
            bad = "itertools.tee"
    if bad is None:
        x = g.get("_LOST_APPEND")
        if not (type(x) is BuiltinFunctionType and x.__name__ == "append"
                and x.__self__ is _LOST and type(_LOST) is list):
            bad = "_LOST.append"
    if bad is None:
        x = g.get("_CONSUME")
        dq = type(x.__self__) if type(x) is BuiltinFunctionType else None
        if not (type(x) is BuiltinFunctionType and x.__name__ == "extend" and type(dq) is type
                and dq.__flags__ & (1 << 8) and dq.__module__ == "collections"
                and dq.__qualname__ == "deque" and x.__self__.maxlen == 0):
            bad = "collections.deque"
    if bad is None:
        x = g.get("_VALUES")
        if not (type(x) is MethodDescriptorType and x.__objclass__ is dict
                and x.__name__ == "values"):
            bad = "dict.values"
    if bad is not None:
        raise GateSpecError(
            f"[V5:UNSUPPORTED_VERSION] {bad} is not the C builtin (a wrapper or subclass was "
            f"installed before this coverage_trace()): styxx's one-call steps must call C "
            f"functions only")
    import asyncio                                   # M0 step 5 (GAP-09)
    grl = asyncio.events._get_running_loop           # C2 (GAP-02), M0 step 6: read afresh, checked
    if not (type(grl) is BuiltinFunctionType and grl.__name__ == "_get_running_loop"
            and grl.__self__ is sys.modules.get("_asyncio")):
        raise GateSpecError(
            "[V5:UNSUPPORTED_VERSION] asyncio.events._get_running_loop is not the C builtin (a "
            "wrapper or subclass was installed before this coverage_trace()): styxx's one-call "
            "steps must call C functions only")
    if _MON[0] is None:                              # M0 step 7: only now, every check passed
        _MON[0] = mon
    global _get_running_loop
    _get_running_loop = grl
    if _HANDLE_DICT[0] is None:                      # read by the first coverage_trace(), never again
        _HANDLE_DICT[0] = _TYPE_DICT.__get__(asyncio.events.Handle)
        _LOOP_DICT[0] = _TYPE_DICT.__get__(asyncio.base_events.BaseEventLoop)
    _cut_refresh()                                   # E2: the constructor runs it too
    fac = _CoverageTracer.__new__(_CoverageTracer)   # M0 step 10: no facade __init__ (revision 9, GAP-08)
    fac._core = _Core(experiment, weakref.ref(fac))
    return fac


# -- introspection (M10) -----------------------------------------------------------------------

def _v5_state():
    t = _TOOL[0]
    mon = _MON[0]
    rows = []
    for m in list(_MINTED.values()):
        le = mon[6](t, m.code) if (t is not None and mon is not None) else 0   # C3 (GAP-03)
        rows.append((m.qualname, len(m.holders), m.fn.__code__ is m.code, le, len(m.pend)))
    rows.sort()
    r = _GUARD["hint"]
    n = r.succ.get("next")
    while n is not None:
        r = n
        n = r.succ.get("next")
    return {
        "mints": [{"target": a, "holders": b, "installed": c, "local_events": d, "pending": e}
                  for a, b, c, d, e in rows],
        "anchors": len(_ANCHORS),
        "guard": "free" if r.tid is None else ("held" if _alive(r) else "dead"),
        "cut": len(_CUT),
        "cut_current": _HANDLE_DICT[0] is None or _cut_ok(),        # revision 9, GAP-05
        "tool": t,
        "tool_ours": mon is not None and _ours(),
        "global_events": mon[1](t) if (t is not None and mon is not None) else 0,
        "pid": os.getpid(),
    }


def _v5_faultpoints():
    ct = _CoverageTracer.__dict__
    return {
        "coverage_trace": coverage_trace.__code__,
        "_CoverageTracer.__enter__": ct["__enter__"].__code__,
        "_CoverageTracer.__exit__": ct["__exit__"].__code__,
        "_CoverageTracer.run": ct["run"].__code__,
        "_CoverageTracer.run_async": ct["run_async"].__code__,
        "_CoverageTracer.record": ct["record"].__code__,
        "_enter": _enter.__code__, "_exit": _exit.__code__, "_enter_txn": _enter_txn.__code__,
        "_exit_txn": _exit_txn.__code__, "_resolve_target": _resolve_target.__code__,
        "_own_dict": _own_dict.__code__, "_cache_callee": _cache_callee.__code__,
        "_provenance": _provenance.__code__, "_ensure_tool": _ensure_tool.__code__,
        "_mint": _mint.__code__, "_retire": _retire.__code__, "_reconcile": _reconcile.__code__,
        "_prune": _prune.__code__, "_locked": _locked.__code__, "_acquire": _acquire.__code__,
        "_release": _release.__code__, "_txn": _txn.__code__, "_alive": _alive.__code__,
        "_open": _open.__code__, "_commit": _commit.__code__, "_detach": _detach.__code__,
        "_run": _run.__code__, "_run_async": _run_async.__code__, "_lazy_text": _lazy_text.__code__,
        "_cut_ok": _cut_ok.__code__, "_cut_refresh": _cut_refresh.__code__,
        "_reclaim": _reclaim.__code__, "_take": _take.__code__, "_register": _register.__code__,
        "_set_local": _set_local.__code__, "_unwind_on": _unwind_on.__code__,
        "_unwind_off": _unwind_off.__code__, "_ours": _ours.__code__, "_named": _named.__code__,
        "_clone_alive": _clone_alive.__code__, "_on_entry": _on_entry.__code__,
        "_on_exit": _on_exit.__code__, "_on_unwind": _on_unwind.__code__,
        "_outcome": _outcome.__code__, "_publish": _publish.__code__,
        "_forget_in_child": _forget_in_child.__code__, "_v5_state": _v5_state.__code__,
        "_v5_faultpoints": _v5_faultpoints.__code__,
    }


# -- the at-fork handler (M9) ------------------------------------------------------------------

def _forget_in_child():
    if _MON[0] is None:                              # a no-op until a tracer has been constructed
        return
    _GUARD["hint"] = _Txn(None, 0, None)             # 1.
    _ANCHORS.clear()                                 # 2.
    t = _TOOL[0]
    ours = t is not None and _named(t)
    if ours:
        _MON[0][2](t, 0)                             # 3.
    ms = list(_MINTED.values())
    for m in ms:                                     # 4.
        if ours:
            _MON[0][3](t, m.code, 0)
        m.pend.clear()
    _BY_FN.clear()                                   # 5.
    _MINTED.clear()
    for m in ms:                                     # 6. last: the only step that runs user code
        if m.fn.__code__ is m.code:
            m.fn.__code__ = m.original


def _finite(v):
    """M11: math.isfinite, catching OverflowError only (an int too large for a float). One of the SM2 region's scoring functions (revision 9, GAP-08)."""
    try:
        return math.isfinite(v)
    except OverflowError:
        return False


def _check_trace_shape(name: str, tr: dict) -> None:
    """BAD_TRACE, in one pass before anything is read. The exact type of every key, end, note,
    problem and gates_sha256 is tested before any hash, membership or comparison (M11)."""
    for k in tr:
        if type(k) is not str:
            raise GateSpecError(f"[V5:BAD_TRACE] gate {name!r}: the trace has a non-str key")
    if set(tr) != _TRACE_KEYS:
        raise GateSpecError(
            f"[V5:BAD_TRACE] gate {name!r}: the trace's keys are {sorted(tr)}, not exactly "
            f"{sorted(_TRACE_KEYS)}")
    if type(tr["gates_sha256"]) is not str:
        raise GateSpecError(f"[V5:BAD_TRACE] gate {name!r}: gates_sha256 must be a str")
    tg = tr["targets"]
    if type(tg) is not dict:
        raise GateSpecError(f"[V5:BAD_TRACE] gate {name!r}: targets must be a dict of str to str")
    for k, v in tg.items():
        if type(k) is not str or type(v) is not str:
            raise GateSpecError(f"[V5:BAD_TRACE] gate {name!r}: targets must be a dict of str to str")
    secs = tr["sections"]
    if type(secs) is not dict:
        raise GateSpecError(f"[V5:BAD_TRACE] gate {name!r}: sections must be a dict with str keys")
    for s, ops in secs.items():
        if type(s) is not str:
            raise GateSpecError(f"[V5:BAD_TRACE] gate {name!r}: sections must be a dict with str keys")
        if type(ops) is not list or not ops:
            raise GateSpecError(
                f"[V5:BAD_TRACE] gate {name!r}: section {s!r} must be a non-empty list of openings")
        for o in ops:
            if type(o) is not dict:
                raise GateSpecError(
                    f"[V5:BAD_TRACE] gate {name!r}: an opening of {s!r} must be a dict with exactly "
                    f"{sorted(_OPENING_KEYS)}")
            for k in o:
                if type(k) is not str:
                    raise GateSpecError(
                        f"[V5:BAD_TRACE] gate {name!r}: an opening of {s!r} has a non-str key")
            if set(o) != _OPENING_KEYS:
                raise GateSpecError(
                    f"[V5:BAD_TRACE] gate {name!r}: an opening of {s!r} must be a dict with exactly "
                    f"{sorted(_OPENING_KEYS)}")
            end = o["end"]
            if type(end) is not str or end not in _ENDS:
                raise GateSpecError(
                    f"[V5:BAD_TRACE] gate {name!r}: an opening of {s!r} has an end that is not one "
                    f"of {sorted(_ENDS)}")
            notes = o["notes"]
            if type(notes) is not list:
                raise GateSpecError(
                    f"[V5:BAD_TRACE] gate {name!r}: an opening of {s!r} has notes that are not a list")
            for n in notes:
                mt = _CODE_RE.match(n) if type(n) is str else None
                if mt is None or mt.group(1) not in _NOTE_CODES:
                    raise GateSpecError(
                        f"[V5:BAD_TRACE] gate {name!r}: an opening of {s!r} has a note that is not a "
                        f"str beginning with a known note code")
            for kk in ("calls", "ambiguous"):
                d = o[kk]
                if type(d) is not dict:
                    raise GateSpecError(
                        f"[V5:BAD_TRACE] gate {name!r}: an opening's {kk} must be a dict with str keys")
                for t in d:
                    if type(t) is not str:
                        raise GateSpecError(
                            f"[V5:BAD_TRACE] gate {name!r}: an opening's {kk} must be a dict with "
                            f"str keys")
    un = tr["uncredited"]
    if type(un) is not dict:
        raise GateSpecError(
            f"[V5:BAD_TRACE] gate {name!r}: uncredited must be a dict of exactly dispatched and "
            f"unattributed, each a dict with str keys")
    for k, d in un.items():
        if type(k) is not str or type(d) is not dict:
            raise GateSpecError(
                f"[V5:BAD_TRACE] gate {name!r}: uncredited must be a dict of exactly dispatched and "
                f"unattributed, each a dict with str keys")
        for t in d:
            if type(t) is not str:
                raise GateSpecError(
                    f"[V5:BAD_TRACE] gate {name!r}: uncredited must be a dict of exactly dispatched "
                    f"and unattributed, each a dict with str keys")
    if set(un) != _UNCREDITED_KEYS:
        raise GateSpecError(
            f"[V5:BAD_TRACE] gate {name!r}: uncredited must be a dict of exactly dispatched and "
            f"unattributed, each a dict with str keys")
    pr = tr["problems"]
    if type(pr) is not list:
        raise GateSpecError(
            f"[V5:BAD_TRACE] gate {name!r}: problems must be a list of str, each beginning with a "
            f"known recorded code")
    for p in pr:
        mt = _CODE_RE.match(p) if type(p) is str else None
        if mt is None or mt.group(1) not in _RECORDED_CODES:
            raise GateSpecError(
                f"[V5:BAD_TRACE] gate {name!r}: problems must be a list of str, each beginning with "
                f"a known recorded code")


if hasattr(os, "register_at_fork"):                 # M9: registered at import on every version
    os.register_at_fork(after_in_child=_forget_in_child)
