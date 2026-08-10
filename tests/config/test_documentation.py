"""Executable examples from the configuration references."""

from pathlib import Path

from lclang.config import parse_config

ROOT = Path(__file__).resolve().parents[2]


def test_bilingual_references_cover_the_configuration_contract() -> None:
    """English and Chinese references describe each public configuration concept."""
    english = (ROOT / "docs" / "reference" / "configuration.md").read_text(
        encoding="utf-8"
    )
    chinese = (ROOT / "docs" / "zh" / "configuration.md").read_text(encoding="utf-8")
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
