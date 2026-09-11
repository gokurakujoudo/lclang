"""Generated documentation preserves source and has complete, portable navigation."""

import json
import shutil
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

import pytest
from markdown_it import MarkdownIt

from scripts.build_site import build_site
from scripts.export_wiki import ROOT
from scripts.site_navigation import documentation_groups


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
        for name in ("README.md", "LICENSE", "AGENTS.md", "mkdocs.yml"):
            shutil.copyfile(ROOT / name, root / name)
        output = root / "build/lclang"
        sample = root / "docs/README.md"
        sample.write_text(sample.read_text(encoding="utf-8") + (
            '\n## Highlighting examples\n\n'
            '```python\n\nasync def greet():\n\treturn "<script>&雪"\n\n```\n\n'
            '```lcl\ntrue if item?.value ?? null else false\n```\n\n'
            '```lclcfg\nusing "base.lclcfg"\nport: 8443 # default\n```\n\n'
            '```unknown-language\n<script>unsafe</script>\n```\n'
        ), encoding="utf-8")
        paths = build_site(root, output, "revision")
        parsed = {path.resolve(): SiteParser(path) for path in output.rglob("*.html")}
        assert len(paths) == len(list((root / "docs").rglob("*.md")))
        for path in paths:
            page = parsed[path.resolve()]
            for url in page.links:
                link = urlsplit(url)
                if link.scheme or link.netloc:
                    continue
                target = (path.parent / unquote(link.path)).resolve() if link.path else path
                if target.is_dir():
                    target /= "index.html"
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
        search = json.loads((output / "search/search_index.json").read_text(encoding="utf-8"))
        assert any("recalculate" in entry["text"] for entry in search["docs"])
        for entry in search["docs"]:
            link = urlsplit(entry["location"])
            target = (output / (link.path or "index.html")).resolve()
            assert target in parsed
            if link.fragment:
                assert link.fragment in parsed[target].ids
        assert (output / "assets/logo.png").is_file()
        assert (output / ".nojekyll").is_file()
        home = (output / "index.html").read_text(encoding="utf-8")
        assert 'class="wy-nav-side' in home
        assert '<span class="k">async' in home
        assert '<span class="kc">true' in home
        assert '<span class="s' in home
        assert "&lt;script&gt;unsafe&lt;/script&gt;" in home
        assert "<script>unsafe</script>" not in home
        assert ((output / "assets/logo.png").read_bytes()
                == (ROOT / "site/assets/logo.png").read_bytes())
        assert 'assets/favicon.png' in home
        assert not (output / "overrides/main.html").exists()
        guide = (output / "development/index.html").read_text(encoding="utf-8")
        assert "github.com/gokurakujoudo/lclang/blob/revision/" in guide
        with pytest.raises(ValueError, match="subdirectory"):
            build_site(root, root / "docs", "revision")


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
