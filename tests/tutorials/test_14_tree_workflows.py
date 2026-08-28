"""Executable contracts for tutorial chapter 14."""

from tests.tutorials.support import execute_tutorial


def test_tree_workflows_tutorial() -> None:
    """Every complete tree-workflow example runs exactly as published."""
    execute_tutorial("14-tree-workflows.md", 2)
