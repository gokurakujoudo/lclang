"""The standalone source audit works without an installed lclang distribution."""

import os
import subprocess
import sys
from pathlib import Path


def test_source_audit_discovers_the_checkout_without_site_initialization() -> None:
    """A clean import environment finds src explicitly and runs the complete source audit."""
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-S", "-m", "scripts.check_project"],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
