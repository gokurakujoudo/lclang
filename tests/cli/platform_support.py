"""Static cross-platform fixtures for CLI subprocess acceptance tests."""

from pathlib import Path

# Complete Python application used without shell token parsing.
SAMPLE_SCRIPT = '''\
import asyncio
import sys

from lclang.cli import (
    CliContext,
    CliEntrance,
    CliResult,
    CliResultStatus,
    CommandGroup,
    ParameterDoc,
    cli,
)


@cli.command(
    parameter_docs=(
        ParameterDoc("message", str, True, "Rendered message"),
        ParameterDoc("literal", str, True, "Literal token"),
        ParameterDoc("quoted", str, True, "Quoted token"),
    )
)
async def show_command(context: CliContext) -> CliResult:
    """Render values supplied by every invocation layer.

    :param context: Current invocation state.
    :returns: Successful composite result.
    """
    message = await context.frame.get("message")
    literal = await context.frame.get("literal")
    quoted = await context.frame.get("quoted")
    context.logger.info("message=%s", message)
    description = (
        f"{message}|{literal}|{quoted}|{context.as_of_date.isoformat()}|"
        f"{str(context.dryrun).lower()}"
    )
    return CliResult(CliResultStatus.SUCCESS, description)


admin = CommandGroup("admin", "Administrative commands", (show_command,))
entrance = CliEntrance(CommandGroup("root", "Application", (admin,)), "3.2.1")
raise SystemExit(asyncio.run(entrance.run()))
'''
# Root static configuration used by the subprocess case.
ROOT_CONFIG = 'using "shared.lclcfg"\nmessage: prefix + suffix\n'
# Included static configuration used by the subprocess case.
SHARED_CONFIG = 'prefix: "café "\nsuffix: "config"\n'


def materialize_platform_case(root: Path) -> tuple[Path, Path]:
    """Write the fixed application and config graph under one temporary root.

    :param root: Automatically cleaned per-case directory.
    :returns: Sample script and root configuration paths.
    """
    application = root / "spaced 应用" / "sample tool.py"
    application.parent.mkdir()
    application.write_text(SAMPLE_SCRIPT, encoding="utf-8")
    config_root = root / "static 配置"
    config_root.mkdir()
    config = config_root / "root.lclcfg"
    config.write_text(ROOT_CONFIG, encoding="utf-8")
    (config_root / "shared.lclcfg").write_text(SHARED_CONFIG, encoding="utf-8")
    return application, config
