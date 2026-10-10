"""Audit encoded production failures and the builtin diagnostic hierarchy."""

from __future__ import annotations

import ast
import builtins
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The standalone gate audits the checkout before pytest or an editable install supplies src.
sys.path.insert(0, str(ROOT / "src"))
from lclang.error import get_error_code_path, get_error_codes  # noqa: E402
from lclang.error.codes.code_registry import CODE_ENUMS  # noqa: E402

# These ordinary constructors participate in the same explicit-code contract.
ERROR_CONSTRUCTORS = frozenset(
    {
        "CalendarCannotLoadException",
        "CalendarLogicException",
        "DateOperationOutOfScopeException",
        "UnappliedCalendarOperationException",
        "EscapeDecodeError",
        "FStringScanError",
        "InternalLiteralScanError",
        "RouteFailure",
        "usage_error",
    }
)
# Native control/protocol signals retain Python behavior and need no builtin code.
CONTROL_SIGNALS = frozenset(
    {
        "StopIteration",
        "StopAsyncIteration",
        "SystemExit",
        "KeyboardInterrupt",
        "CancelledError",
        "BaseExceptionGroup",
    }
)
NATIVE_FAILURES = frozenset(
    name
    for name, value in vars(builtins).items()
    if isinstance(value, type) and issubclass(value, BaseException) and name not in CONTROL_SIGNALS
)


def check_error_source(source: str, path: Path) -> list[str]:
    """Find uncoded ordinary raises and unregistered code references in one module."""
    tree = ast.parse(source, filename=str(path))
    aliases = {
        alias.asname or alias.name: alias.name
        for statement in ast.walk(tree)
        if isinstance(statement, ast.ImportFrom)
        and (
            (statement.module or "").startswith("lclang.error.codes.")
            or statement.module == "lclang.error"
        )
        for alias in statement.names
        if alias.name in {group.__name__ for group in CODE_ENUMS}
    }
    members = {group.__name__: set(group.__members__) for group in CODE_ENUMS}
    failures: list[str] = []
    for node in ast.walk(tree):
        reason: str | None = None
        if isinstance(node, ast.Assert):
            reason = "ordinary assertions must raise an encoded LCL failure"
        elif isinstance(node, ast.Raise) and node.exc is not None:
            function = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            name = (
                function.id
                if isinstance(function, ast.Name)
                else function.attr if isinstance(function, ast.Attribute) else ""
            )
            if name in NATIVE_FAILURES and name not in CONTROL_SIGNALS:
                reason = f"native proactive failure {name} must use an LCL error"
        elif isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            )
            if (
                (name.startswith("Lcl") and "Error" in name) or name in ERROR_CONSTRUCTORS
            ) and not any(keyword.arg == "code" for keyword in node.keywords):
                reason = f"{name} construction must specify its code"
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
        ):
            domain = aliases[node.value.id]
            if node.attr not in members[domain]:
                reason = f"unregistered builtin code {domain}.{node.attr}"
        if reason is not None:
            failures.append(f"{path}:{getattr(node, "lineno", 0)}: {reason}")
    return failures


def check_error_registry() -> list[str]:
    """Verify builtin uniqueness, decimal shape, and complete hierarchy labels."""
    failures: list[str] = []
    codes = get_error_codes()
    for group in CODE_ENUMS:
        values = [str(member) for member in group]
        if values != sorted(values):
            failures.append(f"{group.__name__}: members must follow numeric code order")
        for member in group:
            if re.fullmatch(r"E" + str(member)[4:6] + r"_[A-Z][A-Z0-9_]*", member.name) is None:
                failures.append(f"{group.__name__}.{member.name}: expected Exx_REASON naming")
    if len(codes) != len(set(codes)) or any(
        len(group) != len(group.__members__) for group in CODE_ENUMS
    ):
        failures.append("builtin error codes must be unique and have no aliases")
    for code in codes:
        if re.fullmatch(r"LCL[0-9]{6}", code) is None:
            failures.append(f"invalid builtin error code: {code}")
            continue
        labels = get_error_code_path(code)
        for digit, label in zip(code[3:], labels, strict=True):
            if digit != "0" and label.startswith("Unspecified"):
                failures.append(f"{code}: missing classification meaning: {label}")
    return failures


def check_error_contract(root: Path = ROOT / "src/lclang") -> list[str]:
    """Audit the registry and every production source file."""
    failures = check_error_registry()
    for path in sorted(root.rglob("*.py")):
        failures.extend(check_error_source(path.read_text(encoding="utf-8"), path))
    return failures
