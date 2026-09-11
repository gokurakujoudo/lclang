"""Build GitHub Pages from the canonical, executable Markdown documentation."""

import argparse
import json
import posixpath
import re
import shutil
import subprocess
import tomllib
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from markdown_it import MarkdownIt
from markdown_it.token import Token

from scripts.export_wiki import REPOSITORY, ROOT
from scripts.site_highlighting import highlight_code


def page_route(source: Path) -> str:
    """Map a documentation-relative source to its portable HTML route."""
    return source.with_name("index.html").as_posix() if source.name == "README.md" else (
        source.with_suffix(".html").as_posix()
    )


def plain_text(tokens: list[Token]) -> str:
    """Extract visible inline text without Markdown formatting markers."""
    return "".join(
        " " if token.type in {"softbreak", "hardbreak"} else token.content
        for token in tokens if token.type in {"text", "code_inline", "softbreak", "hardbreak"}
    )


def local_link(url: str, source: Path, root: Path, ref: str) -> str:
    """Resolve document links locally and other repository files at the source revision."""
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return url
    target = (source.parent / unquote(parsed.path)).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError(f"{source}: invalid local link {url}")
    if target.is_relative_to(root / "docs") and target.suffix == ".md":
        current = page_route(source.relative_to(root / "docs"))
        path = posixpath.relpath(page_route(target.relative_to(root / "docs")),
                                 posixpath.dirname(current) or ".")
    else:
        path = f"{REPOSITORY}/blob/{quote(ref, safe='')}/{target.relative_to(root).as_posix()}"
    return urlunsplit(("", "", path, parsed.query, parsed.fragment))


def render_document(
    source: Path, root: Path, ref: str,
) -> tuple[str, str, str, list[dict[str, str]]]:
    """Render exact code blocks, unique heading anchors, contents and searchable sections."""
    markdown = MarkdownIt("commonmark", {"highlight": highlight_code}).enable(
        ["table", "strikethrough"],
    )
    tokens = markdown.parse(source.read_text(encoding="utf-8"))
    headings: list[str] = []
    sections: list[dict[str, str]] = []
    ids: set[str] = {"main", "navigation", "search-title", "search-input",
                     "search-status", "search-results"}
    title = source.stem
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            label = plain_text(tokens[index + 1].children or [])
            slug = re.sub(r"[^\w\- ]", "", label.lower()).replace(" ", "-") or "section"
            anchor, suffix = slug, 0
            while anchor in ids:
                suffix += 1
                anchor = f"{slug}-{suffix}"
            ids.add(anchor)
            token.attrSet("id", anchor)
            if token.tag == "h1":
                title = label
            else:
                headings.append(f'<a class="toc-{token.tag}" href="#{anchor}">'
                                f'{escape(label)}</a>')
            sections.append({"heading": label, "anchor": anchor, "text": ""})
        if (sections and token.type in {"inline", "fence", "code_block"}
                and (index == 0 or tokens[index - 1].type != "heading_open")):
            sections[-1]["text"] += (plain_text(token.children) if token.children else
                                     token.content) + " "
        for child in token.children or []:
            for attribute in ("href", "src"):
                url = child.attrGet(attribute)
                if url:
                    child.attrSet(attribute, local_link(str(url), source, root, ref))
    content = markdown.renderer.render(tokens, markdown.options, {})
    return content, title, "".join(headings), sections


def documentation_groups(root: Path) -> dict[str, list[Path]]:
    """Discover pages, taking tutorial order only from its canonical table of contents."""
    docs = root / "docs"
    introduction = Path("tutorials/README.md")
    tokens = MarkdownIt().parse((docs / introduction).read_text(encoding="utf-8"))
    chapters: list[Path] = []
    for token in tokens:
        for child in token.children or []:
            href = str(child.attrGet("href") or "")
            if child.type == "link_open" and re.fullmatch(r"\d\d-[\w-]+\.md", href):
                path = introduction.parent / href
                if path not in chapters:
                    chapters.append(path)
    groups = {"Getting started": [Path("README.md"), Path("installation.md"),
                                  Path("quick-start.md")],
              "Tutorials": [introduction, *chapters]}
    for name, folder in (("Reference", "reference"), ("Development", "development")):
        groups[name] = [Path(folder) / "README.md", *(
            path.relative_to(docs) for path in sorted((docs / folder).glob("*.md"))
            if path.name != "README.md"
        )]
    found = [page for pages in groups.values() for page in pages]
    if set(found) != {path.relative_to(docs) for path in docs.rglob("*.md")}:
        raise ValueError("Every documentation page must appear in navigation")
    return groups


def build_site(root: Path, output: Path, ref: str) -> list[Path]:
    """Generate a self-contained static site; refuse outputs outside the build directory."""
    root, output = root.resolve(), output.resolve()
    if not output.is_relative_to(root / "build") or output == root / "build":
        raise ValueError("Site output must be a subdirectory of the repository build directory")
    groups = documentation_groups(root)
    pages = [page for values in groups.values() for page in values]
    rendered = {page: render_document(root / "docs" / page, root, ref) for page in pages}
    template = Template((root / "site/template.html").read_text(encoding="utf-8"))
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    output.mkdir(parents=True, exist_ok=True)
    for asset in (root / "site").iterdir():
        if asset.is_dir():
            shutil.copytree(asset, output / asset.name, dirs_exist_ok=True)
        elif asset.suffix in {".css", ".js"}:
            shutil.copyfile(asset, output / asset.name)
    search: list[dict[str, str]] = []
    for position, page in enumerate(pages):
        content, title, toc, sections = rendered[page]
        route = page_route(page)
        base = "../" * (len(Path(route).parts) - 1) or "./"
        navigation = []
        group = next(name for name, values in groups.items() if page in values)
        for name, values in groups.items():
            links = []
            for other in values:
                label = "Overview" if other == Path("README.md") else rendered[other][1]
                selected = ' aria-current="page"' if other == page else ""
                links.append(f'<a href="{base}{page_route(other)}"{selected}>{escape(label)}</a>')
            opened = " open" if name in {group, "Getting started", "Reference"} else ""
            navigation.append(f'<details{opened}><summary>{name}</summary>{"".join(links)}</details>')
        pagination = []
        for offset, label in ((-1, "← Previous"), (1, "Next →")):
            if 0 <= position + offset < len(pages):
                other = pages[position + offset]
                pagination.append(f'<a href="{base}{page_route(other)}"><span>{label}</span>'
                                  f'<strong>{escape(rendered[other][1])}</strong></a>')
        for section in sections:
            search.append({**section, "title": title, "group": group,
                           "url": f'{route}#{section["anchor"]}'})
        html = template.substitute(
            title=escape(title),
            description=escape(sections[0]["text"][:180] if sections else title),
            route=route, base=base, version=escape(project["version"]), group=group,
            page_class="home" if page == Path("README.md") else "document",
            navigation="".join(navigation), content=content, toc=toc,
            pagination="".join(pagination),
            source_url=f"{REPOSITORY}/blob/{quote(ref, safe='')}/docs/{page.as_posix()}",
        )
        target = output / route
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
    (output / "search-index.json").write_text(
        json.dumps(search, ensure_ascii=False), encoding="utf-8",
    )
    (output / ".nojekyll").touch()
    return [output / page_route(page) for page in pages]


def main() -> None:
    """Build the checked-out documentation for local preview or Pages deployment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/site")
    args = parser.parse_args()
    ref = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = build_site(ROOT, args.output, ref)
    print(f"Built {len(paths)} documentation pages in {args.output}")


if __name__ == "__main__":
    main()
