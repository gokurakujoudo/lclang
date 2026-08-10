"""Unit tests mirroring :mod:`lclang.config.lines`."""

import pytest

from lclang.config.errors import LclConfigSyntaxError
from lclang.config.lines import (
    comment_offset,
    mask_physical_line,
    scan_logical_lines,
    split_physical_lines,
)
from lclang.config.positions import advance_position, end_position
from lclang.source import SourceOrigin, SourcePosition
from lclang.types import SourceName


def test_physical_helpers_cover_newlines_quotes_comments_and_markers() -> None:
    """Physical scanning remains exact across all accepted newline spellings."""
    assert split_physical_lines("") == []
    assert split_physical_lines("text") == [("text", "", 1, 0)]
    assert [item[1] for item in split_physical_lines("a\rb\r\nc\n")] == ["\r", "\r\n", "\n"]
    assert mask_physical_line("value: '# not comment' # yes")[0].endswith("      ")
    assert mask_physical_line("value: 1 \\ # yes")[1]
    assert not mask_physical_line("value: '\\\\'")[1]
    assert comment_offset('value: "escaped \\" # text" # yes') is not None
    assert comment_offset("value: '''# text'''") is None
    assert end_position("") == end_position("")
    assert end_position("a\r\nb").line == 2
    start = SourcePosition(3, 4, 10)
    assert advance_position(start, "a\r\nb\rc\nd") == SourcePosition(6, 2, 18)


def test_logical_line_rainy_continuations_are_structured() -> None:
    """Missing and empty physical fragments cannot masquerade as continuation."""
    origin = SourceOrigin(SourceName("lines"))
    with pytest.raises(LclConfigSyntaxError, match="another physical"):
        scan_logical_lines("value: 1 \\", origin)
    with pytest.raises(LclConfigSyntaxError, match="blank or comment"):
        scan_logical_lines("value: 1 \\\n# only comment\n", origin)
