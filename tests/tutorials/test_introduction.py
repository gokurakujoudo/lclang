"""Execute the introduction's explicitly paired configuration example."""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from tests.documentation.examples import ROOT, execute_example, marked_blocks


def test_introduction_config_example_executes_with_isolated_file_input() -> None:
    """Load the exact paired configuration and Python source in temporary storage."""
    text = (ROOT / "docs/tutorials/README.md").read_text(encoding="utf-8")
    configs = marked_blocks(text, "<!-- lclang-intro-config -->", "lclcfg")
    examples = marked_blocks(text, "<!-- lclang-intro-config-exec -->", "python")
    assert configs
    for index, (config, source) in enumerate(zip(configs, examples, strict=True), 1):
        namespace = execute_example(source, f"introduction-config:{index}")
        main = cast(Callable[[Path], Awaitable[None]], namespace["main"])
        with TemporaryDirectory() as directory:
            path = Path(directory) / "pricing.lclcfg"
            path.write_text(config, encoding="utf-8")
            asyncio.run(main(path))
