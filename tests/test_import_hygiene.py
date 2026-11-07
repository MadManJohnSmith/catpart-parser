"""The stdlib-only constraint on the package core (ADR-0002, ticket #11).

Acceptance criterion: "Core modules import nothing outside the standard
library." This is a packaging constraint, not one of Spec A's two behavior
seams, so it is pinned statically: every ``src/catpart`` module's AST may
only import standard-library modules or the package itself. A
byte-compiled check (as opposed to importing and introspecting
``sys.modules``) sees the declared imports of every module, including
ones a test run never executes.

The second test feeds the checker a violating synthetic module, proving
the guard can fail (it is not a check that passes by construction).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC_CATPART = Path(__file__).resolve().parents[1] / "src" / "catpart"

_ALLOWED_ROOTS = frozenset(sys.stdlib_module_names) | {"catpart"}


def nonstdlib_roots(source: str) -> set[str]:
    """Root modules of absolute imports outside :data:`_ALLOWED_ROOTS`.

    Relative imports (``from . import x``) are intra-package by
    definition and never reported.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(
                alias.name.split(".")[0]
                for alias in node.names
                if alias.name.split(".")[0] not in _ALLOWED_ROOTS
            )
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            root = node.module.split(".")[0]
            if root not in _ALLOWED_ROOTS:
                roots.add(root)
    return roots


def test_core_imports_are_stdlib_only() -> None:
    offenders = {
        f"{path.relative_to(SRC_CATPART)}: {sorted(roots)}"
        for path in sorted(SRC_CATPART.rglob("*.py"))
        if (roots := nonstdlib_roots(path.read_text(encoding="utf-8")))
    }
    assert not offenders, f"non-stdlib imports in core: {offenders}"


def test_checker_flags_nonstdlib_import(tmp_path: Path) -> None:
    violating = tmp_path / "violating.py"
    violating.write_text("import requests\nfrom os.path import join\n", encoding="utf-8")
    assert nonstdlib_roots(violating.read_text(encoding="utf-8")) == {"requests"}
