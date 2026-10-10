"""Typed command decorators and immutable command groups."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import get_type_hints

from lclang.cli.context import CliContext
from lclang.cli.models import CliResult, ParameterDoc
from lclang.cli.validation import (
    DECLARATION_RESERVED_NAMES,
    normalize_text,
    require_command_segment,
    require_lcl_qualified_name,
)
from lclang.defaults import DefaultBinding
from lclang.error import LclCliError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_constructor, guard_failure
from lclang.error.codes.cli import Code as cli_codes
from lclang.masking import normalize_masked_mapping

CommandHandler = Callable[[CliContext], Awaitable[CliResult]]


@guard_failure(LclCliError, cli_codes.NATIVE_411)
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


@guard_failure(LclValidationError, cli_codes.NATIVE_411)
def validate_handler(handler: object) -> CommandHandler:
    """Return a handler satisfying the exact async public contract.

    :param handler: Candidate decorated object.
    :returns: Validated async handler.
    :raises LclValidationError: If callable shape or annotations are incompatible.
    """
    if not inspect.iscoroutinefunction(handler):
        raise LclValidationError(
            "CLI command handler must be async",
            code=cli_codes.E11_CLI_COMMAND_HANDLER_MUST_BE_ASYNC,
        )
    signature = inspect.signature(handler)
    parameters = tuple(signature.parameters.values())
    if (
        len(parameters) != 1
        or parameters[0].name != "context"
        or parameters[0].kind is not inspect.Parameter.POSITIONAL_OR_KEYWORD
        or parameters[0].default is not inspect.Parameter.empty
    ):
        raise LclValidationError(
            "CLI command handler must accept exactly context",
            code=cli_codes.E11_CLI_COMMAND_HANDLER_MUST_ACCEPT_EXACTLY_CONTEXT,
        )
    try:
        hints = get_type_hints(handler)
    except Exception as error:
        raise LclValidationError(
            "CLI command handler annotations cannot be resolved",
            code=cli_codes.E11_CLI_COMMAND_HANDLER_ANNOTATIONS_CANNOT_BE_RESOLVED,
        ) from error
    if hints.get("context") is not CliContext or hints.get("return") is not CliResult:
        raise LclValidationError(
            "CLI command handler annotations must be CliContext and CliResult",
            code=cli_codes.E11_CLI_COMMAND_HANDLER_ANNOTATIONS_MUST_BE_CLICONTEXT_AND_CLIRESULT,
        )
    return handler


@guard_constructor(LclValidationError, cli_codes.NATIVE_411)
@dataclass(frozen=True, slots=True)
class Command:
    """Declare one executable async leaf command.

    :param name: Literal snake_case command segment.
    :param summary: One-line help summary.
    :param parameter_docs: Ordered configuration parameter declarations.
    :param preset: Immutable shallow host-binding preset.
    :param handler: Exactly typed async Python handler.
    :param masked_names: Immutable normalized preset names to redact.
    :param default_bindings: Lowest-priority lazy workflow variable declarations.
    """

    name: str
    summary: str
    parameter_docs: Sequence[ParameterDoc]
    preset: Mapping[str, object]
    handler: CommandHandler
    masked_names: frozenset[str] = field(default_factory=frozenset[str], kw_only=True)
    default_bindings: Mapping[str, DefaultBinding] = field(
        default_factory=dict[str, DefaultBinding], kw_only=True
    )

    @guard_failure(LclValidationError, cli_codes.NATIVE_411)
    def __post_init__(self) -> None:
        """Detach declaration inputs and reject ambiguous metadata.

        :returns: ``None``.
        :raises LclValidationError: If a declaration or handler has the wrong type.
        :raises LclValidationError: If a name is invalid, duplicate, or reserved.
        """
        name = require_command_segment(self.name, "command name")
        docs = tuple(self.parameter_docs)
        if any(not isinstance(item, ParameterDoc) for item in docs):
            raise LclValidationError(
                "command parameter docs must contain ParameterDoc values",
                code=cli_codes.E11_COMMAND_PARAMETER_DOCS_MUST_CONTAIN_PARAMETERDOC_VALUES,
            )
        names = [item.name for item in docs]
        if len(names) != len(set(names)):
            raise LclValidationError(
                "duplicate command parameter name",
                code=cli_codes.E11_DUPLICATE_COMMAND_PARAMETER_NAME,
            )
        if any(name.split(".", 1)[0] in DECLARATION_RESERVED_NAMES for name in names):
            raise LclValidationError(
                "command parameter name is reserved",
                code=cli_codes.E11_COMMAND_PARAMETER_NAME_IS_RESERVED,
            )
        if not isinstance(self.preset, Mapping):
            raise LclValidationError(
                "command preset must be a mapping",
                code=cli_codes.E11_COMMAND_PRESET_MUST_BE_A_MAPPING,
            )
        normalized_preset, masked_names = normalize_masked_mapping(
            self.preset,
            self.masked_names,
        )
        for preset_name in normalized_preset:
            require_lcl_qualified_name(preset_name, "preset name")
        if {name.split(".", 1)[0] for name in normalized_preset} & DECLARATION_RESERVED_NAMES:
            raise LclValidationError(
                "command preset name is reserved",
                code=cli_codes.E11_COMMAND_PRESET_NAME_IS_RESERVED,
            )
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "summary", normalize_text(self.summary, "command summary"))
        object.__setattr__(self, "parameter_docs", docs)
        object.__setattr__(self, "preset", MappingProxyType(normalized_preset))
        object.__setattr__(self, "masked_names", masked_names)
        object.__setattr__(self, "default_bindings", MappingProxyType(dict(self.default_bindings)))
        object.__setattr__(self, "handler", validate_handler(self.handler))

    @guard_async_failure(LclCliError, cli_codes.NATIVE_411)
    async def run(self, args: Sequence[str] | None = None) -> int:
        """Run this command directly from full argv.

        :param args: Full argv, or ``None`` to adapt the current process.
        :returns: Integer command status.
        """
        from lclang.cli.run import run_command

        return await run_command(self, args)


@guard_constructor(LclValidationError, cli_codes.NATIVE_411)
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

    @guard_failure(LclValidationError, cli_codes.NATIVE_411)
    def __post_init__(self) -> None:
        """Detach children and reject invalid or ambiguous group declarations.

        :returns: ``None``.
        :raises LclValidationError: If one child has an unsupported type.
        :raises LclValidationError: If name or child names are invalid or duplicated.
        """
        name = require_command_segment(self.name, "command group name")
        children = tuple(self.commands)
        if any(not isinstance(item, (Command, CommandGroup)) for item in children):
            raise LclValidationError(
                "command group children must be commands or groups",
                code=cli_codes.E11_COMMAND_GROUP_CHILDREN_MUST_BE_COMMANDS_OR_GROUPS,
            )
        names = [item.name for item in children]
        if len(names) != len(set(names)):
            raise LclValidationError(
                "duplicate command group child name",
                code=cli_codes.E11_DUPLICATE_COMMAND_GROUP_CHILD_NAME,
            )
        object.__setattr__(self, "name", name)
        description = normalize_text(self.description, "group description")
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "commands", children)


class CliFacade:
    """Create immutable commands through a concise decorator surface."""

    @guard_failure(LclCliError, cli_codes.NATIVE_411)
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
        values: Mapping[str, object] = {} if preset is None else preset

        def decorate(handler: CommandHandler) -> Command:
            """Convert one exactly typed handler into a command.

            :param handler: Async handler to validate and retain.
            :returns: Immutable declared command.
            """
            default_name = getattr(handler, "__name__", "command")
            if default_name.endswith("_command"):
                default_name = default_name[: -len("_command")]
            selected_name = default_name if name is None else name
            selected_summary = handler_summary(handler) if summary is None else summary
            return Command(selected_name, selected_summary, docs, values, handler)

        return decorate


# Shared stateless decorator facade.
cli = CliFacade()
