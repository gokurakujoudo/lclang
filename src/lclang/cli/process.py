"""Full-argv adaptation for Python-script CLI invocations."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass

from lclang.error import LclCliError, LclCliUsageError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor, guard_failure
from lclang.error.codes.cli import Code as cli_codes


@guard_constructor(LclValidationError, cli_codes.NATIVE_432)
@dataclass(frozen=True, slots=True)
class ArgvParts:
    """Separate executable, script, and post-script tokens.

    :param executable_path: Exact Python executable token.
    :param script_path: Exact Python script token.
    :param tokens: Tokens after the script.
    """

    executable_path: str
    script_path: str
    tokens: tuple[str, ...]

    @property
    @guard_failure(LclCliError, cli_codes.NATIVE_432)
    def script_label(self) -> str:
        """Return the script basename used in help and version output.

        :returns: Platform-neutral final path component.
        """
        return self.script_path.replace("\\", "/").rsplit("/", 1)[-1]


@guard_failure(LclCliError, cli_codes.NATIVE_432)
def split_argv(args: Sequence[str] | None = None) -> ArgvParts:
    """Snapshot and validate one full Python-script argv.

    :param args: Full explicit argv, or ``None`` for current process state.
    :returns: Immutable executable/script/token partition.
    :raises LclCliUsageError: If argv is incomplete or contains invalid tokens.
    """
    values = (sys.executable, *sys.argv) if args is None else tuple(args)
    if len(values) < 2:
        raise LclCliUsageError(
            "full argv requires executable and .py script",
            code=cli_codes.E32_FULL_ARGV_REQUIRES_EXECUTABLE_AND_PY_SCRIPT,
        )
    if any(not isinstance(item, str) or not item for item in values):
        raise LclCliUsageError(
            "argv tokens must be non-empty text",
            code=cli_codes.E32_ARGV_TOKENS_MUST_BE_NON_EMPTY_TEXT,
        )
    if not values[1].endswith(".py"):
        raise LclCliUsageError(
            "script path must end in .py", code=cli_codes.E32_SCRIPT_PATH_MUST_END_IN_PY
        )
    return ArgvParts(values[0], values[1], tuple(values[2:]))
