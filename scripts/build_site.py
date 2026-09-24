"""Build the MkDocs Read the Docs site for local preview and GitHub Pages."""

import argparse
import subprocess
from pathlib import Path

from mkdocs.commands.build import build

# MkDocs leaves keyword override types unspecified in its public loader.
from mkdocs.config import load_config  # pyright: ignore[reportUnknownVariableType]

from scripts.export_wiki import ROOT
from scripts.site_navigation import documentation_groups


def build_site(root: Path, output: Path, ref: str) -> list[Path]:
    """Build strictly inside build/ and return the generated documentation pages."""
    root, output = root.resolve(), output.resolve()
    if not output.is_relative_to(root / "build") or output == root / "build":
        raise ValueError("Site output must be a subdirectory of the repository build directory")
    config = load_config(
        str(root / "mkdocs.yml"),
        site_dir=str(output),
        extra={"revision": ref},
    )
    config.plugins.on_startup(command="build", dirty=False)
    try:
        build(config)
    finally:
        config.plugins.on_shutdown()
    return [
        output
        / (page.with_name("index.html") if page.name == "README.md" else page.with_suffix(".html"))
        for pages in documentation_groups(root).values()
        for page in pages
    ]


def main() -> None:
    """Build the checked-out documentation with the project's MkDocs configuration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/site")
    args = parser.parse_args()
    ref = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = build_site(ROOT, args.output, ref)
    print(f"Built {len(paths)} documentation pages in {args.output}")


if __name__ == "__main__":
    main()
