"""Wiki publication preserves tested examples and complete document navigation."""

import re
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts.export_wiki import ROOT, WIKI, export_wiki, page_name, rewrite_links
from tests.documentation.examples import marked_blocks


def test_complete_wiki_export_preserves_examples_and_resolves_page_links() -> None:
    """Every source page is exported and every cross-page Wiki link has a destination."""
    with TemporaryDirectory() as directory:
        output = Path(directory)
        generated = export_wiki(ROOT, output, "revision")
        sources = list((ROOT / "docs").rglob("*.md"))
        assert len(generated) == len(sources) + 2
        for source in sources:
            page = output / f"{page_name(source.relative_to(ROOT / 'docs'))}.md"
            content = page.read_text(encoding="utf-8")
            original = source.read_text(encoding="utf-8")
            assert marked_blocks(content) == marked_blocks(original)
            for target in re.findall(re.escape(WIKI) + r"/([^\s)#]+)", content):
                assert (output / f"{target}.md").is_file(), target
        marker = output / "handwritten.txt"
        marker.write_text("keep", encoding="utf-8")
        export_wiki(ROOT, output, "revision")
        assert marker.read_text(encoding="utf-8") == "keep"


def test_wiki_links_keep_code_fragments_and_external_urls() -> None:
    """Relative pages and attachments resolve without changing code or external URLs."""
    with TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        docs = root / "docs"
        docs.mkdir()
        source = docs / "README.md"
        source.write_text("# Home", encoding="utf-8")
        (docs / "other.md").write_text("# Other", encoding="utf-8")
        (docs / "data.json").write_text("{}", encoding="utf-8")
        text = "[page](other.md#heading) [data](data.json) [external](https://example.com)"
        code = "\n`[code](missing.md)`\n```python\n'[code](missing.md)'\n```\n"
        result = rewrite_links(text + code + "[anchor](#heading)", source, root, "abc")
        assert f"[page]({WIKI}/other#heading)" in result
        assert "/blob/abc/docs/data.json" in result
        assert code in result and "[anchor](#heading)" in result
        assert "[external](https://example.com)" in result
        with pytest.raises(ValueError, match="invalid local link"):
            rewrite_links("[missing](missing.md)", source, root, "abc")
        with pytest.raises(ValueError, match="overlap"):
            export_wiki(root, docs, "abc")
