"""Structural and executable checks for bilingual configuration guidance."""

from pathlib import Path

from pylcl.config import parse_config

ROOT = Path(__file__).resolve().parents[2]


def test_bilingual_guides_cover_the_verified_contract_and_are_linked() -> None:
    """English and Chinese indexes expose every central 0.2 configuration topic."""
    english = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    chinese = (ROOT / "doc_cn" / "configuration_cn.md").read_text(encoding="utf-8")
    for term in (
        "__LCL_VERSION__",
        "__file__",
        "__dir__",
        "using",
        "ConfigLoadLimits",
        "ConfigLoader",
        "evaluate_config",
    ):
        assert term in english
        assert term in chinese
    assert "configuration.md" in (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "configuration_cn.md" in (ROOT / "doc_cn" / "README_cn.md").read_text(
        encoding="utf-8"
    )


def test_documented_file_grammar_example_parses() -> None:
    """The guide's representative version, continuation, and using syntax executes."""
    document = parse_config(
        "__LCL_VERSION__: 1\n"
        "base: 2\n"
        "total: (base + \\ # continue\n"
        "  3)\n"
        'using "parts/common.lclcfg"\n',
        source_path=ROOT / "example.lclcfg",
    )
    assert document.version == 1
    assert len(document.declarations) == 3
