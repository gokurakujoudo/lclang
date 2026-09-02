"""Structure and executable-example contracts for every tutorial chapter."""

from __future__ import annotations

from pathlib import Path

# Repository root containing the published tutorial series.
ROOT = Path(__file__).resolve().parents[2]
# Ordered chapter filenames and titles from the public series table of contents.
CHAPTERS = (
    ("01-expressions-and-values.md", "Expressions and values"),
    ("02-modules-and-frames.md", "Modules and Frames"),
    ("03-language.md", "The LCL language"),
    ("04-configuration-files.md", "Configuration files"),
    ("05-async-python-integration.md", "Async Python integration"),
    ("06-caching-and-recalculation.md", "Caching and recalculation"),
    ("07-errors-and-inspection.md", "Errors and inspection"),
    ("08-dependency-analysis.md", "Dependency analysis"),
    ("09-command-line-applications.md", "Command-line applications"),
    ("10-workflow-status.md", "Workflow status"),
    ("11-business-day-calendars.md", "Business-day calendars"),
    ("12-production-patterns.md", "Production patterns"),
    ("13-scoped-values-and-frame-evaluation.md", "Scoped values and Frame evaluation"),
    ("14-tree-workflows.md", "Tree workflows"),
    ("15-energy-settlement-workflow.md", "Case Study: Energy Settlement Workflow"),
    ("16-python-utilities.md", "Python utilities for downstream applications"),
)


def executable_examples(text: str) -> list[str]:
    """Extract every Python example marked as an executable contract.

    :param text: Complete chapter Markdown.
    :returns: Python sources following the shared execution marker.
    """
    marker = "<!-- lclang-tutorial-exec -->"
    return [
        part.split("```python", 1)[1].split("```", 1)[0].strip()
        for part in text.split(marker)[1:]
    ]


def test_series_toc_links_every_published_chapter_in_order() -> None:
    """The introduction provides live ordered links instead of roadmap promises."""
    introduction = (ROOT / "docs" / "tutorials" / "README.md").read_text(
        encoding="utf-8"
    )
    positions = []
    for filename, title in CHAPTERS:
        link = f"[{title}]({filename})"
        assert link in introduction
        positions.append(introduction.index(link))
    assert positions == sorted(positions)
    assert "strong way of working" in introduction
    assert "flexibility within that way" in introduction


def test_every_chapter_is_substantial_and_has_executable_assertions() -> None:
    """Each lesson states its outcome and advances through executable operations."""
    for filename, title in CHAPTERS:
        path = ROOT / "docs" / "tutorials" / filename
        text = path.read_text(encoding="utf-8")
        test_name = f"test_{Path(filename).stem.replace('-', '_')}.py"
        assert (ROOT / "tests" / "tutorials" / test_name).is_file()
        examples = executable_examples(text)
        assert text.startswith(f"# {title}")
        assert "## What you will learn" in text
        assert len(text.splitlines()) >= 80
        assert len(examples) >= 2


def test_main_concept_chapter_states_the_lclang_design_philosophy() -> None:
    """The central Module/Frame lesson explains constraint-driven flexibility."""
    text = (ROOT / "docs" / "tutorials" / CHAPTERS[1][0]).read_text(encoding="utf-8")
    assert "strong way of working" in text
    assert "flexibility within that way" in text
    assert "Module" in text
    assert "Frame" in text
