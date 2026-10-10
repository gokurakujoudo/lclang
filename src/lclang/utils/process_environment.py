"""Live read-only process-environment utility.

Defines ``EnvironmentFrame``, ``Environment``, ``BoundEnvironment``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from lclang.common.scoped_proxy import ScopedProxyFactory, ScopedProxyValue
from lclang.common.source_location import SourceSpan
from lclang.error import LclUtilityError, UtilityErrorCode
from lclang.error.exception_base import LclAttributeError, LclValidationError
from lclang.error.operation_guard import guard_async_failure, guard_constructor, guard_failure


class EnvironmentFrame(Protocol):
    """Describe Frame lookup required by a bound environment utility."""

    async def get_resolved(self, name: str, span: SourceSpan | None) -> object:
        """Resolve one complete scoped override.

        :param name: Complete qualified binding name.
        :param span: Optional source span for diagnostics.
        :returns: Fully resolved override value.
        """
        ...


class Environment(ScopedProxyFactory):
    """Expose current process environment variables without mutation."""

    @guard_failure(LclAttributeError, UtilityErrorCode.E31_PROCESS_ENVIRONMENT_NATIVE_FAILURE)
    def __getattr__(self, name: str) -> str | None:
        """Return one live environment value through attribute syntax.

        :param name: Environment variable name.
        :returns: Current text value, or ``None`` when absent.
        :raises LclAttributeError: If Python requests a private protocol attribute.
        """
        if name.startswith("__"):
            raise LclAttributeError(name, code=UtilityErrorCode.E31_PRIVATE_ATTRIBUTE_ACCESS)
        return os.environ.get(name)

    @guard_failure(LclUtilityError, UtilityErrorCode.E31_PROCESS_ENVIRONMENT_NATIVE_FAILURE)
    def get(self, name: str, default: object = None) -> object:
        """Return one live environment value or a caller-supplied default.

        :param name: Environment variable name, including non-LCL identifiers.
        :param default: Value returned unchanged when the variable is absent.
        :returns: Current text value or *default*.
        :raises LclValidationError: If *name* is not text.
        """
        if not isinstance(name, str):
            raise LclValidationError(
                "environment variable name must be text",
                code=UtilityErrorCode.E31_ENVIRONMENT_VARIABLE_NAME_MUST_BE_TEXT,
            )
        return os.environ.get(name, default)

    @guard_failure(LclUtilityError, UtilityErrorCode.E31_PROCESS_ENVIRONMENT_NATIVE_FAILURE)
    def field_names(self) -> list[str]:
        """Return current environment names usable through LCL attributes.

        :returns: Alphabetically sorted valid LCL identifiers.
        """
        from lclang.lang.common.binding_names import LCL_RESERVED_NAMES

        return sorted(
            name for name in os.environ if name.isidentifier() and name not in LCL_RESERVED_NAMES
        )

    @guard_failure(LclUtilityError, UtilityErrorCode.E31_PROCESS_ENVIRONMENT_NATIVE_FAILURE)
    def bind(self, frame: object, path: tuple[str, ...]) -> ScopedProxyValue:
        """Create a Frame-bound environment view for LCL lookup.

        :param frame: Requesting Frame containing optional scoped overrides.
        :param path: Complete environment utility path.
        :returns: Bound environment view.
        """
        return BoundEnvironment(frame, path, self)  # type: ignore[arg-type]


@guard_constructor(LclValidationError, UtilityErrorCode.E31_PROCESS_ENVIRONMENT_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class BoundEnvironment(ScopedProxyValue):
    """Combine scoped Frame overrides with live environment fallback.

    :param frame: Frame where override lookup begins.
    :param path: Complete environment utility path.
    :param environment: Live process environment view.
    :param trace: Optional terminal dependency recorder.
    """

    frame: EnvironmentFrame
    path: tuple[str, ...]
    environment: Environment
    trace: Callable[[str, SourceSpan], None] | None = None

    def __repr__(self) -> str:
        """Return a stable utility representation.

        :returns: Qualified bound-environment label.
        """
        return f"BoundEnvironment({'.'.join(self.path)})"

    @guard_failure(LclAttributeError, UtilityErrorCode.E31_PROCESS_ENVIRONMENT_NATIVE_FAILURE)
    def __getattr__(self, name: str) -> Any:
        """Return a scoped override or live environment lookup awaitable.

        :param name: Direct environment variable identifier.
        :returns: Coroutine resolving an override, live value, or ``None``.
        :raises LclAttributeError: If Python requests a private protocol attribute.
        """
        if name.startswith("__"):
            raise LclAttributeError(name, code=UtilityErrorCode.E31_PRIVATE_ATTRIBUTE_ACCESS)
        return self.get(name)

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E31_PROCESS_ENVIRONMENT_NATIVE_FAILURE)
    async def get(self, name: str, default: object = None) -> object:
        """Resolve a direct override before consulting the live environment.

        :param name: Environment variable name, including non-LCL identifiers.
        :param default: Value returned when no override or live value exists.
        :returns: Scoped value, nested proxy, live text, or *default*.
        :raises LclValidationError: If *name* is not text.
        """
        from lclang.lang.runtime.frame.binding_lookup import find_scoped_binding
        from lclang.lang.runtime.frame.scoped_proxy import FrameProxy

        if not isinstance(name, str):
            raise LclValidationError(
                "environment variable name must be text",
                code=UtilityErrorCode.E31_ENVIRONMENT_VARIABLE_NAME_MUST_BE_TEXT,
            )
        full = ".".join((*self.path, name))
        owner, kind = find_scoped_binding(self.frame, full)
        if owner is None:
            return self.environment.get(name, default)
        if kind == "proxy":
            return FrameProxy(self.frame, (*self.path, name), self.trace)
        return await self.frame.get_resolved(full, None)

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E31_PROCESS_ENVIRONMENT_NATIVE_FAILURE)
    async def field_names(self) -> list[str]:
        """Return sorted live and scoped direct environment identifiers.

        :returns: Alphabetically sorted unique valid LCL identifiers.
        """
        from lclang.lang.runtime.frame.binding_lookup import hierarchy_binding_names

        prefix = ".".join(self.path) + "."
        names = {
            name[len(prefix) :].split(".", 1)[0]
            for name in hierarchy_binding_names(self.frame)
            if name.startswith(prefix) and len(name) > len(prefix)
        }
        names.update(self.environment.field_names())
        return sorted(names)

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E31_PROCESS_ENVIRONMENT_NATIVE_FAILURE)
    async def resolve_attribute(
        self,
        name: str,
        *,
        safe: bool,
        span: SourceSpan,
    ) -> object:
        """Resolve an LCL environment attribute with scoped precedence.

        :param name: Direct environment identifier or utility method.
        :param safe: Whether a missing value uses safe-access semantics.
        :param span: Complete attribute source span.
        :returns: Utility method, override, nested proxy, live text, or ``None``.
        """
        from lclang.lang.runtime.frame.binding_lookup import find_scoped_binding
        from lclang.lang.runtime.frame.scoped_proxy import FrameProxy

        if name == "get":
            return self.get
        if name == "field_names":
            return self.field_names
        full = ".".join((*self.path, name))
        owner, kind = find_scoped_binding(self.frame, full)
        if owner is None:
            if self.trace is not None:
                self.trace(full, span)
            return self.environment.get(name)
        if kind == "proxy":
            return FrameProxy(self.frame, (*self.path, name), self.trace)
        if self.trace is not None:
            self.trace(full, span)
        return await self.frame.get_resolved(full, span)

    @guard_failure(LclUtilityError, UtilityErrorCode.E31_PROCESS_ENVIRONMENT_NATIVE_FAILURE)
    def with_trace(
        self,
        trace: Callable[[str, SourceSpan], None],
    ) -> BoundEnvironment:
        """Return an equivalent environment view with dependency tracing.

        :param trace: Callback receiving qualified terminal names and spans.
        :returns: Equivalent immutable traced environment utility.
        """
        return BoundEnvironment(self.frame, self.path, self.environment, trace)


# Shared stateless live environment view.
env = Environment()
