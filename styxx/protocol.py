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

import functools
import gc
import hashlib
import importlib
import itertools
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
# fullmatch, not ^...$: "$" also matches before a trailing newline (red team round 1, N2).
_TARGET_RE = re.compile(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*:[A-Za-z_]\w*(\.[A-Za-z_]\w*)*",
                        re.ASCII)
_TRACE_KEY = "coverage_trace"
_TRACER_ID = "styxx.protocol.coverage_trace/2"

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
        # Round 2 R2-D6: a non-dict result used to raise AttributeError here; the pre-run safety
        # tool reports, it does not crash (every path below already refuses a non-dict).
        smoke = bool(result.get("smoke")) if isinstance(result, dict) else False
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
                out[key] = {"path": _TRACE_KEY,
                            "present": isinstance(result, dict)
                            and isinstance(result.get(_TRACE_KEY), dict),
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
        """v5e score-time check for one declaring gate. Returns {declared target: union count}.

        The order is the spec's, and every refusal carries its complete literal code at its own
        site, so the frozen mutation gate can delete each one alone: NO_TRACE, WRONG_TRACER,
        BAD_TRACE (exact types, one pass, before anything is read), STALE_TRACE, TARGET_SET,
        BAD_COUNT, a recorded problem (the FIRST one's own code), SECTION_ABSENT, NOT_EXERCISED.
        """
        c = self.coverage[name]
        tr = dict.get(result, _TRACE_KEY) if type(result) is dict else None
        if type(tr) is not dict:
            raise GateSpecError(
                f"[V5:NO_TRACE] gate {name!r} declares 'exercises' but the result carries no "
                f"{_TRACE_KEY!r} dict -- run the harness inside styxx.protocol.coverage_trace() "
                f"and store its record(). A declared coverage with no trace is unverified, not met.")
        if dict.get(tr, "tracer") != _TRACER_ID:
            raise GateSpecError(
                f"[V5:WRONG_TRACER] gate {name!r}: {_TRACE_KEY}.tracer is "
                f"{dict.get(tr, 'tracer')!r}, not {_TRACER_ID!r} -- this trace was not written by "
                f"the machinery that can read it")
        _check_trace_shape(name, tr)
        if tr["gates_sha256"] != self.gates_sha256:
            raise GateSpecError(
                f"[V5:STALE_TRACE] gate {name!r}: the trace was taken against gates block "
                f"{str(tr['gates_sha256'])[:12]}..., not this one ({self.gates_sha256[:12]}...). "
                f"A trace of a different declaration is not evidence about this one.")
        if sorted(tr["targets"]) != self.coverage_targets:
            raise GateSpecError(
                f"[V5:TARGET_SET] gate {name!r}: the trace's target set {sorted(tr['targets'])} "
                f"differs from the declared set {self.coverage_targets}")
        declared = set(self.coverage_targets)
        for where, d in _count_dicts(tr):
            for t, n in d.items():
                if t not in declared or type(n) is not int or n < 1:
                    raise GateSpecError(
                        f"[V5:BAD_COUNT] gate {name!r}: {where} holds {t!r}: {n!r}; counts are "
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
            if first == "FOREIGN_PROFILER":
                raise GateSpecError(f"[V5:FOREIGN_PROFILER] gate {name!r}: {problems[0]}{listed}")
            if first == "CLONE_CALLED":
                raise GateSpecError(f"[V5:CLONE_CALLED] gate {name!r}: {problems[0]}{listed}")
            if first == "CLONE_ALIVE":
                raise GateSpecError(f"[V5:CLONE_ALIVE] gate {name!r}: {problems[0]}{listed}")
            if first == "CODE_SWAPPED":
                raise GateSpecError(f"[V5:CODE_SWAPPED] gate {name!r}: {problems[0]}{listed}")
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
#
# v5e, "mint-and-anchor" (DESIGN_protocol_v5e_mint_anchor_2026_09_24.md). Three red-team rounds
# broke v5's first design by reopening two classes -- target identity and call attribution -- one
# patched instance at a time. This replaces the machinery rather than patching it:
#
#   IDENTITY. A frame counts for declared target T iff frame.f_code IS M_T and frame.f_globals IS
#   F_T.__globals__, where M_T is a fresh code object minted at trace entry with
#   F_T.__code__.replace() and published only by assigning it to F_T.__code__. Every function that
#   merely SHARES T's original code (factory products, wraps siblings, clones, vendored copies)
#   runs a different object, so the class closes by construction.
#
#   ATTRIBUTION. A counted frame is credited to opening O iff O's anchor (the frame of the
#   cov.run() call or cov.run_async() coroutine that opened O) is registered and is met on the
#   frame's f_back chain before the first asyncio dispatch frame (Handle._run), and no other open
#   opening of O's tracer is met there. No inherited state is ever read.
#
# Every coded emission carries its complete literal code at its own site (G7 of the prereg), so
# the frozen mutation gate can delete each one alone.

_CACHE_WRAPPER = type(functools.lru_cache(None)(lambda: 0))   # functools._lru_cache_wrapper (C)
_LOCK = threading.RLock()     # __enter__/__exit__/_open/_close only; never the hook, never record()
_MINTED: dict = {}            # id(M) -> _Mint (the mint holds M, so the id cannot be reused)
_BY_FN: dict = {}             # id(F_T) -> _Mint (holds F_T)
_ANCHORS: dict = {}           # id(anchor frame) -> _Opening (the opening holds the frame)
_THREADS: dict = {}           # thread ident -> [open openings on that thread, install epoch]
_EPOCH = itertools.count(1)   # global, so a recreated _THREADS entry never reuses an epoch
_ACTIVE = 0                   # tracers between a completed __enter__ and the start of __exit__
_STOP = None                  # asyncio.events.Handle._run.__code__ while any tracer is active
_CODE_RE = re.compile(r"\[V5:([A-Z_]+)\] ")
_NOTE_CODES = frozenset({"PROFILER_LOST", "THREAD_HOP", "OPEN_AT_EXIT", "LAZY_RESULT"})
_RECORDED_CODES = frozenset({"REENTRY", "TRACE_INACTIVE", "UNDECLARED_SECTION", "NESTED_SECTION",
                             "FOREIGN_PROFILER", "CLONE_CALLED", "CLONE_ALIVE", "CODE_SWAPPED"})
_TRACE_KEYS = frozenset({"tracer", "gates_sha256", "targets", "sections", "uncredited", "problems"})
_OPENING_KEYS = frozenset({"calls", "ambiguous", "end", "notes"})
_ENDS = frozenset({"returned", "raised", "open"})
_FIXED_SENTENCE = ("work on other threads, pools, executors or asyncio tasks is credited only to a "
                   "section that work opens itself")


class _Mint:
    __slots__ = ("fn", "original", "code", "globals", "tracers")

    def __init__(self, fn):
        self.fn = fn
        self.original = fn.__code__
        self.code = fn.__code__.replace()
        self.globals = fn.__globals__
        self.tracers = ()             # replaced, never mutated: the hook reads it without a lock


class _Opening:
    __slots__ = ("tracer", "section", "frame", "tid", "epoch", "calls", "ambiguous", "end", "notes")

    def __init__(self, tracer, section, frame, tid, epoch):
        self.tracer, self.section, self.frame, self.tid, self.epoch = (
            tracer, section, frame, tid, epoch)
        self.calls: dict = {}
        self.ambiguous: dict = {}
        self.end = "open"
        self.notes: list = []


def _bump(d: dict, names) -> None:
    for n in names:
        d[n] = d.get(n, 0) + 1


def _hook(frame, event, arg):
    """The one profile function. No try/except (an exception here propagates as CPython defines,
    and CPython then drops the hook: calls after that are lost, never invented), and no lock."""
    tid = threading.get_ident()
    if not _ACTIVE or tid not in _THREADS:
        sys.setprofile(None)                         # self-removal
        return
    if event != "call":
        return
    code = frame.f_code
    m = _MINTED.get(id(code))
    if m is None or m.code is not code:              # identity, never equality
        return
    tracers = m.tracers
    if frame.f_globals is not m.globals:             # a clone under other globals: credits nothing
        for t in tracers:
            t._clone_called.add(id(code))
        return
    found, cut, stop, f = [], False, _STOP, frame.f_back
    while f is not None:
        if f.f_code is stop:
            cut = True
            break
        o = _ANCHORS.get(id(f))
        if o is not None and o.frame is f:
            found.append(o)
        f = f.f_back
    for t in tracers:
        names = t._by_code.get(id(code))
        if not names:
            continue
        mine = [o for o in found if o.tracer is t]
        if len(mine) == 1:
            _bump(mine[0].calls, names)
        elif mine:
            for o in mine:
                _bump(o.ambiguous, names)
        else:
            u = t._uncredited.get(tid)
            if u is None:
                u = t._uncredited[tid] = ({}, {})
            _bump(u[0] if cut else u[1], names)


def _own_dict(obj):
    try:
        d = object.__getattribute__(obj, "__dict__")
    except Exception:                                # noqa: BLE001
        return None
    return d if type(d) is dict else None


def _defined_in(obj, mod_dict) -> bool:
    """Provenance: obj, or a link of its own-__dict__ __wrapped__ chain, is a function whose
    __globals__ IS the declared module's dict. The walk steps only through FunctionType and C cache
    wrappers, at most 16 hops, cycle-detected, and never calls getattr."""
    seen, cur = set(), obj
    for _ in range(17):
        if cur is None or id(cur) in seen:
            return False
        seen.add(id(cur))
        if type(cur) is types.FunctionType:
            if cur.__globals__ is mod_dict:
                return True
        elif type(cur) is not _CACHE_WRAPPER:
            return False
        d = _own_dict(cur)
        cur = d.get("__wrapped__") if d is not None else None
    return False


def _resolve_target(target: str):
    """``module:qualname`` -> (the declared object, F_T the function whose code is minted), or a
    refusal. Resolution never runs user code except the import and a module's PEP 562 __getattr__."""
    mod_name, qual = target.split(":", 1)
    try:
        mod = importlib.import_module(mod_name)
    except Exception as e:                           # noqa: BLE001  (SyntaxError included)
        raise GateSpecError(
            f"[V5:UNRESOLVED] declared target {target!r}: importing {mod_name!r} raised "
            f"{type(e).__name__}: {e}") from e
    obj, holder = mod, None
    for i, part in enumerate(qual.split(".")):
        if isinstance(obj, types.ModuleType):
            if i > 0:
                raise GateSpecError(
                    f"[V5:INSTANCE_PATH] declared target {target!r}: {part!r} is reached through the "
                    f"module {obj.__name__!r} after the colon -- put the full module path before it")
            d = vars(obj)
            if part in d:
                holder, obj = d, d[part]
            elif "__getattr__" in d:
                try:
                    holder, obj = None, d["__getattr__"](part)
                except Exception as e:               # noqa: BLE001
                    raise GateSpecError(
                        f"[V5:UNRESOLVED] declared target {target!r}: {mod_name}.__getattr__"
                        f"({part!r}) raised {type(e).__name__}: {e}") from e
            else:
                raise GateSpecError(
                    f"[V5:UNRESOLVED] declared target {target!r}: {mod_name!r} has no attribute "
                    f"{part!r} and no module __getattr__ (an unimported submodule is not an attribute)")
        elif isinstance(obj, type):
            own = vars(obj)
            if part in own:
                holder, obj = own, own[part]
            elif any(part in vars(k) for k in obj.__mro__[1:]):
                raise GateSpecError(
                    f"[V5:INHERITED] declared target {target!r}: {part!r} is inherited by "
                    f"{obj.__qualname__}, not defined on it -- declare the defining class")
            else:
                raise GateSpecError(
                    f"[V5:UNRESOLVED] declared target {target!r}: class {obj.__qualname__} has no "
                    f"attribute {part!r} in its own or any base's __dict__")
        else:
            d = _own_dict(obj)
            if d is None or part not in d:
                raise GateSpecError(
                    f"[V5:INSTANCE_PATH] declared target {target!r}: {part!r} is not in the own "
                    f"__dict__ of the {type(obj).__name__} it is reached through -- an attribute "
                    f"that comes from a class is declared on the class ({type(obj).__qualname__})")
            holder, obj = d, d[part]
    if isinstance(obj, (staticmethod, classmethod)):
        obj = obj.__func__
    declared = obj
    if type(obj) is types.FunctionType:
        fn = obj
    elif type(obj) is _CACHE_WRAPPER:
        d = _own_dict(obj)
        body = d.get("__wrapped__") if d is not None else None
        if type(body) is not types.FunctionType:
            raise GateSpecError(
                f"[V5:NOT_A_FUNCTION] declared target {target!r}: a cache wrapper whose body is "
                f"{type(body).__name__}, not a Python function")
        if any(v is body for v in vars(mod).values()) or (
                holder is not None and any(v is body for v in holder.values())):
            raise GateSpecError(
                f"[V5:NOT_A_FUNCTION] declared target {target!r}: the cache wrapper's body is also "
                f"bound by name in the namespace -- declare that name instead")
        fn = body
    else:
        raise GateSpecError(
            f"[V5:NOT_A_FUNCTION] declared target {target!r} resolves to {type(obj).__name__}: only "
            f"Python functions, staticmethod/classmethod of one, and C cache wrappers (through their "
            f"body) can be observed")
    if not _defined_in(declared, vars(mod)):
        where = getattr(fn.__code__, "co_filename", "?")
        raise GateSpecError(
            f"[V5:FOREIGN_DEFINITION] declared target {target!r}: neither it nor its __wrapped__ "
            f"chain was defined in {mod_name!r} (its code comes from {where}) -- a re-export, a "
            f"stub or a mock bound at the name is not the function the declaration names")
    return declared, fn


class _CoverageTracer:
    """One trace: mints the declared targets at entry, credits calls by stack anchor."""

    def __init__(self, experiment: "Experiment"):
        if not isinstance(experiment, Experiment):
            raise TypeError("coverage_trace() takes the Experiment whose frozen gates block "
                            "declares the targets -- never a caller-supplied list")
        if not experiment.coverage_targets:
            raise GateSpecError(
                "[V5:NOTHING_DECLARED] no gate in this prereg declares 'exercises' -- a coverage "
                "trace with nothing declared would record nothing and could be mistaken for a check "
                "that passed")
        self._exp = experiment
        self._state = "new"                          # new -> active -> exiting -> exited
        self._by_code: dict = {}                     # id(M) -> tuple of declared names
        self._prov: dict = {}                        # declared name -> "file:line"
        self._mints: list = []
        self._openings: list = []
        self._problems: list = []
        self._clone_called: set = set()
        self._uncredited: dict = {}                  # tid -> (dispatched{}, unattributed{})

    def _refuse_recorded(self, msg: str):
        """A misuse refusal that is also written into the trace (every caller passes a literal
        code), so a harness that swallows the exception cannot hide it from score()."""
        if self._state != "new":
            self._problems.append(msg)
        raise GateSpecError(msg)

    # -- lifecycle ------------------------------------------------------------------------------

    def __enter__(self):
        global _ACTIVE, _STOP
        if self._state != "new":
            self._refuse_recorded(
                f"[V5:REENTRY] this coverage_trace is {self._state}; a tracer is entered exactly "
                f"once -- nested use needs a second tracer")
        import asyncio.events
        resolved = [(t, *_resolve_target(t)) for t in self._exp.coverage_targets]
        with _LOCK:
            for t, _declared, fn in resolved:
                m = _BY_FN.get(id(fn))
                if m is not None and m.fn is fn and fn.__code__ is not m.code:
                    raise GateSpecError(
                        f"[V5:CODE_SWAPPED] declared target {t!r}: an enclosing trace minted it and "
                        f"its __code__ has since been replaced -- the trace cannot tell its calls apart")
            by_fn: dict = {}
            for t, _declared, fn in resolved:
                m = _BY_FN.get(id(fn))
                if m is None or m.fn is not fn:
                    m = _Mint(fn)
                    fn.__code__ = m.code
                    _MINTED[id(m.code)] = m
                    _BY_FN[id(fn)] = m
                if id(fn) not in by_fn:
                    by_fn[id(fn)] = m
                    m.tracers = m.tracers + (self,)
                    self._mints.append(m)
                self._by_code[id(m.code)] = self._by_code.get(id(m.code), ()) + (t,)
                self._prov[t] = f"{m.original.co_filename}:{m.original.co_firstlineno}"
            _STOP = asyncio.events.Handle._run.__code__
            _ACTIVE += 1
            self._state = "active"
        return self

    def __exit__(self, exc_type, exc, tb):
        global _ACTIVE, _STOP
        with _LOCK:
            if self._state != "active":
                return False
            self._state = "exiting"
            _ACTIVE -= 1
            self._by_code = {}                       # first: nothing can credit this tracer now
            for o in self._openings:
                if o.frame is not None:
                    o.notes.append(
                        f"[V5:OPEN_AT_EXIT] section {o.section!r} was still open when the trace "
                        f"exited; only calls made before the exit count")
                    _ANCHORS.pop(id(o.frame), None)
                    o.frame = None
                    st = _THREADS.get(o.tid)
                    if st is not None:
                        st[0] -= 1
                        if st[0] <= 0:
                            del _THREADS[o.tid]
            for cid in sorted(self._clone_called):
                m = _MINTED.get(cid)
                who = m.fn.__qualname__ if m is not None else "?"
                self._problems.append(
                    f"[V5:CLONE_CALLED] the minted code of {who} ran under globals that are not its "
                    f"function's: a function was built from its code object, or it was exec'd")
            for m in self._mints:
                m.tracers = tuple(t for t in m.tracers if t is not self)
                if m.fn.__code__ is not m.code:
                    self._problems.append(
                        f"[V5:CODE_SWAPPED] {m.fn.__qualname__}.__code__ was replaced during the "
                        f"trace -- calls through the replacement were not observed")
                elif not m.tracers:
                    m.fn.__code__ = m.original
                if not m.tracers:
                    _MINTED.pop(id(m.code), None)
                    _BY_FN.pop(id(m.fn), None)
                expected = 2 + (m.fn.__code__ is m.code)   # the mint's slot, the argument, the fn
                if sys.getrefcount(m.code) - expected > 0:
                    holders = [r for r in gc.get_referrers(m.code)
                               if type(r) is types.FunctionType and r is not m.fn]
                    if holders:
                        self._problems.append(
                            f"[V5:CLONE_ALIVE] {len(holders)} live function(s) other than "
                            f"{m.fn.__qualname__} hold its minted code ({sorted({h.__qualname__ for h in holders})}) "
                            f"-- a clone built during the trace would be credited as it")
            if _ACTIVE == 0:
                _STOP = None
                if sys.getprofile() is _hook:
                    sys.setprofile(None)
            self._state = "exited"
        return False

    # -- sections -------------------------------------------------------------------------------

    def run(self, section, fn, /, *args, **kwargs):
        """Open *section*, call fn(*args, **kwargs) from this frame, close it on return AND raise."""
        o = self._open(section, sys._getframe())
        end = "raised"
        try:
            result = fn(*args, **kwargs)
            end = "returned"
        finally:
            self._close(o, end)
        if isinstance(result, (types.CoroutineType, types.GeneratorType, types.AsyncGeneratorType)):
            o.notes.append(
                f"[V5:LAZY_RESULT] section {section!r}: fn returned a {type(result).__name__}; its "
                f"body runs after the section closed, so none of it counts")
        return result

    async def run_async(self, section, afn, /, *args, **kwargs):
        """The coroutine form: this coroutine's frame is the anchor."""
        o = self._open(section, sys._getframe())
        end = "raised"
        try:
            result = await afn(*args, **kwargs)
            end = "returned"
        finally:
            self._close(o, end)
        return result

    def _open(self, section, anchor):
        if self._state != "active":
            self._refuse_recorded(
                f"[V5:TRACE_INACTIVE] section {section!r}: the trace is {self._state}, not active")
        if section not in self._exp.coverage_sections:
            self._refuse_recorded(
                f"[V5:UNDECLARED_SECTION] section {section!r} is not declared by any gate "
                f"(declared: {self._exp.coverage_sections})")
        stop, f = _STOP, anchor.f_back
        while f is not None:
            if f.f_code is stop:
                break
            o = _ANCHORS.get(id(f))
            if o is not None and o.frame is f and o.tracer is self:
                self._refuse_recorded(
                    f"[V5:NESTED_SECTION] section {section!r} opened on the stack of an open "
                    f"opening of section {o.section!r} of the same trace -- one call would count "
                    f"for two gates")
            f = f.f_back
        tid = threading.get_ident()
        with _LOCK:
            prof = sys.getprofile()
            if prof is not None and prof is not _hook:
                self._refuse_recorded(
                    f"[V5:FOREIGN_PROFILER] section {section!r}: a {type(prof).__name__} is already "
                    f"installed as this thread's profiler; it is left untouched, and a section "
                    f"cannot be observed alongside it")
            st = _THREADS.setdefault(tid, [0, 0])
            if prof is None:
                st[1] = next(_EPOCH)
                sys.setprofile(_hook)
            st[0] += 1
            o = _Opening(self, section, anchor, tid, st[1])
            self._openings.append(o)
            _ANCHORS[id(anchor)] = o                 # registration is the last statement
        return o

    def _close(self, o, end):
        tid = threading.get_ident()
        with _LOCK:
            if o.frame is None:                      # detached by the tracer's exit
                return
            _ANCHORS.pop(id(o.frame), None)
            o.frame = None
            st = _THREADS.get(o.tid)
            if tid != o.tid:
                o.notes.append(
                    f"[V5:THREAD_HOP] section {o.section!r} closed on another thread than it "
                    f"opened on")
            elif sys.getprofile() is not _hook or st is None or st[1] != o.epoch:
                o.notes.append(
                    f"[V5:PROFILER_LOST] section {o.section!r}: the profile hook was replaced or "
                    f"dropped while it was open; calls after that on this thread were not observed")
            if st is not None:
                st[0] -= 1
                if st[0] <= 0:
                    del _THREADS[o.tid]
                    if tid == o.tid and sys.getprofile() is _hook:
                        sys.setprofile(None)
            o.end = end

    def record(self) -> dict:
        """The trace to store under ``coverage_trace``, taken after the trace exits."""
        if self._state in ("new", "active"):
            raise GateSpecError(
                f"[V5:TRACE_ACTIVE] record() on a {self._state} trace -- take it after the trace "
                f"exits")
        if self._state != "exited":
            raise GateSpecError(
                "[V5:TRACE_INCOMPLETE] the trace's exit did not complete, so its checks and its "
                "restorations did not all run")
        sections: dict = {}
        for o in list(self._openings):
            sections.setdefault(o.section, []).append({
                "calls": dict(sorted(dict(o.calls).items())),
                "ambiguous": dict(sorted(dict(o.ambiguous).items())),
                "end": o.end, "notes": list(o.notes)})
        disp: dict = {}
        unat: dict = {}
        for a, b in list(self._uncredited.values()):
            for k, v in dict(a).items():
                disp[k] = disp.get(k, 0) + v
            for k, v in dict(b).items():
                unat[k] = unat.get(k, 0) + v
        return {"tracer": _TRACER_ID, "gates_sha256": self._exp.gates_sha256,
                "targets": dict(sorted(self._prov.items())),
                "sections": dict(sorted(sections.items())),
                "uncredited": {"dispatched": dict(sorted(disp.items())),
                               "unattributed": dict(sorted(unat.items()))},
                "problems": list(self._problems)}


def _check_trace_shape(name: str, tr: dict) -> None:
    """BAD_TRACE, in one pass before anything is read. Every type check is exact."""
    if set(tr) != _TRACE_KEYS:
        raise GateSpecError(
            f"[V5:BAD_TRACE] gate {name!r}: the trace's keys are {sorted(map(str, tr))}, not "
            f"exactly {sorted(_TRACE_KEYS)}")
    tg = tr["targets"]
    if type(tg) is not dict or not all(type(k) is str and type(v) is str for k, v in tg.items()):
        raise GateSpecError(f"[V5:BAD_TRACE] gate {name!r}: targets must be a dict of str to str")
    secs = tr["sections"]
    if type(secs) is not dict or not all(type(k) is str for k in secs):
        raise GateSpecError(f"[V5:BAD_TRACE] gate {name!r}: sections must be a dict with str keys")
    for s, ops in secs.items():
        if type(ops) is not list or not ops:
            raise GateSpecError(
                f"[V5:BAD_TRACE] gate {name!r}: section {s!r} must be a non-empty list of openings")
        for o in ops:
            if type(o) is not dict or set(o) != _OPENING_KEYS:
                raise GateSpecError(
                    f"[V5:BAD_TRACE] gate {name!r}: an opening of {s!r} must be a dict with exactly "
                    f"{sorted(_OPENING_KEYS)}")
            if o["end"] not in _ENDS or type(o["end"]) is not str:
                raise GateSpecError(
                    f"[V5:BAD_TRACE] gate {name!r}: an opening of {s!r} has end {o['end']!r}")
            notes = o["notes"]
            if type(notes) is not list or not all(
                    type(n) is str and (_CODE_RE.match(n) or [None, None])[1] in _NOTE_CODES
                    for n in notes):
                raise GateSpecError(
                    f"[V5:BAD_TRACE] gate {name!r}: an opening of {s!r} has notes {notes!r}; each "
                    f"note is a str beginning with a known note code")
            for k in ("calls", "ambiguous"):
                if type(o[k]) is not dict or not all(type(t) is str for t in o[k]):
                    raise GateSpecError(
                        f"[V5:BAD_TRACE] gate {name!r}: an opening's {k} must be a dict with str keys")
    un = tr["uncredited"]
    if type(un) is not dict or set(un) != {"dispatched", "unattributed"} or not all(
            type(d) is dict and all(type(t) is str for t in d) for d in un.values()):
        raise GateSpecError(
            f"[V5:BAD_TRACE] gate {name!r}: uncredited must be a dict of exactly dispatched and "
            f"unattributed, each a dict with str keys")
    pr = tr["problems"]
    if type(pr) is not list or not all(
            type(p) is str and (_CODE_RE.match(p) or [None, None])[1] in _RECORDED_CODES for p in pr):
        raise GateSpecError(
            f"[V5:BAD_TRACE] gate {name!r}: problems must be a list of str, each beginning with a "
            f"known recorded code")


def _count_dicts(tr: dict):
    for s, ops in tr["sections"].items():
        for i, o in enumerate(ops):
            yield f"sections[{s!r}][{i}].calls", o["calls"]
            yield f"sections[{s!r}][{i}].ambiguous", o["ambiguous"]
    yield "uncredited.dispatched", tr["uncredited"]["dispatched"]
    yield "uncredited.unattributed", tr["uncredited"]["unattributed"]


def coverage_trace(experiment: "Experiment") -> _CoverageTracer:
    """Trace a harness against the targets its frozen prereg declares (protocol v5e).

    ::

        exp = Experiment("PREREG_x.md")
        with coverage_trace(exp) as cov:
            res["degenerate_refusal_rate"] = cov.run("G4_refuses_degenerate", battery)
        res["coverage_trace"] = cov.record()
        exp.score(res)       # refuses if a declared target never ran on the section's own stack

    Sections are calls (``cov.run`` / ``await cov.run_async``). Work on other threads, pools,
    executors or asyncio tasks is credited only to a section that work opens itself.
    """
    return _CoverageTracer(experiment)
