"""Language evaluator behaviour without an installed runtime budget."""

from typing import cast

import pytest

from lclang.lang.engine.evaluator.ast_interpreter import interpret_expression
from lclang.lang.engine.parser import parse_expression


@pytest.mark.asyncio
async def test_interpreter_has_no_implicit_runtime_limits() -> None:
    """The language layer remains unrestricted outside a runtime Frame."""
    source = "[item for item in values]"
    values = tuple(range(10_001))
    result = await interpret_expression(parse_expression(source), {"values": values})
    assert isinstance(result, list)
    assert len(cast(list[object], result)) == len(values)
