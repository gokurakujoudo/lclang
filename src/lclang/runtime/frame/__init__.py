"""Frame runtime package and public construction values."""

from lclang.runtime.frame.evaluation_limits import EvaluationLimits
from lclang.runtime.frame.fallback import NO_FALLBACK
from lclang.runtime.frame.frame import Frame
from lclang.runtime.frame.frame_factory import FrameFactory
from lclang.runtime.frame.inspection_values import (
    VariableInspectionStatus,
    VariableInspectionTree,
)
from lclang.scope_proxy import FrameProxy

# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = [
    "EvaluationLimits",
    "Frame",
    "FrameFactory",
    "FrameProxy",
    "NO_FALLBACK",
    "VariableInspectionStatus",
    "VariableInspectionTree",
]
