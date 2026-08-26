"""Lazy local runtime Frame evaluation and snapshot caching."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from types import MappingProxyType
from weakref import WeakSet

from lclang.errors import LclEvaluationError, LclNameError
from lclang.runtime.frame.closing import FrameClosingApi
from lclang.runtime.frame.dependencies import (
    InternalDependencySnapshotApi,
    InternalFrameDependencies,
)
from lclang.runtime.frame.derivation import FrameDerivationApi
from lclang.runtime.frame.evaluation import FrameEvaluationApi
from lclang.runtime.frame.inspector import FrameInspectionApi
from lclang.runtime.frame.lifecycle import InternalFrameLifecycle
from lclang.runtime.frame.limits import EvaluationLimits
from lclang.runtime.frame.lookup import FrameLookupApi
from lclang.runtime.frame.recalculation import internal_refresh_definition
from lclang.runtime.frame.scoped import (
    find_scoped_binding,
    hierarchy_binding_names,
    validate_frame_hierarchy,
)
from lclang.runtime.frame.values import FrameValuesApi
from lclang.runtime.modules import Module
from lclang.scopes import validate_binding_names
from lclang.types import FrameId


class Frame(
    FrameDerivationApi,
    FrameLookupApi,
    FrameValuesApi,
    FrameInspectionApi,
    FrameClosingApi,
    FrameEvaluationApi,
    InternalDependencySnapshotApi,
):
    """Cache lazy evaluations for one runtime module instance.

    :param module: Immutable local definition snapshot.
    :param frame_id: Optional identifier, defaulting to ``frame-<module name>``.
    :param values: Optional initial host bindings copied at construction time.
    :param parent: Optional ancestor used after local definitions and bindings.
    :param limits: Optional resource ceilings, or stable defaults when omitted.
    :param native_values: Whether local host bindings are canonical lclang values.
    :raises TypeError: If an optional identifier or native flag has the wrong type.
    :raises ValueError: If *frame_id* or any host binding name is empty.

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
    ) -> None:
        """Create an empty result cache over immutable inputs.

        :param module: Immutable local definition snapshot.
        :param frame_id: Optional string identifier or nominal Frame identifier.
        :param values: Optional initial host bindings copied at construction time.
        :param parent: Optional ancestor used after local definitions and bindings.
        :param limits: Optional resource ceilings, or defaults when omitted.
        :param native_values: Whether local host bindings are canonical lclang values.
        :returns: ``None`` after independent runtime state is initialized.
        :raises TypeError: If *frame_id* or *native_values* has the wrong type.
        :raises ValueError: If the effective ID or a host binding name is empty.

        .. note::
           Omitting *frame_id* derives ``frame-<module name>`` deterministically.
        """
        if frame_id is not None and not isinstance(frame_id, str):
            raise TypeError("frame identifier must be a string")
        if not isinstance(native_values, bool):
            raise TypeError("native-values flag must be Boolean")
        effective_id = FrameId(f"frame-{module.name}") if frame_id is None else FrameId(frame_id)
        if not effective_id:
            raise ValueError("frame identifier cannot be empty")
        snapshot = {} if values is None else dict(values)
        if any(not isinstance(name, str) for name in snapshot):
            raise TypeError("host binding names must be strings")
        if any(not name for name in snapshot):
            raise ValueError("host binding name cannot be empty")
        validate_binding_names(snapshot)
        self.module = module
        self.frame_id = effective_id
        self._values = snapshot
        self.values: Mapping[str, object] = MappingProxyType(self._values)
        self.parent = parent
        self._children: WeakSet[Frame] = WeakSet()
        self.limits = EvaluationLimits() if limits is None else limits
        self.native_values = native_values
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

    async def recalculate(self, name: str) -> object:
        """Explicitly refresh one owned definition snapshot.

        :param name: Non-empty definition name to refresh.
        :returns: Newly evaluated result after its atomic cache commit.
        :raises ValueError: If *name* is empty.
        :raises LclEvaluationError: If *name* selects a host binding or fails.
        :raises LclNameError: If *name* is absent from the Frame hierarchy.

        .. note::
           Cached dependants and the previous snapshot are never invalidated.
        """
        self._lifecycle.ensure_open(None)
        if not name:
            raise ValueError("variable name cannot be empty")
        _, kind = find_scoped_binding(self, name)
        if kind == "proxy":
            raise LclEvaluationError(f"Frame proxy cannot be recalculated: {name}")
        if name in self.module.definitions:
            return await internal_refresh_definition(
                name,
                self._inflight,
                self._refreshes,
                self.evaluate_definition,
                lambda: self._lifecycle.ensure_open(None),
            )
        if name in self.values:
            message = f"host binding cannot be recalculated: {name}"
            raise LclEvaluationError(message)
        if self.parent is not None:
            return await self.parent.recalculate(name)
        raise LclNameError(f"unknown variable: {name}")
