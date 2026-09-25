"""What the frozen mutation gate cannot see, measured instead of asserted.

The mutation gate (``mutation_gate.py``, frozen with PREREG v5e) promises that every coded
emission in ``styxx/protocol.py`` is a mutation site, and that a refusal it cannot mutate is a
hygiene violation. Both promises are syntactic: a site is a ``raise GateSpecError(<coded literal>)``
or an expression-statement call whose first argument is a coded literal. This script does two
things, neither of which touches the frozen gate:

1. BLIND SHAPES. For each alternative way to emit a coded message, it builds a small toy module
   (with the v5 marker, so the hygiene region exists) and asks the frozen functions whether they
   see it: is it a site, and is it a hygiene violation? A shape that is neither is a blind spot. A
   future implementation could use it by accident and escape both the gate and the check.

2. CENSUS OF THE REAL FILE. It finds every string literal or f-string in ``styxx/protocol.py`` whose
   literal text begins with a complete code ``[V5:<CODE>]`` (at the start, or right after a
   leading space or newline), and checks that each one lies inside a statement the gate mutates. A
   coded literal outside every site is an emission the gate never tested. For the committed
   implementation this count should be zero. The census is exact for literals and blind to codes
   built at run time; the hygiene check covers those only for ``raise GateSpecError``.

Writes ``mutation_gate_blindspots.json``. The reading: the gate's 57/57 is a statement about 57
sites, and this file is the evidence that those 57 are all the coded literals the implementation
contains, not a claim that the gate is complete for any future implementation.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import mutation_gate as mg  # noqa: E402  (the frozen gate; imported, never modified)

IMPL = ROOT / "styxx" / "protocol.py"
OUT = HERE / "mutation_gate_blindspots.json"

HEAD = ("class GateSpecError(ValueError):\n    pass\n\n\n"
        "class Experiment:\n    pass\n\n\n" + mg.MARKER + "\n\n")

# Each shape emits the same refusal in a different syntax. "seen_as" is filled in by the frozen
# functions, never by hand.
SHAPES = {
    "control: raise GateSpecError(literal)":
        "def f(x):\n    if x:\n        raise GateSpecError('[V5:DEMO] refused')\n",
    "control: expression call with literal":
        "def f(self, x):\n    if x:\n        self._refuse('[V5:DEMO] refused')\n",
    "control: raise GateSpecError(non-literal)":
        "def f(x):\n    m = '[V5:DEMO] refused'\n    if x:\n        raise GateSpecError(m)\n",
    "raise via a helper that returns the exception":
        "def _err(m):\n    return GateSpecError(m)\n\n"
        "def f(x):\n    if x:\n        raise _err('[V5:DEMO] refused')\n",
    "raise GateSpecError through a module attribute":
        "import types\nerrors = types.SimpleNamespace(GateSpecError=GateSpecError)\n\n"
        "def f(x):\n    if x:\n        raise errors.GateSpecError('[V5:DEMO] refused')\n",
    "raise an alias of GateSpecError":
        "Refusal = GateSpecError\n\n"
        "def f(x):\n    if x:\n        raise Refusal('[V5:DEMO] refused')\n",
    "recorded problem appended by augmented assignment":
        "def f(self, x):\n    if x:\n        self.problems += ['[V5:DEMO] refused']\n",
    "emission as the value of a return":
        "def f(self, x):\n    if x:\n        return self._refuse('[V5:DEMO] refused')\n",
    "emission assigned to a name":
        "def f(self, x):\n    if x:\n        _ = self._refuse('[V5:DEMO] refused')\n",
    "emission inside a conditional expression":
        "def f(self, x):\n    self._refuse('[V5:DEMO] refused') if x else None\n",
    "code in a keyword argument":
        "def f(self, x):\n    if x:\n        self._refuse(msg='[V5:DEMO] refused')\n",
    "code not at the start of the literal":
        "def f(x):\n    if x:\n        raise GateSpecError('refused: [V5:DEMO]')\n",
}


def _probe(body: str) -> dict:
    src = HEAD + body
    sites = mg.refusal_sites(src)
    hyg = mg.hygiene_violations(src)
    return {"sites": len(sites), "hygiene_violations": len(hyg),
            "blind": not sites and not hyg}


_CODE_AT_START = re.compile(r"\s?\[V5:[A-Z_]+\]")


def _coded_literal(node) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return bool(_CODE_AT_START.match(node.value))
    if isinstance(node, ast.JoinedStr) and node.values:
        first = node.values[0]
        return (isinstance(first, ast.Constant) and isinstance(first.value, str)
                and bool(_CODE_AT_START.match(first.value)))
    return False


def census(src: str) -> dict:
    tree = ast.parse(src)
    sites = mg.refusal_sites(src)
    spans = [(a, b) for a, b, *_ in sites]
    docstrings = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
                docstrings.add(id(n.body[0].value))
    # f-string parts are Constants too; count each f-string once, as a whole.
    inner = {id(v) for n in ast.walk(tree) if isinstance(n, ast.JoinedStr) for v in n.values}
    literals, outside = 0, []
    for n in ast.walk(tree):
        if id(n) in docstrings or id(n) in inner or not _coded_literal(n):
            continue
        literals += 1
        if not any(a <= n.lineno <= b for a, b in spans):
            outside.append({"line": n.lineno,
                            "text": src.split("\n")[n.lineno - 1].strip()[:120]})
    return {"coded_literals": literals, "sites": len(sites),
            "coded_literals_outside_every_site": outside}


def main() -> int:
    shapes = {name: _probe(body) for name, body in SHAPES.items()}
    controls_ok = (shapes["control: raise GateSpecError(literal)"]["sites"] == 1
                   and shapes["control: expression call with literal"]["sites"] == 1
                   and shapes["control: raise GateSpecError(non-literal)"]["hygiene_violations"] == 1)
    src = IMPL.read_text(encoding="utf-8")
    real = census(src)
    blind = sorted(k for k, v in shapes.items() if v["blind"] and not k.startswith("control"))
    out = {
        "what": "shapes of coded emission the frozen mutation gate neither mutates nor flags, "
                "and a census of coded literals in the real implementation",
        "gate_file": "papers/first-afference/mutation_gate.py",
        "gate_sha256": hashlib.sha256((HERE / "mutation_gate.py").read_bytes()).hexdigest(),
        "impl_sha256": hashlib.sha256(src.encode("utf-8")).hexdigest(),
        "controls_ok": controls_ok,
        "shapes": shapes,
        "n_blind_shapes": len(blind),
        "blind_shapes": blind,
        "census": real,
        "n_coded_literals_outside_every_site": len(real["coded_literals_outside_every_site"]),
        "reading": ("The gate's guarantee holds for the implementation it was run on only if the "
                    "census finds no coded literal outside a site. It does not hold for arbitrary "
                    "future implementations: every blind shape listed here would escape both the "
                    "mutation gate and the hygiene check. A successor gate should mutate by coded "
                    "literal (the census), not by statement shape."),
    }
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"controls ok: {controls_ok} | blind shapes {len(blind)}/{len(SHAPES) - 3} | "
          f"census: {real['coded_literals']} coded literals, {real['sites']} sites, "
          f"{len(real['coded_literals_outside_every_site'])} outside every site -> {OUT.name}")
    for k in blind:
        print("  blind:", k)
    for o in real["coded_literals_outside_every_site"]:
        print("  outside:", o)
    return 0 if controls_ok else 1


if __name__ == "__main__":
    sys.exit(main())
