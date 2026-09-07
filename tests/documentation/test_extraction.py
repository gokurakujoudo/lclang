"""Whitespace preservation and malformed-marker contracts for document fixtures."""

import pytest

from tests.documentation.examples import EXECUTION_MARKER, marked_blocks


def test_extractor_preserves_all_source_whitespace() -> None:
    """A leading blank line belongs to the example rather than the fence header."""
    source = '\nvalue = "line"\n\nassert value == "line"\n'
    assert marked_blocks(f"{EXECUTION_MARKER}\n```python\n{source}```") == [source]


@pytest.mark.parametrize("suffix", ["", "\n```lcl\n1\n```", "\nprose\n```python\n1\n```"])
def test_extractor_rejects_unpaired_or_misplaced_markers(suffix: str) -> None:
    """Markers cannot silently select the wrong language or a later unrelated block."""
    with pytest.raises(AssertionError, match="malformed"):
        marked_blocks(EXECUTION_MARKER + suffix)
