"""Resolver contracts and mapping-backed name lookup.

Defines ``Resolver``, ``MappingResolver``, ``ScopedResolver``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from lclang.error import LanguageErrorCode, LclEvaluationError, LclNameError
from lclang.error.awaitable_failure import resolve_operation_value
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_async_failure, guard_constructor, guard_failure
from lclang.error.verbose_diagnostic import (
    internal_trace,
    internal_verbose_enabled,
)
from lclang.error.verbose_failure import trace_verbose_failure
from lclang.lang.common.identifiers import VarName
from lclang.lang.common.source_location import SourceSpan
from lclang.lang.engine.evaluator.evaluation_journal import record_value_read
from lclang.lang.engine.evaluator.lookup_tracing import trace_resolver_value
from lclang.utils.binding_mask import normalize_masked_mapping


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


@guard_constructor(LclValidationError, LanguageErrorCode.E33_NAME_RESOLUTION_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class MappingResolver:
    """Adapt a caller-owned mapping to :class:`Resolver`.

    :param values: String-keyed mapping read on every lookup.

    .. note::
       The mapping is retained by reference and is never copied or mutated.
    """

    values: Mapping[str, object]

    @guard_failure(LclValidationError, LanguageErrorCode.E33_NAME_RESOLUTION_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Validate current key spellings without copying the borrowed mapping.

        :returns: ``None`` after marked aliases are proven unambiguous.
        :raises LclEvaluationError: If a binding name is not text.
        :raises LclEvaluationError: If normalized names collide or markers are malformed.
        """
        normalize_masked_mapping(self.values)

    @guard_async_failure(LclEvaluationError, LanguageErrorCode.E33_NAME_RESOLUTION_NATIVE_FAILURE)
    async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
        """Return a mapped value or raise a source-aware name error.

        :param name: Variable name used as the mapping key.
        :param span: Source range attached to a missing-name error.
        :returns: Current mapped value, which may itself be awaitable.
        :raises LclNameError: If *name* is absent from the mapping.
        :raises LclEvaluationError: If live mapping mutation creates a marked alias collision.

        .. note::
           Membership follows the supplied mapping's ordinary string-key rules.
        """
        try:
            plain = str(name)
            marked = f"{plain}!"
            if plain in self.values and marked in self.values:
                raise LclEvaluationError(
                    f"duplicate normalized binding name: {plain}",
                    code=LanguageErrorCode.E33_DUPLICATE_NORMALIZED_BINDING_NAME,
                )
            masked = marked in self.values
            selected = self.values[marked if masked else plain]
        except KeyError:
            if internal_verbose_enabled():
                internal_trace("lookup", f"No binding for {name} was found in external input")
            raise LclNameError(
                f"unknown variable: {name}",
                span=span,
                code=LanguageErrorCode.E33_UNKNOWN_VARIABLE,
            ) from None
        try:
            result = await resolve_operation_value(
                selected,
                LclEvaluationError,
                LanguageErrorCode.E33_NAME_RESOLUTION_NATIVE_FAILURE,
                span=span,
            )
        except BaseException as error:
            trace_verbose_failure(
                error, str(name), phase="awaiting external input", stage="lookup", masked=masked
            )
            raise
        record_value_read(str(name), result, span, masked=masked, source="external")
        trace_resolver_value(str(name), result, masked=masked)
        return result


@guard_constructor(LclValidationError, LanguageErrorCode.E33_NAME_RESOLUTION_NATIVE_FAILURE)
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

    @guard_async_failure(LclEvaluationError, LanguageErrorCode.E33_NAME_RESOLUTION_NATIVE_FAILURE)
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
            record_value_read(str(name), selected, span, source="argument")
            trace_resolver_value(str(name), selected, local=True)
            return selected
        return await self.parent.resolve(name, span=span)
