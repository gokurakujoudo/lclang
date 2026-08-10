"""Typed command decorators and immutable command groups."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import get_type_hints

from pylcl.cli.context import CliContext
from pylcl.cli.models import CliResult, ParameterDoc
from pylcl.cli.validation import (
    DECLARATION_RESERVED_NAMES,
    freeze_mapping,
    normalize_text,
    require_command_segment,
    require_lcl_identifier,
)

CommandHandler = Callable[[CliContext], Awaitable[CliResult]]


def handler_summary(handler: CommandHandler) -> str:
    """Extract normalized prose before rST fields and directives.

    :param handler: Validated command handler.
    :returns: One-line prose summary, possibly empty.
    """
    documentation = inspect.getdoc(handler) or ""
    prose: list[str] = []
    for line in documentation.splitlines():
        stripped = line.strip()
        if stripped.startswith(":") or stripped.startswith(".. "):
            break
        prose.append(stripped)
    return " ".join(" ".join(prose).split())


def validate_handler(handler: object) -> CommandHandler:
    """Return a handler satisfying the exact async public contract.

    :param handler: Candidate decorated object.
    :returns: Validated async handler.
    :raises TypeError: If callable shape or annotations are incompatible.
    """
    if not inspect.iscoroutinefunction(handler):
        raise TypeError("CLI command handler must be async")
    signature = inspect.signature(handler)
    parameters = tuple(signature.parameters.values())
    if (
        len(parameters) != 1
        or parameters[0].name != "context"
        or parameters[0].kind is not inspect.Parameter.POSITIONAL_OR_KEYWORD
        or parameters[0].default is not inspect.Parameter.empty
    ):
        raise TypeError("CLI command handler must accept exactly context")
    try:
        hints = get_type_hints(handler)
    except Exception as error:
        raise TypeError("CLI command handler annotations cannot be resolved") from error
    if hints.get("context") is not CliContext or hints.get("return") is not CliResult:
        raise TypeError("CLI command handler annotations must be CliContext and CliResult")
    return handler


@dataclass(frozen=True, slots=True)
class Command:
    """Declare one executable async leaf command.

    :param name: Literal snake_case command segment.
    :param summary: One-line help summary.
    :param parameter_docs: Ordered configuration parameter declarations.
    :param preset: Immutable shallow host-binding preset.
    :param handler: Exactly typed async Python handler.
    """

    name: str
    summary: str
    parameter_docs: Sequence[ParameterDoc]
    preset: Mapping[str, object]
    handler: CommandHandler

    def __post_init__(self) -> None:
        """Detach declaration inputs and reject ambiguous metadata.

        :returns: ``None``.
        :raises TypeError: If a declaration or handler has the wrong type.
        :raises ValueError: If a name is invalid, duplicate, or reserved.
        """
        name = require_command_segment(self.name, "command name")
        docs = tuple(self.parameter_docs)
        if any(not isinstance(item, ParameterDoc) for item in docs):
            raise TypeError("command parameter docs must contain ParameterDoc values")
        names = [item.name for item in docs]
        if len(names) != len(set(names)):
            raise ValueError("duplicate command parameter name")
        if set(names) & DECLARATION_RESERVED_NAMES:
            raise ValueError("command parameter name is reserved")
        preset = freeze_mapping(self.preset, "command preset")
        for preset_name in preset:
            require_lcl_identifier(preset_name, "preset name")
        if set(preset) & DECLARATION_RESERVED_NAMES:
            raise ValueError("command preset name is reserved")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "summary", normalize_text(self.summary, "command summary"))
        object.__setattr__(self, "parameter_docs", docs)
        object.__setattr__(self, "preset", preset)
        object.__setattr__(self, "handler", validate_handler(self.handler))

    async def run(self, args: Sequence[str] | None = None) -> int:
        """Run this command directly from full argv.

        :param args: Full argv, or ``None`` to adapt the current process.
        :returns: Integer command status.
        """
        from pylcl.cli.run import run_command

        return await run_command(self, args)


@dataclass(frozen=True, slots=True)
class CommandGroup:
    """Compose ordered commands and groups under one snake_case name.

    :param name: Literal snake_case group name.
    :param description: Human-readable group help.
    :param commands: Ordered child commands or groups.
    """

    name: str
    description: str
    commands: Sequence[Command | CommandGroup]

    def __post_init__(self) -> None:
        """Detach children and reject invalid or ambiguous group declarations.

        :returns: ``None``.
        :raises TypeError: If one child has an unsupported type.
        :raises ValueError: If name or child names are invalid or duplicated.
        """
        name = require_command_segment(self.name, "command group name")
        children = tuple(self.commands)
        if any(not isinstance(item, (Command, CommandGroup)) for item in children):
            raise TypeError("command group children must be commands or groups")
        names = [item.name for item in children]
        if len(names) != len(set(names)):
            raise ValueError("duplicate command group child name")
        object.__setattr__(self, "name", name)
        description = normalize_text(self.description, "group description")
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "commands", children)


class CliFacade:
    """Create immutable commands through a concise decorator surface."""

    def command(
        self,
        name: str | None = None,
        summary: str | None = None,
        parameter_docs: Iterable[ParameterDoc] = (),
        preset: Mapping[str, object] | None = None,
    ) -> Callable[[CommandHandler], Command]:
        """Return a decorator producing a :class:`Command`.

        :param name: Optional command name; handler name is the default.
        :param summary: Optional help summary; handler prose is the default.
        :param parameter_docs: Ordered parameter declarations.
        :param preset: Optional shallow host-binding preset.
        :returns: Decorator that validates and snapshots one handler.
        """
        docs = tuple(parameter_docs)
        values = {} if preset is None else dict(preset)

        def decorate(handler: CommandHandler) -> Command:
            """Convert one exactly typed handler into a command.

            :param handler: Async handler to validate and retain.
            :returns: Immutable declared command.
            """
            selected_handler = validate_handler(handler)
            default_name = handler.__name__
            if default_name.endswith("_command"):
                default_name = default_name[: -len("_command")]
            selected_name = default_name if name is None else name
            selected_summary = handler_summary(handler) if summary is None else summary
            return Command(selected_name, selected_summary, docs, values, selected_handler)

        return decorate


# Shared stateless decorator facade.
cli = CliFacade()
