"""Built-in lclang commands for static inspection and lazy evaluation."""

from contextlib import suppress

from lclang._version import __version__
from lclang.cli.builtin_docs import render_builtin_docs
from lclang.cli.commands import CommandGroup, cli
from lclang.cli.context import CliContext
from lclang.cli.entrance import CliEntrance
from lclang.cli.models import CliResult, ParameterDoc

# Shared required output binding documented by both built-in commands.
# Unitless parameter names, command groups and entrance objects below define the built-in CLI
# contract. RESULT, EVAL and FORCE preserve exact routing and override spellings; the shared
# immutable entrance keeps module execution consistent with embedded commands.
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
# Optional strict parsing switch shared by expression-oriented commands.
FORCE_PARAMETER = ParameterDoc(
    "FORCE",
    bool,
    False,
    "Require marked RESULT text to contain valid LCL",
    False,
)


@cli.command(parameter_docs=(RESULT_PARAMETER, EVAL_PARAMETER, FORCE_PARAMETER))
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


@cli.command(parameter_docs=(RESULT_PARAMETER, FORCE_PARAMETER))
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


# Root container for the three executable lclang module commands.
LCLANG_CLI_GROUP = CommandGroup(
    "lclang",
    "Inspect, evaluate, and document LCL builtins",
    (parse_lcl_command, eval_lcl_command, builtins_command),
)
# Public entrance used by the module adapter and in-process callers.
LCLANG_CLI_ENTRANCE = CliEntrance(LCLANG_CLI_GROUP, __version__)
