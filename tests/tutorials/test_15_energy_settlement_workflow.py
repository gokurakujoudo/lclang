"""Executable contracts for tutorial chapter 15."""

from tests.tutorials.support import execute_tutorial


def test_energy_settlement_workflow_tutorial() -> None:
    """The configuration contract and complete CLI workflow run as published."""
    execute_tutorial("15-energy-settlement-workflow.md", 2)
