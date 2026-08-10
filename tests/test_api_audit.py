"""Public API and production declaration hardening tests."""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, get_args, get_type_hints

import lclang
import lclang.cli
import lclang.config
import lclang.lang
import lclang.runtime
import lclang.runtime.frame
import lclang.workflow

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MODULES = (
    lclang,
    lclang.lang,
    lclang.runtime,
    lclang.runtime.frame,
    lclang.config,
    lclang.cli,
    lclang.workflow,
)
API_NAMESPACE = {
    name: getattr(module, name) for module in PUBLIC_MODULES for name in module.__all__
}


def contains_any(annotation: object) -> bool:
    """Return whether one resolved annotation contains unconstrained Any."""
    return annotation is Any or any(contains_any(item) for item in get_args(annotation))


def test_production_declarations_do_not_use_single_underscore_names() -> None:
    """Only Python protocol dunders may begin with an underscore."""
    failures: list[str] = []
    for path in sorted((ROOT / "src" / "lclang").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("_")
                and not node.name.endswith("__")
            ):
                failures.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.name}")
    assert failures == []


def test_public_exports_are_exact_documented_and_typed() -> None:
    """Every curated export exists once and has resolvable constrained hints."""
    for module in PUBLIC_MODULES:
        exports = module.__all__
        assert len(exports) == len(set(exports))
        assert all(hasattr(module, name) for name in exports)
        visible = {
            name
            for name, value in vars(module).items()
            if (not name.startswith("_") or name in module.__all__)
            and not isinstance(value, ModuleType)
        }
        assert visible == set(exports)
        for name in exports:
            value = getattr(module, name)
            if inspect.isclass(value) or inspect.isfunction(value):
                assert inspect.getdoc(value)
                globalns = {**vars(sys.modules[value.__module__]), **API_NAMESPACE}
                hints = get_type_hints(value, globalns=globalns)
                assert not any(contains_any(annotation) for annotation in hints.values())
