"""Deterministic recursive command discovery."""

from __future__ import annotations

import pkgutil
from types import ModuleType
from typing import cast

from lclang.cli.commands import Command, CommandGroup


def scan_commands(
    module: ModuleType,
    name: str,
    description: str,
) -> CommandGroup:
    """Import a module tree and flatten its public commands into one group.

    :param module: Developer-owned trusted Python module or package to import and inspect.
    :param name: Resulting command-group name.
    :param description: Human-readable group description.
    :returns: Deterministically ordered command group.
    :raises TypeError: If *module* is not a module.
    :raises ValueError: If distinct commands share one name.
    """
    if not isinstance(module, ModuleType):
        raise TypeError("command scan root must be a module")
    modules = [module]
    package_path = getattr(module, "__path__", None)
    if package_path is not None:
        names = sorted(
            item.name
            for item in pkgutil.walk_packages(package_path, module.__name__ + ".")
        )
        modules.extend(
            cast(ModuleType, pkgutil.resolve_name(module_name)) for module_name in names
        )
    commands: list[Command] = []
    seen_objects: set[int] = set()
    seen_names: set[str] = set()
    for current in modules:
        for attribute in sorted(vars(current)):
            if attribute.startswith("_"):
                continue
            value = getattr(current, attribute)
            if not isinstance(value, Command) or id(value) in seen_objects:
                continue
            if value.name in seen_names:
                raise ValueError(f"duplicate scanned command name: {value.name}")
            seen_objects.add(id(value))
            seen_names.add(value.name)
            commands.append(value)
    return CommandGroup(name, description, commands)
