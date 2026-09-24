"""Check lclang source-size and exhaustive documentation policies."""

from __future__ import annotations

import ast
import builtins
import inspect
import io
import sys
import tokenize
from collections.abc import Iterator
from pathlib import Path

# Maximum code-bearing physical lines per production module.
MAX_SOURCE_LINES = 200
# Python and dataclass protocol methods supported by production objects.
PROTOCOL_METHODS = frozenset(
    name
    for value in (object, type, int, str, list, dict)
    for name in dir(value)
    if name.startswith("__")
    and name.endswith("__")
    and inspect.isroutine(getattr(value, name, None))
) | {
    "__post_init__",
    "__del__",
    "__fspath__",
    "__get__",
    "__set__",
    "__delete__",
    "__set_name__",
    "__length_hint__",
    "__missing__",
    "__complex__",
    "__matmul__",
    "__rmatmul__",
    "__imatmul__",
    "__iadd__",
    "__isub__",
    "__imul__",
    "__itruediv__",
    "__ifloordiv__",
    "__imod__",
    "__ipow__",
    "__ilshift__",
    "__irshift__",
    "__iand__",
    "__ixor__",
    "__ior__",
    "__copy__",
    "__deepcopy__",
    "__setstate__",
    "__buffer__",
    "__release_buffer__",
    "__getattr__",
    "__enter__",
    "__exit__",
    "__aenter__",
    "__aexit__",
    "__await__",
    "__aiter__",
    "__anext__",
    "__iter__",
    "__next__",
}
# Repository root containing the production package.
ROOT = Path(__file__).resolve().parents[1]
DocumentedNode = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
CallableNode = ast.FunctionDef | ast.AsyncFunctionDef


def documented_nodes(tree: ast.Module) -> list[DocumentedNode]:
    """Return every declaration governed by the production policy.

    :param tree: Parsed Python module.
    :returns: Module plus every class, function, method, and nested function.

    .. note::
       Source ordering keeps diagnostics deterministic across platforms.
    """
    declarations: list[ast.ClassDef | CallableNode] = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    declarations.sort(key=lambda node: node.lineno)
    return [tree, *declarations]


def callable_parameters(node: CallableNode) -> list[str]:
    """Return declared non-receiver parameter names."""
    positional = [*node.args.posonlyargs, *node.args.args]
    names = [argument.arg for argument in [*positional, *node.args.kwonlyargs]]
    if node.args.vararg is not None:
        names.append(node.args.vararg.arg)
    if node.args.kwarg is not None:
        names.append(node.args.kwarg.arg)
    return [name for name in names if name not in {"self", "cls"}]


def exception_names(expression: ast.expr | None) -> set[str]:
    """Read directly named exception types from a handler or raise expression."""
    if expression is None:
        return {"BaseException"}
    if isinstance(expression, ast.Call):
        expression = expression.func
    if isinstance(expression, ast.Tuple):
        return set[str]().union(*(exception_names(item) for item in expression.elts))
    if isinstance(expression, ast.Name):
        return {expression.id} if expression.id[:1].isupper() else set()
    if isinstance(expression, ast.Attribute):
        return {expression.attr} if expression.attr[:1].isupper() else set()
    return set()


def catches_exception(name: str, handlers: set[str]) -> bool:
    """Match explicit names and known builtin exception inheritance."""
    if name in handlers or "BaseException" in handlers:
        return True
    exception = getattr(builtins, name, None)
    return isinstance(exception, type) and any(
        isinstance(handler := getattr(builtins, caught, None), type)
        and issubclass(exception, handler)
        for caught in handlers
    )


def raised_exception_names(node: CallableNode) -> set[str]:
    """Collect direct escaping raises without attributing nested callables."""

    def visit(current: ast.AST, caught: set[str]) -> set[str]:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return set()
        if isinstance(current, ast.Raise):
            return (
                set()
                if current.exc is None
                else {
                    name
                    for name in exception_names(current.exc)
                    if not catches_exception(name, caught)
                }
            )
        if isinstance(current, (ast.Try, ast.TryStar)):
            handled = set[str]().union(*(exception_names(item.type) for item in current.handlers))
            protected = set[str]().union(
                *(visit(child, caught | handled) for child in current.body)
            )
            remaining = [*current.handlers, *current.orelse, *current.finalbody]
            return protected | set[str]().union(*(visit(child, caught) for child in remaining))
        return set[str]().union(*(visit(child, caught) for child in ast.iter_child_nodes(current)))

    return set[str]().union(*(visit(child, set()) for child in node.body))


def class_fields(node: ast.ClassDef) -> list[str]:
    """Return public annotated constructor fields."""
    return [
        child.target.id
        for child in node.body
        if isinstance(child, ast.AnnAssign)
        and isinstance(child.target, ast.Name)
        and not child.target.id.startswith("_")
    ]


def requires_return_field(node: CallableNode) -> bool:
    """Return whether a callable produces a documented result value.

    :param node: Function declaration being checked.
    :returns: ``True`` when its annotation or return statements yield a value.

    .. note::
       Explicit ``-> None`` and bare-return procedures omit ``:returns:``.
    """
    if isinstance(node.returns, ast.Constant) and node.returns.value is None:
        return False
    if node.returns is not None:
        return True
    return any(
        isinstance(child, ast.Return) and child.value is not None for child in ast.walk(node)
    )


def effective_source_lines(source: str, tree: ast.Module) -> int:
    """Count code-bearing physical lines after removing imports and documentation.

    :param source: Complete Python source text.
    :param tree: Parsed syntax tree for the source.
    :returns: Number of nonempty physical implementation lines.
    """
    lines = source.splitlines()
    excluded: list[tuple[tuple[int, int], tuple[int, int]]] = []
    documentation: set[int] = set()
    for scope in documented_nodes(tree):
        for index, statement in enumerate(scope.body):
            if not (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Constant)
                and isinstance(statement.value.value, str)
            ):
                continue
            previous = scope.body[index - 1] if index else None
            attribute_doc = isinstance(scope, (ast.Module, ast.ClassDef)) and isinstance(
                previous, (ast.Assign, ast.AnnAssign)
            )
            if index == 0 or attribute_doc or id(previous) in documentation:
                documentation.add(id(statement))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) or (
            isinstance(node, ast.Expr) and id(node) in documentation
        ):
            end_line = node.end_lineno or node.lineno
            start_column = len(lines[node.lineno - 1].encode()[: node.col_offset].decode())
            end_column = len(lines[end_line - 1].encode()[: node.end_col_offset].decode())
            excluded.append(((node.lineno, start_column), (end_line, end_column)))
    ignored = {
        tokenize.ENCODING,
        tokenize.ENDMARKER,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.NEWLINE,
        tokenize.NL,
        tokenize.COMMENT,
    }
    counted: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type in ignored or token.string == ";":
            continue
        if any(start <= token.start and token.end <= end for start, end in excluded):
            continue
        counted.update(
            number
            for number in range(token.start[0], token.end[0] + 1)
            if lines[number - 1].strip()
        )
    return len(counted)


def constant_failures(source: str, tree: ast.Module, path: Path) -> Iterator[str]:
    """Require associated explanations for named constants and enum groups."""
    lines = source.splitlines()
    comment_lines = {
        token.start[0]
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    }
    for scope in ast.walk(tree):
        if not isinstance(scope, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        enum_group = isinstance(scope, ast.ClassDef) and any(
            (
                isinstance(base, ast.Name)
                and base.id in {"Enum", "StrEnum", "IntEnum", "Flag", "IntFlag"}
            )
            or (
                isinstance(base, ast.Attribute)
                and base.attr in {"Enum", "StrEnum", "IntEnum", "Flag", "IntFlag"}
            )
            for base in scope.bases
        )
        group_documented = False
        if isinstance(scope, ast.ClassDef) and scope.lineno > 1:
            group_documented = lines[scope.lineno - 2].lstrip().startswith("#")
        for index, statement in enumerate(scope.body):
            preceding = lines[statement.lineno - 2].strip() if statement.lineno > 1 else ""
            if preceding.startswith("#"):
                group_documented = True
            elif not preceding:
                group_documented = False
            targets = (
                statement.targets
                if isinstance(statement, ast.Assign)
                else [statement.target] if isinstance(statement, ast.AnnAssign) else []
            )
            names = [
                target.id
                for target in targets
                if isinstance(target, ast.Name)
                and (target.id.isupper() or target.id == "__all__" or enum_group)
            ]
            following = scope.body[index + 1] if index + 1 < len(scope.body) else None
            description = (
                isinstance(following, ast.Expr)
                and isinstance(following.value, ast.Constant)
                and isinstance(following.value.value, str)
            )
            inline = (statement.end_lineno or statement.lineno) in comment_lines
            if names and not (group_documented or description or inline):
                yield f"{path}:{statement.lineno}: constant {', '.join(names)} lacks explanation"


def rst_failures(node: DocumentedNode, path: Path) -> list[str]:
    """Report missing rST contract fields for one declaration."""
    if isinstance(node, ast.Module):
        return []
    docstring = ast.get_docstring(node) or ""
    name = node.name
    failures: list[str] = []
    if isinstance(node, ast.ClassDef):
        parameters = class_fields(node)
    else:
        parameters = callable_parameters(node)
        if requires_return_field(node) and ":returns:" not in docstring:
            failures.append(f"{path}:{name}: docstring lacks ':returns:'")
        for exception in sorted(raised_exception_names(node)):
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
    tree = ast.parse(source, filename=str(path))
    if effective_source_lines(source, tree) > MAX_SOURCE_LINES:
        failures.append(f"{path}: source exceeds 200 lines")
    failures.extend(constant_failures(source, tree, path))
    nodes = documented_nodes(tree)
    methods = {
        id(member)
        for parent in ast.walk(tree)
        if isinstance(parent, ast.ClassDef)
        for member in parent.body
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for node in nodes:
        if (
            not isinstance(node, ast.Module)
            and node.name.startswith("_")
            and not (id(node) in methods and node.name in PROTOCOL_METHODS)
        ):
            failures.append(f"{path}:{node.name}: declaration name starts with underscore")
    missing = [node for node in nodes if ast.get_docstring(node) is None]
    if missing:
        names = ", ".join(node.name for node in missing if not isinstance(node, ast.Module))
        failures.append(f"{path}: declaration lacks a docstring: {names or '<module>'}")
    for node in nodes:
        if ast.get_docstring(node) is not None:
            failures.extend(rst_failures(node, path))
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
        for path in sorted((ROOT / "src" / "lclang").rglob("*.py"))
        for failure in check_file(path)
    ]
    for failure in failures:
        print(failure)
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
