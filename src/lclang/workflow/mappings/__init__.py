"""Recursive dataclass mapping boundaries for workflow consumers.

Exports ``mapped_outputs``, ``mapping_text``, ``mapping_variables``, ``materialize_args``,
``require_mapping``.
"""

from lclang.workflow.mappings.mapping_binding import (
    mapped_outputs,
    mapping_text,
    mapping_variables,
    materialize_args,
    require_mapping,
)

# Unitless compatibility exports retain the existing mapping entry points while
# keeping structure, record annotations, values, and diagnostics in this subsystem.
__all__ = [
    "mapped_outputs",
    "mapping_text",
    "mapping_variables",
    "materialize_args",
    "require_mapping",
]
