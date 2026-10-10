"""Reader-friendly fixture contracts and defining-directory path recommendations."""

import re

import pytest

from tests.documentation.cases import (
    DocumentCase,
    assert_output_matches,
    execute_file_case,
    extract_file_cases,
    normalize_workspace,
    validate_fixture_path,
)
from tests.documentation.examples import ROOT, document_paths


@pytest.mark.parametrize("name", ["", "/root.lclcfg", "../secret", "C:/secret", "a\\b"])
def test_fixtures_stay_inside_their_workspace(name: str) -> None:
    """Malformed documentation paths cannot escape isolated case directories."""
    with pytest.raises(AssertionError, match="unsafe fixture path"):
        validate_fixture_path(name)


def test_cases_require_unique_complete_metadata_and_one_execution() -> None:
    """Case extraction reports author mistakes with the chapter and case name."""
    valid = (
        "<!-- lclang-doc-case: example -->\n<!-- lclang-doc-exec -->\n"
        '```python\nprint("hello")\n```\n<!-- /lclang-doc-case -->'
    )
    assert extract_file_cases(valid, "chapter")[0].source == 'print("hello")\n'
    for malformed in (valid + valid, valid[:-10], valid.replace("lclang-doc-exec", "other")):
        with pytest.raises(AssertionError, match="chapter"):
            extract_file_cases(malformed, "chapter")
    fixture = "<!-- lclang-doc-file: example.lclcfg -->\n```lclcfg\nx: 1\n```\n"
    with pytest.raises(AssertionError, match="duplicate file"):
        extract_file_cases(
            valid.replace("<!-- lclang-doc-exec -->", fixture * 2 + "<!-- lclang-doc-exec -->"),
            "chapter",
        )


def test_execution_verifies_streams_exit_status_and_generated_file() -> None:
    """All displayed result kinds are compared with the actual isolated process."""
    source = (
        'from pathlib import Path\nimport sys\nprint("done")\n'
        'print("detail", file=sys.stderr)\nPath("result.txt").write_text("saved\\n")\n'
        "raise SystemExit(3)\n"
    )
    case = DocumentCase(
        "observable", "chapter", {}, source, "done\n", "detail\n", 3, {"result.txt": "saved\n"}
    )
    execute_file_case(case, ROOT)
    with pytest.raises(AssertionError, match="expected[\\s\\S]*-old[\\s\\S]*\\+new"):
        assert_output_matches("new\n", "old\n", "chapter:case: stdout")
    assert (
        normalize_workspace(str(ROOT / "config.lclcfg"), ROOT, {"config.lclcfg"}) == "config.lclcfg"
    )


def test_all_documented_file_introductions_use_defining_directory() -> None:
    """Examples consistently follow the explicit __dir__ path convention."""
    pattern = re.compile(r'\b(?:using|import)\??\s+(f?)(["\'])(.*?)\2')
    for path in document_paths():
        for prefix, _, target in pattern.findall(path.read_text(encoding="utf-8")):
            if ".lclcfg" in target:
                assert prefix == "f" and target.startswith("{__dir__}/"), (path, target)
