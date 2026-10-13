"""Validated workflow log paths and lifecycle record metadata.

Defines ``validate_log_stack``, ``make_lifecycle_metadata``.
"""

from lclang.error import LclValidationError, WorkflowErrorCode


def validate_log_stack(stack: tuple[str, ...]) -> None:
    """Validate a detached log path without restricting business call names.

    :param stack: Tuple of nonempty path components; an empty tuple is valid.
    :raises LclValidationError: If the tuple or any component has the wrong type.
    :raises LclValidationError: If any component is empty.
    """
    if not isinstance(stack, tuple) or any(not isinstance(item, str) for item in stack):
        raise LclValidationError(
            "workflow log path must be a tuple of strings",
            code=WorkflowErrorCode.E33_LOG_PATH_MUST_BE_A_TUPLE_OF_STRINGS,
        )
    if any(not item for item in stack):
        raise LclValidationError(
            "workflow log path components cannot be empty",
            code=WorkflowErrorCode.E33_LOG_PATH_COMPONENTS_CANNOT_BE_EMPTY,
        )


def make_lifecycle_metadata(branch: str, dryrun: bool) -> dict[str, object]:
    """Mark lifecycle records for the default short layout without losing attribution.

    :param branch: Complete dot-connected log path.
    :param dryrun: Execution's dry-run signal.
    :returns: Unitless record markers and identity shared by workflow producers.
    """
    return {
        "lclang_workflow_lifecycle": True,
        "lclang_task_branch": branch,
        "lclang_dryrun": dryrun,
    }
