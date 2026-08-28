"""Workflow definition and static rendering contracts."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest

import lclang.workflow as wf


@dataclass
class ContextArgs:
    """Arguments used by the rendering context."""

    seed: int


@dataclass
class ContextOutputs:
    """Outputs used by the rendering context."""

    resource: int


@dataclass
class RootArgs:
    """Arguments used by the rendering task."""

    source: int
    literal: int = 100


@dataclass
class RootOutputs:
    """Outputs used by the rendering task."""

    result: int
    ignored: int = 0


async def root_action(
    context: wf.TaskContext,
    args: RootArgs,
    status_mgr: wf.ExecutionStatusManager,
) -> RootOutputs:
    """Return one rendered output.

    :param context: Current task execution context.
    :param args: Materialized task arguments.
    :param status_mgr: Current task status manager.
    :returns: Rendered output value.
    """
    del context, status_mgr
    return RootOutputs(args.source + args.literal)


@asynccontextmanager
async def resource_context(
    context: wf.TaskContext,
    args: ContextArgs,
    status_mgr: wf.ExecutionStatusManager,
) -> AsyncIterator[ContextOutputs]:
    """Yield one unused rendering resource.

    :param context: Current task context.
    :param args: Materialized context arguments.
    :param status_mgr: Context-task status manager.
    :returns: Async iterator yielding one resource.
    """
    del context, status_mgr
    yield ContextOutputs(args.seed)


def test_workflow_to_lines_renders_context_scope_and_field_flows() -> None:
    """Contexts wrap child tasks and mappings use stable field-flow notation."""
    source = wf.define_variable[int]("source", "Source value", is_masked=True)
    resource = wf.define_variable[int]("resource")
    result = wf.define_variable[int]("result")

    context_task = wf.define_context_task(
        "resource_context",
        "Provide resource",
        resource_context,
        ContextArgs(seed=source.quote),
        ContextOutputs(resource=resource.quote),
    )
    child = wf.define_task("child", "Child task")
    root = wf.define_task(
        "root",
        "Root task",
        task_action=root_action,
        args_mapping=RootArgs(source=source.quote),
        outputs_mapping=RootOutputs(result=result.quote),
        context_tasks=[context_task],
        children=[child],
    )
    workflow = wf.define_workflow("Example workflow", root_task=root)

    assert workflow.to_lines() == [
        'Workflow "Example workflow"',
        '└─ task root "Root task" args=RootArgs{source <- $source!, literal <- 100} '
        'outputs=RootOutputs{result -> $result, ignored -> <unmapped>}',
        '   └─ enter context resource_context "Provide resource" '
        'args=ContextArgs{seed <- $source!} '
        'outputs=ContextOutputs{resource -> $resource}',
        '      ├─ task child "Child task" args=<none> outputs=<none>',
        '      └─ exit context resource_context "Provide resource" '
        'args=ContextArgs{seed <- $source!} '
        'outputs=ContextOutputs{resource -> $resource}',
    ]


def test_workflow_definition_rejects_duplicate_ids_and_cycles() -> None:
    """The reusable tree has globally unique IDs and cannot contain a cycle."""
    duplicate = wf.define_task("same", "Duplicate")
    root = wf.define_task("same", "Root", children=[duplicate])
    with pytest.raises(ValueError, match="duplicate workflow task ID"):
        wf.define_workflow("Invalid", root)

    children: list[wf.TaskNode] = []
    cyclic = wf.define_task("cyclic", "Cyclic", children=children)
    children.append(cyclic)
    assert cyclic.children == ()
