"""Structural and executable checks for the tutorial introduction."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

# Repository root containing the published tutorial introduction.
ROOT = Path(__file__).resolve().parents[2]
# Published introduction and table of contents for the complete series.
INTRODUCTION = ROOT / "docs" / "tutorials" / "README.md"
# Superseded unnumbered tutorial paths that must stay retired.
RETIRED_TUTORIALS = (
    "calendar.md",
    "cli.md",
    "configuration.md",
    "dependency-analysis.md",
    "language.md",
    "runtime.md",
    "workflow.md",
)


def marked_blocks(text: str, marker: str, language: str) -> list[str]:
    """Extract fenced examples that immediately follow one marker.

    :param text: Complete tutorial Markdown.
    :param marker: Exact HTML comment placed before each executable block.
    :param language: Markdown fence language to select.
    :returns: Source text from every matching fenced block.
    """
    fence = f"```{language}"
    return [part.split(fence, 1)[1].split("```", 1)[0].strip() for part in text.split(marker)[1:]]


def test_introduction_publishes_the_complete_progressive_series() -> None:
    """The introduction names every implemented topic in learning order."""
    text = INTRODUCTION.read_text(encoding="utf-8")
    assert "# Learn lclang: start here" in text
    assert "## The tutorial series" in text
    for topic in (
        "Expressions and values",
        "Modules and Frames",
        "The LCL language",
        "Configuration files",
        "Async Python integration",
        "Caching and recalculation",
        "Errors and inspection",
        "Dependency analysis",
        "Command-line applications",
        "Workflow status",
        "Business-day calendars",
        "Production patterns",
        "Tree workflows",
        "Case Study: Energy Settlement Workflow",
    ):
        assert topic in text
    assert "**Expected result**" not in text
    assert all(not (INTRODUCTION.parent / name).exists() for name in RETIRED_TUTORIALS)


def test_introduction_python_examples_execute_in_order() -> None:
    """The direct examples remain independent, complete, and copyable."""
    text = INTRODUCTION.read_text(encoding="utf-8")
    examples = marked_blocks(text, "<!-- lclang-intro-exec -->", "python")
    assert len(examples) == 3
    for index, source in enumerate(examples, start=1):
        namespace = {"__name__": f"lclang_intro_example_{index}"}
        exec(compile(source, f"<lclang-intro-{index}>", "exec"), namespace)


def test_introduction_config_example_executes_with_isolated_file_input() -> None:
    """The final example loads the exact documented config in temporary storage."""
    text = INTRODUCTION.read_text(encoding="utf-8")
    configs = marked_blocks(text, "<!-- lclang-intro-config -->", "lclcfg")
    examples = marked_blocks(text, "<!-- lclang-intro-config-exec -->", "python")
    assert len(configs) == 1
    assert len(examples) == 1

    namespace = {"__name__": "lclang_intro_config_example"}
    exec(compile(examples[0], "<lclang-intro-config>", "exec"), namespace)
    main = cast(Callable[[Path], Awaitable[None]], namespace["main"])
    with TemporaryDirectory(prefix="lclang-intro-") as directory:
        path = Path(directory) / "pricing.lclcfg"
        path.write_text(configs[0] + "\n", encoding="utf-8")
        asyncio.run(main(path))
