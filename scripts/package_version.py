"""Read the checkout's canonical literal package version without importing lclang."""

import ast
from pathlib import Path


def read_package_version(root: Path) -> str:
    """Read one nonempty literal version from the canonical production source.

    :param root: Project checkout containing src/lclang/__version__.py.
    :returns: Version text declared by the package.
    :raises ValueError: If the source lacks one nonempty literal version definition.
    :raises OSError: If the version source cannot be read.
    :raises SyntaxError: If the source is not valid Python.
    """
    source = root / "src/lclang/__version__.py"
    versions = [
        node.value
        for node in ast.parse(source.read_text(encoding="utf-8"), filename=str(source)).body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        )
    ]
    if (
        len(versions) != 1
        or not isinstance(versions[0], ast.Constant)
        or not isinstance(versions[0].value, str)
        or not versions[0].value
    ):
        raise ValueError("Package version requires one nonempty literal __version__ definition")
    return versions[0].value
