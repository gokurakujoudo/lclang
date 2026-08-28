"""Resolver contracts and mapping-backed name lookup."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from lclang.diagnostics import (
    internal_render_value,
    internal_trace,
    internal_verbose_enabled,
)
from lclang.errors import LclNameError
from lclang.lang.evaluator.awaitables import resolve_awaitable
from lclang.masking import normalize_masked_mapping
from lclang.source import SourceSpan
from lclang.types import VarName


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

    def __post_init__(self) -> None:
        """Validate current key spellings without copying the borrowed mapping.

        :returns: ``None`` after marked aliases are proven unambiguous.
        :raises TypeError: If a binding name is not text.
        :raises ValueError: If normalized names collide or markers are malformed.
        """
        normalize_masked_mapping(self.values)

    async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
        """Return a mapped value or raise a source-aware name error.

        :param name: Variable name used as the mapping key.
        :param span: Source range attached to a missing-name error.
        :returns: Current mapped value, which may itself be awaitable.
        :raises LclNameError: If *name* is absent from the mapping.
        :raises ValueError: If live mapping mutation creates a marked alias collision.

        .. note::
           Membership follows the supplied mapping's ordinary string-key rules.
        """
        try:
            plain = str(name)
            marked = f"{plain}!"
            if plain in self.values and marked in self.values:
                raise ValueError(f"duplicate normalized binding name: {plain}")
            masked = marked in self.values
            selected = self.values[marked if masked else plain]
        except KeyError:
            if internal_verbose_enabled():
                internal_trace("lookup", f"name={str(name)!r} source=missing")
            raise LclNameError(f"unknown variable: {name}", span=span) from None
        if not internal_verbose_enabled():
            return selected
        try:
            result = await resolve_awaitable(selected)
        except BaseException as error:
            internal_trace(
                "lookup",
                f"name={str(name)!r} source=external-provided "
                f"error={internal_render_value(error, masked=masked)}",
            )
            raise
        internal_trace(
            "lookup",
            f"name={str(name)!r} source=external-provided "
            f"value={internal_render_value(result, masked=masked)}",
        )
        return result


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
            selected = self.values[str(name)]
            if not internal_verbose_enabled():
                return selected
            try:
                result = await resolve_awaitable(selected)
            except BaseException as error:
                internal_trace(
                    "lookup",
                    f"name={str(name)!r} source=local-provided "
                    f"error={internal_render_value(error)}",
                )
                raise
            internal_trace(
                "lookup",
                f"name={str(name)!r} source=local-provided "
                f"value={internal_render_value(result)}",
            )
            return result
        return await self.parent.resolve(name, span=span)
