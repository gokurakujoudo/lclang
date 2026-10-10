"""Readable Markdown file fixtures and exact observable-result assertions."""

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from difflib import unified_diff
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

CASE_PATTERN = re.compile(
    r"<!-- lclang-doc-case: ([a-z0-9-]+)(?: exit=([0-9]+))? -->\s*\n(.*?)<!-- /lclang-doc-case -->",
    re.DOTALL,
)
ROLE_PATTERN = re.compile(
    r"<!-- lclang-doc-(file|output): ([^\n]+?) -->\s*\n```[^\n]*\n(.*?)^```[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True)
class DocumentCase:
    """Keep one chapter case's exact source and expected observable results."""

    name: str
    filename: str
    files: dict[str, str]
    source: str
    stdout: str = ""
    stderr: str = ""
    exit_status: int = 0
    expected_files: dict[str, str] = field(default_factory=dict[str, str])


def strip_file_cases(text: str) -> str:
    """Exclude file cases from the legacy in-process example collector."""
    return CASE_PATTERN.sub("", text)


def validate_fixture_path(name: str) -> None:
    """Reject paths that escape a case's independent temporary workspace."""
    path = PurePosixPath(name)
    assert (
        name and not path.is_absolute() and ".." not in path.parts
    ), f"unsafe fixture path: {name}"
    assert "\\" not in name and ":" not in name, f"unsafe fixture path: {name}"


def extract_file_cases(text: str, filename: str) -> list[DocumentCase]:
    """Read exact fixture, execution, and output fences from marked cases."""
    from tests.documentation.examples import marked_blocks

    matches = list(CASE_PATTERN.finditer(text))
    assert len(matches) == text.count("<!-- lclang-doc-case:"), f"{filename}: malformed file case"
    assert len(matches) == text.count(
        "<!-- /lclang-doc-case -->"
    ), f"{filename}: dangling file case"
    cases: list[DocumentCase] = []
    names: set[str] = set()
    for match in matches:
        name, exit_status, body = match.groups()
        assert name not in names, f"{filename}: duplicate case {name}"
        names.add(name)
        source = marked_blocks(body)
        assert len(source) == 1, f"{filename}:{name}: expected one runnable Python example"
        files: dict[str, str] = {}
        expected: dict[str, str] = {}
        outputs: dict[str, str] = {}
        roles = ROLE_PATTERN.findall(body)
        assert len(roles) == body.count("<!-- lclang-doc-file:") + body.count(
            "<!-- lclang-doc-output:"
        ), f"{filename}:{name}: malformed fixture or output"
        for role, label, content in roles:
            if role == "file":
                validate_fixture_path(label)
                assert label not in files, f"{filename}:{name}: duplicate file {label}"
                files[label] = content
            elif label in {"stdout", "stderr"}:
                assert label not in outputs, f"{filename}:{name}: duplicate output {label}"
                outputs[label] = content
            else:
                assert label.startswith("file "), f"{filename}:{name}: unknown output {label}"
                label = label[5:]
                validate_fixture_path(label)
                assert label not in expected, f"{filename}:{name}: duplicate output file {label}"
                expected[label] = content
        cases.append(
            DocumentCase(
                name,
                filename,
                files,
                source[0],
                outputs.get("stdout", ""),
                outputs.get("stderr", ""),
                int(exit_status or 0),
                expected,
            )
        )
    return cases


def normalize_workspace(text: str, root: Path, names: set[str]) -> str:
    """Replace only known temporary fixture paths with their displayed filenames."""
    for name in sorted(names, key=len, reverse=True):
        physical = str(root / name)
        text = text.replace(physical.replace("\\", "\\\\"), name).replace(physical, name)
    return text


def execute_file_case(case: DocumentCase, repository: Path) -> None:
    """Materialize exact Markdown fixtures and verify outputs from an isolated process."""
    with TemporaryDirectory(prefix="lclang-doc-case-") as directory:
        root = Path(directory)
        for name, source in case.files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8", newline="")
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(repository / "src"), environment.get("PYTHONPATH", "")]
        )
        result = subprocess.run(
            [sys.executable, "-c", case.source],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        names = set(case.files) | set(case.expected_files)
        assert (
            result.returncode == case.exit_status
        ), f"{case.filename}:{case.name}: exit {result.returncode}\n{result.stderr}"
        assert_output_matches(
            normalize_workspace(result.stdout, root, names),
            case.stdout,
            f"{case.filename}:{case.name}: stdout",
        )
        assert_output_matches(
            normalize_workspace(result.stderr, root, names),
            case.stderr,
            f"{case.filename}:{case.name}: stderr",
        )
        for name, expected in case.expected_files.items():
            assert_output_matches(
                (root / name).read_text(encoding="utf-8"),
                expected,
                f"{case.filename}:{case.name}: {name}",
            )


def assert_output_matches(actual: str, expected: str, label: str) -> None:
    """Report a readable expected-versus-actual difference for one example result."""
    difference = "".join(
        unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile="expected",
            tofile="actual",
        )
    )
    assert actual == expected, f"{label} differs\n{difference}"
