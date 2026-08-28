"""First recursively scanned command fixture."""

from lclang.cli import CliContext, CliResult, cli


@cli.command(name="alpha")
async def alpha_command(context: CliContext) -> CliResult:
    """Return the first scanned result.

    :param context: Current CLI invocation.
    :returns: Successful empty result.
    """
    del context
    return CliResult.success("")
