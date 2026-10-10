"""CLI routing exceptions and retained command scope.

Defines ``RouteFailure``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lclang.error.codes.e4_cli_error_code import CliErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.exception_family import LclCliUsageError
from lclang.error.operation_guard import guard_constructor

if TYPE_CHECKING:
    from lclang.cli.command_definition import CommandGroup


@guard_constructor(LclValidationError, CliErrorCode.E21_COMMAND_ROUTING_NATIVE_FAILURE)
class RouteFailure(LclCliUsageError):
    """Report routing failure with its nearest group scope."""

    def __init__(
        self, message: str, group: CommandGroup, path: tuple[str, ...], *, code: str | None = None
    ) -> None:
        """Create one nearest-scope routing failure.

        :param message: Human-readable routing problem.
        :param group: Nearest group whose help should render.
        :param path: Consumed path to that group.
        :param code: Classified routing cause.
        :returns: ``None``.
        """
        super().__init__(message, code=code)
        self.group = group
        self.path = path
