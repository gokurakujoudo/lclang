"""Install pylcl artifacts into fresh environments and run public API smoke tests."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import venv
from pathlib import Path


def venv_python(root: Path, platform: str = os.name) -> Path:
    """Return the Python executable inside a virtual environment.

    :param root: Virtual-environment directory.
    :param platform: Operating-system family, normally :data:`os.name`.
    :returns: Interpreter path for Windows or POSIX.
    """
    if platform == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def smoke_program(artifact_kind: str) -> str:
    """Return the fixed public-API smoke program for one artifact kind.

    :param artifact_kind: Machine-readable artifact label in the output record.
    :returns: Standalone Python source executed outside the repository.
    :raises ValueError: If *artifact_kind* is blank.
    """
    if not artifact_kind:
        raise ValueError("artifact kind cannot be empty")
    return f'''\
import asyncio
import sys
from pathlib import Path

import pylcl
from pylcl.runtime import build_dependency_graph, topological_order

sync_value = pylcl.evaluate_sync(pylcl.parse_expression("3 + 4"), {{}})


async def main() -> None:
    expression = pylcl.parse_expression("1 + 2")
    assert pylcl.to_source(expression) == "1 + 2"
    assert await pylcl.evaluate(expression, {{}}) == 3
    assert sync_value == 7
    module = pylcl.Module(
        pylcl.ModuleName("smoke"),
        {{
            "base": pylcl.parse_expression("1"),
            "value": pylcl.parse_expression("base + 1"),
            "payload": pylcl.parse_expression('json.encode({{"ok": true}})'),
            "iter_value": pylcl.parse_expression("iter.first([1, 2])"),
            "text_value": pylcl.parse_expression('text.join("-", ["a", "b"])'),
            "data_value": pylcl.parse_expression('data.lookup({{"x": 1}}, "x")'),
        }},
    )
    frame = pylcl.FrameFactory(module, pylcl.STANDARD_PRESET).create(
        pylcl.FrameId("smoke:1"),
    )
    try:
        value = await frame.get("value")
        snapshot = frame.dependency_snapshot("value")
        refreshed = await frame.recalculate("base")
        assert await frame.get("value") == value
        assert refreshed == 1
        assert await frame.get("payload") == '{{"ok":true}}'
        assert await frame.get("iter_value") == 1
        assert await frame.get("text_value") == "a-b"
        assert await frame.get("data_value") == 1
        graph = build_dependency_graph(module)
        order = topological_order(graph)
        assert order
        dependency = str(snapshot.dynamic_edges[0].target)
    finally:
        await frame.close()
    assert frame.closed is True
    assert Path(pylcl.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    print("pylcl-smoke version=" + pylcl.__version__ +
          " artifact={artifact_kind} value=" + str(value) +
          " dependency=" + dependency + " closed=" + str(frame.closed).lower())


asyncio.run(main())
'''


def run_command(command: tuple[str, ...], cwd: Path, env: dict[str, str]) -> int:
    """Run one smoke subprocess with explicit environment isolation.

    :param command: Executable and arguments to run.
    :param cwd: Directory outside the repository used as working directory.
    :param env: Environment with repository import paths removed.
    :returns: Child return code.
    """
    return subprocess.run(command, cwd=cwd, env=env, check=False).returncode


def create_temp_root(parent: Path, prefix: str) -> Path:
    """Create a temporary verification root beneath a writable artifact parent.

    :param parent: Directory beside the artifact being verified.
    :param prefix: Prefix used to identify the temporary root.
    :returns: Newly created temporary directory.
    :raises OSError: If the parent cannot host a temporary directory.

    .. note::
       Using the artifact parent avoids platform temp ACLs while keeping the
       smoke working directory separate from the package source tree.
    """
    parent.mkdir(parents=True, exist_ok=True)
    root = parent / f"{prefix}{uuid.uuid4().hex}"
    root.mkdir()
    return root


def smoke_install(wheel: Path, artifact_kind: str = "wheel") -> int:
    """Install one wheel without dependencies and execute the complete smoke.

    :param wheel: Wheel artifact to verify.
    :param artifact_kind: Label identifying the artifact in the success record.
    :returns: Zero when installation and public runtime smoke succeed.
    """
    root = create_temp_root(wheel.parent, "pylcl-smoke-")
    try:
        environment = root / "venv"
        previous_temp = {name: os.environ.get(name) for name in ("TEMP", "TMP", "TMPDIR")}
        previous_tempdir = tempfile.tempdir
        try:
            for name in previous_temp:
                os.environ[name] = str(root)
            tempfile.tempdir = str(root)
            venv.EnvBuilder(with_pip=False).create(environment)
        finally:
            tempfile.tempdir = previous_tempdir
            for name, value in previous_temp.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        python = str(venv_python(environment))
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["PYTHONNOUSERSITE"] = "1"
        env["TEMP"] = str(root)
        env["TMP"] = str(root)
        env["TMPDIR"] = str(root)
        install = run_command(
            (
                sys.executable, "-m", "pip", "--python", python, "install", "--no-deps",
                "--no-index", str(wheel),
            ),
            root,
            env,
        )
        if install:
            return install
        program = root / "smoke.py"
        program.write_text(smoke_program(artifact_kind), encoding="utf-8")
        return run_command((python, str(program)), root, env)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and execute the clean-install smoke test.

    :param argv: Optional command arguments.
    :returns: Smoke-test return code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--artifact-kind", default="wheel")
    options = parser.parse_args(argv)
    return smoke_install(options.wheel.resolve(), options.artifact_kind)


if __name__ == "__main__":
    sys.exit(main())
