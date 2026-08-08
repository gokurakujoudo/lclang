"""Structural and executable acceptance for the English tutorial path."""

import re
import subprocess
import sys
from pathlib import Path

from pylcl import parse_expression
from pylcl.config import parse_config

# Repository root containing the user-facing documentation trees.
ROOT = Path(__file__).resolve().parents[1]
# Canonical English tutorial documents in table-of-contents order.
TUTORIALS = (
    ROOT / "docs" / "tutorials" / "README.md",
    ROOT / "docs" / "tutorials" / "runtime.md",
    ROOT / "docs" / "tutorials" / "lcl_examples.md",
    ROOT / "docs" / "tutorials" / "config_file.md",
    ROOT / "docs" / "tutorials" / "dependency-analytics.md",
)
# Superseded documents that must not leave stale navigation behind.
REMOVED_DOCUMENTS = (
    ROOT / "docs" / "tutorials" / "index.md",
    ROOT / "docs" / "user-cheatsheet.md",
    ROOT / "docs" / "tutorials" / "runtime-quickstart.md",
    ROOT / "doc_cn" / "runtime-quickstart_cn.md",
)


def marked_python(text: str) -> tuple[str, ...]:
    """Extract standalone Python examples selected for real execution."""
    pattern = r"<!-- pylcl-exec -->\s*```python\n(.*?)\n```"
    return tuple(re.findall(pattern, text, flags=re.DOTALL))


def fenced_lcl(text: str) -> tuple[str, ...]:
    """Extract every complete LCL expression in the language gallery."""
    return tuple(re.findall(r"```lcl\n(.*?)\n```", text, flags=re.DOTALL))


def markdown_links(text: str) -> tuple[str, ...]:
    """Extract local Markdown document targets, retaining optional anchors."""
    pattern = r"\[[^]\n]+\]\(([^)\n]+\.md(?:#[^)]*)?)\)"
    return tuple(re.findall(pattern, text))


def test_tutorial_index_is_a_three_minute_install_and_navigation_start() -> None:
    """Sunny: one short entry point installs pylcl, runs it, and routes readers."""
    index = TUTORIALS[0].read_text(encoding="utf-8")
    for heading in ("# Learn pylcl", "## Install", "## Three-minute tour", "## Tutorials"):
        assert heading in index
    for tutorial in TUTORIALS[1:]:
        assert tutorial.name in index
    assert "python -m pip install" in index


def test_tutorials_cover_runtime_language_and_configuration_concepts() -> None:
    """Sunny: the focused guides cover their promised beginner and advanced scope."""
    runtime = TUTORIALS[1].read_text(encoding="utf-8")
    gallery = TUTORIALS[2].read_text(encoding="utf-8")
    config = TUTORIALS[3].read_text(encoding="utf-8")
    analytics = TUTORIALS[4].read_text(encoding="utf-8")
    for term in (
        "Module",
        "Frame",
        "lhs()",
        "parse_ymd",
        "FrameDependencyGraph",
        "recalculate",
        "close()",
    ):
        assert term in runtime
    for term in (
        "Literals",
        "Comprehensions",
        "Functions",
        "Try and with",
        "Y combinator",
        "Fibonacci",
        "Quicksort",
        "lhs()",
        "parse_ymd",
    ):
        assert term in gallery
    for term in (
        ".lclcfg",
        "using",
        "__file__",
        "__dir__",
        "lhs()",
        "parse_ymd",
        "load_config",
    ):
        assert term in config
    for term in (
        "DependencyKind",
        "DependencyGraph",
        "FrameDependencyGraph",
        "dependency_snapshot",
        "reconcile_dependency_edges",
        "topological_order",
        "do not evaluate",
    ):
        assert term in analytics


def test_tutorial_examples_execute_and_gallery_expressions_parse() -> None:
    """Composite: examples run independently and every gallery expression parses."""
    blocks: list[str] = []
    for tutorial in TUTORIALS:
        blocks.extend(marked_python(tutorial.read_text(encoding="utf-8")))
    assert len(blocks) >= 6
    for block in blocks:
        result = subprocess.run(
            [sys.executable, "-c", block],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    gallery = TUTORIALS[2].read_text(encoding="utf-8")
    expressions = fenced_lcl(gallery)
    assert len(expressions) >= 20
    for expression in expressions:
        parse_expression(expression)


def test_config_examples_parse_without_loading_and_keep_file_origin() -> None:
    """Composite: every config fence is valid as one unresolved physical file."""
    tutorial = TUTORIALS[3]
    text = tutorial.read_text(encoding="utf-8")
    examples = tuple(re.findall(r"```lclcfg\n(.*?)\n```", text, flags=re.DOTALL))
    assert len(examples) >= 3
    for index, example in enumerate(examples):
        parse_config(example, source_path=tutorial.parent / f"example-{index}.lclcfg")


def test_removed_guides_and_broken_markdown_links_cannot_return() -> None:
    """Rainy: superseded files stay absent and all user navigation resolves."""
    assert all(not document.exists() for document in REMOVED_DOCUMENTS)
    user_documents = (
        *TUTORIALS,
        ROOT / "docs" / "README.md",
        ROOT / "README.md",
        ROOT / "README_cn.md",
        ROOT / "doc_cn" / "README_cn.md",
    )
    for document in user_documents:
        text = document.read_text(encoding="utf-8")
        for target in markdown_links(text):
            path = target.split("#", maxsplit=1)[0]
            assert (document.parent / path).resolve().exists(), f"{document}: {target}"
        for removed in REMOVED_DOCUMENTS:
            assert removed.name not in text
