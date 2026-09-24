"""Language evaluator behaviour without an installed runtime budget."""

from typing import cast

import pytest

from lclang import evaluate
from lclang.lang.parser import parse_expression


@pytest.mark.asyncio
async def test_standalone_evaluation_has_no_implicit_runtime_limits() -> None:
    """The language layer remains unrestricted outside a runtime Frame."""
    source = "[item for item in values]"
    values = tuple(range(10_001))
    result = await evaluate(parse_expression(source), {"values": values})
    assert isinstance(result, list)
    assert len(cast(list[object], result)) == len(values)
