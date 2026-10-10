"""Observable contracts for hierarchical failures."""

import pytest

from lclang.error import LclError
from lclang.lang import define_frame, define_module, parse_expression


def test_syntax_failure_has_a_six_digit_builtin_code() -> None:
    """An incomplete expression has a classified syntax cause."""
    with pytest.raises(LclError) as caught:
        parse_expression("1 +")
    assert caught.value.code == "LCL121491"


@pytest.mark.asyncio
async def test_distinct_evaluation_causes_have_distinct_codes() -> None:
    """Division, assertions and explicit raises remain distinguishable."""
    module = define_module(
        "failures", {"divide": "1 / 0", "check": "assert(false)", "raise_value": 'raise("stop")'}
    )
    codes: list[str] = []
    async with define_frame(module) as frame:
        for name in ("divide", "check", "raise_value"):
            with pytest.raises(LclError) as caught:
                await frame.get(name)
            codes.append(caught.value.code)
    assert codes == ["LCL131421", "LCL136961", "LCL136962"]
