"""Source contracts for functional APIs, concrete files and shared layers."""

import ast
from importlib import import_module
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/lclang"


@pytest.mark.parametrize(
    "name",
    [
        "api",
        "types",
        "sources",
        "errors",
        "error_context",
        "records",
        "_version",
        "ast",
        "runtime",
        "stdlib",
        "lang.lexer",
        "lang.parser",
        "lang.printer",
        "lang.evaluator",
    ],
)
def test_obsolete_modules_are_unavailable(name: str) -> None:
    """Old source paths provide no forwarding or compatibility modules."""
    with pytest.raises(ModuleNotFoundError) as caught:
        import_module("lclang." + name)
    assert caught.value.name == "lclang." + name


def test_every_module_overview_identifies_its_declared_contents() -> None:
    """A file overview names its concrete classes and functions without a word quota."""
    for path in SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        overview = ast.get_docstring(tree)
        assert overview is not None and "\n\n" in overview, path
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                assert f"``{node.name}``" in overview, (path, node.name)
        if any(isinstance(node, ast.ClassDef) for node in tree.body):
            assert not path.stem.endswith("_value"), path
        assert path.stem not in {"base", "atoms", "records", "types", "sources", "errors"}, path


def test_only_package_initializers_curate_import_only_exports() -> None:
    """Standalone files contain implementation or data rather than forwarding imports."""
    for path in SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        statements = [
            node
            for node in tree.body
            if not isinstance(node, (ast.Import, ast.ImportFrom))
            and not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
        ]
        if path.name == "__init__.py":
            for node in statements:
                if isinstance(node, ast.Assign):
                    assert all(
                        isinstance(target, ast.Name) and target.id == "__all__"
                        for target in node.targets
                    ), path
                else:
                    assert (
                        isinstance(node, ast.AnnAssign)
                        and isinstance(node.target, ast.Name)
                        and node.target.id == "__all__"
                    ), path
            continue
        implementations = [
            node
            for node in statements
            if not (
                isinstance(node, ast.Assign)
                and all(
                    isinstance(target, ast.Name) and target.id == "__all__"
                    for target in node.targets
                )
            )
        ]
        assert implementations, path


def test_owned_state_uses_declared_fields_instead_of_instance_dictionaries() -> None:
    """Module discovery remains the single native-module reflection exception."""
    failures: list[str] = []
    for path in SOURCE.rglob("*.py"):
        relative = path.relative_to(SOURCE).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "__dict__":
                failures.append(f"{relative}:{node.lineno}: instance dictionary")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "vars"
            ):
                assert relative == "cli/command_discovery.py", relative
                assert (
                    len(node.args) == 1
                    and isinstance(node.args[0], ast.Name)
                    and node.args[0].id == "current"
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"getattr", "setattr", "delattr"}
                and len(node.args) > 1
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "__dict__"
            ):
                failures.append(f"{relative}:{node.lineno}: dynamic instance dictionary")
    assert failures == []


@pytest.mark.parametrize("package", ["common", "lang/common", "lang/ast"])
def test_shared_packages_do_not_depend_on_language_execution_or_application_adapters(
    package: str,
) -> None:
    """Shared primitives, language records and nodes keep dependency flow inward."""
    for path in (SOURCE / package).rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(
                    (
                        "lclang.cli",
                        "lclang.config",
                        "lclang.workflow",
                        "lclang.logger",
                        "lclang.utils",
                        "lclang.lang.engine",
                        "lclang.lang.runtime",
                        "lclang.lang.stdlib",
                    )
                ), (path, module)
                if package == "common":
                    assert not module.startswith("lclang.lang"), (path, module)


def test_behavioral_packages_follow_the_production_subsystems() -> None:
    """No active tests retain the superseded AST/runtime/stdlib or engine paths."""
    for obsolete in [
        "ast",
        "runtime",
        "stdlib",
        "lang/lexer",
        "lang/parser",
        "lang/printer",
        "lang/evaluator",
    ]:
        assert list((ROOT / "tests" / obsolete).rglob("*.py")) == [], obsolete
    for current in [
        "common",
        "lang/common",
        "lang/ast",
        "lang/engine",
        "lang/runtime",
        "lang/stdlib",
    ]:
        assert list((ROOT / "tests" / current).rglob("test_*.py")), current
