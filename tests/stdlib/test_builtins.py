"""Unit tests mirroring :mod:`pylcl.stdlib.builtins`."""

import ast
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from pylcl.lang.parser import parse_expression
from pylcl.runtime import FrameFactory, Module
from pylcl.stdlib import STANDARD_MANIFESTS, STANDARD_PRESET
from pylcl.types import FrameId, ModuleName


def test_standard_manifests_and_preset_have_stable_reviewed_order() -> None:
    """Built-in namespaces and entry metadata form one durable public surface."""
    assert tuple(item.namespace for item in STANDARD_MANIFESTS) == (
        "iter",
        "text",
        "data",
        "json",
    )
    assert tuple(STANDARD_PRESET.values) == ("iter", "text", "data", "json")
    summaries = (
        entry.summary.strip()
        for item in STANDARD_MANIFESTS
        for entry in item.entries
    )
    assert all(summaries)


@pytest.mark.asyncio
async def test_standard_preset_composes_async_helpers_in_a_frame() -> None:
    """Ordinary LCL calls auto-await helpers exposed through namespaces."""

    async def items() -> AsyncIterator[str]:
        yield "alpha"
        yield "beta"

    module = Module(
        ModuleName("app"),
        {"value": parse_expression('text.join("-", iter.collect(items))')},
    )
    frame = FrameFactory(module, STANDARD_PRESET).create(
        FrameId("frame:1"), values={"items": items()}
    )
    assert await frame.get("value") == "alpha-beta"


def test_helper_modules_import_only_reviewed_capability_roots() -> None:
    """The concrete helper surface cannot acquire ambient I/O capabilities."""
    root = Path(__file__).parents[2] / "pylcl" / "stdlib"
    allowed = {"__future__", "collections", "json", "pylcl", "types"}
    for name in ("iterables.py", "text.py", "data.py", "json_values.py", "builtins.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        imports = (
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
        assert set(imports) <= allowed
