"""Publish tested Markdown as flat GitHub Wiki pages without changing examples."""

import argparse
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/gokurakujoudo/lclang"
WIKI = f"{REPOSITORY}/wiki"
# Code spans and fenced blocks precede links so source examples stay byte-for-byte intact.
MARKDOWN_LINK = re.compile(r"(```.*?```|`[^`\n]*`)|(\[[^\]\n]+\]\()([^\s)]+)(\))", re.DOTALL)


def page_name(relative: Path) -> str:
    """Map a path relative to docs to a unique, stable Wiki page name."""
    indexes = {
        "README.md": "Home",
        "tutorials/README.md": "Tutorials",
        "reference/README.md": "Reference",
        "development/README.md": "Development",
    }
    return indexes.get(relative.as_posix(), "-".join(relative.with_suffix("").parts))


def rewrite_links(text: str, source: Path, root: Path, ref: str) -> str:
    """Resolve local prose links to Wiki pages or versioned repository files.

    :param text: Original Markdown including exact executable examples.
    :param source: Absolute Markdown source path.
    :param root: Absolute repository path.
    :param ref: Source revision used for non-document links.
    :returns: Markdown with only local prose link destinations replaced.
    :raises ValueError: If a local destination is absent or outside the repository.
    """
    def replace(match: re.Match[str]) -> str:
        if match[1]:
            return match[0]
        parsed = urlsplit(match[3])
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match[0]
        destination = (source.parent / unquote(parsed.path)).resolve()
        if not destination.is_relative_to(root) or not destination.is_file():
            raise ValueError(f"{source}: invalid local link {match[3]}")
        if destination.suffix == ".md" and destination.is_relative_to(root / "docs"):
            url = f"{WIKI}/{page_name(destination.relative_to(root / 'docs'))}"
        else:
            relative = destination.relative_to(root).as_posix()
            url = f"{REPOSITORY}/blob/{quote(ref, safe='')}/{relative}"
        target = urlsplit(url)
        url = urlunsplit((target.scheme, target.netloc, target.path, parsed.query, parsed.fragment))
        return f"{match[2]}{url}{match[4]}"

    return MARKDOWN_LINK.sub(replace, text)


def export_wiki(root: Path, output: Path, ref: str) -> list[Path]:
    """Write Wiki pages and navigation, preserving unrelated checkout files.

    :param root: Repository containing canonical Markdown in docs.
    :param output: Export directory or an existing Wiki checkout.
    :param ref: Revision identifying the exact documentation source.
    :returns: Generated Markdown paths, including navigation and footer.
    :raises ValueError: If names collide, links break, or output overlaps sources.
    """
    root, output = root.resolve(), output.resolve()
    if output == root or output.is_relative_to(root / "docs") or root.is_relative_to(output):
        raise ValueError("Wiki output must not overlap documentation sources")
    pages: dict[str, str] = {}
    for source in sorted((root / "docs").rglob("*.md")):
        name = page_name(source.relative_to(root / "docs"))
        if name.casefold() in {key.casefold() for key in pages}:
            raise ValueError(f"Duplicate Wiki page: {name}")
        content = rewrite_links(source.read_text(encoding="utf-8"), source, root, ref)
        origin = f"{REPOSITORY}/blob/{quote(ref, safe='')}/{source.relative_to(root).as_posix()}"
        pages[name] = f"{content.rstrip()}\n\n---\n[Edit the tested source]({origin}).\n"
    pages["_Sidebar"] = (
        '<img src="https://gokurakujoudo.github.io/lclang/assets/logo.png" '
        'width="40" height="40" alt="lclang logo">\n\n'
        f"[Home]({WIKI}/Home)\n\n[Quick start]({WIKI}/quick-start)\n\n"
        f"[Tutorial series]({WIKI}/Tutorials)\n\n[Reference]({WIKI}/Reference)\n\n"
        f"[Development]({WIKI}/Development)\n\n"
        "[Project website](https://gokurakujoudo.github.io/lclang/)\n"
    )
    pages["_Footer"] = (
        f"Published from [{ref[:12]}]({REPOSITORY}/tree/{quote(ref, safe='')}). "
        "Documentation is maintained and tested in the source repository.\n"
    )
    output.mkdir(parents=True, exist_ok=True)
    for name, content in pages.items():
        (output / f"{name}.md").write_text(content, encoding="utf-8")
    return [output / f"{name}.md" for name in pages]


def main() -> None:
    """Export the current checked-out documentation to the requested directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    ref = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = export_wiki(ROOT, args.output, ref)
    print(f"Exported {len(paths)} Wiki files to {args.output}")


if __name__ == "__main__":
    main()
