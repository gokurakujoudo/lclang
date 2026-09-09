"""Recognize CLI logger parameters and flatten entry-point defaults."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields

from lclang.ast import LclAstNode, LclConstant
from lclang.logger import LoggerHandlerConfig
from lclang.logger.config import CONFIG_FIELDS
from lclang.logger.sink_config import CONSOLE_FIELDS, FILE_FIELDS


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
