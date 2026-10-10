"""The checkout and build backend use one canonical version definition."""

import ast
import re
import tomllib
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts.package_version import read_package_version

ROOT = Path(__file__).resolve().parents[2]


def test_version_metadata_has_one_source() -> None:
    """Runtime imports and Hatchling metadata identify the same literal source."""
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" not in metadata["project"]
    assert "version" in metadata["project"]["dynamic"]
    assert metadata["tool"]["hatch"]["version"] == {
        "source": "regex",
        "path": "src/lclang/__version__.py",
    }
    definitions: list[tuple[Path, object]] = []
    for path in (ROOT / "src/lclang").rglob("*.py"):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in node.targets
            ):
                assert isinstance(node.value, ast.Constant)
                definitions.append((path.relative_to(ROOT), node.value.value))
    assert len(definitions) == 1
    path, version = definitions[0]
    assert path == Path("src/lclang/__version__.py")
    assert isinstance(version, str) and re.fullmatch(r"1\.0\.(0|[1-9][0-9]*)", version)
    assert import_module("lclang.__version__").__version__ == version
    assert read_package_version(ROOT) == version


@pytest.mark.parametrize(
    "source",
    [
        "",
        "other = '1.0.16'",
        "__version__ = ''",
        "__version__ = 16",
        "__version__ = str(16)",
        "__version__ = '1.0.16'\n__version__ = '1.0.17'",
    ],
)
def test_version_reader_rejects_ambiguous_or_nonliteral_definitions(source: str) -> None:
    """Invalid metadata cannot become an implicitly evaluated or arbitrary version."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        package = root / "src/lclang"
        package.mkdir(parents=True)
        (package / "__version__.py").write_text(source, encoding="utf-8")
        with pytest.raises(ValueError, match="one nonempty literal"):
            read_package_version(root)


def test_version_reader_does_not_execute_unrelated_package_statements() -> None:
    """Reading build metadata does not initialize the package or execute its source."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        package = root / "src/lclang"
        package.mkdir(parents=True)
        (package / "__version__.py").write_text(
            "raise RuntimeError('must not run')\n__version__ = '1.0.42'\n",
            encoding="utf-8",
        )
        assert read_package_version(root) == "1.0.42"
