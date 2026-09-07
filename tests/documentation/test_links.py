"""Local Markdown navigation contracts without external-network dependency."""

import re
from urllib.parse import unquote, urlsplit

from tests.documentation.examples import document_paths


def test_local_document_links_resolve() -> None:
    """Every maintained relative page or file link points to a real artifact."""
    for path in document_paths():
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text = re.sub(r"`[^`]*`", "", text)
        for target in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", text):
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path:
                continue
            destination = (path.parent / unquote(parsed.path)).resolve()
            assert destination.exists(), f"{path}: broken link {target}"
