"""Workflow adapter for shared structured failure aggregation."""

from lclang.error.aggregation import combine_failures as combine_error_failures
from lclang.error.codes.workflow import Code as workflow_codes


def combine_failures(pending: BaseException | None, cleanup: BaseException) -> BaseException:
    """Keep workflow failures and cleanup causes in their original order.

    :param pending: Failure already propagating through an owned resource scope.
    :param cleanup: Failure raised while exiting that scope.
    :returns: Ordinary LCL group or original control signal with retained causes.
    """
    return combine_error_failures(pending, cleanup, code=workflow_codes.COMPOSITE_FAILURE)
