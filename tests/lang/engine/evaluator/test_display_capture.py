"""Display consumers can change admission without affecting expression results."""

import logging

import pytest

from lclang.lang import parse_expression
from lclang.lang.engine.evaluator.ast_interpreter import interpret_expression
from lclang.logger import use_verbose


@pytest.mark.asyncio
@pytest.mark.parametrize("admissions", range(17))
async def test_logger_closes_admission_between_expression_boundaries(admissions: int) -> None:
    """A borrowed logger may stop admitting records after a producer's initial check."""

    class ClosingLogger(logging.Logger):
        def __init__(self) -> None:
            super().__init__("closing", logging.DEBUG)
            self.remaining = admissions

        def isEnabledFor(self, level: int) -> bool:
            del level
            admitted = self.remaining > 0
            self.remaining -= 1
            return admitted

    node = parse_expression("((x) -> x + 1)(1)")
    logger = ClosingLogger()
    with use_verbose(logger):
        assert await interpret_expression(node) == 2
    assert logger.remaining < admissions
