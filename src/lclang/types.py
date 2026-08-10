"""Nominal identifier types used throughout lclang."""

from typing import NewType

VarName = NewType("VarName", str)
"""Name of an LCL variable."""

ModuleName = NewType("ModuleName", str)
"""Name of an LCL module."""

FrameId = NewType("FrameId", str)
"""Unique identifier of a runtime frame."""

SourceName = NewType("SourceName", str)
"""Human-readable name of an LCL source."""
