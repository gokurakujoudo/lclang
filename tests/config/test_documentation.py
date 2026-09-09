"""Parse the exact configuration grammar examples published in the reference."""

import pytest

from lclang.config import parse_config
from tests.documentation.examples import ROOT, marked_blocks


@pytest.mark.parametrize(
    "source",
    marked_blocks(
        (ROOT / "docs/reference/configuration.md").read_text(encoding="utf-8"),
        "<!-- lclang-config-parse -->", "lclcfg",
    ),
)
def test_documented_configuration_source_parses(source: str) -> None:
    """The real marked grammar examples preserve supported syntax and declarations."""
    document = parse_config(source, source_path=ROOT / "example.lclcfg")
    assert document.version == 1
    assert document.declarations
