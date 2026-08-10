"""Built-in pylcl commands for static inspection and lazy evaluation."""

from contextlib import suppress

from pylcl._version import __version__
from pylcl.cli.builtin_docs import render_builtin_docs
from pylcl.cli.commands import CommandGroup, cli
from pylcl.cli.context import CliContext
from pylcl.cli.entrance import CliEntrance
from pylcl.cli.models import CliResult, ParameterDoc

# Shared required output binding documented by both built-in commands.
RESULT_PARAMETER = ParameterDoc(
    "RESULT",
    object,
    True,
    "Result binding to inspect or evaluate",
)
# Optional evaluated-inspection switch for the parse command.
EVAL_PARAMETER = ParameterDoc(
    "EVAL",
    bool,
    False,
    "Evaluate RESULT before rendering its inspection tree",
    False,
)


@cli.command(parameter_docs=(RESULT_PARAMETER, EVAL_PARAMETER))
async def parse_lcl_command(context: CliContext) -> CliResult:
    """Render the dependency tree for RESULT, optionally after evaluation.

    :param context: Current module-command invocation.
    :returns: Successful unevaluated or post-evaluation inspection tree.

    .. note::
       Ordinary RESULT failures are retained in the Frame cache and rendered.
    """
    if await context.frame.get("EVAL") is True:
        with suppress(Exception):
            await context.frame.get("RESULT")
    tree = context.frame.inspect_variable("RESULT")
    return CliResult.success("\n".join(tree.to_lines()))


@cli.command(parameter_docs=(RESULT_PARAMETER,))
async def eval_lcl_command(context: CliContext) -> CliResult:
    """Evaluate RESULT and render its string representation.

    :param context: Current module-command invocation.
    :returns: Successful evaluated result.
    :raises Exception: If lazy ``RESULT`` evaluation fails.
    """
    value = await context.frame.get("RESULT")
    return CliResult.success(str(value))


@cli.command()
async def builtins_command(context: CliContext) -> CliResult:
    """List canonical LCL builtins and namespace methods.

    :param context: Current module-command invocation.
    :returns: Successful deterministic builtin documentation listing.

    .. note::
       Rendering uses static reviewed metadata and does not evaluate the Frame.
    """
    return CliResult.success(render_builtin_docs())


# Root container for the three executable pylcl module commands.
PYLCL_CLI_GROUP = CommandGroup(
    "pylcl",
    "Inspect, evaluate, and document LCL builtins",
    (parse_lcl_command, eval_lcl_command, builtins_command),
)
# Public entrance used by the module adapter and in-process callers.
PYLCL_CLI_ENTRANCE = CliEntrance(PYLCL_CLI_GROUP, __version__)
