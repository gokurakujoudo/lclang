"""Extract exact marked Markdown source for independent document examples."""

import re
from pathlib import Path

# Repository location and unitless marker shared by all ordinary Python examples.
ROOT = Path(__file__).resolve().parents[2]
EXECUTION_MARKER = "<!-- lclang-doc-exec -->"


def marked_blocks(text: str, marker: str = EXECUTION_MARKER, language: str = "python") -> list[str]:
    """Extract exact fenced source and reject misplaced or dangling markers."""
    pattern = re.escape(marker) + r"\s*```" + re.escape(language) + r"[ \t]*\n(.*?)^```[ \t]*$"
    blocks = re.findall(pattern, text, flags=re.MULTILINE | re.DOTALL)
    assert len(blocks) == text.count(marker), f"malformed {marker} block"
    return blocks


def document_paths() -> list[Path]:
    """Return the single root README and every maintained documentation page."""
    return [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]


def execute_example(source: str, filename: str) -> dict[str, object]:
    """Execute exact source in a fresh namespace and return fixture entry points."""
    namespace: dict[str, object] = {"__name__": "lclang_document_example"}
    exec(compile(source, filename, "exec"), namespace)
    return namespace
