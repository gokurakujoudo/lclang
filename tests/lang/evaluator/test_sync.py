"""Unit tests mirroring :mod:`lclang.lang.evaluator.sync`."""

import pytest

import lclang
from lclang.lang.parser import parse_expression


def test_evaluate_sync_owns_a_private_loop() -> None:
    """Synchronous callers can evaluate only outside an active event loop."""
    assert lclang.evaluate_sync(parse_expression("answer"), {"answer": 42}) == 42


def test_evaluate_sync_prefers_source_text_and_retains_structured_syntax_errors() -> None:
    """The sole synchronous boundary parses source before normal evaluation."""
    assert lclang.evaluate_sync("answer + 1", {"answer": 41}) == 42
    with pytest.raises(lclang.LclSyntaxError):
        lclang.evaluate_sync("1 +")


@pytest.mark.asyncio
async def test_evaluate_sync_rejects_a_running_loop() -> None:
    """Async callers receive guidance instead of nested-loop behaviour."""
    with pytest.raises(lclang.LclSyntaxError):
        lclang.evaluate_sync("1 +")
    with pytest.raises(RuntimeError, match="await evaluate"):
        lclang.evaluate_sync("1")


def test_root_exports_the_sole_sync_boundary() -> None:
    """The synchronous convenience remains discoverable at package root."""
    assert "evaluate_sync" in lclang.__all__
