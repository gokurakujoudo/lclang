"""Dynamic using failures retain their scene, identity and actual loading route."""

import io
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang.config import load_config
from lclang.error import LclError
from lclang.logger import LclExceptionFormatter, use_verbose


@pytest.mark.asyncio
async def test_nested_using_preserves_target_scene_and_failure_identity() -> None:
    """A context wrapper adds loading evidence without hiding its original cause."""
    output = io.StringIO()
    logger = logging.Logger("using-display", logging.DEBUG)
    handler = logging.StreamHandler(output)
    handler.setFormatter(LclExceptionFormatter("%(levelname)s | %(message)s"))
    logger.addHandler(handler)
    with TemporaryDirectory() as directory:
        root = Path(directory)
        main, child = root / "main.lclcfg", root / "child.lclcfg"
        main.write_text('using f"{__dir__}/child.lclcfg"', encoding="utf-8")
        child.write_text('divisor: 0\nusing f"{__dir__}/{1 / divisor}.lclcfg"', encoding="utf-8")
        with use_verbose(logger), pytest.raises(LclError) as caught:
            await load_config(main)
        error = caught.value
        assert error.verbose_failure_id is not None
        assert isinstance(error.__cause__, LclError)
        assert error.verbose_failure_id == error.__cause__.verbose_failure_id
        text = str(error)
        assert "<expression unavailable>" not in text
        assert "divisor: (int) 0" in text
        assert "ZeroDivisionError: division by zero" in text
        assert text.count("Source:") == 1
        assert "__lclang_file_target" not in text
        verbose = output.getvalue()
        assert "Resolved using target" in verbose
        assert "Evaluation tree for __lclang_file_target" not in verbose
        assert "Loading route" in verbose
