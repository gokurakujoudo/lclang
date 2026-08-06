"""Resolver contracts and mapping-backed name lookup."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pylcl.errors import LclNameError
from pylcl.source import SourceSpan
from pylcl.types import VarName


@runtime_checkable
class Resolver(Protocol):
    """Resolve names for one evaluation environment.

    .. note::
       Implementations may perform asynchronous, cached, or hierarchical lookup.
    """

    async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
        """Return the value bound to one name.

        :param name: Variable name requested by an AST name node.
        :param span: Source range used for lookup diagnostics.
        :returns: Immediate or deferred value associated with *name*.

        .. note::
           Resolver-specific exceptions propagate through the evaluator unchanged.
        """
        ...


@dataclass(frozen=True, slots=True)
class MappingResolver:
    """Adapt a caller-owned mapping to :class:`Resolver`.

    :param values: String-keyed mapping read on every lookup.

    .. note::
       The mapping is retained by reference and is never copied or mutated.
    """

    values: Mapping[str, object]

    async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
        """Return a mapped value or raise a source-aware name error.

        :param name: Variable name used as the mapping key.
        :param span: Source range attached to a missing-name error.
        :returns: Current mapped value, which may itself be awaitable.
        :raises LclNameError: If *name* is absent from the mapping.

        .. note::
           Membership follows the supplied mapping's ordinary string-key rules.
        """
        try:
            return self.values[str(name)]
        except KeyError:
            raise LclNameError(f"unknown variable: {name}", span=span) from None


@dataclass(frozen=True, slots=True)
class ScopedResolver:
    """Overlay local bindings on another resolver.

    :param values: Local string-keyed bindings checked first.
    :param parent: Resolver used when a local binding is absent.

    .. note::
       Neither mapping nor parent is copied or mutated by lookup.
    """

    values: Mapping[str, object]
    parent: Resolver

    async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
        """Resolve locally before delegating to the parent.

        :param name: Variable name requested by evaluation.
        :param span: Source range forwarded to parent diagnostics.
        :returns: Local value or the parent's resolved result.

        .. note::
           A local value of ``None`` still shadows the parent binding.
        """
        if str(name) in self.values:
            return self.values[str(name)]
        return await self.parent.resolve(name, span=span)
