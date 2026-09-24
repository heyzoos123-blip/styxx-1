# -*- coding: utf-8 -*-
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

import contextlib
import hashlib
import importlib
import inspect
import marshal
import math
import json
import numbers
import re
import subprocess
import sys
import threading
import types
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Experiment", "Verdict", "PrologueError", "GateSpecError",
           "undeclared_power_gates", "coverage_trace"]


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
_TARGET_RE = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*:[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$",
                        re.ASCII)
_TRACE_KEY = "coverage_trace"
_TRACER_ID = "styxx.protocol.coverage_trace/1"

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
                    f"gate {n!r}: 'section' without 'exercises' declares a place and nothing to "
                    f"find in it — half a declaration checks nothing while looking like a check")
            ex = g["exercises"]
            if not isinstance(ex, list) or not ex:
                raise GateSpecError(
                    f"gate {n!r}: 'exercises' must be a non-empty list of \"module:qualname\" "
                    f"strings, got {ex!r}. An empty declaration would pass every harness.")
            bad = [t for t in ex if not isinstance(t, str) or not _TARGET_RE.match(t)]
            if bad:
                raise GateSpecError(
                    f"gate {n!r}: 'exercises' entries must be ASCII \"module:qualname\" strings "
                    f"(e.g. \"styxx.power:reachable\"); refused {bad!r}")
            if len(set(ex)) != len(ex):
                raise GateSpecError(f"gate {n!r}: 'exercises' names a target twice: {ex!r}")
            sec = g.get("section", n)
            if not isinstance(sec, str) or not sec or not sec.isascii():
                raise GateSpecError(
                    f"gate {n!r}: 'section' must be a non-empty ASCII string, got {sec!r}")
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

        Call this before launching a run. ``_resolve`` already raises on a missing path, but only
        at scoring time — after the compute is spent. B49 lost a whole re-analysis to a gate whose
        path resolved to a real but *wrong* field; this catches the cheaper cousin (a path that is
        simply absent) for the cost of one call.

        **It cannot catch B49's actual error.** A path that resolves to an existing field the
        author did not intend is indistinguishable from a correct one, because the machinery has
        no access to intent. ``metric_means`` records that intent for a human reader; it is not a
        check and must not be read as one.
        """
        import math
        out = {}
        smoke = bool(result.get("smoke"))
        for name, path in self.metric_paths.items():
            try:
                val = _resolve(result, path)
            except GateSpecError:
                out[name] = {"path": path, "present": False, "usable": False,
                             "note": ("result is a smoke run; smoke scores by type and never "
                                      "reads gate metrics" if smoke else "path not in result")}
                continue
            usable = isinstance(val, (int, float)) and not isinstance(val, bool)                 and math.isfinite(val)
            out[name] = {"path": path, "present": True, "usable": usable,
                         "note": None if usable else
                         f"resolves to {type(val).__name__}"
                         f"{' (NaN/inf)' if isinstance(val, float) else ''} — score() cannot "
                         f"compare it"}
        # v4 composition paths get the same pre-run resolution (red team D4: the pre-run safety
        # tool previously passed a result whose 'over' path was absent, and score() then refused
        # after the compute was spent — the exact failure mode this method exists to prevent).
        for name, c in self.composition.items():
            for kind in ("over", "excluding"):
                if kind not in c:
                    continue
                key = f"{name}:{kind}"
                try:
                    val = _resolve(result, c[kind])
                except GateSpecError:
                    out[key] = {"path": c[kind], "present": False, "usable": False,
                                "note": ("smoke run" if smoke else
                                         f"composition path ({kind}) not in result")}
                    continue
                want = dict if kind == "over" else list
                ok = isinstance(val, want) and (bool(val) if kind == "over" else True)
                out[key] = {"path": c[kind], "present": True, "usable": ok,
                            "note": None if ok else
                            f"composition path ({kind}) resolves to {type(val).__name__}; "
                            f"score() will refuse it"}
        # v5 coverage gets the same pre-scoring check: a harness that forgot a section learns it
        # here, with the reason, rather than as a refusal from score().
        for name in self.coverage:
            key = f"{name}:exercises"
            try:
                self._check_coverage(name, result)
                out[key] = {"path": _TRACE_KEY, "present": True, "usable": True, "note": None}
            except GateSpecError as e:
                out[key] = {"path": _TRACE_KEY, "present": isinstance(result.get(_TRACE_KEY), dict),
                            "usable": False, "note": "smoke run" if smoke else str(e)}
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
        """Refuse a declaring gate unless the trace shows every declared target called in its
        section. Returns {target: calls} for the gate. Everything ill-formed refuses: a trace that
        can be half-read is a trace that can be half-forged.
        """
        c = self.coverage[name]
        tr = result.get(_TRACE_KEY) if isinstance(result, dict) else None
        if not isinstance(tr, dict):
            raise GateSpecError(
                f"gate {name!r} declares 'exercises' but the result carries no "
                f"{_TRACE_KEY!r} — run the harness inside styxx.protocol.coverage_trace() and "
                f"store its record(). A declared coverage with no trace is unverified, not met.")
        if tr.get("tracer") != _TRACER_ID:
            raise GateSpecError(
                f"gate {name!r}: {_TRACE_KEY}.tracer is {tr.get('tracer')!r}, not "
                f"{_TRACER_ID!r} — this trace was not written by the machinery that can be read")
        if tr.get("gates_sha256") != self.gates_sha256:
            raise GateSpecError(
                f"gate {name!r}: the coverage trace was taken against gates block "
                f"{str(tr.get('gates_sha256'))[:12]}…, not this one ({self.gates_sha256[:12]}…). "
                f"A trace of a different declaration is not evidence about this one.")
        targets = tr.get("targets")
        if not isinstance(targets, dict) or sorted(targets) != self.coverage_targets:
            raise GateSpecError(
                f"gate {name!r}: the trace's target set "
                f"{sorted(targets) if isinstance(targets, dict) else targets!r} differs from the "
                f"declared set {self.coverage_targets} — it recorded something other than what "
                f"the frozen document asks about")
        sections = tr.get("sections")
        if not isinstance(sections, dict):
            raise GateSpecError(f"gate {name!r}: {_TRACE_KEY}.sections is not a dict")
        sec = sections.get(c["section"])
        if not isinstance(sec, dict):
            raise GateSpecError(
                f"gate {name!r}: section {c['section']!r} is absent from the trace — the "
                f"harness never opened it, so nothing it ran can be attributed to this gate")
        for t, n in sec.items():
            if t not in targets or isinstance(n, bool) or not isinstance(n, int) or n < 1:
                raise GateSpecError(
                    f"gate {name!r}: section {c['section']!r} holds {t!r}: {n!r}; the tracer "
                    f"writes only declared targets with positive integer call counts")
        missing = [t for t in c["exercises"] if t not in sec]
        if missing:
            raise GateSpecError(
                f"gate {name!r}: COVERAGE VIOLATION — the harness never executed {missing} in "
                f"section {c['section']!r} (it did execute {sorted(sec) or 'none of them'}). The "
                f"metric was produced without running what the gate names. This is the P1 defect "
                f"(cycle 158): G4 scored 1.0 while its harness touched one of five entry points.")
        return {t: sec[t] for t in c["exercises"]}

    def score(self, result: dict, smoke: bool = False) -> Verdict:
        # power_basis rides on the Verdict as metadata; verdict STRINGS are untouched so every
        # committed seal keeps verifying byte-identically.
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
            # numbers.Real for consistency with the composition member guard (verification pass
            # F4: the two guards disagreed on what a number is — np.float32 aggregated as a
            # member but refused as a quoted metric). bool stays banned; both refuse safely.
            if isinstance(_v, bool) or not isinstance(_v, numbers.Real) \
                    or not math.isfinite(float(_v)):
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
            if all(fired.get(k) == v for k, v in row["when"].items()):
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


# -- v5: the coverage tracer ------------------------------------------------------------------

def _resolve_target(target: str) -> types.CodeType:
    """``"module:qualname"`` -> the code object that runs when it is called, or a refusal."""
    mod_name, qual = target.split(":", 1)
    try:
        obj = importlib.import_module(mod_name)
        for part in qual.split("."):
            obj = inspect.getattr_static(obj, part)
    except (ImportError, AttributeError) as e:
        raise GateSpecError(
            f"declared target {target!r} does not resolve ({type(e).__name__}: {e}) — a "
            f"declaration naming nothing would read as unexercised forever, or worse, as a "
            f"typo nobody notices") from e
    if isinstance(obj, (staticmethod, classmethod)):
        obj = obj.__func__
    obj = inspect.unwrap(obj) if callable(obj) else obj
    code = getattr(obj, "__code__", None)
    if not isinstance(code, types.CodeType):
        raise GateSpecError(
            f"declared target {target!r} resolves to {type(obj).__name__}, which has no Python "
            f"code object to observe (builtins, C extensions and properties cannot be traced). "
            f"Declare the Python function that calls it instead.")
    return code


class _CoverageTracer:
    """Records calls to declared targets' code objects, attributed to the open section."""

    def __init__(self, experiment: "Experiment"):
        if not isinstance(experiment, Experiment):
            raise TypeError("coverage_trace() takes the Experiment whose frozen gates block "
                            "declares the targets — never a caller-supplied list")
        if not experiment.coverage_targets:
            raise GateSpecError(
                "no gate in this prereg declares 'exercises' — a coverage trace with nothing "
                "declared would record nothing and could be mistaken for a check that passed")
        self._exp = experiment
        self._codes: dict = {}
        self._code_sha: dict = {}
        for t in experiment.coverage_targets:
            code = _resolve_target(t)
            self._codes.setdefault(code, []).append(t)
            self._code_sha[t] = hashlib.sha256(marshal.dumps(code)).hexdigest()
        self._lock = threading.Lock()
        self._current = None
        self._sections: dict = {}
        self._unsectioned: dict = {}
        self._active = False

    def _bump(self, bucket: dict, targets: list) -> None:
        for t in targets:
            bucket[t] = bucket.get(t, 0) + 1

    def _make_hook(self, prev):
        codes = self._codes

        def hook(frame, event, arg):
            if event == "call" and self._active:
                ts = codes.get(frame.f_code)
                if ts:
                    with self._lock:
                        sec = self._current
                        self._bump(self._sections[sec] if sec is not None
                                   else self._unsectioned, ts)
            if prev is not None:
                prev(frame, event, arg)
        return hook

    def __enter__(self):
        self._prev_sys = sys.getprofile()
        self._prev_thr = (threading.getprofile() if hasattr(threading, "getprofile")
                          else getattr(threading, "_profile_hook", None))
        self._active = True
        sys.setprofile(self._make_hook(self._prev_sys))
        threading.setprofile(self._make_hook(self._prev_thr))
        return self

    def __exit__(self, *exc):
        self._active = False
        sys.setprofile(self._prev_sys)
        threading.setprofile(self._prev_thr)
        return False

    @contextlib.contextmanager
    def section(self, name: str):
        """Attribute every declared-target call made while this is open to *name*."""
        if name not in self._exp.coverage_sections:
            raise GateSpecError(
                f"section {name!r} is not declared by any gate (declared: "
                f"{self._exp.coverage_sections}) — calls recorded under it could never count, "
                f"so opening it is refused before the work runs")
        with self._lock:
            if self._current is not None:
                raise GateSpecError(
                    f"section {name!r} opened inside section {self._current!r} — nested "
                    f"sections would make one call count for two gates")
            self._current = name
            self._sections.setdefault(name, {})
        try:
            yield self
        finally:
            with self._lock:
                self._current = None

    def record(self) -> dict:
        """The trace to store in the result under ``coverage_trace``."""
        with self._lock:
            return {"tracer": _TRACER_ID,
                    "gates_sha256": self._exp.gates_sha256,
                    "targets": dict(sorted(self._code_sha.items())),
                    "sections": {k: dict(sorted(v.items()))
                                 for k, v in sorted(self._sections.items())},
                    "unsectioned": dict(sorted(self._unsectioned.items())),
                    "scope_note": ("calls in this interpreter's threads only; work in a child "
                                   "process is not observed and reads as unexercised")}


def coverage_trace(experiment: "Experiment") -> _CoverageTracer:
    """Trace a harness against the targets its frozen prereg declares (protocol v5).

    ::

        exp = Experiment("PREREG_x.md")
        with coverage_trace(exp) as cov:
            with cov.section("G4_refuses_degenerate"):
                res["degenerate_refusal_rate"] = run_degenerate_battery()
        res["coverage_trace"] = cov.record()
        exp.score(res)       # refuses if a declared target was never called in its section

    Targets resolve on construction, so a declaration naming nothing refuses before any work
    runs. Calls are observed by code-object identity through ``sys.setprofile`` (chained to any
    profiler already installed, so tracers nest) and in threads started while tracing.
    """
    return _CoverageTracer(experiment)
