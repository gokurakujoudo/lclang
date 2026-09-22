"""Collect variable defaults and own their per-execution lookup environment."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from lclang.defaults import NO_DEFAULT, DefaultBinding
from lclang.runtime import Frame
from lclang.runtime.frame.defaults import create_default_frame, default_scope
from lclang.workflow.definitions import ContextTask, TaskNode, Workflow
from lclang.workflow.mappings import mapping_variables


def workflow_defaults(workflow: Workflow) -> dict[str, DefaultBinding]:
    """Collect declarations without evaluating literals or invoking factories.

    :param workflow: Reusable task tree.
    :returns: Default bindings keyed by their possibly masked variable names.
    """
    bindings: dict[str, DefaultBinding] = {}

    def visit(task: TaskNode) -> None:
        """Visit the current action, its contexts, and descendants.

        :param task: Current task node.
        """
        definitions: tuple[TaskNode | ContextTask, ...] = (task, *task.context_tasks)
        for definition in definitions:
            for mapping in (definition.args_mapping, definition.outputs_mapping):
                for variable in mapping_variables(mapping):
                    if variable.default is not NO_DEFAULT or variable.default_factory is not None:
                        name = variable.name + ("!" if variable.is_masked else "")
                        bindings.setdefault(name, DefaultBinding(
                            variable.default, variable.default_factory,
                        ))
        for child in task.children:
            visit(child)

    visit(workflow.root_task)
    return bindings


@asynccontextmanager
async def execution_defaults(workflow: Workflow, frame: Frame) -> AsyncIterator[None]:
    """Own missing fallback bindings for exactly one workflow execution.

    :param workflow: Reusable variable declarations.
    :param frame: Borrowed execution Frame whose hierarchy remains unchanged.
    :returns: Async scope isolating factory caches and retaining existing snapshots.
    """
    bindings = {
        name: binding for name, binding in workflow_defaults(workflow).items()
        if not frame.has(name.removesuffix("!"))
    }
    if not bindings:
        yield
        return
    async with create_default_frame(bindings) as defaults:
        with default_scope(frame, defaults):
            yield
