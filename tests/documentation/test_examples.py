"""Execute ordinary examples from README, guides, tutorials and references."""

import pytest

from tests.documentation.examples import ROOT, document_paths, execute_example, marked_blocks


@pytest.mark.parametrize(
    "source,filename",
    [
        pytest.param(source, f"{path}:{index}", id=f"{path.relative_to(ROOT)}:{index}")
        for path in document_paths()
        for index, source in enumerate(marked_blocks(path.read_text(encoding="utf-8")), 1)
    ],
)
def test_document_example(source: str, filename: str) -> None:
    """The source users copy is the source compiled and executed by acceptance."""
    execute_example(source, filename)
