"""The static introduction links to real Wiki pages and shows runnable Python."""

from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.export_wiki import ROOT, WIKI, export_wiki
from tests.documentation.examples import execute_example


class SiteParser(HTMLParser):
    """Collect links, IDs, stylesheets and the exact Python introduction example."""

    def __init__(self) -> None:
        """Initialize empty navigation and example collections."""
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.styles: list[str] = []
        self.example = ""
        self.in_example = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(str(values["id"]))
        if tag == "a":
            self.links.append(str(values["href"]))
        if tag == "link" and values.get("rel") in {"stylesheet", "icon", "apple-touch-icon"}:
            self.styles.append(str(values["href"]))
        if tag == "img":
            assert "alt" in values
            self.styles.append(str(values["src"]))
        if tag == "code" and values.get("data-example") == "python":
            self.in_example = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "code":
            self.in_example = False

    def handle_data(self, data: str) -> None:
        if self.in_example:
            self.example += data


def test_intro_links_assets_and_exact_example() -> None:
    """All local navigation resolves and the Python shown to users executes."""
    parser = SiteParser()
    parser.feed((ROOT / "site/index.html").read_text(encoding="utf-8"))
    assert parser.example
    execute_example(parser.example, "site/index.html")
    assert all((ROOT / "site" / name).is_file() for name in parser.styles)
    with TemporaryDirectory() as directory:
        pages = export_wiki(ROOT, Path(directory), "revision")
        names = {page.stem for page in pages}
        for link in parser.links:
            if link.startswith(WIKI + "/"):
                assert link.removeprefix(WIKI + "/") in names
            elif link.startswith("#"):
                assert link[1:] in parser.ids
