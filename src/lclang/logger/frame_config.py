"""Resolve scoped Frame settings into standalone logger configuration."""

from __future__ import annotations

import logging
from copy import copy
from typing import cast

from lclang.error import LclError, LclLoggerError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_failure
from lclang.error.codes.logging import Code as logging_codes
from lclang.error.wrapping import wrap_failure
from lclang.logger.config import LoggerHandlerConfig, handler_config
from lclang.logger.validation import level, mapping
from lclang.runtime import Frame
from lclang.runtime.frame.binding_lookup import find_scoped_binding
from lclang.scope_proxy import FrameProxy


@guard_async_failure(LclLoggerError, logging_codes.NATIVE_613)
async def proxy_values(proxy: FrameProxy) -> dict[str, object]:
    """Resolve only the effective logger subtree and its necessary dependencies.

    :param proxy: Logger or nested configuration proxy.
    :returns: Plain nested values suitable for core validation.
    :raises LclValidationError: If a leaf expression fails, annotated with its field path.
    """
    values: dict[str, object] = {}
    for name in await proxy.field_names():
        try:
            value = await proxy.get(name)
        except Exception as error:
            path = ".".join((*proxy.path, name))
            if isinstance(error, ExceptionGroup):
                failure = wrap_failure(
                    cast(ExceptionGroup[Exception], error),
                    LclValidationError,
                    (
                        error.code
                        if isinstance(error, LclError)
                        else logging_codes.E13_CANNOT_RESOLVE_LOGGER_SETTING_VALUE
                    ),
                )
                failure.add_note(f"logger setting {path}")
                raise failure from failure.__cause__
            raise LclValidationError(
                f"cannot resolve logger setting {path!r}",
                code=(
                    error.code
                    if isinstance(error, LclError)
                    else logging_codes.E13_CANNOT_RESOLVE_LOGGER_SETTING_VALUE
                ),
            ) from error
        values[name] = await proxy_values(value) if isinstance(value, FrameProxy) else value
    return values


@guard_failure(LclLoggerError, logging_codes.NATIVE_613)
def verbose_config(config: LoggerHandlerConfig) -> LoggerHandlerConfig:
    """Lower output thresholds without changing sink ownership or source filters.

    :param config: Fully validated configured outputs.
    :returns: Fresh configuration with DEBUG admission or a lower existing level.
    """
    console = dict(config.console)
    if config.resolved_console().enabled:
        console["level"] = min(config.resolved_console().level, logging.DEBUG)
    files = {name: dict(mapping(value, name)) for name, value in config.file.items()}
    for name, sink in config.resolved_files().items():
        if sink.enabled:
            files[name]["level"] = min(sink.level, logging.DEBUG)
    return LoggerHandlerConfig(
        level=min(level(config.level, "logger.level"), logging.DEBUG),
        format=config.format,
        console=console,
        file=files,
        takeover_loggers=config.takeover_loggers,
        capture_warnings=config.capture_warnings,
        timezone=config.timezone,
    )


@guard_async_failure(LclLoggerError, logging_codes.NATIVE_613)
async def resolve_logger_config(frame: Frame, verbose: bool = False) -> LoggerHandlerConfig:
    """Materialize layered logger fields once before any sinks are initialized.

    :param frame: Caller-owned Frame containing scoped logger fields and dependencies.
    :param verbose: Whether to force DEBUG for enabled outputs.
    :returns: Validated settings, using handler defaults when the namespace is absent.
    :raises LclValidationError: If the namespace is not a FrameProxy or a field type is invalid.
    :raises LclValidationError: If a field value is invalid or a leaf expression fails.
    :raises LclError: If resolving the logger namespace fails.
    :raises LclLoggerError: If native configuration resolution fails.

    .. note::
       Only logger fields and their dependencies are evaluated. The caller owns
       the Frame and handler scope; resolution neither starts sinks nor closes resources.
    """
    missing = object()
    proxy = await frame.get("logger", fallback=missing)
    if proxy is missing:
        values = {}
    elif isinstance(proxy, FrameProxy):
        values = await proxy_values(proxy)
    else:
        raise LclValidationError(
            "logger must remain a FrameProxy configuration namespace",
            code=logging_codes.E13_LOGGER_MUST_REMAIN_A_FRAMEPROXY_CONFIGURATION_NAMESPACE,
        )
    try:
        config = handler_config(values)
    except LclValidationError as error:
        path = error.message.partition(":")[0]
        failure = copy(error)
        failure.message = f"{error.message} (source: {logger_source(frame, path)})"
        failure.args = (failure.message,)
        raise failure from error.__cause__
    return verbose_config(config) if verbose else config


@guard_failure(LclLoggerError, logging_codes.NATIVE_613)
def logger_source(frame: Frame, path: str) -> str:
    """Locate source metadata without evaluating the invalid field again.

    :param frame: Application configuration hierarchy.
    :param path: Qualified field reported by core validation.
    :returns: Source location or nearest owning layer for absent required fields.
    """
    owner, _ = find_scoped_binding(frame, path)
    parts = path.split(".")
    if owner is None and len(parts) >= 4 and parts[:2] == ["logger", "file"]:
        inherited = ".".join((*parts[:2], "default", *parts[3:]))
        inherited_owner, _ = find_scoped_binding(frame, inherited)
        if inherited_owner is not None:
            owner, path = inherited_owner, inherited
    while owner is None and "." in path:
        path = path.rpartition(".")[0]
        owner, _ = find_scoped_binding(frame, path)
    if owner is None:
        return str(frame.module.name)
    definition = owner.module.definitions.get(path)
    if definition is None:
        return str(owner.module.name)
    span = definition.span
    return f"{owner.module.name}, {span.origin.name}:{span.start.line}:{span.start.column}"
