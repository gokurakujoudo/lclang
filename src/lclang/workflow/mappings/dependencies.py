"""Scope-aware mapping dependencies and dataclass field fallback metadata."""

from dataclasses import MISSING

from lclang.workflow.definitions import TaskNode, Workflow
from lclang.workflow.mappings.bindings import mapping_variables
from lclang.workflow.mappings.structure import MappingNode, mapping_nodes, mapping_structure
from lclang.workflow.variables import TaskVar


def has_field_default(node: MappingNode) -> bool:
    """Inspect constructor fallback metadata without calling its factory.

    :param node: One structural mapping location.
    :returns: Whether this location has a dataclass constructor default.
    """
    return node.field is not None and (
        node.field.default is not MISSING or node.field.default_factory is not MISSING
    )


def external_uses(workflow: Workflow) -> tuple[MappingNode, ...]:
    """Find unresolved argument locations using execution's context scope rules.

    :param workflow: Workflow definition to analyze.
    :returns: External mapping locations in first-use order, retaining repetitions.
    """
    assigned: set[str] = set()
    external: list[MappingNode] = []

    def use(mapping: object | None, visible: set[str]) -> None:
        """Record unresolved quotes from one argument mapping.

        :param mapping: Optional dataclass mapping.
        :param visible: Names assigned in the current scope.
        """
        for node in mapping_nodes(mapping_structure(mapping)):
            if isinstance(node.value, TaskVar) and node.value.name not in visible:
                external.append(node)

    def visit(task: TaskNode, inherited: frozenset[str] = frozenset()) -> None:
        """Analyze one task in parent-first depth-first order.

        :param task: Current task definition.
        :param inherited: Context bindings visible from ancestor task scopes.
        """
        local = assigned | set(inherited)
        for context in task.context_tasks:
            use(context.args_mapping, local)
            local.update(item.name for item in mapping_variables(context.outputs_mapping))
        use(task.args_mapping, local)
        assigned.update(item.name for item in mapping_variables(task.outputs_mapping))
        for child in task.children:
            visit(child, frozenset(local))

    visit(workflow.root_task)
    return tuple(external)
