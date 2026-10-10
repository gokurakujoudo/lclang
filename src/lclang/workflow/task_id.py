"""Workflow task identifier.

Declares ``TaskID``.
"""

from typing import NewType

TaskID = NewType("TaskID", str)
"""Unique identifier of a workflow task or context task."""
