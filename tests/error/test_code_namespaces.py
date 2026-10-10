"""Public vocabulary names and cold package import contracts."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import lclang
import lclang.error as errors
from lclang.error.codes.code_registry import CODE_ENUMS


def test_code_vocabularies_have_descriptive_public_names_and_order() -> None:
    """Each domain exports one sorted enum with Exx reason identifiers."""
    for domain, group in enumerate(CODE_ENUMS):
        assert getattr(errors, group.__name__) is group
        assert group.__name__ in errors.__all__
        assert group.__module__.split(".")[-1].startswith(f"e{domain}_")
        assert list(map(str, group)) == sorted(map(str, group))
        assert all(
            re.fullmatch(r"E" + str(member)[4:6] + r"_[A-Z][A-Z0-9_]*", member.name)
            for member in group
        )
    assert not hasattr(errors, "Code")


@pytest.mark.parametrize(
    "first",
    [
        "error",
        "common",
        "lang",
        "lang.common",
        "lang.ast",
        "lang.engine",
        "lang.runtime",
        "lang.stdlib",
        "config",
        "cli",
        "workflow",
        "logger",
        "utils",
    ],
)
def test_major_packages_import_without_prior_initialization(first: str) -> None:
    """A fresh interpreter can enter through each supported package."""
    source = (
        f"import lclang.{first}\n"
        "from lclang.lang import define_module, parse_expression\n"
        "from lclang.error import LanguageErrorCode\n"
        "assert define_module('cold', {}).name == 'cold'\n"
        "assert parse_expression('1') is not None\n"
        "assert str(LanguageErrorCode.E31_DIVISION_BY_ZERO) == 'LCL131421'\n"
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    result = subprocess.run(
        [sys.executable, "-c", source],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_root_contains_metadata_and_functional_packages_only() -> None:
    """Daily APIs and old forwarding modules do not leak through the root."""
    root = Path(__file__).resolve().parents[2] / "src/lclang"
    assert sorted(path.name for path in root.glob("*.py")) == ["__init__.py", "__version__.py"]
    assert lclang.__all__ == []
    assert not hasattr(lclang, "LclError")
    assert not hasattr(lclang, "define_frame")
    assert not hasattr(lclang, "parse_expression")
