"""Execute the configuration files and expected outputs readers see in Markdown."""

import ast

import pytest

from tests.documentation.cases import DocumentCase, execute_file_case, extract_file_cases
from tests.documentation.examples import ROOT, document_paths


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(case, id=f"{path.relative_to(ROOT)}:{case.name}")
        for path in document_paths()
        for case in extract_file_cases(path.read_text(encoding="utf-8"), str(path))
    ],
)
def test_document_file_case(case: DocumentCase) -> None:
    """The exact source and displayed results constitute the executable contract."""
    tree = ast.parse(case.source, filename=case.filename)
    assert not any(
        isinstance(node, ast.Import)
        and any(alias.name == "lclang" or alias.name.startswith("lclang.") for alias in node.names)
        for node in ast.walk(tree)
    ), "use explicit lclang symbol imports"
    execute_file_case(case, ROOT)
