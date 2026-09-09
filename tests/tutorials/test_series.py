"""Tutorial navigation derived from the single maintained table of contents."""

import re

from tests.documentation.examples import ROOT, marked_blocks


def tutorial_chapters() -> list[tuple[str, str]]:
    """Read linked chapter titles and paths from the introduction's ordered list."""
    text = (ROOT / "docs/tutorials/README.md").read_text(encoding="utf-8")
    return re.findall(r"^\d+\. \*\*\[([^]]+)\]\((\d{2}-[^)]+\.md)\)", text, re.MULTILINE)


def test_series_directory_titles_and_navigation_match_the_toc() -> None:
    """The TOC lists every real chapter once, in its numbered reading order."""
    chapters = tutorial_chapters()
    paths = [filename for title, filename in chapters]
    directory = ROOT / "docs/tutorials"
    assert paths
    assert len(paths) == len(set(paths))
    assert paths == sorted(paths)
    assert set(paths) == {path.name for path in directory.glob("*.md") if path.name != "README.md"}
    for index, (title, filename) in enumerate(chapters):
        text = (directory / filename).read_text(encoding="utf-8")
        assert text.splitlines()[0] == f"# {title}"
        assert marked_blocks(text), f"chapter without executable workflow: {filename}"
        previous = re.findall(r"\[Previous:[^]]+\]\(([^)]+)\)", text)
        following = re.findall(r"\[Next:[^]]+\]\(([^)]+)\)", text)
        assert previous == ([] if index == 0 else [paths[index - 1]])
        assert following == ([] if index + 1 == len(paths) else [paths[index + 1]])
        assert "](README.md)" in text
