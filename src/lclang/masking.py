"""Shared trailing-marker normalization for masked bindings."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

# Suffix declaring that one exact binding name is masked.
MASK_SUFFIX = "!"
# Stable diagnostic replacement for masked payloads.
MASKED_VALUE = "*masked*"


def split_masked_name(name: str) -> tuple[str, bool]:
    """Remove one optional trailing mask marker from a binding name.

    :param name: Raw binding spelling.
    :returns: Normalized name and whether it carried the marker.
    :raises TypeError: If *name* is not text.
    :raises ValueError: If the marker is empty, repeated, or separated by space.
    """
    if not isinstance(name, str):
        raise TypeError("binding names must be strings")
    if not name.endswith(MASK_SUFFIX):
        return name, False
    normalized = name[:-1]
    if not normalized or normalized.endswith(MASK_SUFFIX) or normalized[-1].isspace():
        raise ValueError("invalid masked binding name")
    return normalized, True


def normalize_masked_mapping[ValueT](
    values: Mapping[str, ValueT],
    masked_names: Iterable[str] = (),
) -> tuple[dict[str, ValueT], frozenset[str]]:
    """Normalize marked keys and combine explicit immutable mask metadata.

    :param values: String-keyed bindings to detach.
    :param masked_names: Already-normalized names to mark additionally.
    :returns: Detached normalized mapping and immutable exact-name mask set.
    :raises TypeError: If a mapping key or explicit name is not text.
    :raises ValueError: If normalized names collide or a marker is malformed.
    """
    normalized: dict[str, ValueT] = {}
    selected_masks: set[str] = set()
    for raw_name, value in values.items():
        name, masked = split_masked_name(raw_name)
        if name in normalized:
            raise ValueError(f"duplicate normalized binding name: {name}")
        normalized[name] = value
        if masked:
            selected_masks.add(name)
    for name in normalize_masked_names(masked_names):
        if name not in normalized:
            raise ValueError(f"masked name has no binding: {name}")
        selected_masks.add(name)
    return normalized, frozenset(selected_masks)


def normalize_masked_names(masked_names: Iterable[str]) -> frozenset[str]:
    """Validate already-normalized exact-name mask metadata.

    :param masked_names: Names supplied separately from their bindings.
    :returns: Detached immutable name set.
    :raises TypeError: If a name is not text.
    :raises ValueError: If a name is empty or still carries a marker.
    """
    selected: set[str] = set()
    for raw_name in masked_names:
        name, marked = split_masked_name(raw_name)
        if not name or marked:
            raise ValueError("masked-names metadata must use normalized names")
        selected.add(name)
    return frozenset(selected)
