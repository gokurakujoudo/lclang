"""Adapt layered LCL logger bindings to the standalone logging configuration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import fields

from lclang.ast import LclAstNode, LclConstant
from lclang.logger import LoggerHandlerConfig
from lclang.logger.config import CONFIG_FIELDS, handler_config
from lclang.logger.sink_config import CONSOLE_FIELDS, FILE_FIELDS
from lclang.logger.validation import level, mapping
from lclang.runtime import Frame
from lclang.runtime.frame.binding_lookup import find_scoped_binding
from lclang.scope_proxy import FrameProxy


def logger_parameter(name: str) -> bool:
    """Recognize valid framework logger leaf names without accepting arbitrary prefixes.

    :param name: Full qualified parameter name.
    :returns: Whether the name belongs to the public logger schema.
    """
    parts = name.split(".")
    if len(parts) < 2 or parts[0] != "logger":
        return False
    if parts[1] == "console":
        return len(parts) == 3 and parts[2] in CONSOLE_FIELDS
    if parts[1] == "file":
        if len(parts) < 4 or not parts[2].isidentifier():
            return False
        if parts[3] == "rotation":
            return len(parts) == 5 and parts[4] in {"mode", "max_bytes", "interval", "align"}
        return len(parts) == 4 and parts[3] in FILE_FIELDS
    return len(parts) == 2 and parts[1] in CONFIG_FIELDS


def logger_definitions(config: LoggerHandlerConfig) -> dict[str, LclAstNode]:
    """Flatten declared defaults while retaining absent sink fields for inheritance.

    :param config: Entry-point logging defaults.
    :returns: Qualified constant definitions for the defaults Frame.
    """
    result: dict[str, LclAstNode] = {}

    def flatten(path: str, value: object) -> None:
        """Expose nested dictionaries as qualified leaves.

        :param path: Qualified field prefix.
        :param value: Frozen configuration field or mapping.
        """
        if isinstance(value, Mapping):
            for key, item in value.items():
                flatten(f"{path}.{key}", item)
            if not value and path.startswith("logger.file."):
                result[path] = LclConstant(value={})
        else:
            result[path] = LclConstant(value=value)

    for item in fields(config):
        flatten(f"logger.{item.name}", getattr(config, item.name))
    return result


async def proxy_values(proxy: FrameProxy) -> dict[str, object]:
    """Resolve only the effective logger subtree and its necessary dependencies.

    :param proxy: Logger or nested configuration proxy.
    :returns: Plain nested values suitable for core validation.
    :raises ValueError: If a leaf expression fails, annotated with its field path.
    """
    values: dict[str, object] = {}
    for name in await proxy.field_names():
        try:
            value = await proxy.get(name)
            values[name] = await proxy_values(value) if isinstance(value, FrameProxy) else value
        except Exception as error:
            path = ".".join((*proxy.path, name))
            raise ValueError(f"{path}: {error}") from error
    return values


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
    )


async def resolve_logger_config(frame: Frame, verbose: bool = False) -> LoggerHandlerConfig:
    """Materialize layered logger fields once before any sinks are initialized.

    :param frame: Final CLI Frame containing config and command-line overrides.
    :param verbose: Whether to force DEBUG for enabled outputs.
    :returns: Validated standalone logger settings.
    :raises TypeError: If the logger namespace is replaced with a scalar value.
    """
    proxy = await frame.get("logger")
    if not isinstance(proxy, FrameProxy):
        raise TypeError("logger must remain a FrameProxy configuration namespace")
    values = await proxy_values(proxy)
    try:
        config = handler_config(values)
    except (TypeError, ValueError) as error:
        path = str(error).partition(":")[0]
        raise type(error)(f"{error} (source: {logger_source(frame, path)})") from error
    return verbose_config(config) if verbose else config


def logger_source(frame: Frame, path: str) -> str:
    """Locate source metadata without evaluating the invalid field again.

    :param frame: Final CLI configuration hierarchy.
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
