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
                # exact reads, as score() reads them: never a subclass's .get (R2-D6: a non-dict
                # result reports here instead of raising)
                out[key] = {"path": _TRACE_KEY,
                            "present": issubclass(type(result), dict)
                            and type(dict.get(result, _TRACE_KEY)) is dict,
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
        """Refuse a declaring gate unless the v5e trace credits every declared target to an
        opening of the gate's section. Returns {declared target: union count over every opening of
        the section} for the gate. The steps run in the spec's order (NO_TRACE, WRONG_TRACER,
        BAD_TRACE in one exact-type pass before anything is read, STALE_TRACE, TARGET_SET,
        BAD_COUNT, a recorded problem, SECTION_ABSENT, NOT_EXERCISED); every message leads with its
        own literal ``[V5:CODE]`` (red team round 1: a mutant that refuses for a later, different
        reason never tested the check it names).
        """
        c = self.coverage[name]
        tr = dict.get(result, _TRACE_KEY) if issubclass(type(result), dict) else None
        if type(tr) is not dict:
            raise GateSpecError(
                f"[V5:NO_TRACE] gate {name!r} declares 'exercises' but the result is not a dict "
                f"carrying a {_TRACE_KEY!r} dict -- run the harness inside "
                f"styxx.protocol.coverage_trace() and store its record(). A declared coverage with "
                f"no trace is unverified, not met.")
        tracer = dict.get(tr, "tracer")
        if type(tracer) is not str or tracer != _TRACER_ID:
            raise GateSpecError(
                f"[V5:WRONG_TRACER] gate {name!r}: {_TRACE_KEY}.tracer is {str(tracer)[:80]!r}, "
                f"not {_TRACER_ID!r} -- only a trace written by the v5e tracer can be read (v5, "
                f"v5c and v5d traces keep their committed verdicts as history)")
        why = _trace_schema_problem(tr)
        if why is not None:
            raise GateSpecError(
                f"[V5:BAD_TRACE] gate {name!r}: {why} -- a trace that can be half-read is a trace "
                f"that can be half-forged")
        sha = tr["gates_sha256"]
        if type(sha) is not str or sha != self.gates_sha256:
            raise GateSpecError(
                f"[V5:STALE_TRACE] gate {name!r}: the coverage trace was taken against gates "
                f"block {str(sha)[:12]}..., not this one ({self.gates_sha256[:12]}...). A trace of "
                f"a different declaration is not evidence about this one.")
        if sorted(tr["targets"]) != self.coverage_targets:
            raise GateSpecError(
                f"[V5:TARGET_SET] gate {name!r}: the trace's target set {sorted(tr['targets'])} "
                f"is not the declared set {self.coverage_targets} -- it recorded something other "
                f"than what the frozen document asks about")
        bad = _bad_count(tr, set(self.coverage_targets))
        if bad is not None:
            raise GateSpecError(
                f"[V5:BAD_COUNT] gate {name!r}: {bad}; the tracer writes only declared targets "
                f"with integer counts >= 1")
        problems = tr["problems"]
        if problems:
            code = _CODE_RE.match(problems[0]).group(1)
            listed = (f"the trace records {len(problems)} problem(s), and each refuses every gate "
                      f"that declares coverage, whatever the harness did with the exception: "
                      f"{problems}")
            if code == "REENTRY":
                raise GateSpecError(f"[V5:REENTRY] gate {name!r}: {listed}")
            if code == "TRACE_INACTIVE":
                raise GateSpecError(f"[V5:TRACE_INACTIVE] gate {name!r}: {listed}")
            if code == "UNDECLARED_SECTION":
                raise GateSpecError(f"[V5:UNDECLARED_SECTION] gate {name!r}: {listed}")
            if code == "NESTED_SECTION":
                raise GateSpecError(f"[V5:NESTED_SECTION] gate {name!r}: {listed}")
            if code == "FOREIGN_PROFILER":
                raise GateSpecError(f"[V5:FOREIGN_PROFILER] gate {name!r}: {listed}")
            if code == "CLONE_CALLED":
                raise GateSpecError(f"[V5:CLONE_CALLED] gate {name!r}: {listed}")
            if code == "CLONE_ALIVE":
                raise GateSpecError(f"[V5:CLONE_ALIVE] gate {name!r}: {listed}")
            if code == "CODE_SWAPPED":
                raise GateSpecError(f"[V5:CODE_SWAPPED] gate {name!r}: {listed}")
            # unreachable: the schema pass admits only the eight recorded codes above
            raise RuntimeError(f"recorded problem code {code!r} has no refusal")
        sec = c["section"]
        ops = tr["sections"].get(sec)
        if ops is None:
            raise GateSpecError(
                f"[V5:SECTION_ABSENT] gate {name!r}: section {sec!r} has no opening in the trace "
                f"-- the harness never opened it (cov.run / cov.run_async), so nothing it ran can "
                f"be attributed to this gate")
        union: dict = {}
        for o in ops:
            for t, n in o["calls"].items():
                union[t] = union.get(t, 0) + n
        missing = [t for t in c["exercises"] if t not in union]
        if missing:
            ends: dict = {}
            for o in ops:
                if o["end"] != "returned":
                    ends[o["end"]] = ends.get(o["end"], 0) + 1
            notes = [n for o in ops for n in o["notes"]]
            unc = tr["uncredited"]
            disp = {t: unc["dispatched"][t] for t in missing if t in unc["dispatched"]}
            unat = {t: unc["unattributed"][t] for t in missing if t in unc["unattributed"]}
            raise GateSpecError(
                f"[V5:NOT_EXERCISED] gate {name!r}: COVERAGE VIOLATION -- not executed on the "
                f"stack of any opening of section {sec!r}: {missing} (did execute "
                f"{sorted(union) or 'none of them'}). The section had {len(ops)} opening(s); ends "
                f"other than 'returned': {ends or 'none'}; notes: {notes or 'none'}. Calls of the "
                f"missing targets seen off every opening's stack (diagnostics, never evidence; "
                f"partial): dispatched past an asyncio dispatch frame {disp}, unattributed "
                f"{unat}. Only a call executed on the stack of an opening of the section counts; "
                f"{_OFF_STACK}. This is the P1 defect (cycle 158): a metric produced without "
                f"running what the gate names.")
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
# Protocol v5e, "mint and anchor" (DESIGN_protocol_v5e_mint_anchor_2026_09_24.md). Three red-team
# rounds against v5-v5d re-entered the same two defect classes by a new door each time; v5e closes
# both by construction instead of by enumeration:
#
# * TARGET IDENTITY by minting. At trace entry each declared function F_T gets a fresh code object
#   M_T = F_T.__code__.replace(), published only by assigning it to F_T.__code__ and restored when
#   the last tracer holding it exits. A frame counts for T iff it runs exactly M_T with F_T's own
#   globals. M_T is in no co_consts, so factory products, wraps siblings, clones made before the
#   trace, exec'd module copies and runtime decoration all run OTHER code objects. Nothing is ever
#   unwrapped for identity.
# * CALL ATTRIBUTION by stack anchor. Sections are calls (cov.run / cov.run_async). A call is
#   credited to an opening iff that opening's anchor frame is on the call's own live f_back chain
#   before asyncio's dispatch frame (Handle._run). No inherited state (ContextVar, thread start,
#   pool lifetime) is ever read, so no runtime hand-off can carry credit.
#
# Counts are lower bounds: every condition that can only LOSE calls (a lost profiler, a thread
# hop, a section open at exit, a lazy result) is a note, never a refusal. Every refusal, recorded
# problem and note below carries its complete literal [V5:CODE] at the site that emits it.
#
# N-version implementation (nversion_v5e/protocol_nv.py), written from the frozen spec alone. Where
# the spec left a choice, this file reads it as follows:
# * __exit__ "never raises" = it raises no refusal of its own; an exception from outside (a signal,
#   a profiler) propagates and leaves the state "exiting" (TRACE_INCOMPLETE). Exit on a tracer that
#   is not active is a no-op returning False.
# * _open runs all four checks and the registration under _LOCK (the sketch holds it only for
#   FOREIGN_PROFILER and registration), so an open cannot register after a concurrent exit.
# * LAZY_RESULT applies to run and run_async alike ("same, with await afn(...)"), through one site.
# * Provenance checks the declared object and at most 16 __wrapped__ links (hop 17 is not reached).
# * Type questions are asked of type(x), never x.__class__: module / class / staticmethod steps use
#   issubclass(type(obj), ...); a section name must be an exact str (else UNDECLARED_SECTION); a
#   tracer id that is not an exact str is WRONG_TRACER; a non-str gates_sha256 is STALE_TRACE;
#   counts must be exact ints >= 1. The result itself may be a dict subclass; the trace may not.
# * All BAD_TRACE clauses share one raise with the failing clause in its message. A recorded
#   problem refuses through one literal raise per recorded code (the first problem's code).
# * UNRESOLVED for an absent module attribute names the would-be submodule path without probing
#   the import system. A cache body found bound by identity in vars(module) or in the namespace
#   that held the wrapper (none after a PEP 562 __getattr__) refuses NOT_A_FUNCTION.
# * NOT_EXERCISED's "did execute" lists every target credited in the section. The trace's targets
#   provenance is F_T's co_filename:co_firstlineno (the body, for a cache wrapper).

_CACHE_WRAPPER = type(functools.lru_cache(None)(lambda: 0))
_LOCK = threading.RLock()   # __enter__/__exit__/_open/_close only. Never the hook, never record().
_MINTED: dict = {}          # id(M) -> _Mint            (the _Mint holds M, so the id cannot be reused)
_BY_FN: dict = {}           # id(F_T) -> _Mint          (holds F_T)
_ANCHORS: dict = {}         # id(anchor frame) -> _Opening (holds the frame until close / exit)
_THREADS: dict = {}         # thread ident -> [open openings on that thread, install epoch]
_EPOCH = itertools.count(1)  # global: a recreated _THREADS entry never reuses an epoch
_ACTIVE = 0                 # tracers between a completed __enter__ and the start of __exit__
_STOP = None                # asyncio.events.Handle._run.__code__, set in __enter__ after minting
_get_ident = threading.get_ident

_MAX_HOPS = 16              # the provenance walk's bound (own-dict __wrapped__ links)
_LAZY_TYPES = (types.CoroutineType, types.GeneratorType, types.AsyncGeneratorType)
_ENDS = ("returned", "raised", "open")
_NOTE_CODES = frozenset({"PROFILER_LOST", "THREAD_HOP", "OPEN_AT_EXIT", "LAZY_RESULT"})
_PROBLEM_CODES = frozenset({"REENTRY", "TRACE_INACTIVE", "UNDECLARED_SECTION", "NESTED_SECTION",
                            "FOREIGN_PROFILER", "CLONE_CALLED", "CLONE_ALIVE", "CODE_SWAPPED"})
_TRACE_KEYS = frozenset({"tracer", "gates_sha256", "targets", "sections", "uncredited", "problems"})
_OPENING_KEYS = frozenset({"calls", "ambiguous", "end", "notes"})
_UNCREDITED_KEYS = frozenset({"dispatched", "unattributed"})
_CODE_RE = re.compile(r"\[V5:([A-Z_]+)\] ")        # used with .match: anchored at the start
_OFF_STACK = ("work on other threads, pools, executors or asyncio tasks is credited only to a "
              "section that work opens itself")


class _Mint:
    """One minted code object, shared by every tracer that declares its function."""
    __slots__ = ("fn", "original", "code", "globals", "tracers")

    def __init__(self, fn, original, code, fn_globals):
        self.fn, self.original, self.code, self.globals = fn, original, code, fn_globals
        self.tracers = ()           # immutable; writers replace it under _LOCK


class _Opening:
    """One execution of cov.run / cov.run_async: its anchor frame and what was credited to it."""
    __slots__ = ("tracer", "section", "frame", "tid", "epoch", "calls", "ambiguous", "end",
                 "notes")

    def __init__(self, tracer, section, frame, tid, epoch):
        self.tracer, self.section, self.frame, self.tid, self.epoch = (tracer, section, frame,
                                                                       tid, epoch)
        self.calls: dict = {}
        self.ambiguous: dict = {}
        self.end = "open"
        self.notes: list = []


def _bump(d: dict, names) -> None:
    for n in names:
        d[n] = d.get(n, 0) + 1


def _hook(frame, event, arg):
    """THE profile function: module level, no try/except, no lock, no handler.

    An exception raised in here (a signal handler's, KeyboardInterrupt, RecursionError) propagates
    as CPython defines and CPython drops the hook on that thread; the loss surfaces as a
    PROFILER_LOST note at close and can only under-count. Calls made while it runs are not
    observed (CPython disables profiling inside a profiler), so it cannot re-enter itself.
    """
    tid = _get_ident()
    if not _ACTIVE or tid not in _THREADS:
        sys.setprofile(None)                            # self-removal
        return
    if event != "call":
        return
    code = frame.f_code
    m = _MINTED.get(id(code))
    if m is None or m.code is not code:                 # identity, never equality
        return
    tracers = m.tracers
    if frame.f_globals is not m.globals:                # a clone of M_T: credits nothing
        for t in tracers:
            t._clone_called.add(id(code))
        return
    found, cut, f = [], False, frame.f_back
    while f is not None:
        if f.f_code is _STOP:
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
            _bump(t._uncredited_for(tid)[0 if cut else 1], names)


def _defined_in(obj, module_globals) -> bool:
    """Provenance: *obj* itself (a function) or a link of its own-``__dict__`` ``__wrapped__``
    chain has ``__globals__ is module_globals``. The walk steps only through functions and C cache
    wrappers, follows at most _MAX_HOPS links, is cycle-detected, and never calls getattr or any
    user code. ``__globals__`` rather than ``__module__``: the latter is a writable string that
    anyone can set and functools.wraps copies; ``__globals__`` is fixed when a function is made."""
    seen, hops = set(), 0
    while True:
        kind = type(obj)
        if kind is types.FunctionType:
            if obj.__globals__ is module_globals:
                return True
        elif kind is not _CACHE_WRAPPER:
            return False
        if hops >= _MAX_HOPS or id(obj) in seen:
            return False
        seen.add(id(obj))
        try:
            d = object.__getattribute__(obj, "__dict__")
        except Exception:                                           # noqa: BLE001
            return False
        if type(d) is not dict:
            return False
        obj = dict.get(d, "__wrapped__")
        hops += 1


def _where(fn) -> str:
    g = fn.__globals__
    name = dict.get(g, "__name__") if issubclass(type(g), dict) else None
    code = fn.__code__
    return f"module {name!r} ({code.co_filename}:{code.co_firstlineno})"


def _resolve_target(target: str):
    """``"module:Q.u.a.l"`` -> F_T, the one function whose minted code will identify the target,
    or a refusal. Runs no user code beyond the import and a module's own PEP 562 __getattr__."""
    mod_name, qual = target.split(":", 1)
    try:
        mod = importlib.import_module(mod_name)
    except Exception as e:                                          # noqa: BLE001
        # Round 1 D2: an import-time RuntimeError / SyntaxError escaped as itself.
        raise GateSpecError(
            f"[V5:UNRESOLVED] declared target {target!r}: importing {mod_name!r} raised "
            f"{type(e).__name__}: {e} -- a declaration naming nothing would read as unexercised "
            f"forever, or as a typo nobody notices") from e
    obj, holder = mod, None
    for i, part in enumerate(qual.split(".")):
        if issubclass(type(obj), types.ModuleType):
            if i > 0:
                raise GateSpecError(
                    f"[V5:INSTANCE_PATH] declared target {target!r}: {part!r} is reached through "
                    f"the module {obj.__name__!r} after the colon -- put the full module path "
                    f"before the colon ({obj.__name__}:...)")
            ns = vars(obj)
            if part in ns:
                obj, holder = ns[part], ns
            elif "__getattr__" in ns:                               # PEP 562
                try:
                    obj = ns["__getattr__"](part)
                except Exception as e:                              # noqa: BLE001
                    raise GateSpecError(
                        f"[V5:UNRESOLVED] declared target {target!r}: module {mod_name!r} has no "
                        f"{part!r} and its __getattr__ raised {type(e).__name__}: {e}") from e
                holder = None
            else:
                raise GateSpecError(
                    f"[V5:UNRESOLVED] declared target {target!r}: module {mod_name!r} has no "
                    f"attribute {part!r} and no module __getattr__. If {mod_name}.{part} is a "
                    f"submodule it is not imported by {mod_name!r}: declare it as "
                    f"\"{mod_name}.{part}:...\"")
        elif issubclass(type(obj), type):
            ns = vars(obj)
            if part in ns:
                obj, holder = ns[part], ns
            elif any(part in vars(k) for k in obj.__mro__[1:]):
                # Round 1 N2: getattr follows the MRO, so "Sub.fit" silently meant Base.fit.
                raise GateSpecError(
                    f"[V5:INHERITED] declared target {target!r}: {part!r} is inherited by "
                    f"{obj.__qualname__}, not defined in its own __dict__ -- any subclass calling it "
                    f"would satisfy this declaration. Declare the defining class.")
            else:
                raise GateSpecError(
                    f"[V5:UNRESOLVED] declared target {target!r}: class {obj.__qualname__} has no "
                    f"attribute {part!r} in its own __dict__ or in any base's")
        else:
            # Round 2 R2-D1 / round 3 nit: an instance step reads the instance's OWN __dict__
            # only (SimpleNamespace, registry objects); never getattr, never __getattr__.
            try:
                d = object.__getattribute__(obj, "__dict__")
            except Exception:                                       # noqa: BLE001
                d = None
            if type(d) is not dict or part not in d:
                cls = type(obj)
                raise GateSpecError(
                    f"[V5:INSTANCE_PATH] declared target {target!r}: {part!r} is not in the own "
                    f"__dict__ of the {cls.__qualname__} instance it is reached through -- an "
                    f"attribute read through an instance comes from its class; declare the class "
                    f"({cls.__module__}:{cls.__qualname__}.{part})")
            obj, holder = d[part], d
    if issubclass(type(obj), (staticmethod, classmethod)):
        obj = obj.__func__
    if type(obj) is types.FunctionType:
        fn = obj                        # nothing is unwrapped: a wraps wrapper IS the target
    elif type(obj) is _CACHE_WRAPPER:
        try:
            d = object.__getattribute__(obj, "__dict__")
        except Exception:                                           # noqa: BLE001
            d = None
        body = dict.get(d, "__wrapped__") if type(d) is dict else None
        if type(body) is not types.FunctionType:
            raise GateSpecError(
                f"[V5:NOT_A_FUNCTION] declared target {target!r} is a C cache wrapper whose "
                f"__wrapped__ is a {type(body).__name__}, not a Python function -- there is no "
                f"code object to mint. Declare the Python function that calls it instead.")
        spaces = [vars(mod)] + ([holder] if holder is not None else [])
        also = sorted({k for ns in spaces for k, v in ns.items() if v is body})
        if also:
            raise GateSpecError(
                f"[V5:NOT_A_FUNCTION] declared target {target!r} is a cache wrapper whose body is "
                f"also bound as {also} -- calls of that name would run the body as this target; "
                f"declare that name instead")
        fn = body                       # the target is the cached body: misses count, hits do not
    else:
        raise GateSpecError(
            f"[V5:NOT_A_FUNCTION] declared target {target!r} resolves to a "
            f"{type(obj).__qualname__}, not a Python function (declarable: a function, a "
            f"staticmethod or classmethod of one, or a C lru_cache/cache wrapper through its "
            f"body). Declare the Python function that does the work instead.")
    if not _defined_in(obj, vars(mod)):
        raise GateSpecError(
            f"[V5:FOREIGN_DEFINITION] declared target {target!r}: its code was defined in "
            f"{_where(fn)}, and no link of its own __wrapped__ chain was defined in {mod_name!r} "
            f"-- a stub, mock or re-export bound at this name before the trace is not the "
            f"declared function. Declare the defining module, or install stubs inside the trace.")
    return fn


def _note_lazy(o, result) -> None:
    """The one LAZY_RESULT site, shared by run and run_async."""
    if type(result) in _LAZY_TYPES:
        o.notes.append(
            f"[V5:LAZY_RESULT] section {o.section!r}: the section's function returned a "
            f"{type(result).__name__}, whose body runs after the section closed -- await a "
            f"coroutine function through run_async, or consume the generator inside the section")


class _CoverageTracer:
    """Records calls to declared targets, credited to the opening whose anchor is on their stack."""

    def __init__(self, experiment: "Experiment"):
        if not isinstance(experiment, Experiment):
            raise TypeError("coverage_trace() takes the Experiment whose frozen gates block "
                            "declares the targets -- never a caller-supplied list")
        if not experiment.coverage_targets:
            raise GateSpecError(
                "[V5:NOTHING_DECLARED] no gate in this prereg declares 'exercises' -- a coverage "
                "trace with nothing declared would record nothing and could be mistaken for a "
                "check that passed")
        self._exp = experiment
        self._state = "new"             # new -> active -> exiting -> exited
        self._by_code: dict = {}        # id(M) -> tuple(declared names); emptied first at exit
        self._prov: dict = {}           # declared name -> "co_filename:co_firstlineno"
        self._mints: list = []          # [(_Mint, names)] this tracer holds
        self._openings: list = []
        self._problems: list = []
        self._clone_called: set = set()
        self._uncredited: dict = {}     # tid -> (dispatched{}, unattributed{}); one writer per tid

    def _fail(self, msg: str):
        """Refuse with *msg*, recording it in the trace if this tracer was ever entered. Every
        caller passes a message that begins with its own literal [V5:CODE]."""
        if self._state != "new":
            self._problems.append(msg)
        raise GateSpecError(msg)

    def _uncredited_for(self, tid):
        u = self._uncredited.get(tid)
        if u is None:
            u = self._uncredited.setdefault(tid, ({}, {}))
        return u

    # -- lifecycle ------------------------------------------------------------------------------

    def __enter__(self):
        global _STOP, _ACTIVE
        if self._state != "new":
            self._fail(
                f"[V5:REENTRY] this coverage_trace was already entered (state: {self._state}) -- a "
                f"tracer is entered exactly once; nested or repeated use needs a second tracer")
        import asyncio.events
        # Resolve every target, then touch anything (a refusal mints nothing).
        groups: dict = {}                            # id(F_T) -> [F_T, [names]]; aliases share
        prov = {}
        for t in self._exp.coverage_targets:
            fn = _resolve_target(t)
            groups.setdefault(id(fn), [fn, []])[1].append(t)
            prov[t] = f"{fn.__code__.co_filename}:{fn.__code__.co_firstlineno}"
        with _LOCK:
            for fn, names in groups.values():
                m = _BY_FN.get(id(fn))
                if m is not None and m.fn is fn and fn.__code__ is not m.code:
                    raise GateSpecError(
                        f"[V5:CODE_SWAPPED] declared target(s) {names}: an enclosing trace minted "
                        f"{fn.__qualname__}'s code, and {fn.__qualname__}.__code__ is no longer that "
                        f"code -- it was replaced during the enclosing trace (hot reload, a harness "
                        f"swap), so its frames can no longer be identified")
            for fn, names in groups.values():
                m = _BY_FN.get(id(fn))
                if m is None or m.fn is not fn:
                    original = fn.__code__
                    m = _Mint(fn, original, original.replace(), fn.__globals__)
                    fn.__code__ = m.code
                    _MINTED[id(m.code)] = m
                    _BY_FN[id(fn)] = m
                m.tracers = m.tracers + (self,)
                names = tuple(sorted(names))
                self._mints.append((m, names))
                self._by_code[id(m.code)] = names
            self._prov = prov
            _STOP = asyncio.events.Handle._run.__code__
            _ACTIVE += 1
            self._state = "active"
        return self

    def __exit__(self, exc_type, exc, tb):
        global _ACTIVE
        with _LOCK:
            if self._state != "active":
                return False
            # 1. stop credit first
            self._state = "exiting"
            _ACTIVE -= 1
            self._by_code = {}
            # 2. detach every still-open opening
            for o in self._openings:
                if o.frame is None:
                    continue
                o.notes.append(
                    f"[V5:OPEN_AT_EXIT] section {o.section!r} was still open when the tracer "
                    f"exited; only the calls made before the exit were counted")
                _ANCHORS.pop(id(o.frame), None)
                o.frame = None
                o.end = "open"
                st = _THREADS.get(o.tid)
                if st is not None:
                    st[0] -= 1
                    if st[0] <= 0:
                        del _THREADS[o.tid]
            # 3. clones that ran the minted code under foreign globals
            for m, names in self._mints:
                if id(m.code) in self._clone_called:
                    self._problems.append(
                        f"[V5:CLONE_CALLED] declared target(s) {list(names)}: the minted code ran "
                        f"with globals other than the declared function's (FunctionType(T.__code__, "
                        f"other) or exec(T.__code__, other)) -- a clone executed the declared code, "
                        f"and those calls were credited to nothing")
            # 4. release each mint: swap check, restore, unregister, clone scan
            for m, names in self._mints:
                m.tracers = tuple(t for t in m.tracers if t is not self)
                if m.fn.__code__ is not m.code:
                    self._problems.append(
                        f"[V5:CODE_SWAPPED] declared target(s) {list(names)}: at exit "
                        f"{m.fn.__qualname__}.__code__ is not the code minted at entry -- it was "
                        f"replaced during the trace (hot reload, a harness swap, another "
                        f"function's code), so what ran as it after the swap is unknown")
                elif not m.tracers:
                    m.fn.__code__ = m.original
                if not m.tracers:
                    if _MINTED.get(id(m.code)) is m:
                        del _MINTED[id(m.code)]
                    if _BY_FN.get(id(m.fn)) is m:
                        del _BY_FN[id(m.fn)]
                # refs to M: the argument, the mint, and F_T while it is still installed
                if sys.getrefcount(m.code) - 2 - (m.fn.__code__ is m.code) > 0:
                    holders = sorted({r.__qualname__ for r in gc.get_referrers(m.code)
                                      if type(r) is types.FunctionType and r is not m.fn})
                    if holders:
                        self._problems.append(
                            f"[V5:CLONE_ALIVE] declared target(s) {list(names)}: at exit another "
                            f"live function holds the minted code ({holders}) -- a same-globals "
                            f"clone made during the trace is credited as the declared function")
            # 5. the last tracer out removes this thread's hook
            if _ACTIVE == 0 and sys.getprofile() is _hook:
                sys.setprofile(None)
            self._mints = []
            self._state = "exited"
        return False

    # -- sections -------------------------------------------------------------------------------

    def _open(self, section, anchor):
        with _LOCK:
            if self._state != "active":
                self._fail(
                    f"[V5:TRACE_INACTIVE] section {section!r} opened on a coverage_trace that is "
                    f"not active (state: {self._state}) -- sections open only between the "
                    f"tracer's __enter__ and __exit__")
            if type(section) is not str or section not in self._exp.coverage_sections:
                self._fail(
                    f"[V5:UNDECLARED_SECTION] section {section!r} is not declared by any gate "
                    f"(declared: {self._exp.coverage_sections}) -- calls recorded under it could "
                    f"never count, so opening it is refused before the work runs")
            f = anchor.f_back
            while f is not None:
                if f.f_code is _STOP:
                    break
                o = _ANCHORS.get(id(f))
                if o is not None and o.frame is f and o.tracer is self:
                    self._fail(
                        f"[V5:NESTED_SECTION] section {section!r} opened on a stack on which "
                        f"section {o.section!r} of the same coverage_trace is open -- one call "
                        f"would be credited to two openings. Open each section on its own stack "
                        f"(a second tracer may nest).")
                f = f.f_back
            prof = sys.getprofile()
            if prof is not None and prof is not _hook:
                self._fail(
                    f"[V5:FOREIGN_PROFILER] a {type(prof).__name__} is installed as this thread's "
                    f"sys.setprofile profiler; it is never called, chained, restored or replaced, "
                    f"so section {section!r} cannot open here. Run the traced harness outside it "
                    f"(settrace tools such as coverage.py and pdb are unaffected).")
            tid = _get_ident()
            st = _THREADS.setdefault(tid, [0, 0])
            if sys.getprofile() is None:
                st[1] = next(_EPOCH)
                sys.setprofile(_hook)
            st[0] += 1
            o = _Opening(self, section, anchor, tid, st[1])
            self._openings.append(o)
            _ANCHORS[id(anchor)] = o                   # registration is the last statement
        return o

    def _close(self, o, end):
        """Deregister first, then record the end. Never raises."""
        with _LOCK:
            if o.frame is None:                        # detached by the tracer's exit
                return
            _ANCHORS.pop(id(o.frame), None)
            o.frame = None
            tid = _get_ident()
            st = _THREADS.get(o.tid)
            if tid != o.tid:
                o.notes.append(
                    f"[V5:THREAD_HOP] section {o.section!r} opened on thread {o.tid} and closed on "
                    f"thread {tid}; calls made while it ran away from its opening thread may not "
                    f"have been observed")
            elif sys.getprofile() is not _hook or st is None or st[1] != o.epoch:
                o.notes.append(
                    f"[V5:PROFILER_LOST] section {o.section!r}: the styxx profile hook was lost on "
                    f"its thread while it was open (replaced by sys.setprofile, or dropped by "
                    f"CPython after an exception raised inside it, e.g. a signal handler's or a "
                    f"RecursionError); calls after the loss were not observed")
            if st is not None:
                st[0] -= 1
                if st[0] <= 0:
                    del _THREADS[o.tid]
                    if tid == o.tid and sys.getprofile() is _hook:
                        sys.setprofile(None)
            o.end = end

    def run(self, section, fn, /, *args, **kwargs):
        """Run ``fn(*args, **kwargs)`` as one opening of *section*; this call's frame is the
        anchor. Only calls on this stack, before any asyncio dispatch frame, are credited."""
        o = self._open(section, sys._getframe())
        end = "raised"
        try:
            result = fn(*args, **kwargs)
            end = "returned"
        finally:
            self._close(o, end)
        _note_lazy(o, result)
        return result

    async def run_async(self, section, afn, /, *args, **kwargs):
        """``await afn(*args, **kwargs)`` as one opening of *section*; this coroutine's frame is
        the anchor. Run the event loop OUTSIDE the section: asyncio.run(cov.run_async(...))."""
        o = self._open(section, sys._getframe())
        end = "raised"
        try:
            result = await afn(*args, **kwargs)
            end = "returned"
        finally:
            self._close(o, end)
        _note_lazy(o, result)
        return result

    # -- the trace ------------------------------------------------------------------------------

    def record(self) -> dict:
        """The trace to store in the result under ``coverage_trace``. Takes no lock; only copies."""
        st = self._state
        if st == "new" or st == "active":
            raise GateSpecError(
                f"[V5:TRACE_ACTIVE] record() on a coverage_trace that has not exited (state: "
                f"{st}) -- the trace is complete only after the tracer's __exit__")
        if st != "exited":
            raise GateSpecError(
                "[V5:TRACE_INCOMPLETE] record() after an __exit__ that did not finish (an "
                "exception interrupted it) -- its checks did not all run, so this trace cannot "
                "be scored")
        sections: dict = {}
        for o in list(self._openings):
            sections.setdefault(o.section, []).append(
                {"calls": dict(sorted(o.calls.items())),
                 "ambiguous": dict(sorted(o.ambiguous.items())),
                 "end": o.end, "notes": list(o.notes)})
        dispatched: dict = {}
        unattributed: dict = {}
        for d, u in list(self._uncredited.values()):
            for src, dst in ((d, dispatched), (u, unattributed)):
                for k, v in list(src.items()):
                    dst[k] = dst.get(k, 0) + v
        return {"tracer": _TRACER_ID,
                "gates_sha256": self._exp.gates_sha256,
                "targets": dict(sorted(self._prov.items())),
                "sections": dict(sorted(sections.items())),
                "uncredited": {"dispatched": dict(sorted(dispatched.items())),
                               "unattributed": dict(sorted(unattributed.items()))},
                "problems": list(self._problems)}


# -- scoring helpers (exact-type schema; nothing is read before the whole trace is checked) ----

def _count_dict_problem(where: str, d) -> str | None:
    if type(d) is not dict:
        return f"{where} is a {type(d).__name__}, not a dict"
    for k in d:
        if type(k) is not str:
            return f"{where} has a {type(k).__name__} key {k!r}; its keys are target names (str)"
    return None


def _coded_problem(where: str, s, known) -> str | None:
    if type(s) is not str:
        return f"{where} holds a {type(s).__name__}, not a str"
    m = _CODE_RE.match(s)
    if m is None or m.group(1) not in known:
        return f"{where} holds {s[:80]!r}, which does not begin with a known [V5:CODE]"
    return None


def _trace_schema_problem(tr: dict) -> str | None:
    """The first schema clause *tr* (an exact dict) fails, or None. Every type check is exact."""
    for k in tr:
        if type(k) is not str:
            return f"the trace has a {type(k).__name__} key {k!r}"
    if set(tr) != _TRACE_KEYS:
        return f"the trace's keys are {sorted(tr)}, not exactly {sorted(_TRACE_KEYS)}"
    targets = tr["targets"]
    if type(targets) is not dict:
        return f"targets is a {type(targets).__name__}, not a dict"
    for k, v in targets.items():
        if type(k) is not str or type(v) is not str:
            return (f"targets must map str to str; it maps a {type(k).__name__} {k!r} to a "
                    f"{type(v).__name__}")
    sections = tr["sections"]
    if type(sections) is not dict:
        return f"sections is a {type(sections).__name__}, not a dict"
    for s, ops in sections.items():
        if type(s) is not str:
            return f"sections has a {type(s).__name__} key {s!r}"
        if type(ops) is not list:
            return f"section {s!r} is a {type(ops).__name__}, not a list of openings"
        if not ops:
            return f"section {s!r} is an empty list; a section in the trace has an opening"
        for i, o in enumerate(ops):
            where = f"opening {i} of section {s!r}"
            if type(o) is not dict:
                return f"{where} is a {type(o).__name__}, not a dict"
            for k in o:
                if type(k) is not str:
                    return f"{where} has a {type(k).__name__} key {k!r}"
            if set(o) != _OPENING_KEYS:
                return f"{where} has keys {sorted(o)}, not exactly {sorted(_OPENING_KEYS)}"
            end = o["end"]
            if type(end) is not str or end not in _ENDS:
                return f"{where} has end {end!r}, not one of {list(_ENDS)}"
            notes = o["notes"]
            if type(notes) is not list:
                return f"{where}'s notes is a {type(notes).__name__}, not a list"
            for n in notes:
                why = _coded_problem(f"{where}'s notes", n, _NOTE_CODES)
                if why is not None:
                    return why
            for k in ("calls", "ambiguous"):
                why = _count_dict_problem(f"{where}'s {k}", o[k])
                if why is not None:
                    return why
    unc = tr["uncredited"]
    if type(unc) is not dict:
        return f"uncredited is a {type(unc).__name__}, not a dict"
    for k in unc:
        if type(k) is not str:
            return f"uncredited has a {type(k).__name__} key {k!r}"
    if set(unc) != _UNCREDITED_KEYS:
        return f"uncredited has keys {sorted(unc)}, not exactly {sorted(_UNCREDITED_KEYS)}"
    for k in ("dispatched", "unattributed"):
        why = _count_dict_problem(f"uncredited.{k}", unc[k])
        if why is not None:
            return why
    problems = tr["problems"]
    if type(problems) is not list:
        return f"problems is a {type(problems).__name__}, not a list"
    for p in problems:
        why = _coded_problem("problems", p, _PROBLEM_CODES)
        if why is not None:
            return why
    return None


def _bad_count(tr: dict, declared) -> str | None:
    """The first count anywhere in a schema-valid trace whose key is not a declared target or whose
    value is not an int >= 1 (bool refused), or None."""
    where = []
    for s, ops in tr["sections"].items():
        for i, o in enumerate(ops):
            where.append((f"opening {i} of section {s!r}: calls", o["calls"]))
            where.append((f"opening {i} of section {s!r}: ambiguous", o["ambiguous"]))
    for k in ("dispatched", "unattributed"):
        where.append((f"uncredited.{k}", tr["uncredited"][k]))
    for label, d in where:
        for k, v in d.items():
            if k not in declared or type(v) is not int or v < 1:
                return f"{label} holds {k!r}: {v!r}"
    return None


def coverage_trace(experiment: "Experiment") -> _CoverageTracer:
    """Trace a harness against the targets its frozen prereg declares (protocol v5e).

    ::

        exp = Experiment("PREREG_x.md")
        with coverage_trace(exp) as cov:
            res["degenerate_refusal_rate"] = cov.run("G4_refuses_degenerate", battery, rng)
            # coroutines: asyncio.run(cov.run_async("G5", main))  -- the loop runs OUTSIDE
        res["coverage_trace"] = cov.record()
        exp.score(res)       # refuses if a declared target never ran on a section's own stack

    Targets resolve at ``__enter__``: a declaration naming nothing, a non-function, or a function
    defined outside the declared module refuses before any work runs, and nothing is minted.
    A call is credited to an opening only when that opening's ``cov.run`` frame (or
    ``cov.run_async`` coroutine) is on the call's own stack, above asyncio's dispatch frame; work on
    other threads, pools, executors or asyncio tasks counts only in a section that work opens
    itself.
    """
    return _CoverageTracer(experiment)
