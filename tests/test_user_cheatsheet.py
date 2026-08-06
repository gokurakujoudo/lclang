"""Structural and executable acceptance for the Python-user cheatsheet."""

import re
import subprocess
import sys
from pathlib import Path

import pylcl
import pylcl.ast
import pylcl.lang
import pylcl.runtime
import pylcl.stdlib

ROOT = Path(__file__).resolve().parents[1]
CHEATSHEET = ROOT / "docs" / "user-cheatsheet.md"
PUBLIC_MODULES = (pylcl, pylcl.ast, pylcl.lang, pylcl.runtime, pylcl.stdlib)


def _marked_python(text: str) -> tuple[str, ...]:
    """Extract standalone examples selected for real execution."""
    pattern = r"<!-- pylcl-exec -->\s*```python\n(.*?)\n```"
    return tuple(re.findall(pattern, text, flags=re.DOTALL))


def test_cheatsheet_covers_every_current_public_export() -> None:
    """Sunny: users can find every implemented public symbol in one inventory."""
    text = CHEATSHEET.read_text(encoding="utf-8")
    for heading in (
        "# pylcl Python user cheatsheet",
        "## Choose the right API layer",
        "## Parse, inspect, print, and evaluate LCL",
        "## Build Modules, Presets, factories, and Frames",
        "## Cache, concurrency, recalculation, and cleanup",
        "## Analyze and observe dependencies",
        "## Use and extend the standard preset",
        "## Source locations and errors",
        "## Complete public symbol inventory",
        "## Rainy cases and operational rules",
    ):
        assert heading in text
    for module in PUBLIC_MODULES:
        for name in module.__all__:
            assert f"`{name}`" in text, f"missing {module.__name__}.{name}"


def test_cheatsheet_examples_execute_and_rainy_contracts_are_explicit() -> None:
    """Composite-complex: documented integrations run and failures stay visible."""
    text = CHEATSHEET.read_text(encoding="utf-8")
    blocks = _marked_python(text)
    assert len(blocks) >= 4
    for block in blocks:
        result = subprocess.run(
            [sys.executable, "-c", block],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
    for term in (
        "evaluate_sync cannot run",
        "never invalidates dependants",
        "not a hostile-code sandbox",
        "LclSyntaxError",
        "LclNameError",
        "LclEvaluationError",
        "LclCircularDependencyError",
        "LclClosedFrameError",
    ):
        assert term in text


def test_cheatsheet_local_links_and_entry_points_remain_valid() -> None:
    """Rainy: broken cross-document navigation cannot silently ship."""
    text = CHEATSHEET.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^]\n]+\]\(([^)\n]+\.md(?:#[^)]*)?)\)", text):
        if "://" in target:
            continue
        path = target.split("#", maxsplit=1)[0]
        assert (CHEATSHEET.parent / path).resolve().exists(), target
    assert "user-cheatsheet.md" in (ROOT / "docs" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "docs/user-cheatsheet.md" in (ROOT / "README.md").read_text(
        encoding="utf-8"
    )
    assert "docs/user-cheatsheet.md" in (ROOT / "README_cn.md").read_text(
        encoding="utf-8"
    )
