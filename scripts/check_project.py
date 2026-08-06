"""Check pylcl source-size and exhaustive documentation policies."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

MAX_SOURCE_LINES = 200
ROOT = Path(__file__).resolve().parents[1]
DocumentedNode = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
CallableNode = ast.FunctionDef | ast.AsyncFunctionDef


def _documented_nodes(tree: ast.Module) -> list[DocumentedNode]:
    """Return every declaration governed by the production policy.

    :param tree: Parsed Python module.
    :returns: Module plus every class, function, method, and nested function.

    .. note::
       Source ordering keeps diagnostics deterministic across platforms.
    """
    declarations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    return [tree, *sorted(declarations, key=lambda node: node.lineno)]


def _callable_parameters(node: CallableNode) -> list[str]:
    positional = [*node.args.posonlyargs, *node.args.args]
    names = [argument.arg for argument in [*positional, *node.args.kwonlyargs]]
    if node.args.vararg is not None:
        names.append(node.args.vararg.arg)
    if node.args.kwarg is not None:
        names.append(node.args.kwarg.arg)
    return [name for name in names if name not in {"self", "cls"}]


def _raised_exception_names(node: CallableNode) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Raise) or child.exc is None:
            continue
        expression = child.exc.func if isinstance(child.exc, ast.Call) else child.exc
        if isinstance(expression, ast.Name):
            names.add(expression.id)
        elif isinstance(expression, ast.Attribute):
            names.add(expression.attr)
    return names


def _class_fields(node: ast.ClassDef) -> list[str]:
    return [
        child.target.id
        for child in node.body
        if isinstance(child, ast.AnnAssign)
        and isinstance(child.target, ast.Name)
        and not child.target.id.startswith("_")
    ]


def _rst_failures(node: DocumentedNode, path: Path) -> list[str]:
    if isinstance(node, ast.Module):
        return []
    docstring = ast.get_docstring(node) or ""
    name = node.name
    failures: list[str] = []
    if ".. note::" not in docstring:
        failures.append(f"{path}:{name}: docstring lacks '.. note::'")
    if isinstance(node, ast.ClassDef):
        parameters = _class_fields(node)
    else:
        parameters = _callable_parameters(node)
        if ":returns:" not in docstring:
            failures.append(f"{path}:{name}: docstring lacks ':returns:'")
        for exception in sorted(_raised_exception_names(node)):
            marker = f":raises {exception}:"
            if marker not in docstring:
                failures.append(f"{path}:{name}: docstring lacks '{marker}'")
    for parameter in parameters:
        marker = f":param {parameter}:"
        if marker not in docstring:
            failures.append(f"{path}:{name}: docstring lacks '{marker}'")
    return failures


def check_source(source: str, path: Path) -> list[str]:
    """Return policy failures for Python source text.

    :param source: Python source text to inspect.
    :param path: Display path used in diagnostics.
    :returns: Human-readable failures; an empty list means success.
    :raises SyntaxError: If the source is not valid Python.
    """
    failures: list[str] = []
    if len(source.splitlines()) > MAX_SOURCE_LINES:
        failures.append(f"{path}: source exceeds 200 lines")
    tree = ast.parse(source, filename=str(path))
    nodes = _documented_nodes(tree)
    missing = [node for node in nodes if ast.get_docstring(node) is None]
    if missing:
        names = ", ".join(node.name for node in missing if not isinstance(node, ast.Module))
        failures.append(f"{path}: declaration lacks a docstring: {names or '<module>'}")
    for node in nodes:
        if ast.get_docstring(node) is not None:
            failures.extend(_rst_failures(node, path))
    return failures


def check_file(path: Path) -> list[str]:
    """Return policy failures for one Python source file.

    :param path: Python source path to inspect.
    :returns: Human-readable failures; an empty list means success.
    :raises OSError: If the source cannot be read.
    :raises SyntaxError: If the source is not valid Python.
    """
    return check_source(path.read_text(encoding="utf-8"), path)


def main() -> int:
    """Check all runtime source files and report failures.

    :returns: Zero when every source file satisfies project policy.
    """
    failures = [
        failure
        for path in sorted((ROOT / "pylcl").rglob("*.py"))
        for failure in check_file(path)
    ]
    for failure in failures:
        print(failure)
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
