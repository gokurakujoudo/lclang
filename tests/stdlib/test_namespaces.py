"""Unit tests mirroring :mod:`pylcl.stdlib.namespaces`."""

from collections.abc import Iterator

import pytest

from pylcl.lang.parser import parse_expression
from pylcl.runtime import FrameFactory, Module
from pylcl.stdlib import (
    StdlibEntry,
    StdlibManifest,
    StdlibNamespace,
    assemble_stdlib,
)
from pylcl.types import FrameId, ModuleName


def _manifest(namespace: str, name: str, value: object) -> StdlibManifest:
    return StdlibManifest(
        namespace,
        (StdlibEntry(name, value, f"Export {name}."),),
    )


def test_namespace_is_an_ordered_mapping_and_attribute_view() -> None:
    """Declared members are equally available to Python and LCL protocols."""
    opaque = object()
    namespace = StdlibNamespace("tools", {"first": 1, "opaque": opaque})
    assert tuple(namespace) == ("first", "opaque")
    assert len(namespace) == 2
    assert namespace["opaque"] is opaque
    assert namespace.first == 1
    assert repr(namespace) == "StdlibNamespace(namespace='tools')"
    missing = "missing"
    with pytest.raises(AttributeError, match="tools"):
        getattr(namespace, missing)
    with pytest.raises(TypeError):
        namespace.members["other"] = 2  # type: ignore[index]


def test_namespace_validates_public_names_and_detaches_input() -> None:
    """Direct construction applies the same unambiguous identifier contract."""
    members: dict[str, object] = {"value": 1}
    namespace = StdlibNamespace("tools", members)
    members["value"] = 2
    assert namespace.value == 1
    with pytest.raises(ValueError):
        StdlibNamespace("", {})
    with pytest.raises(ValueError):
        StdlibNamespace("tools", {"items": 1})


def test_assembly_is_one_pass_ordered_and_rejects_duplicate_namespaces() -> None:
    """Manifest iteration produces one right-sized immutable stdlib preset."""
    consumed: list[str] = []

    def manifests() -> Iterator[StdlibManifest]:
        for manifest in (_manifest("alpha", "one", 1), _manifest("beta", "two", 2)):
            consumed.append(manifest.namespace)
            yield manifest

    preset = assemble_stdlib(manifests(), name="reviewed")
    assert consumed == ["alpha", "beta"]
    assert preset.name == "reviewed"
    assert tuple(preset.values) == ("alpha", "beta")
    assert preset.values["alpha"].one == 1  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="duplicate"):
        assemble_stdlib((_manifest("same", "one", 1), _manifest("same", "two", 2)))


@pytest.mark.asyncio
async def test_assembled_preset_evaluates_through_namespace_attributes() -> None:
    """A Frame can call an opaque manifest value through ordinary attributes."""

    def double(value: int) -> int:
        return value * 2

    preset = assemble_stdlib((_manifest("math", "double", double),))
    module = Module(
        ModuleName("app"),
        {"value": parse_expression("math.double(3)")},
    )
    frame = FrameFactory(module, preset).create(FrameId("frame:1"))
    assert await frame.get("value") == 6


def test_assembly_validates_manifest_objects_and_preset_name() -> None:
    """Malformed assembly inputs fail before constructing partial namespaces."""
    with pytest.raises(TypeError):
        assemble_stdlib((object(),))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        assemble_stdlib((), name="")
