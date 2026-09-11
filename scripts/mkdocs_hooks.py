"""Connect MkDocs to canonical navigation, repository links and shared assets."""

import re
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import File, Files, InclusionLevel
from mkdocs.structure.pages import Page

from scripts.export_wiki import MARKDOWN_LINK, REPOSITORY
from scripts.site_navigation import documentation_groups


def on_config(config: MkDocsConfig) -> MkDocsConfig:
    """Derive navigation and version without maintaining a second tutorial inventory."""
    root = Path(config.docs_dir).parent
    output = Path(config.site_dir).resolve()
    if not output.is_relative_to(root / "build") or output == root / "build":
        raise ValueError("Site output must be a subdirectory of the repository build directory")
    config.nav = [{name: [page.as_posix() for page in pages]}
                  for name, pages in documentation_groups(root).items()]
    config.extra["version"] = tomllib.loads(
        (root / "pyproject.toml").read_text(encoding="utf-8"),
    )["project"]["version"]
    if "revision" not in config.extra:
        config.extra["revision"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True,
        ).strip()
    config.edit_uri = f"blob/{config.extra['revision']}/docs/"
    return config


def on_files(files: Files, config: MkDocsConfig) -> Files:
    """Publish shared site assets without copying them into canonical Markdown."""
    site = Path(config.docs_dir).parent / "site"
    for path in sorted(site.rglob("*")):
        if path.is_file() and path.suffix not in {".md", ".html"}:
            files.append(File.generated(
                config, path.relative_to(site).as_posix(), abs_src_path=str(path),
                inclusion=InclusionLevel.INCLUDED,
            ))
    return files


def on_page_markdown(markdown: str, page: Page, config: MkDocsConfig, files: Files) -> str:
    """Keep document links native to MkDocs and point repository links at the built commit."""
    root = Path(config.docs_dir).parent
    source = Path(config.docs_dir) / page.file.src_uri

    def replace(match: re.Match[str]) -> str:
        if match[1]:
            return match[0]
        parsed = urlsplit(match[3])
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match[0]
        target = (source.parent / unquote(parsed.path)).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError(f"{source}: invalid local link {match[3]}")
        if target.is_relative_to(root / "docs"):
            return match[0]
        revision = quote(str(config.extra["revision"]), safe="")
        url = urlsplit(f"{REPOSITORY}/blob/{revision}/{target.relative_to(root).as_posix()}")
        destination = urlunsplit((url.scheme, url.netloc, url.path, parsed.query, parsed.fragment))
        return f"{match[2]}{destination}{match[4]}"

    return MARKDOWN_LINK.sub(replace, markdown)
