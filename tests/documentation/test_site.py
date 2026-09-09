"""Generated documentation preserves source and has complete, portable navigation."""

import json
import shutil
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

import pytest
from markdown_it import MarkdownIt

from scripts.build_site import build_site, documentation_groups, local_link, render_document
from scripts.export_wiki import ROOT


class SiteParser(HTMLParser):
    """Collect navigation, resource URLs, unique anchors and exact fenced source."""

    def __init__(self, path: Path) -> None:
        """Parse one generated page for the structural acceptance checks."""
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.blocks: list[str] = []
        self.in_pre = False
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if identifier := values.get("id"):
            assert identifier not in self.ids, identifier
            self.ids.add(identifier)
        if tag in {"a", "link", "script", "img"} and (
            link := values.get("href") or values.get("src")
        ):
            self.links.append(link)
        if tag == "img":
            assert "alt" in values
        if tag == "pre":
            self.in_pre = True
            self.blocks.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre":
            self.in_pre = False

    def handle_data(self, data: str) -> None:
        if self.in_pre:
            self.blocks[-1] += data


def test_complete_site_links_anchors_assets_and_examples() -> None:
    """Every page, search result and resource resolves under a nested Pages base path."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for folder in ("docs", "site"):
            shutil.copytree(ROOT / folder, root / folder)
        shutil.copyfile(ROOT / "pyproject.toml", root / "pyproject.toml")
        # Repository links in guides are validated against their real source files.
        for folder in ("src", "tests", "scripts"):
            shutil.copytree(
                ROOT / folder, root / folder, ignore=shutil.ignore_patterns("__pycache__"),
            )
        for name in ("README.md", "LICENSE", "AGENTS.md"):
            shutil.copyfile(ROOT / name, root / name)
        output = root / "build/lclang"
        paths = build_site(root, output, "revision")
        parsed = {path.resolve(): SiteParser(path) for path in paths}
        assert len(paths) == len(list((root / "docs").rglob("*.md")))
        for path, page in parsed.items():
            for url in page.links:
                link = urlsplit(url)
                if link.scheme or link.netloc:
                    continue
                target = (path.parent / unquote(link.path)).resolve() if link.path else path
                assert target.is_relative_to(output), (path, url)
                assert target.is_file(), (path, url)
                if link.fragment:
                    assert unquote(link.fragment) in parsed[target].ids, (path, url)
            relative = path.relative_to(output)
            source = root / "docs" / relative.with_suffix(".md")
            if relative.name == "index.html":
                source = source.with_name("README.md")
            tokens = MarkdownIt().parse(source.read_text(encoding="utf-8"))
            assert page.blocks == [token.content for token in tokens
                                   if token.type in {"fence", "code_block"}]
        search = json.loads((output / "search-index.json").read_text(encoding="utf-8"))
        assert any("recalculate" in entry["text"] for entry in search)
        for entry in search:
            link = urlsplit(entry["url"])
            assert link.fragment in parsed[(output / link.path).resolve()].ids
        assert (output / "assets/logo.png").is_file()
        assert (output / ".nojekyll").is_file()
        assert not (output / "template.html").exists()


def test_rendering_duplicate_headings_links_tables_and_code() -> None:
    """Markdown syntax gets stable anchors while literal code never gets link rewriting."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        docs = root / "docs"
        docs.mkdir()
        source = docs / "README.md"
        source.write_text(
            '# Overview\n\n## `Frame.get()`\n\n## `Frame.get()`\n\n'
            'Words across\na source line break.\n\n'
            '[Next](other.md#heading)\n\n'
            '| Input | Output |\n| --- | --- |\n| 1 | 2 |\n\n'
            '```python\nprint("[Next](other.md)")\n```\n', encoding="utf-8",
        )
        (docs / "other.md").write_text("# Heading\n", encoding="utf-8")
        content, title, toc, sections = render_document(source, root, "rev")
        assert title == "Overview"
        assert 'id="frameget"' in content and 'id="frameget-1"' in content
        assert 'href="other.html#heading"' in content and "<table>" in content
        assert '[Next](other.md)' in content
        assert "#frameget-1" in toc and len(sections) == 3
        assert "Words across a source line break." in sections[-1]["text"]
        assert local_link("https://example.com/a.md", source, root, "rev").endswith("a.md")
        with pytest.raises(ValueError, match="invalid local link"):
            local_link("missing.md", source, root, "rev")
        with pytest.raises(ValueError, match="invalid local link"):
            local_link("../../outside.md", source, root, "rev")
        with pytest.raises(ValueError, match="subdirectory"):
            build_site(root, docs, "rev")


def test_navigation_requires_all_pages_and_follows_tutorial_index() -> None:
    """New unlisted chapters fail instead of silently disappearing from the site."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        shutil.copytree(ROOT / "docs", root / "docs")
        groups = documentation_groups(root)
        assert groups["Tutorials"][1].name == "01-expressions-and-values.md"
        assert groups["Tutorials"][-1].name == "16-python-utilities.md"
        (root / "docs/tutorials/17-unlisted.md").write_text("# Unlisted", encoding="utf-8")
        with pytest.raises(ValueError, match="Every documentation page"):
            documentation_groups(root)
