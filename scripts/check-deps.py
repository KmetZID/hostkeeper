#!/usr/bin/env python3
"""Memastikan src/hostkeeper hanya mengimpor stdlib dan PyYAML (SPEC 11)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ALLOWED_PACKAGES = frozenset(sys.stdlib_module_names | {"yaml", "hostkeeper"})


def check_file(path: Path) -> list[str]:
    violations: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".", 1)[0]
                if top not in ALLOWED_PACKAGES:
                    violations.append(f"{path}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                top = node.module.split(".", 1)[0]
                if top not in ALLOWED_PACKAGES:
                    violations.append(
                        f"{path}:{node.lineno}: from {node.module} import ..."
                    )
    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    src_dir = repo_root / "src"
    violations: list[str] = []

    for py_file in src_dir.rglob("*.py"):
        violations.extend(check_file(py_file))

    if violations:
        print(
            "ERROR: Ditemukan dependensi runtime di luar stdlib dan PyYAML:",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        return 1

    print("OK: Tidak ada dependensi runtime terlarang (hanya stdlib dan PyYAML).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
