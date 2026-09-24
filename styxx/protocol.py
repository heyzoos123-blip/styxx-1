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
import contextvars
import gc
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
# fullmatch, not ^...$: "$" also matches before a trailing newline (red team round 1, N2).
_TARGET_RE = re.compile(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*:[A-Za-z_]\w*(\.[A-Za-z_]\w*)*",
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
        """Refuse a declaring gate unless the trace shows every declared target called in its
        section. Returns {target: calls} for the gate. Everything ill-formed refuses: a trace that
        can be half-read is a trace that can be half-forged. Every message leads with a stable
        ``[V5:CODE]`` so an exam can tell which check refused (red team round 1: a mutant that
        refuses for a later, different reason never tested the check it names).
        """
        c = self.coverage[name]
        tr = result.get(_TRACE_KEY) if isinstance(result, dict) else None
        if not isinstance(tr, dict):
            raise GateSpecError(
                f"[V5:NO_TRACE] gate {name!r} declares 'exercises' but the result carries no "
                f"{_TRACE_KEY!r} — run the harness inside styxx.protocol.coverage_trace() and "
                f"store its record(). A declared coverage with no trace is unverified, not met.")
        if tr.get("tracer") != _TRACER_ID:
            raise GateSpecError(
                f"[V5:WRONG_TRACER] gate {name!r}: {_TRACE_KEY}.tracer is {tr.get('tracer')!r}, "
                f"not {_TRACER_ID!r} — this trace was not written by the machinery that can be "
                f"read")
        if tr.get("gates_sha256") != self.gates_sha256:
            raise GateSpecError(
                f"[V5:STALE_TRACE] gate {name!r}: the coverage trace was taken against gates "
                f"block {str(tr.get('gates_sha256'))[:12]}…, not this one "
                f"({self.gates_sha256[:12]}…). A trace of a different declaration is not "
                f"evidence about this one.")
        targets, sections = tr.get("targets"), tr.get("sections")
        for label, d in (("targets", targets), ("sections", sections)):
            if not isinstance(d, dict) or not all(isinstance(k, str) for k in d):
                raise GateSpecError(
                    f"[V5:BAD_TRACE] gate {name!r}: {_TRACE_KEY}.{label} must be a dict with "
                    f"string keys")
        if sorted(targets) != self.coverage_targets:
            raise GateSpecError(
                f"[V5:TARGET_SET] gate {name!r}: the trace's target set {sorted(targets)} "
                f"differs from the declared set {self.coverage_targets} — it recorded something "
                f"other than what the frozen document asks about")
        sec = sections.get(c["section"])
        if sec is None:
            raise GateSpecError(
                f"[V5:SECTION_ABSENT] gate {name!r}: section {c['section']!r} is absent from the "
                f"trace — the harness never opened it, so nothing it ran can be attributed to "
                f"this gate")
        if not isinstance(sec, dict) or not all(isinstance(k, str) for k in sec):
            raise GateSpecError(
                f"[V5:BAD_TRACE] gate {name!r}: section {c['section']!r} must be a dict with "
                f"string keys")
        for t, n in sec.items():
            if t not in targets or isinstance(n, bool) or not isinstance(n, int) or n < 1:
                raise GateSpecError(
                    f"[V5:BAD_COUNT] gate {name!r}: section {c['section']!r} holds {t!r}: {n!r}; "
                    f"the tracer writes only declared targets with positive integer call counts")
        missing = [t for t in c["exercises"] if t not in sec]
        if missing:
            raise GateSpecError(
                f"[V5:NOT_EXERCISED] gate {name!r}: COVERAGE VIOLATION — the harness never "
                f"executed {missing} in section {c['section']!r} (it did execute "
                f"{sorted(sec) or 'none of them'}). The metric was produced without running what "
                f"the gate names. This is the P1 defect (cycle 158): G4 scored 1.0 while its "
                f"harness touched one of five entry points.")
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
#
# Round 1 of the red team (protocol_v5_redteam_audit.json) broke the first version four ways, and
# each repair below names the break it closes. Code objects are matched by IDENTITY, not
# equality; a code object shared by several functions cannot be declared; the open section is
# per execution context, not per process; foreign profilers and out-of-order use refuse.

_THREAD_START_CODE = threading.Thread.start.__code__
_EMPTY = object()


def _code_holders(code) -> list:
    return [r for r in gc.get_referrers(code) if isinstance(r, types.FunctionType)]


def _wrappers_of(fn) -> list:
    """Functions whose ``__wrapped__`` is *fn* (functools.wraps). Two hops: the wrapper's
    ``__dict__`` refers to fn, and the wrapper refers to that dict."""
    out = []
    for d in gc.get_referrers(fn):
        if isinstance(d, dict) and d.get("__wrapped__") is fn:
            out.extend(r for r in gc.get_referrers(d)
                       if isinstance(r, types.FunctionType) and r.__dict__ is d)
    return out


def _sharing_problem(target: str, fn, code) -> str | None:
    holders = _code_holders(code)
    if len(holders) > 1:
        return (f"[V5:SHARED_CODE] declared target {target!r}: its code object is shared by "
                f"{len(holders)} live functions ({sorted({h.__qualname__ for h in holders})}), "
                f"so a call to any of them is indistinguishable from a call to it. Declare a "
                f"function with its own code (a decorator without functools.wraps, or a factory, "
                f"cannot be declared through).")
    wrappers = _wrappers_of(fn)
    if len(wrappers) > 1:
        # Round 2 R2-D2: run_fast and run_safe both @functools.wraps(_run); declaring run_fast
        # unwrapped to _run, and calling only run_safe satisfied it.
        return (f"[V5:SHARED_CODE] declared target {target!r} unwraps to {fn.__qualname__}, "
                f"which {len(wrappers)} wrappers share "
                f"({sorted({w.__qualname__ for w in wrappers})}) — a call through any of them "
                f"reaches the same code. Declare the inner function's callers individually "
                f"only if each has its own code.")
    return None


def _resolve_target(target: str):
    """``"module:qualname"`` -> (function, code) for the one function that runs when it is
    called, or a refusal."""
    mod_name, qual = target.split(":", 1)
    try:
        obj = importlib.import_module(mod_name)
        for part in qual.split("."):
            if isinstance(obj, type):
                # Round 1 N2: getattr follows the MRO, so "Sub.fit" silently meant Base.fit and
                # Other().fit() satisfied it. A class step must name the class's OWN attribute.
                if part not in vars(obj):
                    if any(part in vars(k) for k in obj.__mro__[1:]):
                        raise GateSpecError(
                            f"[V5:INHERITED] declared target {target!r}: {part!r} is inherited by "
                            f"{obj.__qualname__}, not defined on it — any subclass calling it "
                            f"would satisfy this declaration. Declare the defining class.")
                    raise AttributeError(f"{obj.__qualname__} has no attribute {part!r}")
                obj = vars(obj)[part]
            elif isinstance(obj, types.ModuleType):
                obj = inspect.getattr_static(obj, part)
            else:
                # Round 2 R2-D1: "default_model.fit" stepped through an instance into the MRO
                # and reached Base.fit, reopening the INHERITED hole by another door.
                raise GateSpecError(
                    f"[V5:INSTANCE_PATH] declared target {target!r}: {part!r} is reached through "
                    f"a {type(obj).__name__}, not a module or class — an instance's attribute is "
                    f"whatever its class hierarchy says today. Declare the defining class.")
        if isinstance(obj, (staticmethod, classmethod)):
            obj = obj.__func__
        if callable(obj):
            obj = inspect.unwrap(obj)
    except GateSpecError:
        raise
    except Exception as e:
        # Round 1 D2: an import-time RuntimeError/SyntaxError or a __wrapped__ loop escaped as
        # itself. Anything that stops resolution is a refusal, with the cause attached.
        raise GateSpecError(
            f"[V5:UNRESOLVED] declared target {target!r} does not resolve "
            f"({type(e).__name__}: {e}) — a declaration naming nothing would read as "
            f"unexercised forever, or worse, as a typo nobody notices") from e
    code = getattr(obj, "__code__", None)
    if not isinstance(code, types.CodeType) or not isinstance(obj, types.FunctionType):
        raise GateSpecError(
            f"[V5:NO_CODE] declared target {target!r} resolves to {type(obj).__name__}, which has "
            f"no Python code object to observe (builtins, C extensions and properties cannot be "
            f"traced). Declare the Python function that calls it instead.")
    gc.collect()      # round 2 nit: dead-but-uncollected closures must not count as holders
    problem = _sharing_problem(target, obj, code)
    if problem:
        raise GateSpecError(problem)
    return obj, code


def _identity(fn):
    """What a frame running *fn* itself — not another function sharing its code — must show."""
    cells = []
    for c in fn.__closure__ or ():
        try:
            cells.append(c.cell_contents)
        except ValueError:
            cells.append(_EMPTY)
    return fn.__globals__, fn.__code__.co_freevars, tuple(cells)


class _Hook:
    """The installed profile function. A class, so a nested tracer can recognise and chain it."""
    __slots__ = ("tracer", "prev")

    def __init__(self, tracer, prev):
        self.tracer, self.prev = tracer, prev

    def __call__(self, frame, event, arg):
        t = self.tracer
        if t._exited:
            # Round 2 R2-B3: threads started during the trace kept this inert hook for life.
            # The first event after exit removes it from whichever thread is running it.
            nxt = _skip_exited(self.prev)
            if sys.getprofile() is self:
                sys.setprofile(nxt)
            if nxt is not None:
                nxt(frame, event, arg)
            return
        if event == "call" and t._active:
            try:
                t._on_call(frame)
            except Exception:
                # Round 2 R2-D4: an exception escaping a profile function makes CPython drop
                # the profiler; the section then refused with the wrong reason. Caught here, the
                # hook stays installed and the section refuses HOOK_FAILED instead.
                t._hook_failed = True
        if self.prev is not None:
            self.prev(frame, event, arg)


def _skip_exited(h):
    """Never reinstall the hook of a tracer that has already exited (round 1 D1)."""
    while isinstance(h, _Hook) and h.tracer._exited:
        h = h.prev
    return h


def _thread_profile():
    return (threading.getprofile() if hasattr(threading, "getprofile")
            else getattr(threading, "_profile_hook", None))


class _CoverageTracer:
    """Records calls to declared targets, attributed to their open section."""

    def __init__(self, experiment: "Experiment"):
        if not isinstance(experiment, Experiment):
            raise TypeError("coverage_trace() takes the Experiment whose frozen gates block "
                            "declares the targets — never a caller-supplied list")
        if not experiment.coverage_targets:
            raise GateSpecError(
                "[V5:NOTHING_DECLARED] no gate in this prereg declares 'exercises' — a coverage "
                "trace with nothing declared would record nothing and could be mistaken for a "
                "check that passed")
        self._exp = experiment
        self._codes: dict = {}      # id(code) -> (code, [targets], identity); the ref pins the id
        self._fns: dict = {}        # target -> (fn, code), re-checked at every section close
        self._code_sha: dict = {}
        for t in experiment.coverage_targets:
            fn, code = _resolve_target(t)
            if id(code) in self._codes:
                raise GateSpecError(
                    f"[V5:SHARED_CODE] declared targets {self._codes[id(code)][1] + [t]} resolve "
                    f"to one code object — a single call would count for all of them")
            self._codes[id(code)] = (code, [t], _identity(fn))
            self._fns[t] = (fn, code)
            self._code_sha[t] = hashlib.sha256(marshal.dumps(code)).hexdigest()
        self._lock = threading.Lock()
        self._cv = contextvars.ContextVar(f"styxx_v5_section_{id(self)}", default=None)
        self._thread_section: dict = {}  # Thread -> section open where Thread.start was called
        self._open: dict = {}            # section -> number of open entries
        self._sections: dict = {}
        self._after_close: dict = {}
        self._ambiguous: dict = {}
        self._impostors: dict = {}
        self._unsectioned: dict = {}
        self._close_refusals: list = []
        self._hook_failed = False
        self._active = False
        self._exited = False

    # -- attribution --------------------------------------------------------------------------

    def _effective(self):
        """(section, via) — via is "context" when this context opened it, "thread" when it is
        inherited from where this thread was started."""
        sec = self._cv.get()
        if sec is not None:
            return sec, "context"
        sec = self._thread_section.get(threading.current_thread())
        return sec, "thread" if sec is not None else None

    def _effective_section(self):
        return self._effective()[0]

    def _on_call(self, frame) -> None:
        code = frame.f_code
        if code is _THREAD_START_CODE:
            # Round 1 B3: a thread belongs to the section open where it was STARTED, not to
            # whichever section happens to be open when it later runs.
            th = frame.f_locals.get("self")
            if isinstance(th, threading.Thread):
                with self._lock:
                    self._thread_section[th] = self._effective_section()
        hit = self._codes.get(id(code))
        if hit is None or hit[0] is not code:        # identity, never equality (round 1 B2)
            return
        g, freevars, cells = hit[2]
        genuine = frame.f_globals is g
        if genuine and freevars:
            # Round 2 R2-B1: a function made at runtime from the same code (a decorator without
            # functools.wraps applied later) runs this code object with ITS closure. The call
            # is the declared function's only if the frame's free variables are its objects.
            loc = frame.f_locals
            genuine = all(loc.get(n, _EMPTY) is c for n, c in zip(freevars, cells))
        sec, via = self._effective()
        with self._lock:
            if not genuine:
                bucket = self._impostors.setdefault(sec or "", {})
            elif sec is None:
                bucket = self._unsectioned
            elif self._open.get(sec, 0) <= 0:
                bucket = self._after_close.setdefault(sec, {})
            elif via == "thread" and sum(1 for n in self._open.values() if n > 0) > 1:
                # Round 2 R2-B2: a pool worker started in A, running B's work while both are
                # open, credited A. Inherited attribution counts only when it is unambiguous.
                bucket = self._ambiguous.setdefault(sec, {})
            else:
                bucket = self._sections[sec]
            for t in hit[1]:
                bucket[t] = bucket.get(t, 0) + 1

    # -- lifecycle ----------------------------------------------------------------------------

    def __enter__(self):
        if self._active or self._exited:
            raise GateSpecError(
                "[V5:REENTRY] this coverage_trace is already active or has already exited — a "
                "tracer is entered exactly once; nested use needs a second tracer")
        prev_sys, prev_thr = sys.getprofile(), _thread_profile()
        for where, prev in (("sys", prev_sys), ("threading", prev_thr)):
            if prev is not None and not isinstance(prev, (types.FunctionType, types.MethodType,
                                                          _Hook)):
                # Round 1 B4: a C-level profiler (cProfile) is not callable from Python; chaining
                # it crashed the harness and restoring it destroyed it.
                raise GateSpecError(
                    f"[V5:FOREIGN_PROFILER] a {type(prev).__name__} is installed as the {where} "
                    f"profiler; it cannot be chained or restored from Python. Run the traced "
                    f"harness outside it.")
        self._prev_sys, self._prev_thr = prev_sys, prev_thr
        self._sys_hook, self._thr_hook = _Hook(self, prev_sys), _Hook(self, prev_thr)
        self._active = True
        sys.setprofile(self._sys_hook)
        threading.setprofile(self._thr_hook)
        return self

    def __exit__(self, exc_type, exc, tb):
        self._active = False
        # Ownership is read BEFORE marking the tracer exited: once _exited is set, the next
        # Python-level call reaching the hook removes it (the R2-B3 repair), and this check
        # would then see a profiler it did not install.
        owns_thr = _thread_profile() is self._thr_hook
        owns_sys = sys.getprofile() is self._sys_hook
        self._exited = True
        # Round 2 R2-D5: on every path, stop handing this tracer's hook to new threads.
        if owns_thr:
            threading.setprofile(_skip_exited(self._prev_thr))
        if owns_sys:
            sys.setprofile(_skip_exited(self._prev_sys))
            return False
        if exc_type is not None:
            return False           # never mask the exception already explaining the failure
        raise GateSpecError(
            "[V5:EXIT_ORDER] coverage_trace exited while another profiler is installed — "
            "tracers were exited out of order, or the harness replaced the profiler. Nothing was "
            "restored in this thread; this tracer's hook is inert and removes itself.")

    def _hook_chain_has_self(self) -> bool:
        h = sys.getprofile()
        while isinstance(h, _Hook):
            if h.tracer is self:
                return True
            h = h.prev
        return False

    def _refuse_at_close(self, msg: str):
        with self._lock:
            self._close_refusals.append(msg)
        raise GateSpecError(msg)

    @contextlib.contextmanager
    def section(self, name: str):
        """Attribute every declared-target call made in this context, and in threads started
        from it, to *name* — while it is open."""
        if name not in self._exp.coverage_sections:
            raise GateSpecError(
                f"[V5:UNDECLARED_SECTION] section {name!r} is not declared by any gate "
                f"(declared: {self._exp.coverage_sections}) — calls recorded under it could never "
                f"count, so opening it is refused before the work runs")
        outer = self._effective_section()
        if outer is not None:
            raise GateSpecError(
                f"[V5:NESTED_SECTION] section {name!r} opened inside section {outer!r} — nested "
                f"sections would make one call count for two gates")
        token = self._cv.set(name)
        with self._lock:
            self._open[name] = self._open.get(name, 0) + 1
            self._sections.setdefault(name, {})

        def close() -> bool:
            with self._lock:
                self._open[name] -= 1
            try:
                self._cv.reset(token)
                return True
            except ValueError:
                return False

        try:
            yield self
        except BaseException:
            close()
            raise
        same_context = close()
        if not same_context:
            # Round 2 R2-D6: exited from another Context (an ExitStack or fixture run elsewhere),
            # ContextVar.reset raised ValueError straight through the public API.
            self._refuse_at_close(
                f"[V5:SECTION_CONTEXT] section {name!r} was exited in a different context from "
                f"the one that opened it, so this tracer cannot tell which calls were its own")
        with self._lock:
            alive = [th.name for th, s in self._thread_section.items()
                     if s == name and th.is_alive()]
        if alive:
            self._refuse_at_close(
                f"[V5:THREAD_OUTLIVES] section {name!r} closed with threads started inside it "
                f"still running ({alive}) — their later work could not be told apart from this "
                f"section's. Join them (or shut the pool down) before the section ends.")
        if self._hook_failed:
            self._refuse_at_close(
                f"[V5:HOOK_FAILED] the coverage hook raised while section {name!r} was open "
                f"(e.g. RecursionError at the recursion limit); a call may have gone unrecorded")
        if self._active and not self._hook_chain_has_self():
            self._refuse_at_close(
                f"[V5:PROFILER_REPLACED] section {name!r} closed with this tracer no longer "
                f"installed — the harness replaced the profiler (sys.setprofile, cProfile), or a "
                f"RecursionError raised while CPython was entering the hook made it drop the "
                f"profiler; calls after that point were not observed")
        # Round 2 R2-B1: holders are re-counted at every close, so a function created at runtime
        # from a declared target's code (and still alive) is caught even if never called.
        gc.collect()
        for t, (fn, code) in self._fns.items():
            problem = _sharing_problem(t, fn, code)
            if problem:
                self._refuse_at_close(problem + f" (found at the close of section {name!r})")

    def record(self) -> dict:
        """The trace to store in the result under ``coverage_trace``."""
        def dump(d):
            return {k: dict(sorted(v.items())) for k, v in sorted(d.items())}
        with self._lock:
            return {"tracer": _TRACER_ID,
                    "gates_sha256": self._exp.gates_sha256,
                    "targets": dict(sorted(self._code_sha.items())),
                    "sections": dump(self._sections),
                    "after_close": dump(self._after_close),
                    "ambiguous": dump(self._ambiguous),
                    "impostors": dump(self._impostors),
                    "unsectioned": dict(sorted(self._unsectioned.items())),
                    "close_refusals": list(self._close_refusals),
                    "scope_note": ("calls observed by code-object identity AND frame identity "
                                   "(the declared function's globals and closure) in threads "
                                   "started while tracing, attributed to the section open where "
                                   "the call's context (or its thread's start) began, and "
                                   "counted only while that section is open and, for "
                                   "thread-inherited attribution, the only one open. Not "
                                   "observed: child processes, threads that predate the trace "
                                   "or bypass threading.Thread.start. Target sha256 values are "
                                   "provenance only (marshal includes the file path) and are "
                                   "not checked at scoring.")}


def coverage_trace(experiment: "Experiment") -> _CoverageTracer:
    """Trace a harness against the targets its frozen prereg declares (protocol v5).

    ::

        exp = Experiment("PREREG_x.md")
        with coverage_trace(exp) as cov:
            with cov.section("G4_refuses_degenerate"):
                res["degenerate_refusal_rate"] = run_degenerate_battery()
        res["coverage_trace"] = cov.record()
        exp.score(res)       # refuses if a declared target was never called in its section

    Targets resolve on construction, so a declaration naming nothing — or naming a function
    whose code another function shares — refuses before any work runs. Calls are matched by
    code-object identity through ``sys.setprofile`` (chained to any Python-level profiler
    already installed, so tracers nest) and in threads started while tracing.
    """
    return _CoverageTracer(experiment)
