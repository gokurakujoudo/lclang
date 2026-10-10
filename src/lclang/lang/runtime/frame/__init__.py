"""Frame runtime package and public construction values.

Exports ``EvaluationLimits``, ``Frame``, ``FrameFactory``, ``FrameProxy``, ``NO_FALLBACK``,
``VariableInspectionStatus``, ``VariableInspectionTree``.
"""

from lclang.lang.runtime.frame.evaluation_limit import EvaluationLimits
from lclang.lang.runtime.frame.fallback_marker import NO_FALLBACK
from lclang.lang.runtime.frame.frame import Frame
from lclang.lang.runtime.frame.frame_factory import FrameFactory
from lclang.lang.runtime.frame.scoped_proxy import FrameProxy
from lclang.lang.runtime.frame.variable_inspection import (
    VariableInspectionStatus,
    VariableInspectionTree,
)

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
