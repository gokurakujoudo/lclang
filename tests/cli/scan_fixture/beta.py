"""Second recursively scanned command fixture."""

from lclang.cli import CliContext, CliResult, cli


@cli.command(name="beta")
async def beta_command(context: CliContext) -> CliResult:
    """Return the second scanned result.

    :param context: Current CLI invocation.
    :returns: Successful empty result.
    """
    del context
    return CliResult.success("")
