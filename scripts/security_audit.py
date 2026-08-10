"""Audit production source for capabilities outside the trusted-input boundary."""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

# Modules that provide ambient execution, connectivity, or unsafe object loading.
FORBIDDEN_MODULES = frozenset(
    {"ast", "http", "importlib", "marshal", "pickle", "socket", "subprocess", "urllib"}
)
# Builtins that dynamically compile, execute, or import Python source.
FORBIDDEN_CALLS = frozenset({"__import__", "compile", "eval", "exec"})


def audit_source(source: str, path: Path) -> tuple[str, ...]:
    """Return deterministic capability findings for one Python source.

    :param source: Complete Python source text.
    :param path: Display path used in findings.
    :returns: Ordered policy diagnostics.
    :raises SyntaxError: If *source* is invalid Python.
    """
    tree = ast.parse(source, filename=str(path))
    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.partition(".")[0]
                if root in FORBIDDEN_MODULES:
                    findings.append((node.lineno, f"forbidden import: {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").partition(".")[0]
            if root in FORBIDDEN_MODULES:
                findings.append((node.lineno, f"forbidden import: {node.module}"))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FORBIDDEN_CALLS
        ):
            findings.append((node.lineno, f"forbidden call: {node.func.id}"))
    return tuple(
        f"{path.as_posix()}:{line}: {message}"
        for line, message in sorted(findings, key=lambda item: (item[0], item[1]))
    )


def audit_package(root: Path) -> tuple[str, ...]:
    """Return capability findings for all Python modules beneath a package.

    :param root: Production package directory.
    :returns: Findings ordered by source path and line.
    :raises OSError: If a source file cannot be read.
    :raises SyntaxError: If a source file is invalid Python.
    """
    return tuple(
        finding
        for path in sorted(root.rglob("*.py"))
        for finding in audit_source(path.read_text(encoding="utf-8"), path)
    )


def main(argv: list[str] | None = None) -> int:
    """Run the production capability audit.

    :param argv: Optional command-line arguments.
    :returns: Zero when no forbidden capability is present.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("src/lclang"))
    options = parser.parse_args(argv)
    findings = audit_package(options.root)
    for finding in findings:
        print(finding)
    return int(bool(findings))


if __name__ == "__main__":
    sys.exit(main())
