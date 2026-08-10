"""Public immutable dependency classifications and references."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lclang.source import SourceSpan
from lclang.types import VarName


class DependencyKind(StrEnum):
    """Classify when evaluation can request a dependency.

    .. note::
       String values are stable graph and diagnostic labels.
    """

    EAGER = "eager"
    CONDITIONAL = "conditional"
    DEFERRED = "deferred"
    DYNAMIC = "dynamic"


@dataclass(frozen=True, slots=True)
class DependencyReference:
    """Identify one free-name occurrence and its evaluation class.

    :param name: Non-empty referenced variable name.
    :param kind: Static or runtime dependency classification.
    :param span: Exact source range of this occurrence.
    :raises ValueError: If *name* is empty or *kind* is not a dependency kind.

    .. note::
       Equal names at distinct spans remain distinct diagnostic evidence.
    """

    name: VarName
    kind: DependencyKind
    span: SourceSpan

    def __post_init__(self) -> None:
        """Validate public dependency vocabulary and identifiers.

        :raises ValueError: If the name is empty or kind is invalid.
        """
        if not self.name:
            raise ValueError("dependency name cannot be empty")
        if not isinstance(self.kind, DependencyKind):
            raise ValueError("dependency kind must be a DependencyKind")


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    """Connect one definition to one referenced name occurrence.

    :param source: Non-empty definition that owns the reference.
    :param target: Non-empty referenced variable name.
    :param kind: Static or runtime dependency classification.
    :param span: Exact source range of the target occurrence.
    :raises ValueError: If an endpoint is empty or *kind* is invalid.

    .. note::
       Repeated endpoint pairs remain distinct edges when spans differ.
    """

    source: VarName
    target: VarName
    kind: DependencyKind
    span: SourceSpan

    def __post_init__(self) -> None:
        """Validate endpoints and dependency vocabulary.

        :raises ValueError: If an endpoint is empty or kind is invalid.
        """
        if not self.source or not self.target:
            raise ValueError("dependency edge endpoints cannot be empty")
        if not isinstance(self.kind, DependencyKind):
            raise ValueError("dependency kind must be a DependencyKind")
