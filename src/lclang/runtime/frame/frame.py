"""Concrete Frame state and public lifecycle/evaluation entry points."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from types import MappingProxyType, TracebackType
from typing import Self
from weakref import WeakSet

from lclang.ast import LclAstNode
from lclang.error import LclEvaluationError, LclNameError
from lclang.error.aggregation import combine_failures
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_constructor, guard_failure
from lclang.error.codes.runtime import Code as runtime_codes
from lclang.masking import normalize_masked_mapping, normalize_masked_names
from lclang.runtime.dependency.snapshot import DependencySnapshot
from lclang.runtime.frame.binding_lookup import (
    find_frame,
    hierarchy_binding_names,
    is_name_masked,
    select_binding,
    validate_frame_hierarchy,
)
from lclang.runtime.frame.cache_lifecycle import InternalFrameLifecycle
from lclang.runtime.frame.dependency_snapshots import InternalFrameDependencies, dependency_snapshot
from lclang.runtime.frame.evaluation import (
    evaluate_definition,
    evaluate_expression,
    get_resolved,
    get_value,
    resolve_name,
)
from lclang.runtime.frame.evaluation_flights import internal_refresh_definition
from lclang.runtime.frame.evaluation_limits import EvaluationLimits
from lclang.runtime.frame.fallback import NO_FALLBACK
from lclang.runtime.frame.host_bindings import update_host_bindings
from lclang.runtime.frame.inspection_builder import inspect_variable
from lclang.runtime.frame.inspection_values import (
    VariableInspectionTree,
)
from lclang.runtime.modules import Module
from lclang.scopes import validate_binding_names
from lclang.source import SourceSpan
from lclang.types import FrameId, VarName


@guard_constructor(LclValidationError, runtime_codes.NATIVE_231)
class Frame:
    """Cache lazy evaluations for one runtime module instance.

    :param module: Immutable local definition snapshot.
    :param frame_id: Optional identifier, defaulting to ``frame-<module name>``.
    :param values: Optional initial host bindings copied at construction time.
    :param parent: Optional ancestor used after local definitions and bindings.
    :param limits: Optional resource ceilings, or stable defaults when omitted.
    :param native_values: Whether local host bindings are canonical lclang values.
    :raises LclValidationError: If an optional identifier or native flag has the wrong type.
    :raises LclValidationError: If *frame_id* or any host binding name is empty.

    .. note::
       Parent-owned definitions always evaluate and cache in their parent Frame.
    """

    def __init__(
        self,
        module: Module,
        frame_id: FrameId | str | None = None,
        *,
        values: Mapping[str, object] | None = None,
        parent: Frame | None = None,
        limits: EvaluationLimits | None = None,
        native_values: bool = False,
        masked_names: Iterable[str] = (),
    ) -> None:
        """Create an empty result cache over immutable inputs.

        :param module: Immutable local definition snapshot.
        :param frame_id: Optional string identifier or nominal Frame identifier.
        :param values: Optional initial host bindings copied at construction time.
        :param parent: Optional ancestor used after local definitions and bindings.
        :param limits: Optional resource ceilings, or defaults when omitted.
        :param native_values: Whether local host bindings are canonical lclang values.
        :param masked_names: Additional normalized local names to redact.
        :returns: ``None`` after independent runtime state is initialized.
        :raises LclValidationError: If *frame_id* or *native_values* has the wrong type.
        :raises LclValidationError: If the effective ID or a host binding name is empty.

        .. note::
           Omitting *frame_id* derives ``frame-<module name>`` deterministically.
        """
        if frame_id is not None and not isinstance(frame_id, str):
            raise LclValidationError(
                "frame identifier must be a string",
                code=runtime_codes.E31_FRAME_IDENTIFIER_MUST_BE_A_STRING,
            )
        if not isinstance(native_values, bool):
            raise LclValidationError(
                "native-values flag must be Boolean",
                code=runtime_codes.E31_NATIVE_VALUES_FLAG_MUST_BE_BOOLEAN,
            )
        effective_id = FrameId(f"frame-{module.name}") if frame_id is None else FrameId(frame_id)
        if not effective_id:
            raise LclValidationError(
                "frame identifier cannot be empty",
                code=runtime_codes.E31_FRAME_IDENTIFIER_CANNOT_BE_EMPTY,
            )
        raw_values: Mapping[str, object] = {} if values is None else values
        if any(not isinstance(name, str) for name in raw_values):
            raise LclValidationError(
                "host binding names must be strings",
                code=runtime_codes.E31_FRAME_IDENTIFIER_MUST_BE_A_STRING,
            )
        snapshot, value_masks = normalize_masked_mapping(raw_values)
        if any(not name for name in snapshot):
            raise LclValidationError(
                "host binding name cannot be empty",
                code=runtime_codes.E31_FRAME_IDENTIFIER_CANNOT_BE_EMPTY,
            )
        validate_binding_names(snapshot)
        explicit_masks = normalize_masked_names(masked_names)
        validate_binding_names(explicit_masks)
        self.module = module
        self.frame_id = effective_id
        self._values = snapshot
        self.values: Mapping[str, object] = MappingProxyType(self._values)
        self.masked_names = frozenset(module.masked_names | value_masks | explicit_masks)
        self.parent = parent
        self._children: WeakSet[Frame] = WeakSet()
        self.limits = EvaluationLimits() if limits is None else limits
        self.native_values = native_values
        self._default_frame: Frame | None = None
        self._results: dict[str, object] = {}
        self._failures: dict[str, Exception] = {}
        self._inflight: dict[str, asyncio.Task[object]] = {}
        self._refreshes: dict[str, asyncio.Task[object]] = {}
        self._dependencies = InternalFrameDependencies(module, hierarchy_binding_names(self))
        self._lifecycle = InternalFrameLifecycle(
            self._results,
            self._failures,
            self._inflight,
            self._refreshes,
            self._dependencies.clear,
        )
        validate_frame_hierarchy(self)
        if parent is not None:
            parent._children.add(self)

    @guard_async_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    async def recalculate(self, name: str) -> object:
        """Explicitly refresh one owned definition snapshot.

        :param name: Non-empty definition name to refresh.
        :returns: Newly evaluated result after its atomic cache commit.
        :raises LclValidationError: If *name* is empty.
        :raises LclEvaluationError: If *name* selects a host binding or fails.
        :raises LclNameError: If *name* is absent from the Frame hierarchy.

        .. note::
           Cached dependants and the previous snapshot are never invalidated.
        """
        self._lifecycle.ensure_open(None)
        if not name:
            raise LclValidationError(
                "variable name cannot be empty",
                code=runtime_codes.E31_FRAME_IDENTIFIER_CANNOT_BE_EMPTY,
            )
        selected = select_binding(self, name)
        owner = selected.owner
        if owner is None:
            raise LclNameError(
                f"unknown variable: {name}", code=runtime_codes.E31_UNKNOWN_VARIABLE_VALUE
            )
        owner._lifecycle.ensure_open(None)
        if selected.kind == "proxy":
            raise LclEvaluationError(
                f"Frame proxy cannot be recalculated: {name}",
                code=runtime_codes.E31_FRAME_PROXY_CANNOT_BE_RECALCULATED_VALUE,
            )
        if selected.kind == "host" or name not in owner.module.definitions:
            raise LclEvaluationError(
                f"host binding cannot be recalculated: {name}",
                code=runtime_codes.E31_HOST_BINDING_CANNOT_BE_RECALCULATED_VALUE,
            )
        return await internal_refresh_definition(
            name,
            owner._inflight,
            owner._refreshes,
            owner.evaluate_definition,
            lambda: owner._lifecycle.ensure_open(None),
        )

    @guard_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    def derive(
        self,
        module: Module,
        values: dict[str, object] = {},  # noqa: B006
        *,
        masked_names: Iterable[str] = (),
    ) -> Frame:
        """Create a fresh child Frame borrowing this Frame as its parent.

        :param module: Immutable child definitions and nominal child identifier.
        :param values: Local host bindings copied into the child.
        :param masked_names: Additional normalized hierarchy names to redact.
        :returns: Independent child Frame whose parent is this Frame.
        :raises LclValidationError: If *module* is not a Module or *values* is not a dict.
        :raises LclValidationError: If a local host-binding name is empty.

        .. note::
           The default and caller dictionary are never mutated or retained;
           Frame construction always snapshots the mapping.
           Prefer entering the returned child with ``async with`` so its owned
           state closes while this borrowed parent remains open.
        """
        from lclang.runtime.frame.frame import Frame

        if not isinstance(module, Module):
            raise LclValidationError(
                "derived frame module must be a Module",
                code=runtime_codes.E31_DERIVED_FRAME_MODULE_MUST_BE_A_MODULE,
            )
        if not isinstance(values, dict):
            raise LclValidationError(
                "derived frame values must be a dictionary",
                code=runtime_codes.E31_DERIVED_FRAME_VALUES_MUST_BE_A_DICTIONARY,
            )
        return Frame(
            module,
            FrameId(str(module.name)),
            values=values,
            parent=self,
            masked_names=masked_names,
        )

    @guard_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    def has(self, name: str) -> bool:
        """Report whether the hierarchy resolves a name.

        :param name: Non-empty definition or host-value name.
        :returns: ``True`` when recursive lookup selects any binding.
        :raises LclValidationError: If *name* is empty.

        .. note::
           Presence inspection never evaluates or caches a definition or value.
        """
        return find_frame(self, name) is not None

    @guard_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    def is_masked(self, name: str) -> bool:
        """Report whether the hierarchy marks one exact normalized name.

        :param name: Non-empty binding name to inspect without evaluation.
        :returns: Whether any effective layer marks *name*.
        :raises LclValidationError: If *name* is empty.
        """
        if not name:
            raise LclValidationError(
                "variable name cannot be empty",
                code=runtime_codes.E31_FRAME_IDENTIFIER_CANNOT_BE_EMPTY,
            )
        return is_name_masked(self, name)

    @guard_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    def get_definition(self, name: str) -> LclAstNode | None:
        """Return the selected definition AST without evaluating it.

        :param name: Non-empty definition or host-value name.
        :returns: Nearest selected definition, or ``None`` for a value/miss.
        :raises LclValidationError: If *name* is empty.

        .. note::
           A nearer host value masks an ancestor definition with the same name.
        """
        owner = find_frame(self, name)
        if owner is None:
            return None
        return (
            None
            if select_binding(self, name).kind == "host"
            else owner.module.definitions.get(name)
        )

    @guard_async_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    async def __aenter__(self) -> Self:
        """Enter an owned Frame lifecycle scope.

        :returns: The same open Frame for evaluation inside the scope.
        """
        return self

    @guard_async_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    async def __aexit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the Frame when its asynchronous lifecycle scope exits.

        :param error_type: Exception type raised by the scope, when present.
        :param error: Exception raised by the scope, when present.
        :param traceback: Traceback associated with *error*, when present.
        :returns: ``None`` so an exception from the scope is never suppressed.
        :raises LclEvaluationError: If an owned resource cleanup fails.
        :raises BaseException: If cleanup itself raises a direct base exception.
        """
        try:
            await self.close()
        except BaseException as cleanup:
            failure = combine_failures(error, cleanup, code=runtime_codes.SCOPE_CLEANUP_FAILURE)
            raise failure from failure.__cause__

    @property
    @guard_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    def closed(self) -> bool:
        """Return whether owned cleanup has completely settled.

        :returns: ``True`` only after the shared close Task finishes.

        .. note::
           Requests are rejected while closing even though this remains false.
        """
        return self._lifecycle.closed

    @guard_async_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    async def close(self) -> None:
        """Cancel owned work and release cached resources exactly once.

        :returns: ``None`` after the shared close outcome settles.
        :raises LclEvaluationError: If an owned resource cleanup fails.
        :raises BaseException: If cleanup itself raises a direct base exception.

        .. note::
           Cancelling one caller does not cancel the owned close Task.
        """
        await self._lifecycle.close()

    @guard_async_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    async def get(self, name: str, fallback: object = NO_FALLBACK) -> object:
        """Resolve one local definition or host binding.

        :param name: Non-empty variable name to resolve.
        :param fallback: Value returned unchanged when *name* is absent.
        :returns: Cached or newly evaluated value, or the explicit fallback.
        :raises LclValidationError: If *name* is empty.
        :raises LclNameError: If no binding exists and fallback is ``NO_FALLBACK``.
        :raises Exception: If definition evaluation fails.

        .. note::
           Successful values and ordinary failure instances are cached by name.
           A fallback is neither resolved nor cached and never replaces a
           failure from an existing definition.
        """
        return await get_value(self, name, fallback)

    @guard_async_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    async def evaluate(self, expr: str) -> object:
        """Evaluate one unnamed expression against this open Frame.

        :param expr: Complete LCL source expression.
        :returns: Fully resolved uncached result.
        :raises LclValidationError: If *expr* is not a string.
        :raises LclClosedFrameError: If Frame closing has begun.

        .. note::
           Named dependencies retain ordinary Frame caching while the root
           expression uses ``<expr>`` as its lexical ``lhs()`` owner.
        """
        return await evaluate_expression(self, expr)

    @guard_async_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    async def resolve(self, name: VarName, *, span: SourceSpan) -> object:
        """Resolve a name for the language evaluator.

        :param name: Variable requested by a semantic name node.
        :param span: Requesting source range for missing-name diagnostics.
        :returns: Cached or newly evaluated value.
        :raises LclNameError: If no definition or host binding exists.
        :raises Exception: If definition evaluation fails.

        .. note::
           Local module definitions shadow host bindings with the same name.
        """
        return await resolve_name(self, name, span=span)

    @guard_async_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    async def get_resolved(self, name: str, span: SourceSpan | None) -> object:
        """Resolve one validated name while retaining its diagnostic span.

        :param name: Non-empty variable name.
        :param span: Optional requesting source range.
        :returns: Cached, host-provided, or newly evaluated value.
        :raises LclNameError: If hierarchy lookup cannot select the name.
        :raises Exception: If the selected definition evaluation fails.

        .. note::
           Waiters shield a shared owner Task from caller cancellation.
        """
        return await get_resolved(self, name, span)

    @guard_async_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    async def evaluate_definition(self, name: str) -> object:
        """Evaluate and atomically publish one owned definition snapshot.

        :param name: Definition name owned by this Frame.
        :returns: Newly evaluated value after cache and trace publication.
        :raises Exception: If evaluation fails after publishing its failure.

        .. note::
           Flight cleanup occurs even for cancellation or base exceptions.
        """
        return await evaluate_definition(self, name)

    @guard_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    def mixin(self, values: dict[str, object]) -> None:
        """Copy host bindings into an open Frame.

        :param values: String-keyed host bindings applied right-biased.
        :returns: ``None`` after the atomic mapping update.
        :raises LclValidationError: If *values* is not a string-keyed dictionary.
        :raises LclValidationError: If a host-binding name is empty.
        :raises LclClosedFrameError: If Frame closing has begun.

        .. note::
           Validation and detachment finish before any owned state is changed.
        """
        update_host_bindings(self, values)

    @guard_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    def inspect_variable(self, var_name: str) -> VariableInspectionTree:
        """Inspect one selected variable and its unique direct dependency names.

        :param var_name: Non-empty name whose lookup starts at this Frame.
        :returns: A detached tree of cache, syntax, path, and dependency evidence.
        :raises LclValidationError: If *var_name* is not a string.
        :raises LclValidationError: If *var_name* is empty or the parent graph cycles.
        :raises LclClosedFrameError: If this Frame is closing or closed.

        .. note::
           Inspection never evaluates, awaits, creates tasks, or publishes traces.
        """
        return inspect_variable(self, var_name)

    @guard_failure(LclEvaluationError, runtime_codes.NATIVE_231)
    def dependency_snapshot(self, name: str) -> DependencySnapshot:
        """Return point-in-time dependency evidence for one owned definition.

        :param name: Non-empty definition name to inspect.
        :returns: Immutable static, dynamic, and reconciled edge evidence.
        :raises LclValidationError: If *name* is empty.
        :raises LclEvaluationError: If *name* selects a host binding.
        :raises LclNameError: If *name* is absent from the Frame hierarchy.
        :raises LclClosedFrameError: If this Frame is closing or closed.

        .. note::
           Parent definitions are inspected in their owning parent Frame.
        """
        return dependency_snapshot(self, name)
