"""Derive site navigation from the canonical documentation inventory."""

import re
from pathlib import Path

from markdown_it import MarkdownIt


def documentation_groups(root: Path) -> dict[str, list[Path]]:
    """Discover pages, taking tutorial order only from its canonical table of contents."""
    docs = root / "docs"
    introduction = Path("tutorials/README.md")
    tokens = MarkdownIt().parse((docs / introduction).read_text(encoding="utf-8"))
    chapters: list[Path] = []
    for token in tokens:
        for child in token.children or []:
            href = str(child.attrGet("href") or "")
            if child.type == "link_open" and re.fullmatch(r"\d\d-[\w-]+\.md", href):
                path = introduction.parent / href
                if path not in chapters:
                    chapters.append(path)
    groups = {"Getting started": [Path("README.md"), Path("installation.md"),
                                  Path("quick-start.md")],
              "Tutorials": [introduction, *chapters]}
    for name, folder in (("Reference", "reference"), ("Development", "development")):
        groups[name] = [Path(folder) / "README.md", *(
            path.relative_to(docs) for path in sorted((docs / folder).glob("*.md"))
            if path.name != "README.md"
        )]
    found = [page for pages in groups.values() for page in pages]
    if set(found) != {path.relative_to(docs) for path in docs.rglob("*.md")}:
        raise ValueError("Every documentation page must appear in navigation")
    return groups


